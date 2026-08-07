"""Thread-safe in-memory job status store for tracking background jobs."""
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Literal


@dataclass
class JobStatus:
    """Status of a single background job."""

    job_id: str
    display_name: str
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    progress: int = 0
    total_items: int = 0
    processed_items: int = 0
    message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict | None = None
    error: str | None = None


class JobStatusStore:
    """Thread-safe singleton for job status tracking.

    Uses in-memory dict with threading.Lock for safe concurrent access.
    Only tracks jobs from today - older jobs filtered on read.
    """

    _instance: "JobStatusStore | None" = None
    _lock = Lock()

    def __new__(cls) -> "JobStatusStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._jobs: dict[str, JobStatus] = {}
                    cls._instance._jobs_lock = Lock()
        return cls._instance

    def start_job(self, job_id: str, display_name: str, total_items: int = 0) -> None:
        """Mark job as started/running."""
        with self._jobs_lock:
            self._jobs[job_id] = JobStatus(
                job_id=job_id,
                display_name=display_name,
                status="running",
                total_items=total_items,
                started_at=datetime.now(),
            )

    def is_running(self, job_id: str) -> bool:
        """Whether this job is currently in flight."""
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            return job is not None and job.status == "running"

    def try_start_job(self, job_id: str, display_name: str, total_items: int = 0) -> bool:
        """Start `job_id` unless it is already running.

        Checked and set under one lock so two concurrent triggers cannot both
        see "not running" and launch duplicate work — these jobs write to the
        same tables and burn the same upstream quota.
        """
        with self._jobs_lock:
            existing = self._jobs.get(job_id)
            if existing is not None and existing.status == "running":
                return False

            self._jobs[job_id] = JobStatus(
                job_id=job_id,
                display_name=display_name,
                status="running",
                total_items=total_items,
                started_at=datetime.now(),
            )
            return True

    def update_progress(
        self, job_id: str, processed: int, message: str = ""
    ) -> None:
        """Update job progress. Calculates percentage automatically."""
        with self._jobs_lock:
            if job_id not in self._jobs:
                return
            job = self._jobs[job_id]
            job.processed_items = processed
            job.message = message
            if job.total_items > 0:
                job.progress = int((processed / job.total_items) * 100)

    def complete_job(self, job_id: str, result: dict | None = None) -> None:
        """Mark job as completed successfully."""
        with self._jobs_lock:
            if job_id not in self._jobs:
                return
            job = self._jobs[job_id]
            job.status = "completed"
            job.progress = 100
            job.completed_at = datetime.now()
            job.result = result
            job.processed_items = job.total_items

    def fail_job(self, job_id: str, error: str) -> None:
        """Mark job as failed with error message."""
        with self._jobs_lock:
            if job_id not in self._jobs:
                return
            job = self._jobs[job_id]
            job.status = "failed"
            job.completed_at = datetime.now()
            job.error = error

    def get_all_statuses(self) -> list[JobStatus]:
        """Get all job statuses from today only."""
        today = datetime.now().date()
        with self._jobs_lock:
            return [
                job
                for job in self._jobs.values()
                if job.started_at and job.started_at.date() == today
            ]

    def cleanup_old(self, max_age_hours: int = 24) -> int:
        """Remove jobs older than max_age_hours. Returns count removed."""
        cutoff = datetime.now()
        removed = 0
        with self._jobs_lock:
            to_remove = [
                job_id
                for job_id, job in self._jobs.items()
                if job.started_at
                and (cutoff - job.started_at).total_seconds() > max_age_hours * 3600
            ]
            for job_id in to_remove:
                del self._jobs[job_id]
                removed += 1
        return removed


# Singleton instance for easy import
job_store = JobStatusStore()
