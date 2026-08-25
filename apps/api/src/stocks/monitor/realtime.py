"""Typed DNSE overlay kept separate from stored EOD monitor evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from src.stocks.realtime.contracts import QualityState
from src.stocks.realtime.metrics import ForeignFlowProjection, TradeMetricsProjection
from src.stocks.realtime.projections import ProjectionUnavailable
from src.stocks.realtime.service import (
    RealtimeProjectionBatchResponse,
    RealtimeReadService,
)

from .analytics import StockReading
from .schemas import MonitorState


@dataclass(frozen=True)
class RealtimeStockOverlay:
    symbol: str
    board: str
    as_of: datetime
    session_vwap_vnd: Decimal | None
    active_net_value_vnd: Decimal | None
    active_flow_over_adtv: Decimal | None
    active_buy_volume_shares: int | None
    active_sell_volume_shares: int | None
    foreign_net_value_vnd: Decimal | None
    volume_acceleration: Decimal | None
    quadrant: str | None
    quality_state: str
    issues: tuple[str, ...]


@dataclass(frozen=True)
class RealtimeMarketOverlay:
    state: MonitorState
    eligible: int
    evaluated: int
    board: str
    items: tuple[RealtimeStockOverlay, ...]
    feed_status: str | None
    data_status: str | None
    recovered: bool
    eod_available: bool
    issues: tuple[str, ...]


async def load_realtime_overlay(
    service: RealtimeReadService,
    *,
    eligible_symbols: tuple[str, ...],
    eod_stocks: tuple[StockReading, ...],
    now: datetime,
    stale_after: timedelta = timedelta(minutes=2),
) -> RealtimeMarketOverlay:
    if not eligible_symbols:
        return RealtimeMarketOverlay(
            state=MonitorState.UNAVAILABLE,
            eligible=0,
            evaluated=0,
            board="G1",
            items=(),
            feed_status=None,
            data_status=None,
            recovered=False,
            eod_available=bool(eod_stocks),
            issues=("realtime_scope_empty",),
        )
    try:
        batches = [
            await service.metrics_many(eligible_symbols[start : start + 100], "G1")
            for start in range(0, len(eligible_symbols), 100)
        ]
    except ProjectionUnavailable:
        return RealtimeMarketOverlay(
            state=MonitorState.DISCONNECTED,
            eligible=len(eligible_symbols),
            evaluated=0,
            board="G1",
            items=(),
            feed_status="disconnected",
            data_status=None,
            recovered=False,
            eod_available=bool(eod_stocks),
            issues=("realtime_projection_unavailable",),
        )
    batch = RealtimeProjectionBatchResponse(
        board="G1",
        items=tuple(item for part in batches for item in part.items),
        feed=batches[-1].feed,
        data=batches[-1].data,
    )
    return build_realtime_overlay(
        batch,
        eligible_symbols=eligible_symbols,
        eod_stocks=eod_stocks,
        now=now,
        stale_after=stale_after,
    )


def build_realtime_overlay(
    batch: RealtimeProjectionBatchResponse,
    *,
    eligible_symbols: tuple[str, ...],
    eod_stocks: tuple[StockReading, ...],
    now: datetime,
    stale_after: timedelta = timedelta(minutes=2),
) -> RealtimeMarketOverlay:
    if batch.board != "G1":
        raise ValueError("Market Monitor realtime overlay requires G1")
    eligible = tuple(sorted({symbol.upper() for symbol in eligible_symbols}))
    eligible_set = set(eligible)
    eod = {item.symbol: item for item in eod_stocks}
    overlays: list[RealtimeStockOverlay] = []
    issues: list[str] = []
    any_stale = False
    any_degraded = False

    for item in sorted(batch.items, key=lambda value: value.symbol):
        if item.board != "G1" or item.symbol not in eligible_set:
            continue
        trade = _trade_metric(item.projections.get("trade_metrics"))
        foreign = _foreign_metric(item.projections.get("foreign_flow"))
        if trade is None and foreign is None:
            continue
        clocks = [value.as_of for value in (trade, foreign) if value is not None]
        as_of = max(clocks)
        stale = now - as_of > stale_after
        any_stale = any_stale or stale
        quality = _quality(trade, foreign)
        any_degraded = any_degraded or quality != QualityState.VALID.value
        row_issues: list[str] = []
        if stale:
            row_issues.append("stale_realtime_projection")

        stock = eod.get(item.symbol)
        active_value: Decimal | None = None
        active_ratio: Decimal | None = None
        active_buy: int | None = None
        active_sell: int | None = None
        quadrant: str | None = None
        if trade is not None:
            active_value = Decimal(trade.signed_volume_shares) * trade.session_vwap_vnd
            known_volume = (
                trade.session_volume_shares - trade.unknown_side_volume_shares
            )
            active_buy = (known_volume + trade.signed_volume_shares) // 2
            active_sell = known_volume - active_buy
            if stock is not None and stock.adtv20_vnd is not None and stock.adtv20_vnd > 0:
                active_ratio = active_value / Decimal(str(stock.adtv20_vnd))
            if stock is not None and stock.last_price_vnd is not None:
                price_direction = trade.session_vwap_vnd - Decimal(
                    str(stock.last_price_vnd)
                )
                if price_direction != 0 and active_value != 0:
                    quadrant = (
                        "price_up_" if price_direction > 0 else "price_down_"
                    ) + ("flow_in" if active_value > 0 else "flow_out")

        overlays.append(
            RealtimeStockOverlay(
                symbol=item.symbol,
                board="G1",
                as_of=as_of,
                session_vwap_vnd=(trade.session_vwap_vnd if trade else None),
                active_net_value_vnd=active_value,
                active_flow_over_adtv=active_ratio,
                active_buy_volume_shares=active_buy,
                active_sell_volume_shares=active_sell,
                foreign_net_value_vnd=(foreign.net_value_vnd if foreign else None),
                volume_acceleration=(trade.volume_acceleration if trade else None),
                quadrant=quadrant,
                quality_state=quality,
                issues=tuple(row_issues),
            )
        )

    feed_status = batch.feed.status if batch.feed is not None else None
    data_status = batch.data.status if batch.data is not None else None
    recovered = bool(
        batch.feed is not None
        and batch.feed.status == "connected"
        and batch.feed.reason == "recovered"
    )
    disconnected = feed_status in {"disconnected", "stopped"}
    evaluated = len(overlays)
    if disconnected:
        state = MonitorState.DISCONNECTED
    elif evaluated == 0:
        state = MonitorState.UNAVAILABLE
    elif any_stale:
        state = MonitorState.STALE
    elif evaluated < len(eligible) or any_degraded or data_status in {"degraded", "gapped"}:
        state = MonitorState.PARTIAL
    else:
        state = MonitorState.COMPLETE
    if evaluated < len(eligible):
        issues.append("partial_realtime_coverage")
    if disconnected:
        issues.append("realtime_feed_disconnected")
    if recovered:
        issues.append("realtime_feed_recovered")
    return RealtimeMarketOverlay(
        state=state,
        eligible=len(eligible),
        evaluated=evaluated,
        board="G1",
        items=tuple(overlays),
        feed_status=feed_status,
        data_status=data_status,
        recovered=recovered,
        eod_available=bool(eod_stocks),
        issues=tuple(issues),
    )


@dataclass(frozen=True)
class FlowRanks:
    inflows: tuple[str, ...]
    outflows: tuple[str, ...]
    reversals: tuple[str, ...]


def rank_market_flows(
    eod_stocks: tuple[StockReading, ...],
    realtime: RealtimeMarketOverlay,
    *,
    limit: int = 10,
    horizon: int = 20,
) -> FlowRanks:
    """Rank only VND-denominated flows and detect live-vs-history reversals."""
    if not 1 <= limit <= 50:
        raise ValueError("flow rank limit must be between 1 and 50")
    if horizon not in {1, 5, 20}:
        raise ValueError("flow rank horizon must be 1, 5, or 20")
    field = f"foreign_net_{horizon}d_vnd"
    comparable = [
        item for item in eod_stocks if getattr(item, field) is not None
    ]
    inflows = sorted(
        [item for item in comparable if float(getattr(item, field)) > 0],
        key=lambda item: (-float(getattr(item, field)), item.symbol),
    )[:limit]
    outflows = sorted(
        [item for item in comparable if float(getattr(item, field)) < 0],
        key=lambda item: (float(getattr(item, field)), item.symbol),
    )[:limit]
    by_symbol = {item.symbol: item for item in eod_stocks}
    reversals: list[str] = []
    for live in realtime.items:
        historical = by_symbol.get(live.symbol)
        historical_flow = getattr(historical, field) if historical is not None else None
        if (
            live.foreign_net_value_vnd is None
            or historical is None
            or historical_flow is None
        ):
            continue
        if live.foreign_net_value_vnd * Decimal(str(historical_flow)) < 0:
            reversals.append(live.symbol)
    return FlowRanks(
        inflows=tuple(item.symbol for item in inflows),
        outflows=tuple(item.symbol for item in outflows),
        reversals=tuple(sorted(reversals)[:limit]),
    )


def _trade_metric(payload: dict | None) -> TradeMetricsProjection | None:
    if payload is None:
        return None
    metric = TradeMetricsProjection.model_validate(
        {key: value for key, value in payload.items() if key != "freshness_seconds"}
    )
    if (
        metric.board != "G1"
        or metric.units.get("session_vwap_vnd") != "VND"
        or metric.units.get("signed_volume_shares") != "share"
    ):
        raise ValueError("realtime trade metric has incompatible board or units")
    return metric


def _foreign_metric(payload: dict | None) -> ForeignFlowProjection | None:
    if payload is None:
        return None
    metric = ForeignFlowProjection.model_validate(
        {key: value for key, value in payload.items() if key != "freshness_seconds"}
    )
    if metric.board != "G1" or metric.units.get("net_value_vnd") != "VND":
        raise ValueError("realtime foreign metric has incompatible board or units")
    return metric


def _quality(
    trade: TradeMetricsProjection | None,
    foreign: ForeignFlowProjection | None,
) -> str:
    states = {
        metric.quality_state
        for metric in (trade, foreign)
        if metric is not None
    }
    if QualityState.GAP in states:
        return QualityState.GAP.value
    if states == {QualityState.VALID}:
        return QualityState.VALID.value
    return QualityState.DEGRADED.value
