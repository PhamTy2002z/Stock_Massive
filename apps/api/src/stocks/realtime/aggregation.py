"""Deterministic trade aggregation for realtime and replay processing."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final
from zoneinfo import ZoneInfo

from .contracts import (
    BarResolution,
    ClosedBar,
    EventFamily,
    EventMetadata,
    MarketDataSource,
    PriceBasis,
    ProductGroup,
    QualityState,
    TradeTick,
    TradingSession,
)


AGGREGATION_METHOD_VERSION: Final = 1
BAR_ROLLUP_METHOD_VERSION: Final = 1
HCM: Final = ZoneInfo("Asia/Ho_Chi_Minh")
ACCEPTED_TRADE_BAR_RESOLUTIONS: Final = (
    BarResolution.MINUTE_1,
    BarResolution.MINUTE_3,
    BarResolution.MINUTE_5,
    BarResolution.MINUTE_15,
    BarResolution.MINUTE_30,
    BarResolution.HOUR_1,
)
_MINUTES: Final = {
    BarResolution.MINUTE_1: 1,
    BarResolution.MINUTE_3: 3,
    BarResolution.MINUTE_5: 5,
    BarResolution.MINUTE_15: 15,
    BarResolution.MINUTE_30: 30,
    BarResolution.HOUR_1: 60,
}
_ORDER_MINUTES: Final = {
    **_MINUTES,
    BarResolution.DAY_1: 1_440,
    BarResolution.WEEK_1: 10_080,
}


def aggregate_trades(
    events: Iterable[TradeTick],
    *,
    resolutions: tuple[BarResolution, ...] = (BarResolution.MINUTE_1,),
) -> tuple[ClosedBar, ...]:
    """Aggregate canonical trades without crossing an instrument or session.

    The batch shape lets live processing and replay pass the same durable bucket
    and receive equivalent derived evidence. Duplicate delivery is removed by
    evidence identity before arithmetic.
    """
    selected = tuple(dict.fromkeys(resolutions))
    unsupported = set(selected) - set(ACCEPTED_TRADE_BAR_RESOLUTIONS)
    if not selected or unsupported:
        raise ValueError("unsupported trade-bar resolution")

    unique = {
        event.metadata.evidence_id: event
        for event in events
        if event.metadata.quality_state is not QualityState.DUPLICATE
    }
    ordered = sorted(unique.values(), key=_event_order)
    groups: dict[tuple[object, ...], list[TradeTick]] = defaultdict(list)
    for event in ordered:
        _validate_trade_time(event)
        metadata = event.metadata
        for resolution in selected:
            window_start = bar_window_start(metadata.provider_time, resolution)
            groups[
                (
                    resolution,
                    window_start,
                    metadata.source,
                    metadata.symbol,
                    metadata.exchange,
                    metadata.board,
                    metadata.product_group,
                    metadata.trading_day,
                    metadata.session,
                    metadata.units,
                    metadata.normalization_version,
                )
            ].append(event)

    bars = (_bar_from_group(key, group) for key, group in groups.items())
    return tuple(sorted(bars, key=_bar_order))


def aggregate_bars_to_daily(events: Iterable[ClosedBar]) -> tuple[ClosedBar, ...]:
    """Roll complete intraday evidence into one daily bar per board."""
    unique = {event.metadata.evidence_id: event for event in events}
    groups: dict[tuple[object, ...], list[ClosedBar]] = defaultdict(list)
    for event in unique.values():
        if event.resolution is not BarResolution.MINUTE_1:
            raise ValueError("daily rollup requires one-minute bars")
        if event.metadata.source is not MarketDataSource.INTERNAL:
            raise ValueError("daily rollup requires internally derived minute bars")
        metadata = event.metadata
        groups[
            (
                metadata.symbol,
                metadata.exchange,
                metadata.board,
                metadata.product_group,
                metadata.trading_day,
                metadata.units,
                metadata.normalization_version,
                event.price_basis,
            )
        ].append(event)
    return tuple(
        sorted(
            (_daily_bar(key, group) for key, group in groups.items()),
            key=_bar_order,
        )
    )


def _daily_bar(key: tuple[object, ...], events: list[ClosedBar]) -> ClosedBar:
    (
        symbol,
        exchange,
        board,
        product_group,
        trading_day,
        units,
        normalization_version,
        price_basis,
    ) = key
    ordered = sorted(events, key=lambda event: (event.window_start, event.metadata.evidence_id))
    evidence_ids = tuple(event.metadata.evidence_id for event in ordered)
    raw_hash = hashlib.sha256(
        "\x1f".join(
            (str(BAR_ROLLUP_METHOD_VERSION), BarResolution.DAY_1.value, *evidence_ids)
        ).encode()
    ).hexdigest()
    values = [event.total_value_vnd for event in ordered]
    total_value = None if any(value is None for value in values) else sum(
        (value for value in values if value is not None), start=Decimal(0)
    )
    quality = _bar_rollup_quality(ordered)
    return ClosedBar(
        metadata=EventMetadata(
            source=MarketDataSource.INTERNAL,
            event_family=EventFamily.CLOSED_BAR,
            symbol=str(symbol),
            exchange=exchange,
            board=str(board),
            product_group=product_group,
            trading_day=trading_day,
            session=TradingSession.CLOSED,
            provider_time=ordered[-1].window_end,
            observed_time=max(event.metadata.observed_time for event in ordered),
            units=units,
            schema_version=2,
            normalization_version=int(normalization_version),
            raw_payload_hash=raw_hash,
            quality_state=quality,
        ),
        resolution=BarResolution.DAY_1,
        window_start=ordered[0].window_start,
        window_end=ordered[-1].window_end,
        open_price=ordered[0].open_price,
        high_price=max(event.high_price for event in ordered),
        low_price=min(event.low_price for event in ordered),
        close_price=ordered[-1].close_price,
        volume=sum(event.volume for event in ordered),
        total_value_vnd=total_value,
        price_basis=price_basis,
        method_version=BAR_ROLLUP_METHOD_VERSION,
        input_evidence_ids=evidence_ids,
    )


def _bar_from_group(key: tuple[object, ...], events: list[TradeTick]) -> ClosedBar:
    (
        resolution,
        window_start,
        _source,
        symbol,
        exchange,
        board,
        product_group,
        trading_day,
        session,
        units,
        normalization_version,
    ) = key
    assert isinstance(resolution, BarResolution)
    assert isinstance(window_start, datetime)
    ordered = sorted(events, key=_event_order)
    window_end = window_start + timedelta(minutes=_MINUTES[resolution])
    evidence_ids = tuple(event.metadata.evidence_id for event in ordered)
    raw_hash = hashlib.sha256(
        "\x1f".join(
            (str(AGGREGATION_METHOD_VERSION), resolution.value, *evidence_ids)
        ).encode()
    ).hexdigest()
    observed_time = max(
        window_end,
        *(event.metadata.observed_time for event in ordered),
    )
    total_value = None
    if product_group is not ProductGroup.FUTURES:
        total_value = sum(
            (event.price * event.quantity for event in ordered),
            start=Decimal(0),
        )
    return ClosedBar(
        metadata=EventMetadata(
            source=MarketDataSource.INTERNAL,
            event_family=EventFamily.CLOSED_BAR,
            symbol=str(symbol),
            exchange=exchange,
            board=str(board),
            product_group=product_group,
            trading_day=trading_day,
            session=session,
            provider_time=window_end,
            observed_time=observed_time,
            units=units,
            schema_version=2,
            normalization_version=int(normalization_version),
            raw_payload_hash=raw_hash,
            quality_state=_derived_quality(ordered),
        ),
        resolution=resolution,
        window_start=window_start,
        window_end=window_end,
        open_price=ordered[0].price,
        high_price=max(event.price for event in ordered),
        low_price=min(event.price for event in ordered),
        close_price=ordered[-1].price,
        volume=sum(event.quantity for event in ordered),
        total_value_vnd=total_value,
        price_basis=PriceBasis.RAW,
        method_version=AGGREGATION_METHOD_VERSION,
        input_evidence_ids=evidence_ids,
    )


def bar_window_start(value: datetime, resolution: BarResolution) -> datetime:
    local = value.astimezone(HCM).replace(second=0, microsecond=0)
    minutes = _MINUTES[resolution]
    if minutes == 60:
        return local.replace(minute=0)
    return local - timedelta(minutes=local.minute % minutes)


def _validate_trade_time(event: TradeTick) -> None:
    if event.metadata.provider_time.astimezone(HCM).date() != event.metadata.trading_day:
        raise ValueError("trade provider time conflicts with trading day")


def _derived_quality(events: list[TradeTick]) -> QualityState:
    states = {event.metadata.quality_state for event in events}
    if QualityState.GAP in states:
        return QualityState.GAP
    if states == {QualityState.VALID}:
        return QualityState.VALID
    return QualityState.DEGRADED


def _bar_rollup_quality(events: list[ClosedBar]) -> QualityState:
    states = {event.metadata.quality_state for event in events}
    if QualityState.GAP in states:
        return QualityState.GAP
    if states == {QualityState.VALID}:
        return QualityState.VALID
    return QualityState.DEGRADED


def _event_order(event: TradeTick) -> tuple[datetime, datetime, str]:
    metadata = event.metadata
    return metadata.provider_time, metadata.observed_time, metadata.evidence_id


def _bar_order(bar: ClosedBar) -> tuple[datetime, int, str, str, str]:
    return (
        bar.window_start,
        _ORDER_MINUTES[bar.resolution],
        bar.metadata.board,
        bar.metadata.session.value,
        bar.metadata.evidence_id,
    )
