"""Jobs status API endpoint for polling job progress."""
import asyncio
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from src.auth.dependencies import require_admin
from src.core.job_status_store import job_store
from src.core.ratelimit import heavy_rate_limit
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.database import get_sync_session
from src.stocks.backfill import BackfillStateStore, BackfillStatus
from src.stocks.collector_schedule import (
    BACKFILL_JOB_ID,
    COLLECTOR_JOB_ID,
    backfill_universe_history,
    collect_universe_snapshots,
)
from src.stocks.universe import get_universe
from src.stocks.schemas.common import MessageResponse

# Must match the id jobs.py registers for this collector.
OHLCV_JOB_ID = "daily-ohlcv"

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobStatusResponse(BaseModel):
    """Response model for job status."""

    job_id: str
    display_name: str
    status: Literal["pending", "running", "completed", "failed"]
    progress: int
    total_items: int
    processed_items: int
    message: str | None
    started_at: str | None
    completed_at: str | None
    elapsed_seconds: int | None


@router.get("/status", response_model=list[JobStatusResponse])
def get_jobs_status() -> list[JobStatusResponse]:
    """Get status of all jobs from today.

    Returns list of job statuses, empty if no jobs today.
    Used by frontend for polling progress updates.
    """
    statuses = job_store.get_all_statuses()
    return [
        JobStatusResponse(
            job_id=s.job_id,
            display_name=s.display_name,
            status=s.status,
            progress=s.progress,
            total_items=s.total_items,
            processed_items=s.processed_items,
            message=s.message,
            started_at=s.started_at.isoformat() if s.started_at else None,
            completed_at=s.completed_at.isoformat() if s.completed_at else None,
            elapsed_seconds=(
                int((datetime.now() - s.started_at).total_seconds())
                if s.started_at and s.status == "running"
                else (
                    int((s.completed_at - s.started_at).total_seconds())
                    if s.started_at and s.completed_at
                    else None
                )
            ),
        )
        for s in statuses
    ]


class CollectorRunResponse(BaseModel):
    """The last collection cycle, in the terms an operator judges it by."""

    status: Literal["pending", "running", "completed", "failed"]
    started_at: str | None
    completed_at: str | None
    result: dict | None
    error: str | None


@router.get("/collector", response_model=CollectorRunResponse)
def get_collector_run() -> CollectorRunResponse:
    """Report the last collection cycle, whenever it ran.

    A cycle that has never run is a 404 rather than an invented empty one, so
    a fresh deployment reads differently from a collector that ran and wrote
    nothing.
    """
    status = job_store.get_status(COLLECTOR_JOB_ID)
    if status is None:
        raise HTTPException(
            status_code=404,
            detail="Chưa có chu kỳ thu thập nào chạy trong tiến trình này.",
        )
    return CollectorRunResponse(
        status=status.status,
        started_at=status.started_at.isoformat() if status.started_at else None,
        completed_at=status.completed_at.isoformat() if status.completed_at else None,
        result=status.result,
        error=status.error,
    )


@router.post(
    "/trigger/collector",
    response_model=MessageResponse,
    dependencies=[Depends(heavy_rate_limit), Depends(require_admin)],
)
async def trigger_collector_job(background_tasks: BackgroundTasks) -> MessageResponse:
    """Run one collection cycle now, whatever the calendar says.

    Filling a gap after a bad day is what this is for, so it does not wait for
    the next trading day the scheduled run would. It does respect the
    configuration switch: an operator who turned the collector off turned off
    every path that reaches a Provider Source, not just the scheduled one.
    """
    if not get_settings().collector_enabled:
        raise HTTPException(
            status_code=409,
            detail="Collector đang tắt trong cấu hình (COLLECTOR_ENABLED).",
        )

    if job_store.is_running(COLLECTOR_JOB_ID):
        raise HTTPException(
            status_code=409,
            detail="Chu kỳ thu thập đang chạy. Theo dõi tại /jobs/collector.",
        )

    background_tasks.add_task(collect_universe_snapshots, force=True)
    return MessageResponse(message="Collection cycle triggered", status="started")


class SymbolBackfillResponse(BaseModel):
    """Where one symbol's one-time history load stands."""

    symbol: str
    status: BackfillStatus
    covered_through: str | None
    last_error: str | None


@router.get("/backfill", response_model=list[SymbolBackfillResponse])
def get_backfill_progress(
    db: Session = Depends(get_sync_session),
) -> list[SymbolBackfillResponse]:
    """Report where every Universe symbol's history load stands.

    Read from the durable state rather than from the last run, because a load
    spans many runs and the interesting question spans all of them. Driven by
    the Universe rather than by the state table, so a symbol that has not
    started yet is reported as pending instead of going missing.
    """
    recorded = {state.symbol: state for state in BackfillStateStore(db).all()}
    return [
        SymbolBackfillResponse(
            symbol=symbol,
            status=recorded[symbol].status if symbol in recorded else "pending",
            covered_through=(
                recorded[symbol].covered_through.isoformat()
                if symbol in recorded and recorded[symbol].covered_through
                else None
            ),
            last_error=recorded[symbol].last_error if symbol in recorded else None,
        )
        for symbol in get_universe()
    ]


@router.post(
    "/trigger/backfill",
    response_model=MessageResponse,
    dependencies=[Depends(heavy_rate_limit), Depends(require_admin)],
)
async def trigger_backfill_job(background_tasks: BackgroundTasks) -> MessageResponse:
    """Run one pass of the history load now."""
    if not get_settings().backfill_enabled:
        raise HTTPException(
            status_code=409,
            detail="Backfill đang tắt trong cấu hình (BACKFILL_ENABLED).",
        )

    if job_store.is_running(BACKFILL_JOB_ID):
        raise HTTPException(
            status_code=409,
            detail="Lần nạp lịch sử đang chạy. Theo dõi tại /jobs/backfill.",
        )

    background_tasks.add_task(backfill_universe_history)
    return MessageResponse(message="History backfill triggered", status="started")


@router.post(
    "/trigger/ohlcv",
    response_model=MessageResponse,
    dependencies=[Depends(heavy_rate_limit), Depends(require_admin)],
)
async def trigger_ohlcv_job(background_tasks: BackgroundTasks) -> MessageResponse:
    """Manually trigger OHLCV collection job.

    Runs in background, returns immediately.
    Check /jobs/status for progress.
    """
    from src.core.scheduler import collect_daily_ohlcv_job_async

    # Refuse rather than stack a second run: this job writes to the same tables
    # and spends the same upstream quota as the one already in flight.
    if job_store.is_running(OHLCV_JOB_ID):
        raise HTTPException(
            status_code=409,
            detail="Job thu thập OHLCV đang chạy. Theo dõi tiến độ tại /jobs/status.",
        )

    background_tasks.add_task(collect_daily_ohlcv_job_async)
    return MessageResponse(message="OHLCV job triggered", status="started")
