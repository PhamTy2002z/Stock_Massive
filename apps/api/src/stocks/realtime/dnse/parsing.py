"""Strict JSON wire parsing into S0 normalized event contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

from .. import (
    AggressorSide,
    AuctionSnapshot,
    BarResolution,
    CanonicalUnits,
    ClosedBar,
    DataOutcome,
    DataOutcomeKind,
    EventFamily,
    EventMetadata,
    Exchange,
    ForeignFlowSnapshot,
    IndexTick,
    MarketDataSource,
    NO_UNITS,
    NormalizationMeasure,
    NormalizedMarketEvent,
    PriceBasis,
    PriceUnit,
    ProductGroup,
    QualityState,
    QuantityUnit,
    SecurityDefinition,
    SessionState,
    TradeTick,
    TradingSession,
    ValueUnit,
    normalize_dnse_value,
)
from .metrics import AdapterMetrics


HCM = ZoneInfo("Asia/Ho_Chi_Minh")
_TYPE_FAMILY = {
    "t": EventFamily.TRADE,
    "te": EventFamily.TRADE,
    "q": EventFamily.BOOK,
    "f": EventFamily.FOREIGN_FLOW,
    "ep": EventFamily.AUCTION,
    "s": EventFamily.SESSION,
    "mi": EventFamily.INDEX,
    "emi": EventFamily.INDEX,
    "sd": EventFamily.SECURITY_DEFINITION,
    "o": EventFamily.CLOSED_BAR,
    "oc": EventFamily.CLOSED_BAR,
}


def raw_payload_hash(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ParseResult:
    event: NormalizedMarketEvent | None = None
    outcome: DataOutcome | None = None

    def __post_init__(self) -> None:
        if (self.event is None) == (self.outcome is None):
            raise ValueError("parse result requires exactly one event or outcome")


class DnseEventParser:
    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        metrics: AdapterMetrics | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.metrics = metrics or AdapterMetrics()

    def parse(self, payload: Mapping[str, Any], *, request_id: str) -> ParseResult:
        """Parse a JSON object; MessagePack and unknown schemas are refused."""
        try:
            if not isinstance(payload, Mapping):
                raise ValueError("DNSE payload must be a JSON object")
            family = _TYPE_FAMILY[str(payload["T"])]
            if family is EventFamily.BOOK:
                # S0 deliberately has no quote quantity normalization rule yet.
                raise ValueError("quote quantity scale is not admitted")
            event = self._parse_family(family, payload)
            return ParseResult(event=event)
        except (KeyError, TypeError, ValueError, ArithmeticError):
            self.metrics.increment("parse_failures")
            return ParseResult(
                outcome=DataOutcome(
                    kind=DataOutcomeKind.INVALID_REQUEST,
                    source=MarketDataSource.DNSE,
                    request_id=request_id,
                )
            )

    def _parse_family(
        self, family: EventFamily, payload: Mapping[str, Any]
    ) -> NormalizedMarketEvent:
        metadata = self._metadata(family, payload)
        if family is EventFamily.TRADE:
            side = {1: AggressorSide.BUY, 2: AggressorSide.SELL}.get(
                payload.get("side"), AggressorSide.UNKNOWN
            )
            return TradeTick(
                metadata=metadata,
                price=self._normalized(payload["matchPrice"], metadata, NormalizationMeasure.CASH_PRICE),
                quantity=self._normalized(payload["matchQtty"], metadata, NormalizationMeasure.TRADE_QUANTITY),
                gross_trade_value_vnd=self._optional_normalized(
                    payload.get("grossTradeAmount"), metadata, NormalizationMeasure.GROSS_TRADE_VALUE
                ),
                aggressor_side=side,
                provider_trade_id=_optional_identifier(payload.get("tradeId")),
            )
        if family is EventFamily.FOREIGN_FLOW:
            return ForeignFlowSnapshot(
                metadata=metadata,
                buy_volume=int(self._normalized(payload["totalBuyVolume"], metadata, NormalizationMeasure.FOREIGN_VOLUME)),
                sell_volume=int(self._normalized(payload["totalSellVolume"], metadata, NormalizationMeasure.FOREIGN_VOLUME)),
                buy_value_vnd=self._decimal(self._normalized(payload["totalBuyTradedAmount"], metadata, NormalizationMeasure.FOREIGN_VALUE)),
                sell_value_vnd=self._decimal(self._normalized(payload["totalSellTradedAmount"], metadata, NormalizationMeasure.FOREIGN_VALUE)),
                current_room=_optional_int(payload.get("foreignerBuyPossibleQuantity")),
                total_room=_optional_int(payload.get("foreignerOrderLimitQuantity")),
            )
        if family is EventFamily.AUCTION:
            return AuctionSnapshot(
                metadata=metadata,
                expected_price=self._normalized(payload["expectedTradePrice"], metadata, NormalizationMeasure.CASH_PRICE),
                expected_quantity=int(payload["expectedTradeQuantity"]),
            )
        if family is EventFamily.SESSION:
            return SessionState(
                metadata=metadata,
                provider_session_id=str(payload["tradingSessionId"]),
                provider_event_id=str(payload.get("eventId", payload["tradingSessionId"])),
                is_trading=bool(payload["isTrading"]),
            )
        if family is EventFamily.INDEX:
            return IndexTick(
                metadata=metadata,
                index_value=self._decimal(payload["valueIndexes"]),
                change=_optional_decimal(payload.get("changedValue")),
                change_percent=_optional_decimal(payload.get("changedRatio")),
                estimated=str(payload["T"]) == "emi",
            )
        if family is EventFamily.SECURITY_DEFINITION:
            return SecurityDefinition(
                metadata=metadata,
                instrument_type=str(payload["securityGroupId"]),
                status=str(payload["securityStatus"]),
                isin=payload.get("isin"),
                reference_price=self._optional_normalized(payload.get("basicPrice"), metadata, NormalizationMeasure.CASH_PRICE),
                ceiling_price=self._optional_normalized(payload.get("ceilingPrice"), metadata, NormalizationMeasure.CASH_PRICE),
                floor_price=self._optional_normalized(payload.get("floorPrice"), metadata, NormalizationMeasure.CASH_PRICE),
                price_basis=PriceBasis.RAW,
            )
        if family is EventFamily.CLOSED_BAR:
            end = _timestamp(payload.get("endTime", payload["time"]))
            resolution = _resolution(str(payload["resolution"]))
            seconds = {
                BarResolution.MINUTE_1: 60,
                BarResolution.MINUTE_3: 180,
                BarResolution.MINUTE_5: 300,
                BarResolution.MINUTE_15: 900,
                BarResolution.MINUTE_30: 1800,
                BarResolution.HOUR_1: 3600,
                BarResolution.DAY_1: 86400,
                BarResolution.WEEK_1: 604800,
            }[resolution]
            from datetime import timedelta

            return ClosedBar(
                metadata=metadata,
                resolution=resolution,
                window_start=end - timedelta(seconds=seconds),
                window_end=end,
                open_price=self._normalized(payload["open"], metadata, NormalizationMeasure.CASH_PRICE),
                high_price=self._normalized(payload["high"], metadata, NormalizationMeasure.CASH_PRICE),
                low_price=self._normalized(payload["low"], metadata, NormalizationMeasure.CASH_PRICE),
                close_price=self._normalized(payload["close"], metadata, NormalizationMeasure.CASH_PRICE),
                volume=int(self._normalized(payload["volume"], metadata, NormalizationMeasure.BAR_VOLUME)),
                total_value_vnd=_optional_decimal(payload.get("value")),
                price_basis=PriceBasis.RAW,
            )
        raise ValueError("unsupported DNSE event family")

    def _metadata(self, family: EventFamily, payload: Mapping[str, Any]) -> EventMetadata:
        product = _product_group(payload)
        provider_time = _timestamp(
            payload.get("time", payload.get("transactTime", payload.get("endTime")))
        )
        observed = self._clock()
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("parser clock must be timezone-aware")
        if observed < provider_time:
            observed = provider_time
        session = _session(payload, family)
        return EventMetadata(
            source=MarketDataSource.DNSE,
            event_family=family,
            symbol=str(payload.get("symbol", payload.get("indexName", "MARKET"))),
            exchange=_exchange(payload.get("marketId")),
            board=str(payload.get("boardId", "INDEX" if family is EventFamily.INDEX else "MARKET")),
            product_group=product,
            trading_day=provider_time.astimezone(HCM).date(),
            session=session,
            provider_time=provider_time,
            observed_time=observed,
            units=_units(family, product),
            schema_version=1,
            normalization_version=1,
            raw_payload_hash=raw_payload_hash(payload),
            quality_state=QualityState.VALID,
        )

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        parsed = Decimal(str(value))
        if not parsed.is_finite():
            raise ValueError("numeric field must be finite")
        return parsed

    def _normalized(self, value: Any, metadata: EventMetadata, measure: NormalizationMeasure) -> Decimal | int:
        return normalize_dnse_value(
            self._decimal(value),
            version=metadata.normalization_version,
            product_group=metadata.product_group,
            board=metadata.board,
            measure=measure,
        )

    def _optional_normalized(self, value: Any, metadata: EventMetadata, measure: NormalizationMeasure) -> Decimal | int | None:
        return None if value is None else self._normalized(value, metadata, measure)


def _timestamp(value: Any) -> datetime:
    if isinstance(value, Mapping):
        value = float(value.get("seconds", value.get("Seconds"))) + float(
            value.get("nanos", value.get("Nanos", 0))
        ) / 1_000_000_000
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000 if value > 1_000_000_000_000 else float(value)
        return datetime.fromtimestamp(seconds, UTC)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=HCM)
        return parsed
    raise ValueError("missing or invalid DNSE timestamp")


def _exchange(value: Any) -> Exchange:
    normalized = str(value).upper()
    if normalized in {"STO", "HOSE", "HSX"}:
        return Exchange.HOSE
    if normalized in {"STX", "HNX", "DVX"}:
        return Exchange.HNX
    if normalized in {"UPX", "UPCOM"}:
        return Exchange.UPCOM
    raise ValueError("unknown DNSE market identity")


def _product_group(payload: Mapping[str, Any]) -> ProductGroup:
    if str(payload.get("T")) in {"mi", "emi"}:
        return ProductGroup.INDEX
    value = str(payload.get("productGrpId", payload.get("securityGroupId", "ST"))).upper()
    return {
        "ST": ProductGroup.EQUITY,
        "STOCK": ProductGroup.EQUITY,
        "EF": ProductGroup.ETF,
        "EW": ProductGroup.COVERED_WARRANT,
        "MF": ProductGroup.FUND,
        "BS": ProductGroup.BOND,
        "FU": ProductGroup.FUTURES,
        "FUTURES": ProductGroup.FUTURES,
    }.get(value) or (_raise("unknown DNSE product group"))


def _session(payload: Mapping[str, Any], family: EventFamily) -> TradingSession:
    if family is EventFamily.SECURITY_DEFINITION:
        return TradingSession.REFERENCE
    value = str(payload.get("session", payload.get("tradingSessionId", "CONTINUOUS"))).upper()
    if family is EventFamily.AUCTION and value not in {"ATO", "ATC"}:
        value = str(payload.get("auctionSession", "ATC")).upper()
    return {
        "ATO": TradingSession.ATO,
        "ATC": TradingSession.ATC,
        "CONTINUOUS": TradingSession.CONTINUOUS,
        "1": TradingSession.ATO,
        "2": TradingSession.CONTINUOUS,
        "3": TradingSession.ATC,
        "BREAK": TradingSession.BREAK,
        "CLOSED": TradingSession.CLOSED,
    }.get(value, TradingSession.CONTINUOUS)


def _units(family: EventFamily, product: ProductGroup) -> CanonicalUnits:
    if family is EventFamily.SESSION:
        return NO_UNITS
    if family is EventFamily.INDEX:
        return CanonicalUnits(price=PriceUnit.INDEX_POINT, quantity=QuantityUnit.NONE, value=ValueUnit.NONE)
    if family is EventFamily.FOREIGN_FLOW:
        return CanonicalUnits(price=PriceUnit.NONE, quantity=QuantityUnit.SHARE, value=ValueUnit.VND)
    if family is EventFamily.SECURITY_DEFINITION:
        return CanonicalUnits(
            price=PriceUnit.INDEX_POINT if product in {ProductGroup.FUTURES, ProductGroup.INDEX} else PriceUnit.VND,
            quantity=QuantityUnit.NONE,
            value=ValueUnit.NONE,
        )
    if product is ProductGroup.FUTURES:
        return CanonicalUnits(price=PriceUnit.INDEX_POINT, quantity=QuantityUnit.CONTRACT, value=ValueUnit.NONE)
    return CanonicalUnits(
        price=PriceUnit.VND,
        quantity=QuantityUnit.SHARE,
        value=ValueUnit.NONE if family in {EventFamily.BOOK, EventFamily.AUCTION} else ValueUnit.VND,
    )


def _resolution(value: str) -> BarResolution:
    return {
        "1": BarResolution.MINUTE_1,
        "3": BarResolution.MINUTE_3,
        "5": BarResolution.MINUTE_5,
        "15": BarResolution.MINUTE_15,
        "30": BarResolution.MINUTE_30,
        "1H": BarResolution.HOUR_1,
        "1D": BarResolution.DAY_1,
        "1W": BarResolution.WEEK_1,
    }[value]


def _optional_identifier(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_decimal(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _raise(message: str) -> Any:
    raise ValueError(message)
