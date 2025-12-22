# Phase 1: Database & Models

## Context

- **Parent Plan:** [plan.md](./plan.md)
- **Dependencies:** None
- **Docs:** [code-standards.md](../../docs/code-standards.md), [system-architecture.md](../../docs/system-architecture.md)

## Overview

- **Priority:** P1
- **Effort:** 1.5h
- **Status:** Pending
- **Description:** Create SQLAlchemy model and Alembic migration for storing top performers data

## Key Insights

- Follow existing `StockDailyOHLCV` pattern with unique constraint for idempotent upserts
- Use `BIGINT` for profit/revenue (VND values can be very large)
- Include `exchange` column for filtering HOSE/HNX
- Add indexes for common query patterns (rank, period, exchange)

## Requirements

### Functional
- Store quarterly financial metrics per symbol
- Support upsert operations (ON CONFLICT DO UPDATE)
- Query by period (year, quarter) and exchange

### Non-Functional
- Index for fast rank-ordered queries
- Constraint prevents duplicate entries per symbol/period

## Architecture

```sql
top_performers
├── id (PK, SERIAL)
├── symbol (VARCHAR 10, NOT NULL)
├── company_name (VARCHAR 255)
├── exchange (VARCHAR 10) -- HOSE/HNX
├── year (INT, NOT NULL)
├── quarter (INT, NOT NULL)
├── net_profit (BIGINT) -- VND
├── revenue (BIGINT) -- VND
├── profit_margin (FLOAT) -- %
├── eps (FLOAT)
├── rank (INT) -- computed ranking
├── created_at (TIMESTAMP)
├── updated_at (TIMESTAMP)
└── UNIQUE(symbol, year, quarter)
```

## Related Code Files

### Create
- `apps/api/src/stocks/models.py` (modify - add TopPerformer model)
- `apps/api/alembic/versions/xxxx_add_top_performers_table.py` (new migration)

### Modify
- None

## Implementation Steps

1. **Add SQLAlchemy Model** in `apps/api/src/stocks/models.py`:
```python
class TopPerformer(Base):
    __tablename__ = "top_performers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, index=True)
    company_name = Column(String(255))
    exchange = Column(String(10))  # HOSE, HNX
    year = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)
    net_profit = Column(BigInteger)  # VND
    revenue = Column(BigInteger)  # VND
    profit_margin = Column(Float)  # percentage
    eps = Column(Float)
    rank = Column(Integer, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('symbol', 'year', 'quarter', name='uq_top_performers_symbol_period'),
        Index('ix_top_performers_period', 'year', 'quarter'),
        Index('ix_top_performers_exchange', 'exchange'),
    )
```

2. **Generate Alembic Migration**:
```bash
cd apps/api
alembic revision --autogenerate -m "add top_performers table"
```

3. **Verify migration** - check generated file has correct columns/indexes

4. **Apply migration**:
```bash
alembic upgrade head
```

## Todo List

- [ ] Add TopPerformer model to models.py
- [ ] Import BigInteger, func from sqlalchemy
- [ ] Generate Alembic migration
- [ ] Review migration file for correctness
- [ ] Apply migration to database
- [ ] Verify table created with psql

## Success Criteria

- [ ] TopPerformer model exists in models.py
- [ ] Migration applies without errors
- [ ] Table has correct columns and indexes
- [ ] Unique constraint prevents duplicate symbol/period entries

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Migration conflicts with existing | Low | Run on clean DB first |
| Wrong data types | Medium | Review migration before apply |

## Security Considerations

- No user input directly to DB
- All values sanitized via Pydantic schemas

## Next Steps

- Proceed to Phase 2: Scheduled Batch Job
