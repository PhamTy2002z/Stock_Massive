# FastAPI Job Status Tracking - Best Practices

**Research Date:** 2025-12-24
**Focus:** In-memory job tracking, progress callbacks, polling API design
**Context:** Stock_Massive - FastAPI backend with APScheduler

---

## 1. In-Memory Thread-Safe Job Status Store

### Singleton Pattern với Threading Lock

```python
from threading import Lock
from typing import Dict, Optional
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

class JobStatus(str, Enum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    PROGRESS = "PROGRESS"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"

@dataclass
class JobInfo:
    job_id: str
    status: JobStatus
    progress: int = 0  # 0-100
    total_items: int = 0
    processed_items: int = 0
    message: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[dict] = field(default_factory=dict)

class JobStatusStore:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._jobs: Dict[str, JobInfo] = {}
                    cls._instance._data_lock = Lock()
        return cls._instance

    def create_job(self, job_id: str, total_items: int = 0) -> JobInfo:
        with self._data_lock:
            job = JobInfo(
                job_id=job_id,
                status=JobStatus.PENDING,
                total_items=total_items,
                started_at=datetime.now()
            )
            self._jobs[job_id] = job
            return job

    def update_progress(self, job_id: str, processed: int, message: str = ""):
        with self._data_lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.processed_items = processed
                job.progress = int((processed / job.total_items) * 100) if job.total_items > 0 else 0
                job.message = message
                job.status = JobStatus.PROGRESS

    def complete_job(self, job_id: str, result: dict = None):
        with self._data_lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = JobStatus.SUCCESS
                job.completed_at = datetime.now()
                job.progress = 100
                job.result = result or {}

    def fail_job(self, job_id: str, error: str):
        with self._data_lock:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                job.status = JobStatus.FAILURE
                job.completed_at = datetime.now()
                job.error = error

    def get_job(self, job_id: str) -> Optional[JobInfo]:
        with self._data_lock:
            return self._jobs.get(job_id)

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove jobs older than max_age_hours"""
        with self._data_lock:
            now = datetime.now()
            to_remove = [
                jid for jid, job in self._jobs.items()
                if job.completed_at and (now - job.completed_at).total_seconds() > max_age_hours * 3600
            ]
            for jid in to_remove:
                del self._jobs[jid]
```

---

## 2. Progress Callback Pattern (Non-Intrusive)

### Callback Wrapper cho Existing Functions

```python
from typing import Callable, Optional
import uuid

class ProgressTracker:
    def __init__(self, job_id: str, total_items: int):
        self.job_id = job_id
        self.total_items = total_items
        self.store = JobStatusStore()
        self.store.create_job(job_id, total_items)

    def update(self, processed: int, message: str = ""):
        self.store.update_progress(self.job_id, processed, message)

    def complete(self, result: dict = None):
        self.store.complete_job(self.job_id, result)

    def fail(self, error: str):
        self.store.fail_job(self.job_id, error)

def with_progress_tracking(total_items: int):
    """Decorator để add progress tracking vào existing functions"""
    def decorator(func: Callable):
        async def wrapper(*args, progress_callback: Optional[ProgressTracker] = None, **kwargs):
            try:
                result = await func(*args, progress_callback=progress_callback, **kwargs)
                if progress_callback:
                    progress_callback.complete(result)
                return result
            except Exception as e:
                if progress_callback:
                    progress_callback.fail(str(e))
                raise
        return wrapper
    return decorator

# Usage example
@with_progress_tracking(total_items=100)
async def batch_process_stocks(symbols: list, progress_callback: Optional[ProgressTracker] = None):
    results = []
    for i, symbol in enumerate(symbols):
        # Process symbol
        data = await fetch_stock_data(symbol)
        results.append(data)

        # Update progress (non-intrusive)
        if progress_callback:
            progress_callback.update(i + 1, f"Processing {symbol}")

    return {"processed": len(results)}
```

---

## 3. API Endpoint Design

### RESTful Polling Pattern

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int
    message: str
    processed_items: int
    total_items: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error: Optional[str] = None
    result: Optional[dict] = None

@router.post("/batch-process", status_code=202)
async def start_batch_job(symbols: list[str]):
    """Initiate background job, return job_id immediately"""
    job_id = str(uuid.uuid4())
    tracker = ProgressTracker(job_id, len(symbols))

    # Trigger async job (APScheduler or BackgroundTasks)
    scheduler.add_job(
        batch_process_stocks,
        args=[symbols],
        kwargs={"progress_callback": tracker},
        id=job_id
    )

    return {
        "job_id": job_id,
        "status": "PENDING",
        "message": "Job queued for processing"
    }

@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Poll job status"""
    store = JobStatusStore()
    job = store.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        message=job.message,
        processed_items=job.processed_items,
        total_items=job.total_items,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error=job.error,
        result=job.result
    )

@router.delete("/cleanup")
async def cleanup_jobs(max_age_hours: int = 24):
    """Cleanup old completed jobs"""
    store = JobStatusStore()
    store.cleanup_old_jobs(max_age_hours)
    return {"message": "Cleanup completed"}
```

---

## 4. Integration với APScheduler (Current Setup)

```python
# core/scheduler.py integration
from apscheduler.schedulers.asyncio import AsyncIOScheduler

def setup_job_cleanup(scheduler: AsyncIOScheduler):
    """Auto cleanup old jobs every 6 hours"""
    store = JobStatusStore()
    scheduler.add_job(
        store.cleanup_old_jobs,
        'interval',
        hours=6,
        id='job_cleanup',
        replace_existing=True
    )
```

---

## Key Recommendations

1. **Use In-Memory Store for Simplicity**: Avoid Celery/RQ overhead if APScheduler already exists
2. **Thread-Safe Singleton**: Critical for FastAPI's async workers
3. **202 Accepted Pattern**: Return job_id immediately, poll for status
4. **Progress Callback Optional**: Backward compatible with existing functions
5. **Auto-Cleanup**: Prevent memory leaks with scheduled cleanup job
6. **Structured Status**: Use enum for consistent states (PENDING → PROGRESS → SUCCESS/FAILURE)

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| In-Memory Store | Simple, no extra deps, fast | Lost on restart, not distributed |
| Redis Store | Persistent, distributed | Extra infra, network latency |
| Celery/RQ | Full-featured, battle-tested | Heavy, complex setup |

**Verdict for Stock_Massive**: In-memory sufficient for scheduled jobs (daily batch). Add Redis later if need persistence.

---

## Unresolved Questions

1. Should job status persist across API restarts? (Redis integration needed)
2. Max concurrent jobs limit? (APScheduler already has max_instances)
3. Frontend polling interval? (Suggest 2s with exponential backoff to 10s)
