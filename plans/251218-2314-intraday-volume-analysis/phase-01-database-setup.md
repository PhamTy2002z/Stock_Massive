# Phase 01: Database Setup

**Parent Plan:** [plan.md](plan.md)
**Dependencies:** None
**Docs:** [SQLAlchemy Async Research](research/researcher-01-sqlalchemy-async.md)

## Overview

| Field | Value |
|-------|-------|
| Date | 2024-12-18 |
| Priority | High |
| Implementation Status | Pending |
| Review Status | Pending |

**Description:** Set up async SQLAlchemy database layer with PostgreSQL, create StockIntradayBar model, configure Alembic migrations.

## Key Insights

- Project has SQLAlchemy 2.0 + asyncpg in requirements but no database.py or models
- Config already has `database_url` in `apps/api/src/core/config.py`
- Alembic configured but no migrations exist yet
- Use `expire_on_commit=False` for async sessions

## Requirements

1. Create async database engine and session factory
2. Create StockIntradayBar SQLAlchemy model
3. Configure Alembic env.py for async migrations
4. Generate and run initial migration

## Architecture

```
apps/api/src/
├── core/
│   ├── config.py          # Existing - has database_url
│   └── database.py        # NEW - async engine, session
├── stocks/
│   ├── models.py          # NEW - StockIntradayBar
│   ├── service.py         # Existing
│   └── schemas.py         # Existing
└── main.py                # Update - add lifespan for DB
```

## Related Code Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/src/core/database.py` | Create | Async engine, session factory, get_db dependency |
| `apps/api/src/stocks/models.py` | Create | StockIntradayBar ORM model |
| `apps/api/alembic/env.py` | Update | Configure async migrations |
| `apps/api/src/main.py` | Update | Add lifespan for engine disposal |

## Implementation Steps

### Step 1: Create database.py

```python
# apps/api/src/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
from src.core.config import get_settings

settings = get_settings()

# Convert postgresql:// to postgresql+asyncpg://
DATABASE_URL = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

### Step 2: Create StockIntradayBar model

```python
# apps/api/src/stocks/models.py
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, Integer, UniqueConstraint, Index
from sqlalchemy.sql import func
from src.core.database import Base

class StockIntradayBar(Base):
    __tablename__ = "stock_intraday_bars"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, index=True)
    bar_time = Column(DateTime, nullable=False)
    open_price = Column(Numeric(12, 2))
    high_price = Column(Numeric(12, 2))
    low_price = Column(Numeric(12, 2))
    close_price = Column(Numeric(12, 2))
    volume = Column(BigInteger, nullable=False)
    trade_value = Column(Numeric(18, 2))
    trade_count = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('symbol', 'bar_time', name='uq_symbol_bar_time'),
        Index('idx_intraday_symbol_date', 'symbol', func.date('bar_time')),
    )
```

### Step 3: Update Alembic env.py

Key changes:
- Import async engine from database.py
- Use `run_async_migrations()` pattern
- Import models to register with Base.metadata

### Step 4: Generate migration

```bash
cd apps/api
alembic revision --autogenerate -m "create stock_intraday_bars table"
alembic upgrade head
```

### Step 5: Update main.py lifespan

```python
from contextlib import asynccontextmanager
from src.core.database import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
```

## Todo List

- [ ] Create `apps/api/src/core/database.py`
- [ ] Create `apps/api/src/stocks/models.py`
- [ ] Update `apps/api/alembic/env.py` for async
- [ ] Generate migration with alembic
- [ ] Run migration
- [ ] Update `apps/api/src/main.py` with lifespan
- [ ] Test database connection

## Success Criteria

- [ ] `alembic upgrade head` runs without errors
- [ ] `stock_intraday_bars` table exists in PostgreSQL
- [ ] Async session can be injected into routes
- [ ] Engine disposed on app shutdown

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| DB connection fails | Low | High | Verify DATABASE_URL, test locally |
| Migration conflicts | Low | Medium | Start fresh, no existing migrations |

## Security Considerations

- Database URL from environment variable (not hardcoded)
- Use parameterized queries via SQLAlchemy ORM
- Connection pooling prevents resource exhaustion

## Next Steps

After completion, proceed to [Phase 02: Data Collection Service](phase-02-data-collection-service.md)
