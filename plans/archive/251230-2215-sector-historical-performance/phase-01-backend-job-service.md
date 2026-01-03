# Phase 1: Backend - Scheduled Job & Service

## Overview

| Field | Value |
|-------|-------|
| Priority | P1 |
| Effort | 2h |
| Status | DONE |
| Dependencies | vnstock VCI, Redis |

## Files to Modify/Create

| Action | File |
|--------|------|
| CREATE | `apps/api/src/stocks/analytics/sector_historical_service.py` |
| MODIFY | `apps/api/src/stocks/jobs.py` |
| MODIFY | `apps/api/src/core/scheduler.py` |
| MODIFY | `apps/api/src/core/config.py` |

## Implementation Steps

### Step 1: Create Service Module

**File**: `apps/api/src/stocks/analytics/sector_historical_service.py`

```python
"""Sector historical performance calculator."""
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from vnstock import Listing, Vnstock

from src.core.cache import TradingHoursCache
from src.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Redis cache with 24h TTL (historical data, off-hours only)
sector_historical_cache = TradingHoursCache(
    key_prefix="stock:sector_hist:",
    ttl_trading=86400,   # 24h during trading (use cached)
    ttl_off_hours=86400, # 24h off-hours
)

PERIODS = {
    "1W": 7,
    "2W": 14,
    "1M": 30,
}

class SectorHistoricalService:
    """Calculate sector performance over 1W/2W/1M periods."""

    def __init__(self, source: str = "VCI"):
        self.source = source
        self.delay = settings.sector_historical_delay  # 1.2s

    def calculate_all_periods(self) -> dict:
        """Calculate sector performance for all periods and cache results."""
        # Get VN100 symbols with ICB mapping
        listing = Listing()
        vn100_symbols = listing.symbols_by_group("VN100")
        if vn100_symbols is None:
            logger.error("Failed to get VN100 symbols")
            return {"error": "Failed to get VN100 symbols"}

        symbols = vn100_symbols.tolist() if hasattr(vn100_symbols, "tolist") else list(vn100_symbols)
        logger.info(f"Processing {len(symbols)} VN100 symbols")

        # Get ICB mapping
        all_symbols_df = listing.symbols_by_industries()
        icb_map = {}
        if all_symbols_df is not None and not all_symbols_df.empty:
            for _, row in all_symbols_df.iterrows():
                s = row.get("symbol")
                if s in symbols:
                    icb_map[s] = {
                        "icb_code": str(row.get("icb_code2", "")),
                        "icb_name": str(row.get("icb_name2", "")),
                    }

        # Fetch historical prices for each symbol
        today = datetime.now().date()
        max_days = max(PERIODS.values())
        start_date = (today - timedelta(days=max_days + 5)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        stock_data = {}
        for symbol in symbols:
            try:
                stock = Vnstock().stock(symbol=symbol, source=self.source)
                df = stock.quote.history(start=start_date, end=end_date, interval="1D")
                if df is not None and not df.empty:
                    stock_data[symbol] = df
                time.sleep(self.delay)
            except Exception as e:
                logger.debug(f"Error fetching {symbol}: {e}")

        logger.info(f"Fetched data for {len(stock_data)} symbols")

        # Calculate performance for each period
        results = {}
        for period_name, days in PERIODS.items():
            results[period_name] = self._calculate_period(
                stock_data, icb_map, days, today
            )
            # Cache result
            sector_historical_cache.set(period_name, results[period_name])

        return results

    def _calculate_period(
        self,
        stock_data: dict,
        icb_map: dict,
        days: int,
        today
    ) -> dict:
        """Calculate sector performance for a single period."""
        target_date = today - timedelta(days=days)

        # Calculate % change per stock
        stock_changes = []
        for symbol, df in stock_data.items():
            if symbol not in icb_map:
                continue

            df["date"] = pd.to_datetime(df["time"]).dt.date

            # Get closest dates
            start_row = df[df["date"] <= target_date].tail(1)
            end_row = df[df["date"] == today]
            if end_row.empty:
                end_row = df.tail(1)

            if start_row.empty or end_row.empty:
                continue

            start_price = float(start_row["close"].iloc[0])
            end_price = float(end_row["close"].iloc[0])

            if start_price > 0:
                pct_change = ((end_price - start_price) / start_price) * 100
                stock_changes.append({
                    "symbol": symbol,
                    "icb_code": icb_map[symbol]["icb_code"],
                    "icb_name": icb_map[symbol]["icb_name"],
                    "change_pct": pct_change,
                })

        if not stock_changes:
            return {"top_gainers": [], "top_losers": [], "generated_at": str(datetime.now())}

        # Group by sector, calculate average
        changes_df = pd.DataFrame(stock_changes)
        sector_perf = changes_df.groupby(["icb_code", "icb_name"])["change_pct"].mean().reset_index()
        sector_perf = sector_perf.sort_values("change_pct", ascending=False)

        # Top 5 gainers (positive) and losers (negative)
        top_gainers = [
            {"icb_code": r["icb_code"], "icb_name": r["icb_name"], "change_pct": round(r["change_pct"], 2)}
            for _, r in sector_perf.head(5).iterrows()
        ]
        top_losers = [
            {"icb_code": r["icb_code"], "icb_name": r["icb_name"], "change_pct": round(r["change_pct"], 2)}
            for _, r in sector_perf.tail(5).iloc[::-1].iterrows()
        ]

        return {
            "top_gainers": top_gainers,
            "top_losers": top_losers,
            "generated_at": str(datetime.now()),
        }

    def get_cached(self, period: str) -> Optional[dict]:
        """Get cached result for a period."""
        return sector_historical_cache.get(period)
```

### Step 2: Add Settings Config

**File**: `apps/api/src/core/config.py` (MODIFY)

Add settings:
```python
# Sector Historical Performance
sector_historical_enabled: bool = True
sector_historical_hour: int = 15
sector_historical_minute: int = 45
sector_historical_delay: float = 1.2  # seconds between API calls
```

### Step 3: Add Job Function

**File**: `apps/api/src/stocks/jobs.py` (MODIFY)

```python
from src.stocks.analytics.sector_historical_service import SectorHistoricalService

def collect_sector_historical_job() -> dict:
    """Daily job to calculate sector historical performance."""
    logger.info("Starting sector historical performance calculation")
    job_store.start_job("sector-historical", "Tính hiệu suất ngành", 1)

    try:
        service = SectorHistoricalService()
        result = service.calculate_all_periods()
        logger.info(f"Sector historical calculation complete: {len(result)} periods")
        job_store.complete_job("sector-historical", result)
        return result
    except Exception as e:
        logger.error(f"Sector historical job failed: {e}")
        job_store.fail_job("sector-historical", str(e))
        return {"error": str(e)}
```

### Step 4: Add Scheduler Entry

**File**: `apps/api/src/core/scheduler.py` (MODIFY)

```python
from src.stocks.jobs import collect_sector_historical_job

async def sector_historical_job_wrapper():
    """Wrapper for sector historical job."""
    logger.info("=== SCHEDULED JOB TRIGGERED: Sector Historical Performance ===")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, collect_sector_historical_job)
        logger.info(f"Sector historical complete: {result}")
        return result
    except Exception as e:
        logger.error(f"Sector historical failed: {e}", exc_info=True)
        raise

# In setup_scheduler():
if settings.sector_historical_enabled:
    await scheduler.add_schedule(
        sector_historical_job_wrapper,
        CronTrigger(
            hour=settings.sector_historical_hour,
            minute=settings.sector_historical_minute,
            timezone="Asia/Ho_Chi_Minh",
        ),
        id="sector-historical-daily",
    )
    logger.info(f"Scheduled sector historical at {settings.sector_historical_hour}:{settings.sector_historical_minute:02d} ICT")
```

## Todo List

- [ ] Create `sector_historical_service.py` with SectorHistoricalService class
- [ ] Add config settings to `config.py`
- [ ] Add `collect_sector_historical_job()` to `jobs.py`
- [ ] Add scheduler entry with wrapper function
- [ ] Test job manually via API trigger

## Success Criteria

- Job fetches ~100 VN100 symbols within rate limit
- Job completes in < 3 minutes
- Redis cache populated with 3 periods (1W, 2W, 1M)
- Logs show successful completion

## Risks

| Risk | Mitigation |
|------|------------|
| Rate limiting (60 req/min) | 1.2s delay = ~50 req/min, safe margin |
| VN100 symbols missing ICB | Skip symbols without ICB mapping |
| Holiday = no new data | Use last available trading day |
