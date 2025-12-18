# Phase 02: Data Collection Service

**Parent Plan:** [plan.md](plan.md)
**Dependencies:** [Phase 01](phase-01-database-setup.md)
**Docs:** [Brainstorm Report](../reports/brainstorm-251218-intraday-volume-database-design.md)

## Overview

| Field | Value |
|-------|-------|
| Date | 2024-12-18 |
| Priority | High |
| Implementation Status | Pending |
| Review Status | Pending |

**Description:** Create service to collect intraday tick data from vnstock, aggregate to 5-minute OHLCV bars, and upsert to database.

## Key Insights

- vnstock `quote.intraday()` returns tick data for current day only
- Need to aggregate ticks to 5-min bars using pandas
- Use PostgreSQL upsert (ON CONFLICT DO UPDATE) for idempotency
- Existing StockService in `service.py` already has `get_intraday()` method

## Requirements

1. Create IntradayCollector service class
2. Implement tick-to-bar aggregation (5-min buckets)
3. Add upsert logic for database persistence
4. Support batch collection for multiple symbols

## Architecture

```
IntradayCollector
├── collect_symbol(symbol) -> list[StockIntradayBar]
│   ├── Fetch ticks via StockService.get_intraday()
│   ├── Aggregate to 5-min bars
│   └── Return bar objects
├── save_bars(bars) -> int
│   └── Upsert to database
└── collect_and_save(symbols) -> dict
    └── Orchestrate collection for multiple symbols
```

## Related Code Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/src/stocks/intraday_collector.py` | Create | Collection + aggregation service |
| `apps/api/src/stocks/schemas.py` | Update | Add IntradayBar schema |
| `apps/api/src/stocks/service.py` | Reference | Use existing get_intraday() |

## Implementation Steps

### Step 1: Add Pydantic schema

```python
# Add to apps/api/src/stocks/schemas.py
class IntradayBarCreate(BaseModel):
    symbol: str
    bar_time: datetime
    open_price: float | None
    high_price: float | None
    low_price: float | None
    close_price: float | None
    volume: int
    trade_value: float | None = None
    trade_count: int | None = None

class IntradayBar(IntradayBarCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
```

### Step 2: Create IntradayCollector service

```python
# apps/api/src/stocks/intraday_collector.py
import pandas as pd
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from src.stocks.service import get_stock_service
from src.stocks.models import StockIntradayBar

class IntradayCollector:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stock_service = get_stock_service()

    def aggregate_ticks_to_bars(self, ticks: list, interval_minutes: int = 5) -> list[dict]:
        """Aggregate tick data to OHLCV bars."""
        if not ticks:
            return []

        df = pd.DataFrame([t.model_dump() for t in ticks])
        df['bar_time'] = pd.to_datetime(df['time']).dt.floor(f'{interval_minutes}min')

        bars = df.groupby('bar_time').agg({
            'price': ['first', 'max', 'min', 'last'],
            'volume': 'sum',
            'accumulated_val': lambda x: x.iloc[-1] - x.iloc[0] if len(x) > 1 else 0
        }).reset_index()

        bars.columns = ['bar_time', 'open_price', 'high_price', 'low_price', 'close_price', 'volume', 'trade_value']
        bars['trade_count'] = df.groupby('bar_time').size().values

        return bars.to_dict('records')

    async def collect_symbol(self, symbol: str) -> list[dict]:
        """Collect and aggregate intraday data for a symbol."""
        ticks = self.stock_service.get_intraday(symbol)
        bars = self.aggregate_ticks_to_bars(ticks)
        for bar in bars:
            bar['symbol'] = symbol.upper()
        return bars

    async def save_bars(self, bars: list[dict]) -> int:
        """Upsert bars to database. Returns count of affected rows."""
        if not bars:
            return 0

        stmt = insert(StockIntradayBar).values(bars)
        stmt = stmt.on_conflict_do_update(
            index_elements=['symbol', 'bar_time'],
            set_={
                'open_price': stmt.excluded.open_price,
                'high_price': stmt.excluded.high_price,
                'low_price': stmt.excluded.low_price,
                'close_price': stmt.excluded.close_price,
                'volume': stmt.excluded.volume,
                'trade_value': stmt.excluded.trade_value,
                'trade_count': stmt.excluded.trade_count,
            }
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def collect_and_save(self, symbols: list[str]) -> dict:
        """Collect and save data for multiple symbols."""
        results = {'success': [], 'failed': [], 'total_bars': 0}

        for symbol in symbols:
            try:
                bars = await self.collect_symbol(symbol)
                count = await self.save_bars(bars)
                results['success'].append(symbol)
                results['total_bars'] += count
            except Exception as e:
                results['failed'].append({'symbol': symbol, 'error': str(e)})

        return results
```

### Step 3: Add manual trigger endpoint (for testing)

```python
# Add to apps/api/src/stocks/router.py
@router.post("/intraday/collect")
async def collect_intraday_data(
    symbols: list[str] = Query(default=["VCB", "FPT", "VNM"]),
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger intraday data collection."""
    collector = IntradayCollector(db)
    result = await collector.collect_and_save(symbols)
    return result
```

## Todo List

- [ ] Add IntradayBar schemas to `schemas.py`
- [ ] Create `apps/api/src/stocks/intraday_collector.py`
- [ ] Add manual collection endpoint to router
- [ ] Test aggregation logic with sample data
- [ ] Test upsert with duplicate data
- [ ] Verify data in database

## Success Criteria

- [ ] Tick data aggregates correctly to 5-min bars
- [ ] Bars upserted without duplicates
- [ ] Manual endpoint returns success for test symbols
- [ ] Data visible in PostgreSQL

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| vnstock rate limit | Medium | Medium | Add delay between symbols |
| Empty tick data | Medium | Low | Handle gracefully, skip symbol |
| Aggregation errors | Low | Medium | Unit test aggregation logic |

## Security Considerations

- Validate symbol input (existing validation in service.py)
- Use parameterized queries via SQLAlchemy
- Limit symbols per request to prevent abuse

## Next Steps

After completion, proceed to [Phase 03: Volume Analysis API](phase-03-volume-analysis-api.md)
