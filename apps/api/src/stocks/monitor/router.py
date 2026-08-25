"""Authenticated bounded REST surface for the five Market Monitor lenses."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from src.auth.dependencies import CurrentUser
from src.core.cache import TradingHoursCache
from src.core.database import get_sync_session
from src.core.ratelimit import standard_rate_limit
from src.stocks.realtime.projections import HotProjectionStore
from src.stocks.realtime.service import RealtimeReadService
from src.stocks.realtime.storage import RealtimeEventStore
from src.stocks.providers.normalize import VN_TZ
from src.stocks.shared import StockServiceError, validate_symbol
from src.stocks.universe import build_universe

from .presenters import (
    breadth_response,
    flow_response,
    overview_response,
    sector_response,
    stock_detail_response,
    stock_page_response,
)
from .realtime import load_realtime_overlay
from .schemas import (
    MarketBreadthResponse,
    MarketFlowResponse,
    MarketOverviewResponse,
    MarketSectorResponse,
    MarketStockDetailResponse,
    MarketStockPageResponse,
    MonitorExchange,
    SortDirection,
    StockLens,
)
from .service import MarketMonitorService, monitor_cache_key


router = APIRouter(prefix="/market-monitor", tags=["market-monitor"])
monitor_cache = TradingHoursCache(
    key_prefix="stock:market-monitor:",
    ttl_trading=60,
    ttl_off_hours=15 * 60,
)
StockSort = Literal[
    "symbol",
    "return_1d_pct",
    "return_5d_pct",
    "return_20d_pct",
    "liquidity_ratio",
    "foreign_net_20d_vnd",
    "foreign_flow_over_adtv",
]


def get_monitor_service(
    db: Session = Depends(get_sync_session),
) -> MarketMonitorService:
    return MarketMonitorService(db)


def get_realtime_service(
    db: Session = Depends(get_sync_session),
) -> RealtimeReadService:
    return RealtimeReadService(
        RealtimeEventStore(),
        HotProjectionStore(),
        build_universe(db).symbols,
    )


def _generated_at() -> datetime:
    return datetime.now(UTC)


def _validate_as_of(as_of: date | None) -> None:
    if as_of is not None and as_of > datetime.now(VN_TZ).date():
        raise HTTPException(status_code=422, detail="Market monitor as_of cannot be in the future")


def _validate_horizon(horizon: int) -> None:
    if horizon not in {1, 5, 20}:
        raise HTTPException(status_code=422, detail="Market monitor horizon must be 1, 5, or 20")


def _cache_key(
    service: MarketMonitorService,
    *,
    lens: str,
    exchange: MonitorExchange,
    as_of: date | None,
    window_days: int,
    suffix: str = "",
) -> str:
    base = monitor_cache_key(
        service.session,
        exchange=exchange,
        as_of=as_of,
        window_days=window_days,
    )
    return f"{lens}:{base}:{suffix}"


@router.get(
    "/overview",
    response_model=MarketOverviewResponse,
    dependencies=[Depends(standard_rate_limit)],
)
async def get_overview(
    _current_user: CurrentUser,
    exchange: MonitorExchange = Query(MonitorExchange.ALL),
    as_of: date | None = Query(None),
    window_days: int = Query(253, ge=21, le=253),
    horizon: int = Query(20, ge=1, le=20),
    service: MarketMonitorService = Depends(get_monitor_service),
    realtime_service: RealtimeReadService = Depends(get_realtime_service),
) -> MarketOverviewResponse:
    _validate_as_of(as_of)
    _validate_horizon(horizon)
    snapshot = service.snapshot(exchange, as_of=as_of, window_days=window_days)
    generated_at = _generated_at()
    realtime = await load_realtime_overlay(
        realtime_service,
        eligible_symbols=snapshot.frames.eligible_symbols,
        eod_stocks=snapshot.stocks,
        now=generated_at,
    )
    return overview_response(
        service.session,
        snapshot,
        exchange,
        generated_at=generated_at,
        horizon=horizon,
        realtime=realtime,
    )


@router.get(
    "/breadth",
    response_model=MarketBreadthResponse,
    dependencies=[Depends(standard_rate_limit)],
)
def get_breadth(
    _current_user: CurrentUser,
    exchange: MonitorExchange = Query(MonitorExchange.ALL),
    as_of: date | None = Query(None),
    window_days: int = Query(253, ge=21, le=253),
    service: MarketMonitorService = Depends(get_monitor_service),
) -> MarketBreadthResponse:
    _validate_as_of(as_of)
    key = _cache_key(
        service,
        lens="breadth",
        exchange=exchange,
        as_of=as_of,
        window_days=window_days,
    )
    if (cached := monitor_cache.get(key)) is not None:
        return MarketBreadthResponse.model_validate(cached)
    snapshot = service.snapshot(exchange, as_of=as_of, window_days=window_days)
    response = breadth_response(
        service.session,
        snapshot,
        exchange,
        generated_at=_generated_at(),
    )
    monitor_cache.set(key, response.model_dump(mode="json"))
    return response


@router.get(
    "/flows",
    response_model=MarketFlowResponse,
    dependencies=[Depends(standard_rate_limit)],
)
async def get_flows(
    _current_user: CurrentUser,
    exchange: MonitorExchange = Query(MonitorExchange.ALL),
    as_of: date | None = Query(None),
    window_days: int = Query(253, ge=21, le=253),
    horizon: int = Query(20, ge=1, le=20),
    service: MarketMonitorService = Depends(get_monitor_service),
    realtime_service: RealtimeReadService = Depends(get_realtime_service),
) -> MarketFlowResponse:
    _validate_as_of(as_of)
    _validate_horizon(horizon)
    snapshot = service.snapshot(exchange, as_of=as_of, window_days=window_days)
    generated_at = _generated_at()
    realtime = await load_realtime_overlay(
        realtime_service,
        eligible_symbols=snapshot.frames.eligible_symbols,
        eod_stocks=snapshot.stocks,
        now=generated_at,
    )
    return flow_response(
        service.session,
        snapshot,
        exchange,
        realtime,
        generated_at=generated_at,
        horizon=horizon,
    )


@router.get(
    "/sectors",
    response_model=MarketSectorResponse,
    dependencies=[Depends(standard_rate_limit)],
)
def get_sectors(
    _current_user: CurrentUser,
    exchange: MonitorExchange = Query(MonitorExchange.ALL),
    as_of: date | None = Query(None),
    window_days: int = Query(253, ge=21, le=253),
    service: MarketMonitorService = Depends(get_monitor_service),
) -> MarketSectorResponse:
    _validate_as_of(as_of)
    key = _cache_key(
        service,
        lens="sectors",
        exchange=exchange,
        as_of=as_of,
        window_days=window_days,
    )
    if (cached := monitor_cache.get(key)) is not None:
        return MarketSectorResponse.model_validate(cached)
    snapshot = service.snapshot(exchange, as_of=as_of, window_days=window_days)
    response = sector_response(
        service.session,
        snapshot,
        exchange,
        generated_at=_generated_at(),
    )
    monitor_cache.set(key, response.model_dump(mode="json"))
    return response


@router.get(
    "/stocks",
    response_model=MarketStockPageResponse,
    dependencies=[Depends(standard_rate_limit)],
)
def get_stocks(
    _current_user: CurrentUser,
    exchange: MonitorExchange = Query(MonitorExchange.ALL),
    lens: StockLens = Query(StockLens.OVERVIEW),
    sector_code: str | None = Query(None, min_length=1, max_length=8),
    sort_by: StockSort = Query("symbol"),
    direction: SortDirection = Query(SortDirection.ASC),
    cursor: str | None = Query(None, max_length=512),
    limit: int = Query(25, ge=1, le=50),
    as_of: date | None = Query(None),
    window_days: int = Query(253, ge=21, le=253),
    service: MarketMonitorService = Depends(get_monitor_service),
) -> MarketStockPageResponse:
    _validate_as_of(as_of)
    snapshot = service.snapshot(
        exchange,
        as_of=as_of,
        window_days=window_days,
        sector_code=sector_code,
        sort_by=sort_by,
        descending=direction is SortDirection.DESC,
    )
    binding = {
        "exchange": exchange.value,
        "lens": lens.value,
        "sector_code": sector_code,
        "sort_by": sort_by,
        "direction": direction.value,
        "as_of": as_of.isoformat() if as_of else None,
        "window_days": window_days,
        "generation": hashlib.sha256(
            monitor_cache_key(
                service.session,
                exchange=exchange,
                as_of=as_of,
                window_days=window_days,
            ).encode()
        ).hexdigest()[:24],
    }
    start = _decode_cursor(cursor, binding) if cursor else 0
    next_offset = start + limit
    next_cursor = (
        _encode_cursor(next_offset, binding)
        if next_offset < len(snapshot.stocks)
        else None
    )
    return stock_page_response(
        service.session,
        snapshot,
        exchange,
        lens,
        generated_at=_generated_at(),
        start=start,
        limit=limit,
        next_cursor=next_cursor,
    )


@router.get(
    "/stocks/{symbol}",
    response_model=MarketStockDetailResponse,
    dependencies=[Depends(standard_rate_limit)],
)
def get_stock_detail(
    _current_user: CurrentUser,
    symbol: Annotated[str, Path(min_length=1, max_length=20)],
    exchange: MonitorExchange = Query(MonitorExchange.ALL),
    as_of: date | None = Query(None),
    window_days: int = Query(253, ge=21, le=253),
    service: MarketMonitorService = Depends(get_monitor_service),
) -> MarketStockDetailResponse:
    _validate_as_of(as_of)
    try:
        normalized = validate_symbol(symbol)
    except StockServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    snapshot = service.snapshot(exchange, as_of=as_of, window_days=window_days)
    try:
        return stock_detail_response(
            service.session,
            snapshot,
            exchange,
            normalized,
            generated_at=_generated_at(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _encode_cursor(offset: int, binding: dict[str, object]) -> str:
    raw = json.dumps(
        {"v": 1, "offset": offset, "binding": binding},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str, binding: dict[str, object]) -> int:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        if (
            not isinstance(payload, dict)
            or payload.get("v") != 1
            or payload.get("binding") != binding
            or not isinstance(payload.get("offset"), int)
            or not 0 <= payload["offset"] <= 10_000
        ):
            raise ValueError
        return payload["offset"]
    except (binascii.Error, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid market monitor cursor") from exc
