"""Read-only health surface for the realtime ingestion boundary."""

from __future__ import annotations

import asyncio

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .health import HealthSnapshot
from .contracts import EventFamily, MarketDataSource
from .projections import HotProjectionStore, ProjectionUnavailable
from .service import (
    MAX_EVENT_PAGE_SIZE,
    RealtimePageResponse,
    RealtimeProjectionResponse,
    RealtimeReadService,
)
from .storage import RealtimeEventStore


router = APIRouter(prefix="/realtime", tags=["realtime"])


class RealtimeHealthResponse(BaseModel):
    feed: HealthSnapshot | None
    data: HealthSnapshot | None


async def get_realtime_read_service() -> RealtimeReadService:
    from src.core.database import in_sync_session
    from src.stocks.universe import build_universe

    symbols = await in_sync_session(lambda session: build_universe(session).symbols)
    return RealtimeReadService(
        RealtimeEventStore(),
        HotProjectionStore(),
        symbols,
    )


async def _events(
    family: EventFamily,
    symbol: str,
    start: datetime,
    end: datetime,
    source: MarketDataSource | None,
    cursor: str | None,
    limit: int,
    service: RealtimeReadService,
) -> RealtimePageResponse:
    try:
        return await service.events(
            family,
            symbol,
            start=start,
            end=end,
            source=source,
            cursor=cursor,
            limit=limit,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/trades/{symbol}", response_model=RealtimePageResponse)
async def get_realtime_trades(
    symbol: str,
    start: datetime,
    end: datetime,
    source: MarketDataSource | None = None,
    cursor: str | None = None,
    limit: int = Query(default=200, ge=1, le=MAX_EVENT_PAGE_SIZE),
    service: RealtimeReadService = Depends(get_realtime_read_service),
) -> RealtimePageResponse:
    return await _events(
        EventFamily.TRADE, symbol, start, end, source, cursor, limit, service
    )


@router.get("/bars/{symbol}", response_model=RealtimePageResponse)
async def get_realtime_bars(
    symbol: str,
    start: datetime,
    end: datetime,
    source: MarketDataSource | None = None,
    cursor: str | None = None,
    limit: int = Query(default=200, ge=1, le=MAX_EVENT_PAGE_SIZE),
    service: RealtimeReadService = Depends(get_realtime_read_service),
) -> RealtimePageResponse:
    return await _events(
        EventFamily.CLOSED_BAR, symbol, start, end, source, cursor, limit, service
    )


@router.get("/foreign-flow/{symbol}", response_model=RealtimePageResponse)
async def get_realtime_foreign_flow(
    symbol: str,
    start: datetime,
    end: datetime,
    source: MarketDataSource | None = None,
    cursor: str | None = None,
    limit: int = Query(default=200, ge=1, le=MAX_EVENT_PAGE_SIZE),
    service: RealtimeReadService = Depends(get_realtime_read_service),
) -> RealtimePageResponse:
    return await _events(
        EventFamily.FOREIGN_FLOW,
        symbol,
        start,
        end,
        source,
        cursor,
        limit,
        service,
    )


@router.get("/projections/{symbol}", response_model=RealtimeProjectionResponse)
async def get_realtime_projections(
    symbol: str,
    board: str = Query(default="G1"),
    service: RealtimeReadService = Depends(get_realtime_read_service),
) -> RealtimeProjectionResponse:
    try:
        response = await service.metrics(symbol, board)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ProjectionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not response.projections:
        raise HTTPException(status_code=404, detail="Realtime projections not found")
    return response


@router.get("/health", response_model=RealtimeHealthResponse)
async def get_realtime_health() -> RealtimeHealthResponse:
    """Read durable state only; this endpoint never contacts DNSE."""
    store = RealtimeEventStore()
    feed, data = await asyncio.gather(
        store.read_health("feed"),
        store.read_health("data"),
    )
    if feed is None and data is None:
        raise HTTPException(status_code=404, detail="Realtime health is not recorded")
    return RealtimeHealthResponse(feed=feed, data=data)
