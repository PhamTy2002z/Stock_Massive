"""Read-only health surface for the realtime ingestion boundary."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .health import HealthSnapshot
from .storage import RealtimeEventStore


router = APIRouter(prefix="/realtime", tags=["realtime"])


class RealtimeHealthResponse(BaseModel):
    feed: HealthSnapshot | None
    data: HealthSnapshot | None


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
