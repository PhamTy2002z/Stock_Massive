"""Source-neutral contracts for normalized realtime market evidence.

Provider adapters may construct these models, but provider wire fields and raw
payloads may not cross this boundary.  Every model is strict and immutable so a
bad unit, identity, timestamp, or event-specific field fails before storage.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import ClassVar, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas.common import StrictModel
from ..shared import StockServiceError, validate_symbol


class RealtimeContract(StrictModel):
    """Immutable base for normalized realtime values."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class MarketDataSource(str, Enum):
    """Sources that may contribute market evidence."""

    DNSE = "dnse"
    FIINQUANT = "fiinquant"
    VNSTOCK = "vnstock"
    INTERNAL = "stock_massive"


class EventFamily(str, Enum):
    TRADE = "trade"
    BOOK = "book"
    FOREIGN_FLOW = "foreign_flow"
    AUCTION = "auction"
    SESSION = "session"
    INDEX = "index"
    SECURITY_DEFINITION = "security_definition"
    CLOSED_BAR = "closed_bar"


class Exchange(str, Enum):
    HOSE = "HOSE"
    HNX = "HNX"
    UPCOM = "UPCOM"


class ProductGroup(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    COVERED_WARRANT = "covered_warrant"
    FUND = "fund"
    BOND = "bond"
    FUTURES = "futures"
    INDEX = "index"


class TradingSession(str, Enum):
    PRE_OPEN = "pre_open"
    ATO = "ato"
    CONTINUOUS = "continuous"
    BREAK = "break"
    ATC = "atc"
    POST_CLOSE = "post_close"
    CLOSED = "closed"
    REFERENCE = "reference"


class QualityState(str, Enum):
    VALID = "valid"
    STALE = "stale"
    DEGRADED = "degraded"
    DUPLICATE = "duplicate"
    GAP = "gap"
    INVALID = "invalid"


class PriceUnit(str, Enum):
    VND = "VND"
    INDEX_POINT = "index_point"
    NONE = "none"


class QuantityUnit(str, Enum):
    SHARE = "share"
    CONTRACT = "contract"
    NONE = "none"


class ValueUnit(str, Enum):
    VND = "VND"
    NONE = "none"


class PriceBasis(str, Enum):
    RAW = "raw"
    ADJUSTED_AT_SOURCE = "adjusted_at_source"
    NOT_APPLICABLE = "not_applicable"


class AggressorSide(str, Enum):
    BUY = "buy"
    SELL = "sell"
    UNKNOWN = "unknown"


class BookSide(str, Enum):
    BID = "bid"
    OFFER = "offer"


class BarResolution(str, Enum):
    MINUTE_1 = "1m"
    MINUTE_3 = "3m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    DAY_1 = "1d"
    WEEK_1 = "1w"


class CanonicalUnits(RealtimeContract):
    """Canonical units carried by one normalized event family."""

    price: PriceUnit
    quantity: QuantityUnit
    value: ValueUnit


NO_UNITS = CanonicalUnits(
    price=PriceUnit.NONE,
    quantity=QuantityUnit.NONE,
    value=ValueUnit.NONE,
)


class EventMetadata(RealtimeContract):
    """Identity, provenance, time, units, version, and quality for every event."""

    source: MarketDataSource
    event_family: EventFamily
    symbol: str
    exchange: Exchange
    board: str = Field(min_length=1, max_length=32, pattern=r"^[A-Z0-9_-]+$")
    product_group: ProductGroup
    trading_day: date
    session: TradingSession
    provider_time: datetime
    observed_time: datetime
    units: CanonicalUnits
    schema_version: int = Field(ge=1)
    normalization_version: int = Field(ge=1)
    raw_payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    quality_state: QualityState
    duplicate_of: str | None = Field(
        default=None,
        pattern=r"^evt_[0-9a-f]{64}$",
    )

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        try:
            return validate_symbol(value)
        except StockServiceError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("provider_time", "observed_time")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("event timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_time_and_duplicate_semantics(self) -> Self:
        if self.provider_time > self.observed_time:
            raise ValueError("provider_time cannot be later than observed_time")
        if self.quality_state is QualityState.DUPLICATE and self.duplicate_of is None:
            raise ValueError("duplicate events must identify duplicate_of")
        if self.quality_state is not QualityState.DUPLICATE and self.duplicate_of:
            raise ValueError("duplicate_of is only valid for duplicate events")
        if self.duplicate_of == self.evidence_id:
            raise ValueError("an event cannot be a duplicate of itself")
        return self

    @property
    def evidence_id(self) -> str:
        """Return a collision-resistant identity that always retains source."""
        components = (
            self.source.value,
            self.event_family.value,
            self.symbol,
            self.exchange.value,
            self.board,
            self.product_group.value,
            self.trading_day.isoformat(),
            self.session.value,
            self.provider_time.isoformat(),
            str(self.schema_version),
            self.raw_payload_hash,
        )
        digest = hashlib.sha256("\x1f".join(components).encode()).hexdigest()
        return f"evt_{digest}"

    @property
    def observation_key(self) -> tuple[str, ...]:
        """Return the source-neutral key used to group comparable evidence."""
        return (
            self.event_family.value,
            self.symbol,
            self.exchange.value,
            self.board,
            self.product_group.value,
            self.trading_day.isoformat(),
            self.session.value,
            self.provider_time.isoformat(),
            str(self.schema_version),
        )


class NormalizedEvent(RealtimeContract):
    """Shared event shell with a concrete-family guard."""

    expected_family: ClassVar[EventFamily]
    metadata: EventMetadata

    @model_validator(mode="after")
    def require_expected_family(self) -> Self:
        if self.metadata.event_family is not self.expected_family:
            raise ValueError(
                f"{type(self).__name__} requires event family "
                f"{self.expected_family.value}"
            )
        return self


def _require_price_quantity_units(
    metadata: EventMetadata,
    *,
    cash_value_unit: ValueUnit,
) -> None:
    if metadata.product_group is ProductGroup.FUTURES:
        expected = CanonicalUnits(
            price=PriceUnit.INDEX_POINT,
            quantity=QuantityUnit.CONTRACT,
            value=ValueUnit.NONE,
        )
    elif metadata.product_group is ProductGroup.INDEX:
        expected = CanonicalUnits(
            price=PriceUnit.INDEX_POINT,
            quantity=QuantityUnit.NONE,
            value=ValueUnit.NONE,
        )
    else:
        expected = CanonicalUnits(
            price=PriceUnit.VND,
            quantity=QuantityUnit.SHARE,
            value=cash_value_unit,
        )
    if metadata.units != expected:
        raise ValueError(f"incompatible canonical units for {metadata.product_group.value}")


class TradeTick(NormalizedEvent):
    expected_family = EventFamily.TRADE

    price: Decimal = Field(gt=0)
    quantity: int = Field(gt=0)
    gross_trade_value_vnd: Decimal | None = Field(default=None, ge=0)
    aggressor_side: AggressorSide
    provider_trade_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )

    @model_validator(mode="after")
    def validate_trade(self) -> Self:
        _require_price_quantity_units(
            self.metadata,
            cash_value_unit=ValueUnit.VND,
        )
        if self.metadata.product_group is ProductGroup.INDEX:
            raise ValueError("an index cannot emit a trade")
        if (
            self.metadata.product_group is ProductGroup.FUTURES
            and self.gross_trade_value_vnd is not None
        ):
            raise ValueError("futures trades cannot label gross value as VND")
        return self


class BookLevel(RealtimeContract):
    side: BookSide
    level: int = Field(ge=1, le=10)
    price: Decimal = Field(gt=0)
    quantity: int = Field(gt=0)


class BookSnapshot(NormalizedEvent):
    expected_family = EventFamily.BOOK

    levels: tuple[BookLevel, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_book(self) -> Self:
        _require_price_quantity_units(
            self.metadata,
            cash_value_unit=ValueUnit.NONE,
        )
        if self.metadata.product_group is ProductGroup.INDEX:
            raise ValueError("an index has no order book")
        keys = {(level.side, level.level) for level in self.levels}
        if len(keys) != len(self.levels):
            raise ValueError("book side and level pairs must be unique")
        for side in BookSide:
            positions = sorted(level.level for level in self.levels if level.side is side)
            if positions and positions != list(range(1, len(positions) + 1)):
                raise ValueError("book levels must be contiguous from level one")
        return self


class ForeignFlowSnapshot(NormalizedEvent):
    expected_family = EventFamily.FOREIGN_FLOW

    buy_volume: int = Field(ge=0)
    sell_volume: int = Field(ge=0)
    buy_value_vnd: Decimal = Field(ge=0)
    sell_value_vnd: Decimal = Field(ge=0)
    current_room: int | None = Field(default=None, ge=0)
    total_room: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_foreign_flow(self) -> Self:
        expected = CanonicalUnits(
            price=PriceUnit.NONE,
            quantity=QuantityUnit.SHARE,
            value=ValueUnit.VND,
        )
        if self.metadata.units != expected:
            raise ValueError("foreign flow requires share and VND units")
        if self.metadata.product_group in {ProductGroup.FUTURES, ProductGroup.INDEX}:
            raise ValueError("foreign flow is not admitted for this product group")
        if (
            self.current_room is not None
            and self.total_room is not None
            and self.current_room > self.total_room
        ):
            raise ValueError("current foreign room cannot exceed total room")
        return self


class AuctionSnapshot(NormalizedEvent):
    expected_family = EventFamily.AUCTION

    expected_price: Decimal = Field(gt=0)
    expected_quantity: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_auction(self) -> Self:
        _require_price_quantity_units(
            self.metadata,
            cash_value_unit=ValueUnit.NONE,
        )
        if self.metadata.session not in {TradingSession.ATO, TradingSession.ATC}:
            raise ValueError("auction snapshots require an ATO or ATC session")
        if self.metadata.product_group in {ProductGroup.FUTURES, ProductGroup.INDEX}:
            raise ValueError("auction snapshots are not admitted for this product group")
        return self


class SessionState(NormalizedEvent):
    expected_family = EventFamily.SESSION

    provider_session_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    provider_event_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    is_trading: bool

    @model_validator(mode="after")
    def validate_session_units(self) -> Self:
        if self.metadata.units != NO_UNITS:
            raise ValueError("session state cannot carry market units")
        return self


class IndexTick(NormalizedEvent):
    expected_family = EventFamily.INDEX

    index_value: Decimal = Field(gt=0)
    change: Decimal | None = None
    change_percent: Decimal | None = None
    estimated: bool

    @model_validator(mode="after")
    def validate_index(self) -> Self:
        expected = CanonicalUnits(
            price=PriceUnit.INDEX_POINT,
            quantity=QuantityUnit.NONE,
            value=ValueUnit.NONE,
        )
        if self.metadata.product_group is not ProductGroup.INDEX:
            raise ValueError("index ticks require the index product group")
        if self.metadata.units != expected:
            raise ValueError("index ticks require index-point units")
        return self


class SecurityDefinition(NormalizedEvent):
    expected_family = EventFamily.SECURITY_DEFINITION

    instrument_type: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    status: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    isin: str | None = Field(default=None, min_length=12, max_length=12)
    reference_price: Decimal | None = Field(default=None, gt=0)
    ceiling_price: Decimal | None = Field(default=None, gt=0)
    floor_price: Decimal | None = Field(default=None, gt=0)
    price_basis: PriceBasis

    @model_validator(mode="after")
    def validate_definition(self) -> Self:
        if self.metadata.units.quantity is not QuantityUnit.NONE:
            raise ValueError("security definitions cannot carry a quantity unit")
        if self.metadata.units.value is not ValueUnit.NONE:
            raise ValueError("security definitions cannot carry a value unit")
        expected_price = (
            PriceUnit.INDEX_POINT
            if self.metadata.product_group in {ProductGroup.FUTURES, ProductGroup.INDEX}
            else PriceUnit.VND
        )
        if self.metadata.units.price is not expected_price:
            raise ValueError("security definition price unit conflicts with product group")
        if self.price_basis is not PriceBasis.RAW:
            raise ValueError("realtime security definitions require raw prices")
        prices = (self.floor_price, self.reference_price, self.ceiling_price)
        if all(price is not None for price in prices):
            floor, reference, ceiling = prices
            if not floor <= reference <= ceiling:
                raise ValueError("security price band must contain reference price")
        return self


class ClosedBar(NormalizedEvent):
    expected_family = EventFamily.CLOSED_BAR

    resolution: BarResolution
    window_start: datetime
    window_end: datetime
    open_price: Decimal = Field(gt=0)
    high_price: Decimal = Field(gt=0)
    low_price: Decimal = Field(gt=0)
    close_price: Decimal = Field(gt=0)
    volume: int = Field(ge=0)
    total_value_vnd: Decimal | None = Field(default=None, ge=0)
    price_basis: PriceBasis

    @field_validator("window_start", "window_end")
    @classmethod
    def require_aware_window(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("bar windows must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_bar(self) -> Self:
        _require_price_quantity_units(
            self.metadata,
            cash_value_unit=ValueUnit.VND,
        )
        if self.window_start >= self.window_end:
            raise ValueError("bar window_start must precede window_end")
        if self.metadata.provider_time < self.window_end:
            raise ValueError("closed bar provider_time cannot precede window_end")
        if self.high_price < max(self.open_price, self.close_price):
            raise ValueError("bar high must contain open and close")
        if self.low_price > min(self.open_price, self.close_price):
            raise ValueError("bar low must contain open and close")
        if self.low_price > self.high_price:
            raise ValueError("bar low cannot exceed high")
        if self.price_basis is not PriceBasis.RAW:
            raise ValueError("realtime closed bars require raw prices")
        if self.metadata.product_group is ProductGroup.FUTURES:
            if self.total_value_vnd is not None:
                raise ValueError("futures bars cannot label traded value as VND")
        elif self.metadata.product_group is ProductGroup.INDEX:
            if self.volume != 0 or self.total_value_vnd is not None:
                raise ValueError("index bars cannot carry traded quantity or VND value")
        elif self.total_value_vnd is None and self.metadata.units.value is ValueUnit.VND:
            # A missing optional value is valid; the unit still declares how a
            # future populated value must be interpreted.
            pass
        return self


NormalizedMarketEvent = (
    TradeTick
    | BookSnapshot
    | ForeignFlowSnapshot
    | AuctionSnapshot
    | SessionState
    | IndexTick
    | SecurityDefinition
    | ClosedBar
)
