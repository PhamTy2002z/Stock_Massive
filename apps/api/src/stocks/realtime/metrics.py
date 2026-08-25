"""Source-neutral deterministic projections over normalized S3 evidence."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Final

from pydantic import Field, field_validator

from .contracts import (
    AggressorSide,
    Exchange,
    ForeignFlowSnapshot,
    QualityState,
    RealtimeContract,
    TradeTick,
    TradingSession,
)


TRADE_METRICS_METHOD_VERSION: Final = 1
FOREIGN_FLOW_METHOD_VERSION: Final = 1
UPCOM_REFERENCE_INPUT_METHOD_VERSION: Final = 1
ACCELERATION_WINDOW: Final = timedelta(minutes=5)


class ProjectionIdentity(RealtimeContract):
    symbol: str
    board: str
    trading_day: date
    as_of: datetime
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    method_version: int = Field(ge=1)
    quality_state: QualityState
    units: dict[str, str] = Field(min_length=1)

    @field_validator("as_of")
    @classmethod
    def require_aware_as_of(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("projection as_of must be timezone-aware")
        return value

    @field_validator("evidence_ids")
    @classmethod
    def require_canonical_unique_evidence(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("projection evidence IDs must be unique")
        if any(
            len(item) != 68
            or not item.startswith("evt_")
            or any(character not in "0123456789abcdef" for character in item[4:])
            for item in value
        ):
            raise ValueError("projection evidence IDs must be canonical")
        return value


class TradeMetricsProjection(ProjectionIdentity):
    session_vwap_vnd: Decimal = Field(gt=0)
    session_volume_shares: int = Field(gt=0)
    signed_volume_shares: int
    unknown_side_volume_shares: int = Field(ge=0)
    trade_intensity_per_minute: Decimal = Field(gt=0)
    volume_acceleration: Decimal | None = None


class ForeignFlowProjection(ProjectionIdentity):
    buy_volume_shares: int = Field(ge=0)
    sell_volume_shares: int = Field(ge=0)
    net_volume_shares: int
    buy_value_vnd: Decimal = Field(ge=0)
    sell_value_vnd: Decimal = Field(ge=0)
    net_value_vnd: Decimal
    current_room_shares: int | None = Field(default=None, ge=0)
    total_room_shares: int | None = Field(default=None, ge=0)


class UpcomReferenceInput(ProjectionIdentity):
    round_lot_continuous_vwap_vnd: Decimal = Field(gt=0)
    eligible_volume_shares: int = Field(gt=0)


def project_trade_metrics(events: tuple[TradeTick, ...]) -> TradeMetricsProjection:
    ordered = _ordered_trades(events)
    _require_one_stream(ordered)
    total_volume = sum(event.quantity for event in ordered)
    total_value = sum(
        (event.price * event.quantity for event in ordered), start=Decimal(0)
    )
    buy = sum(
        event.quantity
        for event in ordered
        if event.aggressor_side is AggressorSide.BUY
    )
    sell = sum(
        event.quantity
        for event in ordered
        if event.aggressor_side is AggressorSide.SELL
    )
    unknown = total_volume - buy - sell
    elapsed_minutes = max(
        Decimal(1),
        Decimal(
            str(
                (ordered[-1].metadata.provider_time - ordered[0].metadata.provider_time)
                .total_seconds()
                / 60
            )
        ),
    )
    metadata = ordered[-1].metadata
    return TradeMetricsProjection(
        symbol=metadata.symbol,
        board=metadata.board,
        trading_day=metadata.trading_day,
        as_of=metadata.observed_time,
        evidence_ids=tuple(event.metadata.evidence_id for event in ordered),
        method_version=TRADE_METRICS_METHOD_VERSION,
        quality_state=_quality(ordered),
        units={
            "session_vwap_vnd": "VND",
            "session_volume_shares": "share",
            "signed_volume_shares": "share",
            "unknown_side_volume_shares": "share",
            "trade_intensity_per_minute": "trade/minute",
            "volume_acceleration": "ratio",
        },
        session_vwap_vnd=total_value / total_volume,
        session_volume_shares=total_volume,
        signed_volume_shares=buy - sell,
        unknown_side_volume_shares=unknown,
        trade_intensity_per_minute=Decimal(len(ordered)) / elapsed_minutes,
        volume_acceleration=_volume_acceleration(ordered),
    )


def project_foreign_flow(
    events: tuple[ForeignFlowSnapshot, ...],
) -> ForeignFlowProjection:
    unique = {event.metadata.evidence_id: event for event in events}
    ordered = sorted(unique.values(), key=_event_order)
    if not ordered:
        raise ValueError("foreign-flow projection requires evidence")
    _require_same_identity(ordered)
    latest = ordered[-1]
    metadata = latest.metadata
    return ForeignFlowProjection(
        symbol=metadata.symbol,
        board=metadata.board,
        trading_day=metadata.trading_day,
        as_of=metadata.observed_time,
        evidence_ids=tuple(event.metadata.evidence_id for event in ordered),
        method_version=FOREIGN_FLOW_METHOD_VERSION,
        quality_state=_quality(ordered),
        units={
            "buy_volume_shares": "share",
            "sell_volume_shares": "share",
            "net_volume_shares": "share",
            "buy_value_vnd": "VND",
            "sell_value_vnd": "VND",
            "net_value_vnd": "VND",
            "current_room_shares": "share",
            "total_room_shares": "share",
        },
        buy_volume_shares=latest.buy_volume,
        sell_volume_shares=latest.sell_volume,
        net_volume_shares=latest.buy_volume - latest.sell_volume,
        buy_value_vnd=latest.buy_value_vnd,
        sell_value_vnd=latest.sell_value_vnd,
        net_value_vnd=latest.buy_value_vnd - latest.sell_value_vnd,
        current_room_shares=latest.current_room,
        total_room_shares=latest.total_room,
    )


def project_upcom_reference_input(
    events: tuple[TradeTick, ...],
) -> UpcomReferenceInput:
    eligible = tuple(
        event
        for event in _ordered_trades(events)
        if event.metadata.exchange is Exchange.UPCOM
        and event.metadata.board == "G1"
        and event.metadata.session is TradingSession.CONTINUOUS
    )
    if not eligible:
        raise ValueError("UPCOM reference input requires eligible G1 trades")
    _require_one_stream(eligible)
    volume = sum(event.quantity for event in eligible)
    value = sum(
        (event.price * event.quantity for event in eligible), start=Decimal(0)
    )
    metadata = eligible[-1].metadata
    return UpcomReferenceInput(
        symbol=metadata.symbol,
        board=metadata.board,
        trading_day=metadata.trading_day,
        as_of=metadata.observed_time,
        evidence_ids=tuple(event.metadata.evidence_id for event in eligible),
        method_version=UPCOM_REFERENCE_INPUT_METHOD_VERSION,
        quality_state=_quality(list(eligible)),
        units={
            "round_lot_continuous_vwap_vnd": "VND",
            "eligible_volume_shares": "share",
        },
        round_lot_continuous_vwap_vnd=value / volume,
        eligible_volume_shares=volume,
    )


def _volume_acceleration(events: list[TradeTick]) -> Decimal | None:
    end = events[-1].metadata.provider_time
    recent_start = end - ACCELERATION_WINDOW
    prior_start = recent_start - ACCELERATION_WINDOW
    if events[0].metadata.provider_time > prior_start:
        return None
    recent = sum(
        event.quantity
        for event in events
        if recent_start < event.metadata.provider_time <= end
    )
    prior = sum(
        event.quantity
        for event in events
        if prior_start < event.metadata.provider_time <= recent_start
    )
    if prior == 0:
        return None
    return Decimal(recent - prior) / Decimal(prior)


def _ordered_trades(events: tuple[TradeTick, ...]) -> list[TradeTick]:
    unique = {event.metadata.evidence_id: event for event in events}
    ordered = sorted(unique.values(), key=_event_order)
    if not ordered:
        raise ValueError("trade projection requires evidence")
    return ordered


def _require_one_stream(events: tuple[TradeTick, ...] | list[TradeTick]) -> None:
    _require_same_identity(events)
    sessions = {event.metadata.session for event in events}
    if len(sessions) != 1:
        raise ValueError("trade projection cannot cross a session boundary")


def _require_same_identity(events) -> None:
    identities = {
        (
            event.metadata.symbol,
            event.metadata.source,
            event.metadata.exchange,
            event.metadata.board,
            event.metadata.product_group,
            event.metadata.trading_day,
        )
        for event in events
    }
    if len(identities) != 1:
        raise ValueError("projection evidence must share one market identity")


def _quality(events) -> QualityState:
    states = {event.metadata.quality_state for event in events}
    if QualityState.GAP in states:
        return QualityState.GAP
    if states == {QualityState.VALID}:
        return QualityState.VALID
    return QualityState.DEGRADED


def _event_order(event) -> tuple[datetime, datetime, str]:
    metadata = event.metadata
    return metadata.provider_time, metadata.observed_time, metadata.evidence_id
