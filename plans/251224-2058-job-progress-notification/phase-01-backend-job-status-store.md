# Phase 1: Backend Job Status Store

**Effort:** 1.5h | **Dependencies:** None

## Objective

Create thread-safe in-memory job status store and REST API endpoint for polling.

---

## Task 1.1: Create JobStatusStore (45 min)

**File:** `apps/api/src/core/job_status_store.py`

### Data Model

```python
@dataclass
class JobStatus:
    job_id: str           # "daily-ohlcv", "intraday", "cleanup", "financial-statements"
    display_name: str     # "Daily OHLCV Collection"
    status: Literal["pending", "running", "completed", "failed"]
    progress: int         # 0-100
    total_items: int
    processed_items: int
    message: str | None   # "Processing VNM..."
    started_at: datetime | None
    completed_at: datetime | None
    result: dict | None   # Final result on completion
    error: str | None     # Error message if failed
```

### JobStatusStore Class

```python
class JobStatusStore:
    """Thread-safe singleton for job status tracking."""
    _instance = None
    _lock = Lock()

    def __new__(cls) -> "JobStatusStore": ...
    def start_job(self, job_id: str, display_name: str, total_items: int) -> None: ...
    def update_progress(self, job_id: str, processed: int, message: str = "") -> None: ...
    def complete_job(self, job_id: str, result: dict | None = None) -> None: ...
    def fail_job(self, job_id: str, error: str) -> None: ...
    def get_all_statuses(self) -> list[JobStatus]: ...
    def cleanup_old(self, max_age_hours: int = 24) -> None: ...
```

### Implementation Notes

- Use `threading.Lock()` for thread safety (sync job `collect_daily_ohlcv_job`)
- Singleton pattern: single instance across workers
- `get_all_statuses()` filters jobs from today only
- Auto-calculate progress: `progress = int(processed / total * 100)`

---

## Task 1.2: Add Progress Callbacks to Jobs (30 min)

**File:** `apps/api/src/stocks/jobs.py`

### Job ID Mapping

| Function | Job ID | Display Name |
|----------|--------|--------------|
| `collect_daily_ohlcv_job` | `daily-ohlcv` | Thu thập OHLCV |
| `collect_intraday_data_job` | `intraday` | Thu thập Intraday |
| `cleanup_old_data_job` | `cleanup` | Dọn dẹp dữ liệu cũ |
| `collect_financial_statements_job` | `financial-statements` | Thu thập BCTC |

### Modification Pattern

```python
from src.core.job_status_store import job_store

def collect_daily_ohlcv_job() -> dict:
    # Start tracking
    all_symbols = get_all_symbols(...)
    job_store.start_job("daily-ohlcv", "Thu thập OHLCV", len(all_symbols))

    try:
        for i, symbol in enumerate(all_symbols):
            # ... existing logic ...

            # Update progress every 10 symbols (reduce overhead)
            if i % 10 == 0:
                job_store.update_progress("daily-ohlcv", i + 1, f"Đang xử lý {symbol}")

        result = {...}
        job_store.complete_job("daily-ohlcv", result)
        return result

    except Exception as e:
        job_store.fail_job("daily-ohlcv", str(e))
        raise
```

### Key Points

- Non-intrusive: wrap existing logic, minimal changes
- Progress update frequency: every 10 items (reduce lock contention)
- Always complete/fail in try/finally or try/except

---

## Task 1.3: Create Jobs Router (15 min)

**File:** `apps/api/src/stocks/jobs_router.py`

### Endpoint

```python
router = APIRouter(prefix="/jobs", tags=["jobs"])

class JobStatusResponse(BaseModel):
    job_id: str
    display_name: str
    status: Literal["pending", "running", "completed", "failed"]
    progress: int
    total_items: int
    processed_items: int
    message: str | None
    started_at: str | None    # ISO format
    completed_at: str | None  # ISO format
    elapsed_seconds: int | None

@router.get("/status", response_model=list[JobStatusResponse])
async def get_jobs_status():
    """Get status of all jobs from today."""
    return job_store.get_all_statuses()
```

### API Contract

- Path: `GET /api/v1/jobs/status`
- Response: Array of JobStatusResponse
- Empty array if no jobs today

---

## Task 1.4: Mount Router (5 min)

**File:** `apps/api/src/main.py`

```python
from src.stocks.jobs_router import router as jobs_router

app.include_router(jobs_router, prefix="/api/v1")
```

---

## Acceptance Criteria

- [ ] JobStatusStore is thread-safe (tested with concurrent calls)
- [ ] 4 jobs report progress correctly
- [ ] GET /api/v1/jobs/status returns valid JSON
- [ ] Response time < 50ms
- [ ] Jobs complete/fail correctly tracked

## Test Commands

```bash
# Start API
docker-compose up api

# Check endpoint
curl http://localhost:8000/api/v1/jobs/status

# Trigger manual job (if needed)
curl -X POST http://localhost:8000/api/v1/stocks/analytics/financial-statements/collect
```
