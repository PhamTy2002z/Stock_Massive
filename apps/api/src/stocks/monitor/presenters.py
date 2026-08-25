"""Translate monitor analytics into strict public response contracts."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.stocks.models import ListingRoster, ProviderSnapshot
from src.stocks.providers.normalize import VN_TZ

from .analytics import SectorReading, StockReading
from .frames import ValuationObservation
from .realtime import RealtimeMarketOverlay, rank_market_flows
from .schemas import (
    BreadthSummary,
    DistributionBucket,
    EvidenceFlag,
    FlowMonitorRow,
    IndexPulse,
    MarketBreadthResponse,
    MarketFlowResponse,
    MarketOverviewResponse,
    MarketSectorResponse,
    MarketStockDetailResponse,
    MarketStockPageResponse,
    MetricValue,
    MonitorCoverage,
    MonitorExchange,
    MonitorMeta,
    MonitorSeriesPoint,
    MonitorSource,
    MonitorState,
    SectorMonitorRow,
    StockLens,
    StockMonitorRow,
    ValuationSummary,
)
from .service import METHOD_VERSIONS, MonitorAnalyticsSnapshot


EOD_STALE_AFTER = timedelta(days=7)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _as_of(snapshot: MonitorAnalyticsSnapshot, generated_at: datetime) -> datetime:
    if snapshot.frames.as_of is None:
        return generated_at
    return datetime.combine(snapshot.frames.as_of, time.min, tzinfo=VN_TZ)


def _coverage(eligible: int, evaluated: int) -> MonitorCoverage:
    if eligible > 0 and evaluated == eligible:
        state = MonitorState.COMPLETE
    elif 0 < evaluated < eligible:
        state = MonitorState.PARTIAL
    else:
        state = MonitorState.UNAVAILABLE
    return MonitorCoverage(
        eligible=eligible,
        evaluated=evaluated,
        missing=eligible - evaluated,
        state=state,
    )


def _sources(
    session: Session,
    snapshot: MonitorAnalyticsSnapshot,
    generated_at: datetime,
) -> tuple[MonitorSource, ...]:
    symbols = snapshot.frames.eligible_symbols + tuple(
        item.symbol for item in snapshot.frames.indices.values()
    )
    rows = []
    if symbols:
        source_end = datetime.combine(
            (snapshot.frames.as_of or generated_at.astimezone(VN_TZ).date())
            + timedelta(days=1),
            time.min,
            tzinfo=VN_TZ,
        )
        rows = session.execute(
            select(
                ProviderSnapshot.capability,
                ProviderSnapshot.source,
                func.max(ProviderSnapshot.effective_at),
                func.max(ProviderSnapshot.observed_at),
            )
            .where(
                ProviderSnapshot.symbol.in_(symbols),
                ProviderSnapshot.effective_at < source_end,
            )
            .group_by(ProviderSnapshot.capability, ProviderSnapshot.source)
            .order_by(ProviderSnapshot.capability, ProviderSnapshot.source)
        ).all()
    result = [
        MonitorSource(
            source=f"{source}:{capability}",
            effective_at=(effective := _aware(effective_at)),
            observed_at=_aware(observed_at),
            freshness_seconds=max(0.0, (generated_at - effective).total_seconds()),
            stale=generated_at - effective > EOD_STALE_AFTER,
        )
        for capability, source, effective_at, observed_at in rows
    ]
    roster_observed = session.execute(
        select(func.max(ListingRoster.observed_at)).where(
            ListingRoster.symbol.in_(snapshot.frames.eligible_symbols)
        )
    ).scalar_one_or_none()
    if roster_observed is not None:
        observed = _aware(roster_observed)
        result.append(
            MonitorSource(
                source="vnstock:reference",
                effective_at=observed,
                observed_at=observed,
                freshness_seconds=max(
                    0.0, (generated_at - observed).total_seconds()
                ),
                stale=generated_at - observed > EOD_STALE_AFTER,
            )
        )
    return tuple(result)


def monitor_meta(
    session: Session,
    snapshot: MonitorAnalyticsSnapshot,
    exchange: MonitorExchange,
    *,
    generated_at: datetime,
    state_override: MonitorState | None = None,
    realtime: RealtimeMarketOverlay | None = None,
    extra_issues: Iterable[str] = (),
) -> MonitorMeta:
    coverage = _coverage(snapshot.frames.eligible, snapshot.frames.evaluated)
    as_of = _as_of(snapshot, generated_at)
    state = state_override or coverage.state
    if generated_at - as_of > EOD_STALE_AFTER and state in {
        MonitorState.COMPLETE,
        MonitorState.PARTIAL,
    }:
        state = MonitorState.STALE
    realtime_coverage = None
    if realtime is not None:
        realtime_coverage = MonitorCoverage(
            eligible=realtime.eligible,
            evaluated=realtime.evaluated,
            missing=realtime.eligible - realtime.evaluated,
            state=realtime.state,
        )
        if state is not MonitorState.UNAVAILABLE:
            if realtime.state in {MonitorState.DISCONNECTED, MonitorState.STALE}:
                state = realtime.state
            elif (
                state is not MonitorState.STALE
                and realtime.state in {MonitorState.PARTIAL, MonitorState.UNAVAILABLE}
            ):
                state = MonitorState.PARTIAL
    issues = [
        issue.value
        for refusal in snapshot.frames.refusals
        for issue in refusal.issues
    ]
    issues.extend(extra_issues)
    return MonitorMeta(
        exchange=exchange,
        as_of=as_of,
        generated_at=generated_at,
        state=state,
        coverage=coverage,
        realtime_coverage=realtime_coverage,
        sources=_sources(session, snapshot, generated_at),
        issues=tuple(dict.fromkeys(issues)),
        method_versions=METHOD_VERSIONS,
    )


def _metric(
    value: float | int | None,
    unit: str,
    method: str,
    as_of: datetime,
    issues: Iterable[str] = (),
) -> MetricValue:
    reasons = tuple(dict.fromkeys(issues))
    if value is None and not reasons:
        reasons = ("unavailable",)
    return MetricValue(
        value=value,
        unit=unit,
        as_of=as_of,
        method=method,
        issues=reasons,
    )


def _flag(value: bool | None, method: str, as_of: datetime) -> EvidenceFlag:
    return EvidenceFlag(
        value=value,
        method=method,
        as_of=as_of,
        issues=(() if value is not None else ("insufficient_history",)),
    )


def _breadth_summary(
    snapshot: MonitorAnalyticsSnapshot,
    as_of: datetime,
) -> BreadthSummary:
    value = snapshot.breadth
    return BreadthSummary(
        advancing=_metric(value.advancing, "symbol", "breadth-v1", as_of),
        declining=_metric(value.declining, "symbol", "breadth-v1", as_of),
        unchanged=_metric(value.unchanged, "symbol", "breadth-v1", as_of),
        advance_decline_ratio=_metric(
            value.advance_decline_ratio,
            "ratio",
            "breadth-v1",
            as_of,
            value.issues,
        ),
        above_ma20_pct=_metric(value.above_ma20_pct, "%", "breadth-v1", as_of),
        above_ma50_pct=_metric(value.above_ma50_pct, "%", "breadth-v1", as_of),
        above_ma200_pct=_metric(value.above_ma200_pct, "%", "breadth-v1", as_of),
    )


def _valuation_summary(snapshot: MonitorAnalyticsSnapshot, fallback_as_of: datetime) -> ValuationSummary:
    value = snapshot.valuation
    as_of = (
        datetime.combine(value.as_of, time.min, tzinfo=VN_TZ)
        if value.as_of is not None
        else fallback_as_of
    )
    return ValuationSummary(
        market_pe=_metric(value.market_pe, "ratio", "valuation-regime-v1", as_of),
        market_pb=_metric(value.market_pb, "ratio", "valuation-regime-v1", as_of),
        pe_percentile=_metric(
            value.pe_percentile,
            "%",
            "valuation-regime-v1",
            as_of,
            (() if value.pe_percentile is not None else ("insufficient_valuation_history",)),
        ),
        pb_percentile=_metric(
            value.pb_percentile,
            "%",
            "valuation-regime-v1",
            as_of,
            (() if value.pb_percentile is not None else ("insufficient_valuation_history",)),
        ),
        coverage=_coverage(value.eligible, value.evaluated),
    )


def _sector(row: SectorReading, as_of: datetime) -> SectorMonitorRow:
    coverage = _coverage(row.eligible, row.evaluated)
    return SectorMonitorRow(
        code=row.code,
        name=row.name,
        exchange=MonitorExchange(row.exchange.value),
        return_1d_pct=_metric(row.return_1d_pct, "%", "sector-rotation-v1", as_of),
        return_5d_pct=_metric(row.return_5d_pct, "%", "sector-rotation-v1", as_of),
        return_20d_pct=_metric(row.return_20d_pct, "%", "sector-rotation-v1", as_of),
        relative_strength_1d_pct=_metric(row.relative_strength_1d_pct, "%", "sector-rotation-v1", as_of),
        relative_strength_5d_pct=_metric(row.relative_strength_5d_pct, "%", "sector-rotation-v1", as_of),
        relative_strength_20d_pct=_metric(row.relative_strength_20d_pct, "%", "sector-rotation-v1", as_of),
        advancing_pct=_metric(row.advancing_pct, "%", "sector-rotation-v1", as_of),
        liquidity_ratio=_metric(row.liquidity_ratio, "ratio", "sector-rotation-v1", as_of),
        rotation=row.rotation,
        coverage=coverage,
    )


def _stock(
    row: StockReading,
    as_of: datetime,
    valuations: Iterable[ValuationObservation] = (),
) -> StockMonitorRow:
    latest = max(
        (item for item in valuations if item.symbol == row.symbol),
        key=lambda item: item.session_date,
        default=None,
    )
    valuation_as_of = (
        datetime.combine(latest.session_date, time.min, tzinfo=VN_TZ)
        if latest is not None
        else as_of
    )
    metrics = {
        "last_price_vnd": _metric(row.last_price_vnd, "VND", "stock-screen-v1", as_of),
        "return_1d_pct": _metric(row.return_1d_pct, "%", "stock-screen-v1", as_of),
        "return_5d_pct": _metric(row.return_5d_pct, "%", "stock-screen-v1", as_of),
        "return_20d_pct": _metric(row.return_20d_pct, "%", "stock-screen-v1", as_of),
        "liquidity_ratio": _metric(row.liquidity_ratio, "ratio", "stock-screen-v1", as_of),
        "adtv20_vnd": _metric(row.adtv20_vnd, "VND", "stock-screen-v1", as_of),
        "foreign_net_20d_vnd": _metric(
            row.foreign_net_20d_vnd,
            "VND",
            "stock-screen-v1",
            as_of,
            row.issues,
        ),
        "foreign_flow_over_adtv": _metric(
            row.foreign_flow_over_adtv,
            "ratio",
            "stock-screen-v1",
            as_of,
            row.issues,
        ),
        "pe": _metric(
            latest.pe if latest is not None and latest.pe is not None and latest.pe > 0 else None,
            "ratio",
            "valuation-regime-v1",
            valuation_as_of,
            (() if latest is not None and latest.pe is not None and latest.pe > 0 else ("positive_pe_unavailable",)),
        ),
        "pb": _metric(
            latest.pb if latest is not None and latest.pb is not None and latest.pb > 0 else None,
            "ratio",
            "valuation-regime-v1",
            valuation_as_of,
            (() if latest is not None and latest.pb is not None and latest.pb > 0 else ("positive_pb_unavailable",)),
        ),
    }
    return StockMonitorRow(
        symbol=row.symbol,
        name=row.name,
        exchange=MonitorExchange(row.exchange.value),
        sector_code=row.sector_code,
        sector_name=row.sector_name,
        metrics=metrics,
        trend={
            "above_ma20": _flag(row.above_ma20, "stock-screen-v1", as_of),
            "above_ma50": _flag(row.above_ma50, "stock-screen-v1", as_of),
            "above_ma200": _flag(row.above_ma200, "stock-screen-v1", as_of),
        },
        issues=row.issues,
    )


def overview_response(
    session: Session,
    snapshot: MonitorAnalyticsSnapshot,
    exchange: MonitorExchange,
    *,
    generated_at: datetime,
    horizon: int = 20,
    realtime: RealtimeMarketOverlay | None = None,
) -> MarketOverviewResponse:
    meta = monitor_meta(
        session,
        snapshot,
        exchange,
        generated_at=generated_at,
        realtime=realtime,
        extra_issues=realtime.issues if realtime is not None else (),
    )
    as_of = meta.as_of
    index_names = {"VNINDEX": "VN-Index", "HNXINDEX": "HNX-Index"}
    indices = tuple(
        IndexPulse(
            symbol=item.symbol,
            name=index_names.get(item.symbol, item.symbol),
            level=_metric(item.level, "index_point", "index-pulse-v1", as_of),
            change=_metric(item.change, "index_point", "index-pulse-v1", as_of),
            change_pct=_metric(item.change_pct, "%", "index-pulse-v1", as_of),
            above_ma20=_flag(item.above_ma20, "index-pulse-v1", as_of),
            above_ma50=_flag(item.above_ma50, "index-pulse-v1", as_of),
            above_ma200=_flag(item.above_ma200, "index-pulse-v1", as_of),
        )
        for item in snapshot.indices
    )
    foreign_field = f"foreign_net_{horizon}d_vnd"
    foreign_values = [
        getattr(item, foreign_field)
        for item in snapshot.stocks
        if getattr(item, foreign_field) is not None
    ]
    live_by_symbol = {item.symbol: item for item in realtime.items} if realtime else {}
    live_pairs = [
        (item.active_net_value_vnd, stock.adtv20_vnd)
        for stock in snapshot.stocks
        if (item := live_by_symbol.get(stock.symbol)) is not None
        and item.active_net_value_vnd is not None
        and stock.adtv20_vnd is not None
        and stock.adtv20_vnd > 0
    ]
    live_adtv = sum(float(adtv) for _, adtv in live_pairs)
    active_flow_ratio = (
        sum(float(active) for active, _ in live_pairs) / live_adtv
        if live_pairs and live_adtv > 0
        else None
    )
    active_as_of = max(
        (item.as_of for item in realtime.items),
        default=as_of,
    ) if realtime is not None else as_of
    sectors = tuple(_sector(item, as_of) for item in snapshot.sectors)
    ordered = sorted(
        snapshot.stocks,
        key=lambda item: (
            item.return_1d_pct is None,
            -(item.return_1d_pct or 0),
            item.symbol,
        ),
    )
    return MarketOverviewResponse(
        meta=meta,
        indices=indices,
        breadth=_breadth_summary(snapshot, as_of),
        liquidity=_metric(
            snapshot.breadth.liquidity_ratio,
            "ratio",
            "breadth-v1",
            as_of,
        ),
        foreign_flow=_metric(
            sum(foreign_values) if foreign_values else None,
            "VND",
            "foreign-flow-v1",
            as_of,
            (() if foreign_values else ("foreign_flow_not_stored",)),
        ),
        active_flow_over_adtv=_metric(
            active_flow_ratio,
            "ratio",
            "dnse-active-flow-v1",
            active_as_of,
            (() if active_flow_ratio is not None else ("realtime_projection_unavailable",)),
        ),
        valuation=_valuation_summary(snapshot, as_of),
        leading_sectors=tuple(
            row for row in sectors if row.rotation in {"leading", "improving"}
        )[:5],
        lagging_sectors=tuple(
            row for row in reversed(sectors) if row.rotation in {"lagging", "weakening"}
        )[:5],
        notable_stocks=tuple(
            _stock(item, as_of, snapshot.frames.valuations) for item in ordered[:8]
        ),
    )


def breadth_response(
    session: Session,
    snapshot: MonitorAnalyticsSnapshot,
    exchange: MonitorExchange,
    *,
    generated_at: datetime,
) -> MarketBreadthResponse:
    meta = monitor_meta(session, snapshot, exchange, generated_at=generated_at)
    returns = [item.return_1d_pct for item in snapshot.stocks if item.return_1d_pct is not None]
    buckets = (
        ("down_2", "≤ -2%", lambda value: value <= -2),
        ("down", "-2% đến 0%", lambda value: -2 < value < 0),
        ("flat", "0%", lambda value: value == 0),
        ("up", "0% đến 2%", lambda value: 0 < value < 2),
        ("up_2", "≥ 2%", lambda value: value >= 2),
    )
    value = snapshot.breadth
    return MarketBreadthResponse(
        meta=meta,
        summary=_breadth_summary(snapshot, meta.as_of),
        new_high_20=_metric(value.new_high_20, "symbol", "breadth-v1", meta.as_of),
        new_low_20=_metric(value.new_low_20, "symbol", "breadth-v1", meta.as_of),
        new_high_252=_metric(value.new_high_252, "symbol", "breadth-v1", meta.as_of),
        new_low_252=_metric(value.new_low_252, "symbol", "breadth-v1", meta.as_of),
        advancing_volume_share=_metric(
            value.advancing_volume_share,
            "%",
            "breadth-v1",
            meta.as_of,
        ),
        distribution=tuple(
            DistributionBucket(key=key, label=label, count=sum(predicate(item) for item in returns))
            for key, label, predicate in buckets
        ) if returns else (),
        advance_decline_line=tuple(
            MonitorSeriesPoint(session_date=item.session_date, value=item.cumulative)
            for item in snapshot.advance_decline_line
        ),
    )


def sector_response(
    session: Session,
    snapshot: MonitorAnalyticsSnapshot,
    exchange: MonitorExchange,
    *,
    generated_at: datetime,
) -> MarketSectorResponse:
    meta = monitor_meta(session, snapshot, exchange, generated_at=generated_at)
    return MarketSectorResponse(
        meta=meta,
        sectors=tuple(_sector(item, meta.as_of) for item in snapshot.sectors),
    )


def stock_page_response(
    session: Session,
    snapshot: MonitorAnalyticsSnapshot,
    exchange: MonitorExchange,
    lens: StockLens,
    *,
    generated_at: datetime,
    start: int,
    limit: int,
    next_cursor: str | None,
) -> MarketStockPageResponse:
    meta = monitor_meta(session, snapshot, exchange, generated_at=generated_at)
    return MarketStockPageResponse(
        meta=meta,
        lens=lens,
        items=tuple(
            _stock(item, meta.as_of, snapshot.frames.valuations)
            for item in snapshot.stocks[start : start + limit]
        ),
        next_cursor=next_cursor,
    )


def stock_detail_response(
    session: Session,
    snapshot: MonitorAnalyticsSnapshot,
    exchange: MonitorExchange,
    symbol: str,
    *,
    generated_at: datetime,
) -> MarketStockDetailResponse:
    meta = monitor_meta(session, snapshot, exchange, generated_at=generated_at)
    row = next((item for item in snapshot.stocks if item.symbol == symbol), None)
    if row is None:
        raise LookupError("symbol has no evaluable monitor evidence")
    valuation = [
        item
        for item in snapshot.frames.valuations
        if item.symbol == symbol and item.session_date <= (snapshot.frames.as_of or date.max)
    ]
    latest = max(valuation, key=lambda item: item.session_date) if valuation else None
    return MarketStockDetailResponse(
        meta=meta,
        stock=_stock(row, meta.as_of, snapshot.frames.valuations),
        evidence={
            "valuation": (
                {
                    "session_date": latest.session_date.isoformat(),
                    "pe": latest.pe,
                    "pb": latest.pb,
                    "source": "fiinquant",
                }
                if latest is not None
                else None
            ),
            "issues": list(row.issues),
        },
    )


def flow_response(
    session: Session,
    snapshot: MonitorAnalyticsSnapshot,
    exchange: MonitorExchange,
    realtime: RealtimeMarketOverlay,
    *,
    generated_at: datetime,
    horizon: int = 20,
) -> MarketFlowResponse:
    meta = monitor_meta(
        session,
        snapshot,
        exchange,
        generated_at=generated_at,
        realtime=realtime,
        extra_issues=realtime.issues,
    )
    ranks = rank_market_flows(snapshot.stocks, realtime, horizon=horizon)
    by_symbol = {item.symbol: item for item in snapshot.stocks}
    live = {item.symbol: item for item in realtime.items}

    def aggregate(name: str) -> float | None:
        values = [getattr(item, name) for item in snapshot.stocks if getattr(item, name) is not None]
        return sum(values) if values else None

    def row(symbol: str) -> FlowMonitorRow:
        item = by_symbol[symbol]
        overlay = live.get(symbol)
        active_as_of = overlay.as_of if overlay is not None else meta.as_of
        return FlowMonitorRow(
            symbol=symbol,
            exchange=MonitorExchange(item.exchange.value),
            foreign_net_1d_vnd=_metric(item.foreign_net_1d_vnd, "VND", "foreign-flow-v1", meta.as_of, item.issues),
            foreign_net_5d_vnd=_metric(item.foreign_net_5d_vnd, "VND", "foreign-flow-v1", meta.as_of, item.issues),
            foreign_net_20d_vnd=_metric(item.foreign_net_20d_vnd, "VND", "foreign-flow-v1", meta.as_of, item.issues),
            foreign_flow_over_adtv=_metric(item.foreign_flow_over_adtv, "ratio", "foreign-flow-v1", meta.as_of, item.issues),
            active_flow_over_adtv=_metric(
                float(overlay.active_flow_over_adtv) if overlay and overlay.active_flow_over_adtv is not None else None,
                "ratio",
                "dnse-active-flow-v1",
                active_as_of,
                (() if overlay is not None else ("realtime_projection_unavailable",)),
            ),
            quadrant=overlay.quadrant if overlay is not None else None,
        )

    buy = sum(item.active_buy_volume_shares or 0 for item in realtime.items)
    sell = sum(item.active_sell_volume_shares or 0 for item in realtime.items)
    return MarketFlowResponse(
        meta=meta,
        foreign_net_1d_vnd=_metric(aggregate("foreign_net_1d_vnd"), "VND", "foreign-flow-v1", meta.as_of),
        foreign_net_5d_vnd=_metric(aggregate("foreign_net_5d_vnd"), "VND", "foreign-flow-v1", meta.as_of),
        foreign_net_20d_vnd=_metric(aggregate("foreign_net_20d_vnd"), "VND", "foreign-flow-v1", meta.as_of),
        active_buy_share=_metric(
            buy / (buy + sell) * 100 if buy + sell else None,
            "%",
            "dnse-active-flow-v1",
            max((item.as_of for item in realtime.items), default=meta.as_of),
            (() if buy + sell else ("realtime_projection_unavailable",)),
        ),
        inflows=tuple(row(symbol) for symbol in ranks.inflows),
        outflows=tuple(row(symbol) for symbol in ranks.outflows),
        reversals=tuple(row(symbol) for symbol in ranks.reversals),
    )
