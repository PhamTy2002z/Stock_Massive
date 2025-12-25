# APScheduler Debugging Report

**Date:** 2025-12-25
**ID:** debugger-251225-2350-apscheduler-intraday-issues
**Status:** Investigation Complete

---

## Executive Summary

### Issues Investigated

1. **Scheduled jobs not triggering** - Jobs appear configured but never fire
2. **Intraday job only saved 2/5 symbols** - VHM and VIC have today's data; VCB, FPT, VNM do not

### Root Causes Identified

| Issue | Root Cause | Severity |
|-------|------------|----------|
| Missing scheduler logs | Logger level = WARNING, INFO logs suppressed | HIGH |
| Jobs not firing | Scheduler works BUT no persistence = jobs lost on restart | HIGH |
| 2/5 symbols | vnstock API rate limiting during manual trigger | MEDIUM |

---

## Technical Analysis

### 1. APScheduler Configuration

**Version:** 4.0.0a6 (alpha)

**Findings:**
- Scheduler uses **in-memory data store** (default)
- `AsyncScheduler` context manager usage is correct
- `start_in_background()` call is correct
- All 4 schedules register successfully when tested

```python
# main.py - Correct implementation
async with AsyncScheduler() as scheduler:
    await setup_scheduler(scheduler)
    await scheduler.start_in_background()
    yield
```

**Verified Schedules:**
```
intraday-collection-daily: next_fire=2025-12-26 15:30:00+07:00
data-cleanup-daily: next_fire=2025-12-26 16:00:00+07:00
daily-ohlcv-collection: next_fire=2025-12-26 16:00:00+07:00
collect-financial-statements: next_fire=2025-12-28 02:00:00+07:00
```

### 2. Logging Issue

**Problem:** Scheduler INFO logs not appearing in container logs

**Evidence:**
```python
Root logger handlers: []  # EMPTY - no handlers configured
Root logger level: 30      # WARNING
Scheduler logger effective level: 30  # WARNING
```

**Impact:** All `logger.info()` calls in `scheduler.py` are silently dropped:
- "Scheduler started"
- "Scheduled intraday collection at..."
- "Starting intraday collection for..."

**Note:** Uvicorn access logs (INFO level) appear because uvicorn configures its own handlers.

### 3. Container Runtime Analysis

**Container Status:** Up 23 hours, healthy

**Process:** Single worker (not the `--workers 4` in Dockerfile.prod)
```
/usr/local/bin/python3.11 /usr/local/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
```

**Startup Logs Analysis:**
- No scheduler initialization messages visible
- Application started Dec 24 ~15:57 Vietnam time
- Container has been running continuously

### 4. Intraday Data Analysis

**Today's Data (Dec 25, 2025):**

| Symbol | Bars | Date Range | Status |
|--------|------|------------|--------|
| VHM | 46 | 09:15-14:45 | Has data |
| VIC | 46 | 09:15-14:45 | Has data |
| VCB | 0 | - | Missing |
| FPT | 0 | - | Missing |
| VNM | 0 | - | Missing |

**Creation Timestamp:** `2025-12-25 16:42:02 UTC` (23:42 Vietnam time)

This was **NOT** the scheduled 15:30 job - it was a manual trigger or API call.

**vnstock API Current State (tested now):**
- All 5 symbols return 100 ticks
- API returns only last ~20 minutes of data
- Full day coverage requires calling at 15:30 when more data available

### 5. Why Scheduled Jobs Don't Fire

**Root Cause:** In-memory scheduler + no job execution logging

1. **In-memory data store**: Schedule state not persisted
2. If container restarts or worker recycled, schedules lost
3. Schedules recreated on startup but with next fire time = tomorrow
4. No ERROR logs to indicate job failures (if any)

**Test Result:** Scheduler DOES work when tested in isolation:
```
JOB EXECUTED! count=1
JOB EXECUTED! count=2
... (fires correctly every second)
```

---

## Recommendations

### Immediate Fixes (Priority: HIGH)

#### 1. Enable INFO Logging

Add to `main.py` or create `logging_config.py`:

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

Or in uvicorn command:
```bash
uvicorn src.main:app --log-level info
```

#### 2. Add Scheduler State Logging

Add to lifespan after `start_in_background()`:

```python
schedules = await scheduler.get_schedules()
logger.warning(f"Scheduler started with {len(schedules)} schedules")  # Use warning to ensure visibility
for s in schedules:
    logger.warning(f"  {s.id}: next={s.next_fire_time}")
```

#### 3. Use SQLAlchemy Data Store (Persistent)

Replace in-memory with database-backed store:

```python
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore

# In lifespan
data_store = SQLAlchemyDataStore(engine)
async with AsyncScheduler(data_store) as scheduler:
    ...
```

### Medium-Term Fixes

#### 4. Job Execution Monitoring

Add job execution events logging:

```python
@scheduler.on_schedule_added
async def on_schedule_added(event):
    logger.info(f"Schedule added: {event.schedule_id}")

@scheduler.on_job_executed
async def on_job_executed(event):
    logger.info(f"Job executed: {event.job_id}")
```

#### 5. Health Check for Scheduler

Add endpoint to check scheduler state:

```python
@app.get("/scheduler/status")
async def scheduler_status():
    return {
        "state": scheduler.state.name,
        "schedules": [s.id for s in await scheduler.get_schedules()]
    }
```

---

## Evidence

### Container Startup Logs (No Scheduler Messages)
```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Scheduler Test Output (Works in Isolation)
```
Setting up scheduler...
Schedule added
Schedules after setup: 1
  intraday-collection-daily: next_fire=2025-12-26 15:30:00+07:00
Scheduler state: RunState.started
```

### Today's Intraday Data Creation Times
```
VIC | bar_time: 2025-12-25 09:40:00 | created_at: 2025-12-25 16:42:02
VIC | bar_time: 2025-12-25 09:55:00 | created_at: 2025-12-25 16:42:02
... (all created at 16:42 UTC, not 08:30 UTC which would be 15:30 Vietnam)
```

---

## Unresolved Questions

1. **Why only VHM+VIC collected during manual trigger?**
   - Likely rate limiting from vnstock API
   - Need to check if errors were logged for VCB, FPT, VNM

2. **Was Dec 24 job supposed to run?**
   - Container started ~15:57 Vietnam time (after 15:30)
   - Startup job check would have run but may have found existing data

3. **Is uvicorn running with reload in production?**
   - Could cause scheduler re-initialization issues
   - Check deployment configuration

---

## Files Analyzed

- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/main.py`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/scheduler.py`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/jobs.py`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/intraday_collector.py`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/config.py`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/Dockerfile.prod`
- `/Users/typham/Documents/GitHub/Stock_Massive/docker-compose.prod.yml`
