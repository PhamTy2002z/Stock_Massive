# Phase 04: Scheduled Jobs

**Parent Plan:** [plan.md](plan.md)
**Dependencies:** [Phase 01](phase-01-database-setup.md), [Phase 02](phase-02-data-collection-service.md)
**Docs:** [APScheduler Research](research/researcher-02-apscheduler-fastapi.md)

## Overview

| Field | Value |
|-------|-------|
| Date | 2024-12-18 |
| Priority | Medium |
| Implementation Status | Pending |
| Review Status | Pending |

**Description:** Implement daily scheduled job using APScheduler to collect intraday data after market close (15:30 Vietnam time) and cleanup old data.

## Key Insights

- APScheduler 4.x has native async support via AsyncScheduler
- Integrate with FastAPI lifespan context manager
- CronTrigger for daily 15:30 execution
- Optional: SQLAlchemy datastore for job persistence

## Requirements

1. Add APScheduler dependency
2. Create scheduler module with job definitions
3. Integrate scheduler with FastAPI lifespan
4. Implement data retention cleanup

## Architecture

```
apps/api/src/
├── core/
│   ├── scheduler.py       # NEW - APScheduler setup
│   └── config.py          # Update - add scheduler settings
├── stocks/
│   └── jobs.py            # NEW - scheduled job functions
└── main.py                # Update - integrate scheduler
```

## Related Code Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/requirements.txt` | Update | Add apscheduler>=4.0.0 |
| `apps/api/src/core/config.py` | Update | Add scheduler settings |
| `apps/api/src/core/scheduler.py` | Create | Scheduler setup |
| `apps/api/src/stocks/jobs.py` | Create | Job functions |
| `apps/api/src/main.py` | Update | Integrate scheduler lifespan |

## Implementation Steps

### Step 1: Add dependency

```bash
# Add to requirements.txt
apscheduler>=4.0.0
```

### Step 2: Update config

```python
# Add to apps/api/src/core/config.py
class Settings(BaseSettings):
    # ... existing ...

    # Scheduler
    scheduler_enabled: bool = True
    intraday_collect_hour: int = 15
    intraday_collect_minute: int = 30
    intraday_symbols: str = "VCB,FPT,VNM,VIC,VHM"  # Comma-separated
    intraday_retention_days: int = 30
```

### Step 3: Create job functions

```python
# apps/api/src/stocks/jobs.py
import logging
from datetime import datetime, timedelta
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import async_session_factory
from src.stocks.intraday_collector import IntradayCollector
from src.stocks.models import StockIntradayBar
from src.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

async def collect_intraday_data_job():
    """Daily job to collect intraday data for configured symbols."""
    symbols = [s.strip() for s in settings.intraday_symbols.split(",")]
    logger.info(f"Starting intraday collection for {len(symbols)} symbols")

    async with async_session_factory() as db:
        collector = IntradayCollector(db)
        result = await collector.collect_and_save(symbols)

    logger.info(
        f"Collection complete: {len(result['success'])} success, "
        f"{len(result['failed'])} failed, {result['total_bars']} bars"
    )
    return result

async def cleanup_old_data_job():
    """Daily job to remove data older than retention period."""
    cutoff = datetime.now() - timedelta(days=settings.intraday_retention_days)
    logger.info(f"Cleaning up data older than {cutoff}")

    async with async_session_factory() as db:
        stmt = delete(StockIntradayBar).where(StockIntradayBar.bar_time < cutoff)
        result = await db.execute(stmt)
        await db.commit()

    logger.info(f"Deleted {result.rowcount} old records")
    return result.rowcount
```

### Step 4: Create scheduler module

```python
# apps/api/src/core/scheduler.py
import logging
from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger
from src.core.config import get_settings
from src.stocks.jobs import collect_intraday_data_job, cleanup_old_data_job

logger = logging.getLogger(__name__)
settings = get_settings()

async def setup_scheduler(scheduler: AsyncScheduler):
    """Configure scheduled jobs."""
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled by config")
        return

    # Daily intraday collection at 15:30 Vietnam time
    await scheduler.add_schedule(
        collect_intraday_data_job,
        CronTrigger(
            hour=settings.intraday_collect_hour,
            minute=settings.intraday_collect_minute,
            timezone="Asia/Ho_Chi_Minh",
        ),
        id="intraday-collection-daily",
    )
    logger.info(
        f"Scheduled intraday collection at "
        f"{settings.intraday_collect_hour}:{settings.intraday_collect_minute:02d}"
    )

    # Daily cleanup at 16:00
    await scheduler.add_schedule(
        cleanup_old_data_job,
        CronTrigger(hour=16, minute=0, timezone="Asia/Ho_Chi_Minh"),
        id="data-cleanup-daily",
    )
    logger.info("Scheduled data cleanup at 16:00")
```

### Step 5: Update main.py

```python
# apps/api/src/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler import AsyncScheduler
from src.core.database import engine
from src.core.scheduler import setup_scheduler
from src.core.config import get_settings

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if settings.scheduler_enabled:
        async with AsyncScheduler() as scheduler:
            await setup_scheduler(scheduler)
            await scheduler.start_in_background()
            yield
    else:
        yield

    # Shutdown
    await engine.dispose()

app = FastAPI(
    title="Stock Massive API",
    lifespan=lifespan,
)
```

## Todo List

- [ ] Add apscheduler to requirements.txt
- [ ] Add scheduler settings to config.py
- [ ] Create `apps/api/src/stocks/jobs.py`
- [ ] Create `apps/api/src/core/scheduler.py`
- [ ] Update main.py with scheduler lifespan
- [ ] Test scheduler starts on app launch
- [ ] Verify job executes at scheduled time

## Success Criteria

- [ ] Scheduler starts with app
- [ ] Jobs registered with correct schedule
- [ ] Collection job runs at 15:30
- [ ] Cleanup job removes old data
- [ ] Scheduler disabled via config works

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Job fails silently | Medium | Medium | Add logging, error handling |
| Timezone issues | Medium | High | Explicitly set Asia/Ho_Chi_Minh |
| App restart loses jobs | Low | Low | Jobs re-registered on startup |

## Security Considerations

- Scheduler settings from environment variables
- No external triggers (internal cron only)
- Limit symbols to prevent resource exhaustion

## Next Steps

After completion:
- Monitor job execution in logs
- Consider adding job persistence with SQLAlchemyDataStore
- Add admin endpoint to view job status
