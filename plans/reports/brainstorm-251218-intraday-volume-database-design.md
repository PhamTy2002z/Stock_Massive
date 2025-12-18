# Brainstorm: Intraday Volume Analysis Database Design

**Date:** 2024-12-18
**Topic:** Historical intraday data storage for volume analysis (9:00-15:00)

---

## Problem Statement

User wants to:
1. Retrieve 10 days of historical trading data for a stock
2. Analyze trading volume by time period within trading session (9:00-15:00)
3. Identify peak volume periods
4. Store data in scalable, maintainable, secure database

---

## vnstock Data Availability

### What vnstock Provides

| Method | Data Type | Interval Support | Historical Range |
|--------|-----------|------------------|------------------|
| `quote.history()` | OHLCV | 1m, 5m, 1H, 1D, 1W, 1M | Limited for minute data |
| `quote.intraday()` | Tick-by-tick | Real-time ticks | **Current day only** |

### Key Limitation
- **Minute-level historical data** (1m, 5m) typically limited to ~30 days max
- **Intraday tick data** only available for current trading day
- For 10-day 5-min analysis: **Must collect daily and aggregate**

### Recommended Approach
```python
# Option A: Use 5-min interval history (if available)
quote.history(start='2024-12-08', end='2024-12-18', interval='5m')

# Option B: Collect intraday ticks daily, aggregate to 5-min buckets
quote.intraday()  # Run daily, store, then aggregate
```

---

## Database Schema Design

### Approach Comparison

| Approach | Pros | Cons |
|----------|------|------|
| **A: Store raw ticks** | Maximum flexibility, can re-aggregate | High storage, complex queries |
| **B: Store 5-min OHLCV** | Efficient storage, fast queries | Less flexible |
| **C: Hybrid** | Best of both | More complexity |

### Recommended: Option B (5-min OHLCV)

Rationale: KISS principle - store what you need for analysis.

### Schema Design

```sql
-- Core table: 5-minute OHLCV bars
CREATE TABLE stock_intraday_bars (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    bar_time TIMESTAMP NOT NULL,  -- Start of 5-min bar
    open_price DECIMAL(12,2),
    high_price DECIMAL(12,2),
    low_price DECIMAL(12,2),
    close_price DECIMAL(12,2),
    volume BIGINT NOT NULL,
    trade_value DECIMAL(18,2),    -- VND value
    trade_count INTEGER,          -- Number of trades in bar
    created_at TIMESTAMP DEFAULT NOW(),

    -- Composite unique constraint
    CONSTRAINT uq_symbol_bar_time UNIQUE (symbol, bar_time)
);

-- Indexes for common queries
CREATE INDEX idx_intraday_symbol ON stock_intraday_bars(symbol);
CREATE INDEX idx_intraday_bar_time ON stock_intraday_bars(bar_time);
CREATE INDEX idx_intraday_symbol_date ON stock_intraday_bars(symbol, DATE(bar_time));

-- Partitioning by month (for scalability)
-- Consider later when data grows
```

### SQLAlchemy Model

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
        Index('idx_intraday_symbol_date', symbol, func.date(bar_time)),
    )
```

---

## Data Collection Strategy

### Option 1: Daily Scheduled Job (Recommended)
```
Schedule: Run at 15:30 daily (after market close)
Process:
1. Fetch intraday ticks via quote.intraday()
2. Aggregate to 5-min bars
3. Upsert to database
4. Retain last N days (configurable)
```

### Option 2: Real-time Collection
- More complex, requires background worker
- Overkill for 10-day analysis use case

### Aggregation Logic
```python
def aggregate_ticks_to_bars(ticks_df, interval_minutes=5):
    """Aggregate tick data to OHLCV bars."""
    ticks_df['bar_time'] = ticks_df['time'].dt.floor(f'{interval_minutes}min')

    bars = ticks_df.groupby('bar_time').agg({
        'price': ['first', 'max', 'min', 'last'],
        'volume': 'sum',
        'accumulated_val': lambda x: x.iloc[-1] - x.iloc[0] if len(x) > 1 else x.iloc[0]
    }).reset_index()

    return bars
```

---

## Volume Analysis Query

```sql
-- Find peak volume periods across 10 days
SELECT
    EXTRACT(HOUR FROM bar_time) AS hour,
    (EXTRACT(MINUTE FROM bar_time)::int / 5) * 5 AS minute_bucket,
    AVG(volume) AS avg_volume,
    SUM(volume) AS total_volume,
    COUNT(*) AS sample_count
FROM stock_intraday_bars
WHERE symbol = 'VCB'
  AND bar_time >= NOW() - INTERVAL '10 days'
  AND EXTRACT(HOUR FROM bar_time) BETWEEN 9 AND 14
GROUP BY hour, minute_bucket
ORDER BY avg_volume DESC;
```

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| SQL Injection | Use SQLAlchemy ORM, parameterized queries |
| Data validation | Pydantic schemas for input validation |
| Access control | API authentication (future: JWT) |
| Connection security | SSL/TLS for PostgreSQL connection |
| Sensitive data | No PII in this table; financial data is public |

### Environment Variables
```bash
# .env
DATABASE_URL=postgresql://user:password@host:5432/stockmassive
# Use secrets manager in production
```

---

## Scalability Considerations

### Current Scale (10 days, single stock)
- ~72 bars/day (6 hours * 12 bars/hour)
- ~720 rows for 10 days
- **Trivial** - no optimization needed

### Future Scale (1000 stocks, 1 year)
- ~26M rows/year
- Consider:
  - Table partitioning by month
  - TimescaleDB extension
  - Data retention policy (archive old data)

### Recommended: Start Simple
- Single table, basic indexes
- Add partitioning when data exceeds 10M rows
- Monitor query performance

---

## Implementation Phases

### Phase 1: Database Setup
- [ ] Create `database.py` with engine/session
- [ ] Create `models.py` with StockIntradayBar
- [ ] Configure Alembic env.py
- [ ] Run initial migration

### Phase 2: Data Collection Service
- [ ] Create intraday data collector
- [ ] Implement tick-to-bar aggregation
- [ ] Add upsert logic (handle duplicates)

### Phase 3: Analysis API
- [ ] Endpoint: GET /stocks/{symbol}/volume-analysis
- [ ] Query parameters: days, interval
- [ ] Return peak volume periods

### Phase 4: Scheduled Job (Optional)
- [ ] Celery or APScheduler for daily collection
- [ ] Data retention cleanup

---

## Final Recommendation

**Start with Option B (5-min OHLCV storage)** because:
1. Matches your analysis requirement exactly
2. Minimal storage overhead
3. Fast queries for volume analysis
4. Easy to extend later

**Test vnstock first:**
```python
from vnstock import Quote
quote = Quote(symbol='VCB', source='VCI')
# Test if 5-min historical works
df = quote.history(start='2024-12-08', end='2024-12-18', interval='5m')
print(df.shape, df.head())
```

If 5-min history unavailable for 10 days, implement daily tick collection.

---

## Unresolved Questions

1. **vnstock 5-min limit**: Need to test actual API limit for minute-level historical data
2. **Data source reliability**: VCI vs TCBS - which has better intraday data?
3. **Authentication**: Will this data be public or require user login?
4. **Retention policy**: How long to keep historical intraday data?
