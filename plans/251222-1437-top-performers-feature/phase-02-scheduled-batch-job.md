# Phase 2: Scheduled Batch Job

## Context

- **Parent Plan:** [plan.md](./plan.md)
- **Dependencies:** Phase 1 (Database & Models)
- **Docs:** [code-standards.md](../../docs/code-standards.md)
- **Research:** [Scheduled Jobs Pattern](./research/researcher-scheduled-jobs-report.md)

## Overview

- **Priority:** P1
- **Effort:** 2.5h
- **Status:** DONE (2025-12-22)
- **Description:** Create scheduled job to fetch income statements for HOSE+HNX symbols, compute rankings, store in DB

## Key Insights

From research:
- Follow existing `collect_daily_ohlcv_job()` pattern with async wrapper
- Use `Screener().stock(params={"exchangeName": "HOSE,HNX"})` for symbol list
- Rate limit handling: 2s delay, exponential backoff, skip on rate limit
- Upsert pattern with ON CONFLICT DO UPDATE
- Schedule: Weekly at 02:00 ICT (low traffic, financial data rarely changes)

## Requirements

### Functional
- Fetch all HOSE+HNX symbols (~700-800)
- For each symbol: get latest quarterly income statement
- Extract: net_profit, revenue, eps
- Calculate: profit_margin = net_profit / revenue * 100
- Rank by net_profit descending
- Store/update in top_performers table

### Non-Functional
- Complete within 1 hour
- Handle rate limits gracefully
- Resume capability (track progress)
- Detailed logging

## Architecture

```
collect_top_performers_job() [async]
    │
    ├── 1. Get symbols via Screener(HOSE,HNX)
    │
    ├── 2. For each symbol (with delay):
    │       ├── Fetch income_statement(period='quarter')
    │       ├── Extract latest quarter data
    │       └── Collect results
    │
    ├── 3. Sort by net_profit, assign ranks
    │
    └── 4. Bulk upsert to top_performers table
```

## Related Code Files

### Create
- `apps/api/src/stocks/top_performers_collector.py` (new - main logic)

### Modify
- `apps/api/src/stocks/jobs.py` (add job function)
- `apps/api/src/core/scheduler.py` (register job)
- `apps/api/src/core/config.py` (add settings)

## Implementation Steps

### Step 1: Add Config Settings

In `apps/api/src/core/config.py`:
```python
# Top Performers Job
TOP_PERFORMERS_ENABLED: bool = True
TOP_PERFORMERS_HOUR: int = 2  # 02:00 ICT
TOP_PERFORMERS_MINUTE: int = 0
TOP_PERFORMERS_DELAY: float = 1.5  # seconds between API calls
```

### Step 2: Create Collector Class

Create `apps/api/src/stocks/top_performers_collector.py`:

```python
"""Top performers data collector - fetches quarterly financials for HOSE+HNX."""

import logging
import time
from datetime import datetime
from typing import Optional

from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncSession
from vnstock import Screener, Finance

from src.core.vnstock_wrapper import safe_vnstock_call, get_adaptive_delay, VnstockRateLimitError
from src.stocks.models import TopPerformer

logger = logging.getLogger(__name__)


class TopPerformersCollector:
    """Collects quarterly financial data for top performers ranking."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.base_delay = 1.5

    async def collect(self) -> dict:
        """Main collection method. Returns summary dict."""
        start_time = time.time()

        # 1. Get HOSE+HNX symbols
        symbols_data = self._get_symbols()
        if not symbols_data:
            return {"success": 0, "failed": 0, "error": "Failed to fetch symbols"}

        logger.info(f"Fetching financials for {len(symbols_data)} symbols")

        # 2. Collect financial data
        results = []
        failed = 0
        rate_limited = 0

        for i, row in enumerate(symbols_data):
            symbol = row['symbol']
            exchange = row.get('exchange', 'UNKNOWN')
            company_name = row.get('short_name', row.get('organ_name', ''))

            try:
                data = self._get_quarterly_financials(symbol)
                if data:
                    data['symbol'] = symbol
                    data['exchange'] = exchange
                    data['company_name'] = company_name
                    results.append(data)
                else:
                    failed += 1

            except VnstockRateLimitError:
                rate_limited += 1
                logger.warning(f"Rate limited on {symbol}, skipping")

            except Exception as e:
                failed += 1
                logger.debug(f"Error for {symbol}: {e}")

            # Progress log every 50 symbols
            if (i + 1) % 50 == 0:
                logger.info(f"Progress: {i+1}/{len(symbols_data)} symbols processed")

            # Delay between calls
            delay = get_adaptive_delay(self.base_delay)
            time.sleep(delay)

        # 3. Rank by net_profit
        results.sort(key=lambda x: x.get('net_profit') or 0, reverse=True)
        for rank, item in enumerate(results, 1):
            item['rank'] = rank

        # 4. Store in database
        stored = await self._store_results(results)

        elapsed = time.time() - start_time
        logger.info(f"Collection complete: {stored} stored, {failed} failed, {rate_limited} rate limited in {elapsed:.1f}s")

        return {
            "success": stored,
            "failed": failed,
            "rate_limited": rate_limited,
            "total_symbols": len(symbols_data),
            "elapsed_seconds": round(elapsed, 1)
        }

    def _get_symbols(self) -> list:
        """Get HOSE+HNX symbols via Screener."""
        def _fetch():
            screener = Screener(source="tcbs")
            df = screener.stock(params={"exchangeName": "HOSE,HNX"}, limit=1000)
            return df.to_dict('records')

        try:
            return safe_vnstock_call(_fetch, max_retries=3) or []
        except Exception as e:
            logger.error(f"Failed to fetch symbols: {e}")
            return []

    def _get_quarterly_financials(self, symbol: str) -> Optional[dict]:
        """Get latest quarterly income statement for symbol."""
        def _fetch():
            finance = Finance(symbol=symbol, source="VCI")
            df = finance.income_statement(period='quarter', lang='en', dropna=True)
            if df is None or df.empty:
                return None

            # Get latest quarter (first row after sort)
            latest = df.iloc[0].to_dict()

            # Extract year/quarter from period column
            # Format varies: "Q4-2024" or similar
            year = latest.get('yearReport') or datetime.now().year
            quarter = latest.get('lengthReport') or 4

            net_profit = latest.get('postTaxProfit') or latest.get('Net profit')
            revenue = latest.get('revenue') or latest.get('Net Revenue')
            eps = latest.get('earningPerShare') or latest.get('EPS')

            profit_margin = None
            if net_profit and revenue and revenue != 0:
                profit_margin = round((net_profit / revenue) * 100, 2)

            return {
                'year': int(year),
                'quarter': int(quarter),
                'net_profit': int(net_profit) if net_profit else None,
                'revenue': int(revenue) if revenue else None,
                'profit_margin': profit_margin,
                'eps': float(eps) if eps else None,
            }

        return safe_vnstock_call(_fetch, max_retries=2, base_delay=2.0)

    async def _store_results(self, results: list) -> int:
        """Bulk upsert results to database."""
        if not results:
            return 0

        try:
            for item in results:
                stmt = text("""
                    INSERT INTO top_performers
                    (symbol, company_name, exchange, year, quarter, net_profit, revenue, profit_margin, eps, rank, updated_at)
                    VALUES (:symbol, :company_name, :exchange, :year, :quarter, :net_profit, :revenue, :profit_margin, :eps, :rank, NOW())
                    ON CONFLICT (symbol, year, quarter)
                    DO UPDATE SET
                        company_name = EXCLUDED.company_name,
                        exchange = EXCLUDED.exchange,
                        net_profit = EXCLUDED.net_profit,
                        revenue = EXCLUDED.revenue,
                        profit_margin = EXCLUDED.profit_margin,
                        eps = EXCLUDED.eps,
                        rank = EXCLUDED.rank,
                        updated_at = NOW()
                """)
                await self.db.execute(stmt, item)

            await self.db.commit()
            return len(results)

        except Exception as e:
            logger.error(f"Failed to store results: {e}")
            await self.db.rollback()
            return 0
```

### Step 3: Add Job Function

In `apps/api/src/stocks/jobs.py`, add:

```python
from src.stocks.top_performers_collector import TopPerformersCollector

async def collect_top_performers_job() -> dict:
    """Scheduled job to collect top performers data."""
    logger.info("Starting top performers collection job")

    async with get_async_session() as db:
        collector = TopPerformersCollector(db)
        result = await collector.collect()

    logger.info(f"Top performers job complete: {result}")
    return result
```

### Step 4: Register in Scheduler

In `apps/api/src/core/scheduler.py`, add:

```python
from src.stocks.jobs import collect_top_performers_job

# In setup_scheduler():
if settings.TOP_PERFORMERS_ENABLED:
    await scheduler.add_schedule(
        collect_top_performers_job,
        CronTrigger(
            hour=settings.TOP_PERFORMERS_HOUR,
            minute=settings.TOP_PERFORMERS_MINUTE,
            day_of_week="sun",  # Weekly on Sunday
            timezone="Asia/Ho_Chi_Minh"
        ),
        id="collect-top-performers"
    )
    logger.info(f"Scheduled top performers collection: Sunday {settings.TOP_PERFORMERS_HOUR:02d}:{settings.TOP_PERFORMERS_MINUTE:02d} ICT")
```

## Todo List

- [ ] Add config settings in config.py
- [ ] Create top_performers_collector.py
- [ ] Add job function in jobs.py
- [ ] Register job in scheduler.py
- [ ] Test job manually via endpoint or direct call
- [ ] Verify data stored correctly
- [ ] Check logs for rate limit handling

## Success Criteria

- [ ] Job completes for all HOSE+HNX symbols
- [ ] Data correctly stored with rankings
- [ ] No rate limit errors crash the job
- [ ] Logging shows progress and summary
- [ ] Upsert works (re-running updates existing records)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Rate limit blocks all requests | High | Exponential backoff, skip and continue |
| Job takes too long | Medium | 1.5s delay × 800 = ~20 min, acceptable |
| vnstock API changes | Medium | Fallback column names, error handling |
| Partial data loss | Medium | Upsert preserves existing, logs failures |

## Security Considerations

- No user input in job
- All API calls via safe wrapper
- Database credentials from env

## Next Steps

- Proceed to Phase 3: API Endpoint
