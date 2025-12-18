# APScheduler 4.x + FastAPI Integration Research

## Overview
APScheduler 4.x provides native async support via `AsyncScheduler`, integrating seamlessly with FastAPI's lifespan context manager.

## 1. FastAPI Lifespan Setup

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler: AsyncScheduler | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    scheduler = AsyncScheduler()
    async with scheduler:
        # Add schedules here
        await scheduler.add_schedule(
            daily_task,
            CronTrigger(hour=15, minute=30),
            id="daily-1530"
        )
        await scheduler.start_in_background()
        yield
    # Cleanup automatic on context exit

app = FastAPI(lifespan=lifespan)
```

## 2. Cron-Style Scheduling (Daily at 15:30)

```python
from apscheduler.triggers.cron import CronTrigger

# Daily at 15:30
trigger = CronTrigger(hour=15, minute=30)

# Weekdays only at 15:30
trigger = CronTrigger(day_of_week="mon-fri", hour=15, minute=30)

# With timezone
trigger = CronTrigger(hour=15, minute=30, timezone="Asia/Ho_Chi_Minh")

# CronTrigger params: year, month, day, week, day_of_week, hour, minute, second
# day_of_week: 0-6 (mon-sun) or names: mon,tue,wed,thu,fri,sat,sun
```

### Combining Triggers
```python
from apscheduler.triggers.combining import OrTrigger

# Different times for weekdays vs weekends
trigger = OrTrigger(
    CronTrigger(day_of_week="mon-fri", hour=15, minute=30),
    CronTrigger(day_of_week="sat-sun", hour=11, minute=0),
)
```

## 3. Async Job Execution

```python
async def fetch_intraday_volume():
    """Async job - runs in scheduler's task group."""
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        # Process data...

# Register with scheduler
await scheduler.add_schedule(
    fetch_intraday_volume,
    CronTrigger(hour=15, minute=30),
    id="intraday-volume-fetch",
    misfire_grace_time=300,  # 5 min grace period
    coalesce=CoalescePolicy.latest,  # If missed, run latest only
)
```

### Job with Arguments
```python
async def process_symbol(symbol: str, date: str):
    pass

await scheduler.add_schedule(
    process_symbol,
    CronTrigger(hour=15, minute=30),
    id="process-VN30",
    args=["VN30"],
    kwargs={"date": "today"},
)
```

## 4. Job Persistence & Recovery (SQLAlchemy)

```python
from sqlalchemy.ext.asyncio import create_async_engine
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.eventbrokers.asyncpg import AsyncpgEventBroker

# PostgreSQL persistence
engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")
data_store = SQLAlchemyDataStore(engine)
event_broker = AsyncpgEventBroker.from_async_sqla_engine(engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncScheduler(data_store, event_broker)
    async with scheduler:
        await scheduler.add_schedule(
            daily_task,
            CronTrigger(hour=15, minute=30),
            id="daily-task",
            conflict_policy=ConflictPolicy.replace,  # Update if exists
        )
        await scheduler.start_in_background()
        yield

app = FastAPI(lifespan=lifespan)
```

### Key Persistence Features
- **Auto-recovery**: Jobs survive app restarts
- **Distributed**: Multiple workers share same schedule via DB
- **Conflict handling**: `ConflictPolicy.replace`, `do_nothing`, `exception`
- **Event brokers**: PostgreSQL (asyncpg), Redis, MQTT

## 5. Complete Example

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.abc import ConflictPolicy

DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/stockdb"

async def fetch_intraday_data():
    """Daily 15:30 job to fetch intraday volume data."""
    print("Fetching intraday data...")

@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(DATABASE_URL)
    data_store = SQLAlchemyDataStore(engine)

    async with AsyncScheduler(data_store) as scheduler:
        await scheduler.add_schedule(
            fetch_intraday_data,
            CronTrigger(hour=15, minute=30, timezone="Asia/Ho_Chi_Minh"),
            id="intraday-volume-daily",
            conflict_policy=ConflictPolicy.replace,
        )
        await scheduler.start_in_background()
        yield

app = FastAPI(lifespan=lifespan)
```

## Summary

| Feature | Implementation |
|---------|---------------|
| Lifespan | `@asynccontextmanager` + `async with scheduler` |
| Cron | `CronTrigger(hour=15, minute=30)` |
| Async jobs | Native async functions supported |
| Persistence | `SQLAlchemyDataStore` + PostgreSQL |
| Recovery | Automatic on restart with datastore |

## Unresolved Questions
- None for basic integration; advanced clustering may need Redis event broker testing.
