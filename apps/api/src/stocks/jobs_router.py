"""Jobs status API endpoint for polling job progress."""
import asyncio
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel

from src.core.job_status_store import job_store
from src.core.ratelimit import heavy_rate_limit
from src.auth.dependencies import require_admin

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


@router.post("/trigger/ohlcv", dependencies=[Depends(heavy_rate_limit), Depends(require_admin)])
def trigger_ohlcv_job(background_tasks: BackgroundTasks) -> dict:
    """Manually trigger OHLCV collection job.

    Runs in background, returns immediately.
    Check /jobs/status for progress.
    """
    from src.core.scheduler import collect_daily_ohlcv_job_async

    background_tasks.add_task(collect_daily_ohlcv_job_async)
    return {"message": "OHLCV job triggered", "status": "started"}
