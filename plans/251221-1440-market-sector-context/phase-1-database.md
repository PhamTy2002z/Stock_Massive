# Phase 1: Database Schema & Models

## Context

- **Plan**: `/plans/251221-1440-market-sector-context/plan.md`
- **Research**: `/plans/251221-1440-market-sector-context/research/researcher-backend-analysis.md`
- **Design**: `/plans/reports/brainstorm-251221-1432-market-sector-context.md` (Section 14)

## Overview

**Description**: Create precomputed database tables for storing daily returns, market metrics, and sector benchmarks. This enables zero-runtime calculation for API responses.

**Priority**: P0 (Blocking for all other phases)

**Status**: ✅ DONE (2025-12-21)

**Effort**: 1 day

## Requirements

### Functional
1. Store daily returns for all stocks and indices
2. Store rolling correlation/beta metrics (5D/20D/60D windows)
3. Store sector benchmarks (market-cap weighted)
4. Support efficient queries by symbol and date range
5. Handle "Unclassified" sector (NULL icb_code)

### Non-Functional
1. Indexed for fast lookups (symbol, date)
2. Composite primary keys to prevent duplicates
3. Numeric precision for financial calculations
4. Alembic migration for version control

## Architecture Decisions

### Table Design

**1. stock_daily_returns**
- Purpose: Store daily price and return calculations
- Granularity: One row per (symbol, date)
- Retention: Indefinite (historical data)

**2. stock_market_metrics**
- Purpose: Store precomputed correlation, beta, RS metrics
- Granularity: One row per (symbol, date)
- Windows: 5D, 20D, 60D rolling calculations

**3. sector_daily_benchmark**
- Purpose: Store sector-level aggregated returns
- Granularity: One row per (icb_code, date)
- Calculation: Market-cap weighted average

### Index Strategy
- Primary: Composite keys (symbol+date, icb_code+date)
- Secondary: Individual symbol/date indexes for range queries
- No full-text search needed

## Related Code Files

**Existing**:
- `/apps/api/src/stocks/models.py` - SQLAlchemy models
- `/apps/api/src/core/database.py` - Database connection
- `/apps/api/alembic/env.py` - Migration environment

**New**:
- `/apps/api/src/stocks/models.py` - Add 3 new models
- `/apps/api/alembic/versions/XXXXXX_add_market_context_tables.py` - Migration

## Implementation Steps

### Step 1: Define SQLAlchemy Models (30 min)

Add to `/apps/api/src/stocks/models.py`:

```python
from sqlalchemy import Column, String, Date, Numeric, Integer, BigInteger, Index
from src.core.database import Base

class StockDailyReturn(Base):
    """Daily returns for stocks and indices."""
    __tablename__ = "stock_daily_returns"

    symbol = Column(String(10), primary_key=True, nullable=False)
    date = Column(Date, primary_key=True, nullable=False)
    close_price = Column(Numeric(12, 2), nullable=False)
    return_1d = Column(Numeric(10, 6), nullable=True)  # Simple return
    return_1d_log = Column(Numeric(10, 6), nullable=True)  # Log return

    __table_args__ = (
        Index('ix_stock_daily_returns_symbol', 'symbol'),
        Index('ix_stock_daily_returns_date', 'date'),
    )

class StockMarketMetric(Base):
    """Precomputed market correlation and beta metrics."""
    __tablename__ = "stock_market_metrics"

    symbol = Column(String(10), primary_key=True, nullable=False)
    date = Column(Date, primary_key=True, nullable=False)

    # vs VNINDEX
    corr_5d = Column(Numeric(6, 4), nullable=True)
    corr_20d = Column(Numeric(6, 4), nullable=True)
    corr_60d = Column(Numeric(6, 4), nullable=True)
    beta_20d = Column(Numeric(8, 4), nullable=True)
    beta_60d = Column(Numeric(8, 4), nullable=True)
    rs_market_20d = Column(Numeric(8, 4), nullable=True)  # Relative strength

    # vs Sector
    corr_sector_20d = Column(Numeric(6, 4), nullable=True)
    rs_sector_20d = Column(Numeric(8, 4), nullable=True)
    sector_rank = Column(Integer, nullable=True)
    sector_total = Column(Integer, nullable=True)

    __table_args__ = (
        Index('ix_stock_market_metrics_symbol', 'symbol'),
        Index('ix_stock_market_metrics_date', 'date'),
    )

class SectorDailyBenchmark(Base):
    """Market-cap weighted sector benchmarks."""
    __tablename__ = "sector_daily_benchmark"

    icb_code = Column(String(10), primary_key=True, nullable=False)
    date = Column(Date, primary_key=True, nullable=False)
    mcap_weighted_return = Column(Numeric(10, 6), nullable=False)
    total_mcap = Column(BigInteger, nullable=False)  # VND
    stock_count = Column(Integer, nullable=False)

    __table_args__ = (
        Index('ix_sector_daily_benchmark_icb_code', 'icb_code'),
        Index('ix_sector_daily_benchmark_date', 'date'),
    )
```

### Step 2: Create Alembic Migration (20 min)

```bash
cd /apps/api
alembic revision --autogenerate -m "add market context tables"
```

Review generated migration file, ensure:
- All 3 tables created
- Indexes applied
- Numeric precision correct

### Step 3: Apply Migration (10 min)

```bash
# Test on local DB
alembic upgrade head

# Verify tables created
psql -d stock_massive -c "\dt stock_*"
psql -d stock_massive -c "\d stock_daily_returns"
```

### Step 4: Add Pydantic Schemas (30 min)

Create `/apps/api/src/stocks/schemas/market_context.py`:

```python
from pydantic import BaseModel, Field
from datetime import date
from typing import Optional

class StockDailyReturnSchema(BaseModel):
    """Daily return data."""
    symbol: str
    date: date
    close_price: float
    return_1d: Optional[float] = None
    return_1d_log: Optional[float] = None

    model_config = {"from_attributes": True}

class StockMarketMetricSchema(BaseModel):
    """Market correlation metrics."""
    symbol: str
    date: date
    corr_5d: Optional[float] = None
    corr_20d: Optional[float] = None
    corr_60d: Optional[float] = None
    beta_20d: Optional[float] = None
    beta_60d: Optional[float] = None
    rs_market_20d: Optional[float] = None
    corr_sector_20d: Optional[float] = None
    rs_sector_20d: Optional[float] = None
    sector_rank: Optional[int] = None
    sector_total: Optional[int] = None

    model_config = {"from_attributes": True}

class SectorDailyBenchmarkSchema(BaseModel):
    """Sector benchmark data."""
    icb_code: str
    date: date
    mcap_weighted_return: float
    total_mcap: int
    stock_count: int

    model_config = {"from_attributes": True}
```

### Step 5: Create Repository Layer (30 min)

Create `/apps/api/src/stocks/market_context_repository.py`:

```python
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from datetime import date
from typing import List, Optional
from .models import StockDailyReturn, StockMarketMetric, SectorDailyBenchmark

class MarketContextRepository:
    """Data access layer for market context tables."""

    def __init__(self, db: Session):
        self.db = db

    # Daily Returns
    def upsert_daily_return(self, symbol: str, date: date, close_price: float,
                           return_1d: Optional[float], return_1d_log: Optional[float]):
        """Insert or update daily return."""
        stmt = select(StockDailyReturn).where(
            and_(StockDailyReturn.symbol == symbol, StockDailyReturn.date == date)
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        if existing:
            existing.close_price = close_price
            existing.return_1d = return_1d
            existing.return_1d_log = return_1d_log
        else:
            new_record = StockDailyReturn(
                symbol=symbol, date=date, close_price=close_price,
                return_1d=return_1d, return_1d_log=return_1d_log
            )
            self.db.add(new_record)

        self.db.commit()

    def get_daily_returns(self, symbol: str, start_date: date, end_date: date) -> List[StockDailyReturn]:
        """Get daily returns for symbol in date range."""
        stmt = select(StockDailyReturn).where(
            and_(
                StockDailyReturn.symbol == symbol,
                StockDailyReturn.date >= start_date,
                StockDailyReturn.date <= end_date
            )
        ).order_by(StockDailyReturn.date)

        return list(self.db.execute(stmt).scalars().all())

    # Market Metrics
    def upsert_market_metric(self, symbol: str, date: date, **metrics):
        """Insert or update market metrics."""
        stmt = select(StockMarketMetric).where(
            and_(StockMarketMetric.symbol == symbol, StockMarketMetric.date == date)
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        if existing:
            for key, value in metrics.items():
                setattr(existing, key, value)
        else:
            new_record = StockMarketMetric(symbol=symbol, date=date, **metrics)
            self.db.add(new_record)

        self.db.commit()

    def get_latest_metric(self, symbol: str) -> Optional[StockMarketMetric]:
        """Get most recent metric for symbol."""
        stmt = select(StockMarketMetric).where(
            StockMarketMetric.symbol == symbol
        ).order_by(StockMarketMetric.date.desc()).limit(1)

        return self.db.execute(stmt).scalar_one_or_none()

    # Sector Benchmarks
    def upsert_sector_benchmark(self, icb_code: str, date: date,
                                mcap_weighted_return: float, total_mcap: int, stock_count: int):
        """Insert or update sector benchmark."""
        stmt = select(SectorDailyBenchmark).where(
            and_(SectorDailyBenchmark.icb_code == icb_code, SectorDailyBenchmark.date == date)
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        if existing:
            existing.mcap_weighted_return = mcap_weighted_return
            existing.total_mcap = total_mcap
            existing.stock_count = stock_count
        else:
            new_record = SectorDailyBenchmark(
                icb_code=icb_code, date=date, mcap_weighted_return=mcap_weighted_return,
                total_mcap=total_mcap, stock_count=stock_count
            )
            self.db.add(new_record)

        self.db.commit()

    def get_sector_benchmark(self, icb_code: str, start_date: date, end_date: date) -> List[SectorDailyBenchmark]:
        """Get sector benchmark for date range."""
        stmt = select(SectorDailyBenchmark).where(
            and_(
                SectorDailyBenchmark.icb_code == icb_code,
                SectorDailyBenchmark.date >= start_date,
                SectorDailyBenchmark.date <= end_date
            )
        ).order_by(SectorDailyBenchmark.date)

        return list(self.db.execute(stmt).scalars().all())
```

### Step 6: Write Unit Tests (1 hour)

Create `/apps/api/tests/test_market_context_repository.py`:

```python
import pytest
from datetime import date
from src.stocks.market_context_repository import MarketContextRepository
from src.stocks.models import StockDailyReturn, StockMarketMetric, SectorDailyBenchmark

def test_upsert_daily_return(db_session):
    """Test inserting and updating daily returns."""
    repo = MarketContextRepository(db_session)

    # Insert
    repo.upsert_daily_return('VCB', date(2025, 1, 1), 100.0, 0.02, 0.0198)
    result = repo.get_daily_returns('VCB', date(2025, 1, 1), date(2025, 1, 1))
    assert len(result) == 1
    assert result[0].return_1d == 0.02

    # Update
    repo.upsert_daily_return('VCB', date(2025, 1, 1), 101.0, 0.03, 0.0296)
    result = repo.get_daily_returns('VCB', date(2025, 1, 1), date(2025, 1, 1))
    assert len(result) == 1
    assert result[0].return_1d == 0.03

def test_get_daily_returns_range(db_session):
    """Test fetching daily returns for date range."""
    repo = MarketContextRepository(db_session)

    # Insert multiple dates
    repo.upsert_daily_return('VCB', date(2025, 1, 1), 100.0, 0.02, 0.0198)
    repo.upsert_daily_return('VCB', date(2025, 1, 2), 102.0, 0.02, 0.0198)
    repo.upsert_daily_return('VCB', date(2025, 1, 3), 104.0, 0.0196, 0.0194)

    result = repo.get_daily_returns('VCB', date(2025, 1, 1), date(2025, 1, 3))
    assert len(result) == 3
    assert result[0].date == date(2025, 1, 1)
    assert result[2].date == date(2025, 1, 3)

def test_upsert_market_metric(db_session):
    """Test inserting market metrics."""
    repo = MarketContextRepository(db_session)

    metrics = {
        'corr_20d': 0.85,
        'beta_20d': 1.2,
        'rs_market_20d': 1.05
    }
    repo.upsert_market_metric('VCB', date(2025, 1, 1), **metrics)

    result = repo.get_latest_metric('VCB')
    assert result.corr_20d == 0.85
    assert result.beta_20d == 1.2

def test_upsert_sector_benchmark(db_session):
    """Test inserting sector benchmarks."""
    repo = MarketContextRepository(db_session)

    repo.upsert_sector_benchmark('8355', date(2025, 1, 1), 0.015, 1000000000000, 27)
    result = repo.get_sector_benchmark('8355', date(2025, 1, 1), date(2025, 1, 1))

    assert len(result) == 1
    assert result[0].mcap_weighted_return == 0.015
    assert result[0].stock_count == 27
```

## Success Criteria

- [ ] All 3 tables created in PostgreSQL
- [ ] Alembic migration runs without errors
- [ ] Indexes applied correctly (verify with `\d` in psql)
- [ ] SQLAlchemy models match table schema
- [ ] Repository methods work (unit tests pass)
- [ ] Pydantic schemas validate correctly
- [ ] No N+1 query issues (use `select` with joins)

## Testing Checklist

- [ ] Migration up/down works
- [ ] Composite primary keys prevent duplicates
- [ ] Indexes improve query performance (use EXPLAIN ANALYZE)
- [ ] Numeric precision preserved (no rounding errors)
- [ ] NULL handling for optional fields
- [ ] Repository upsert logic works (insert + update)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Migration conflicts | High | Review auto-generated migration, test locally first |
| Index performance | Medium | Use EXPLAIN ANALYZE, add covering indexes if needed |
| Numeric precision loss | High | Use Numeric(10,6) for returns, test edge cases |
| Duplicate data | Medium | Composite primary keys, upsert logic |

## Dependencies

- PostgreSQL 16 running
- Alembic configured
- SQLAlchemy 2.0+

## Next Phase

Phase 2: EOD Pipeline - Use these tables to store computed metrics
