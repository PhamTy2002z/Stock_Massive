# Phase 2: EOD Pipeline

## Context

- **Plan**: `/plans/251221-1440-market-sector-context/plan.md`
- **Phase 1**: `/plans/251221-1440-market-sector-context/phase-1-database.md`
- **Design**: `/plans/reports/brainstorm-251221-1432-market-sector-context.md` (Section 13)
- **vnstock API**: `/plans/251221-1440-market-sector-context/research/researcher-vnstock-api.md`

## Overview

**Description**: Build end-of-day batch pipeline to fetch OHLCV data, compute daily returns, rolling correlations, beta, relative strength, and sector benchmarks. Stores results in precomputed tables for fast API access.

**Priority**: P0 (Blocking for Phase 3)

**Status**: ✅ DONE (2025-12-21)

**Effort**: 2 days

## Requirements

### Functional
1. Fetch daily OHLCV for all stocks + VNINDEX
2. Compute daily returns (simple & log)
3. Compute rolling metrics (5D/20D/60D windows):
   - Correlation vs VNINDEX
   - Beta vs VNINDEX
   - Relative Strength (stock/market)
4. Compute sector benchmarks (market-cap weighted)
5. Compute sector ranks
6. Handle missing sector → "Unclassified"
7. Schedule daily at 15:30 ICT (after market close)

### Non-Functional
1. Batch processing (all stocks in one run)
2. Error isolation (one stock failure doesn't stop pipeline)
3. Idempotent (can re-run for same date)
4. Logging for monitoring
5. Manual trigger endpoint for backfill

## Architecture Decisions

### Pipeline Flow

```
1. Fetch OHLCV (vnstock) → Raw data
2. Compute daily returns → stock_daily_returns table
3. Compute rolling metrics → stock_market_metrics table
4. Compute sector benchmarks → sector_daily_benchmark table
5. Compute sector ranks → Update stock_market_metrics
```

### Calculation Methods

**Daily Return (Simple)**:
```python
return_1d = (close_today - close_yesterday) / close_yesterday
```

**Daily Return (Log)**:
```python
return_1d_log = ln(close_today / close_yesterday)
```

**Correlation (Pearson)**:
```python
corr = cov(stock_returns, market_returns) / (std(stock) * std(market))
```

**Beta**:
```python
beta = cov(stock_returns, market_returns) / var(market_returns)
```

**Relative Strength**:
```python
rs_20d = (stock_return_20d / market_return_20d)
```

**Sector Benchmark (Market-cap weighted)**:
```python
sector_return = sum(stock_return * market_cap) / sum(market_cap)
```

### Error Handling
- Graceful degradation (log warnings, continue)
- Retry logic for vnstock API failures (3 attempts)
- Skip stocks with insufficient data (< 5 days for 5D window)

## Related Code Files

**Existing**:
- `/apps/api/src/stocks/jobs.py` - APScheduler jobs
- `/apps/api/src/core/scheduler.py` - Scheduler setup
- `/apps/api/src/stocks/price/service.py` - vnstock integration
- `/apps/api/src/stocks/market/service.py` - Sector data

**New**:
- `/apps/api/src/stocks/market_context_service.py` - Pipeline logic
- `/apps/api/src/stocks/market_context_router.py` - Manual trigger endpoint
- `/apps/api/src/stocks/jobs.py` - Add new scheduled job

## Implementation Steps

### Step 1: Create Market Context Service (3 hours)

Create `/apps/api/src/stocks/market_context_service.py`:

```python
import logging
import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from vnstock import Vnstock, Listing

from .market_context_repository import MarketContextRepository
from .market.service import MarketService

logger = logging.getLogger(__name__)

class MarketContextService:
    """Service for computing market context metrics."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = MarketContextRepository(db)
        self.vnstock = Vnstock()
        self.listing = Listing()
        self.market_service = MarketService()

    def run_eod_pipeline(self, target_date: Optional[date] = None):
        """Run end-of-day pipeline for market context metrics."""
        if target_date is None:
            target_date = date.today()

        logger.info(f"Starting EOD pipeline for {target_date}")

        try:
            # Step 1: Fetch and store daily returns
            self._fetch_and_store_daily_returns(target_date)

            # Step 2: Compute rolling metrics
            self._compute_rolling_metrics(target_date)

            # Step 3: Compute sector benchmarks
            self._compute_sector_benchmarks(target_date)

            # Step 4: Compute sector ranks
            self._compute_sector_ranks(target_date)

            logger.info(f"EOD pipeline completed for {target_date}")

        except Exception as e:
            logger.error(f"EOD pipeline failed: {e}", exc_info=True)
            raise

    def _fetch_and_store_daily_returns(self, target_date: date):
        """Fetch OHLCV and compute daily returns."""
        logger.info("Fetching OHLCV data...")

        # Get all symbols
        all_symbols_df = self.listing.all_symbols()
        symbols = all_symbols_df['ticker'].tolist()
        symbols.append('VNINDEX')  # Add market index

        # Date range: need previous day for return calculation
        start_date = target_date - timedelta(days=5)  # Buffer for weekends
        end_date = target_date

        for symbol in symbols:
            try:
                # Fetch history
                quote = self.vnstock.stock(symbol=symbol, source='VCI').quote
                df = quote.history(
                    start=start_date.strftime('%Y-%m-%d'),
                    end=end_date.strftime('%Y-%m-%d'),
                    interval='1D'
                )

                if df.empty:
                    logger.warning(f"No data for {symbol}")
                    continue

                # Sort by date
                df = df.sort_values('time')
                df['date'] = pd.to_datetime(df['time']).dt.date

                # Compute returns
                df['return_1d'] = df['close'].pct_change()
                df['return_1d_log'] = np.log(df['close'] / df['close'].shift(1))

                # Store only target date
                target_row = df[df['date'] == target_date]
                if not target_row.empty:
                    row = target_row.iloc[0]
                    self.repo.upsert_daily_return(
                        symbol=symbol,
                        date=target_date,
                        close_price=float(row['close']),
                        return_1d=float(row['return_1d']) if pd.notna(row['return_1d']) else None,
                        return_1d_log=float(row['return_1d_log']) if pd.notna(row['return_1d_log']) else None
                    )

            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
                continue

        logger.info(f"Stored daily returns for {len(symbols)} symbols")

    def _compute_rolling_metrics(self, target_date: date):
        """Compute rolling correlation, beta, RS for all stocks."""
        logger.info("Computing rolling metrics...")

        # Get all symbols (exclude VNINDEX)
        all_symbols_df = self.listing.all_symbols()
        symbols = all_symbols_df['ticker'].tolist()

        # Fetch VNINDEX returns for correlation
        vnindex_returns = self._get_returns_series('VNINDEX', target_date, lookback_days=90)

        if vnindex_returns is None or len(vnindex_returns) < 5:
            logger.error("Insufficient VNINDEX data")
            return

        for symbol in symbols:
            try:
                stock_returns = self._get_returns_series(symbol, target_date, lookback_days=90)

                if stock_returns is None or len(stock_returns) < 5:
                    continue

                # Align dates
                aligned = pd.DataFrame({
                    'stock': stock_returns,
                    'market': vnindex_returns
                }).dropna()

                if len(aligned) < 5:
                    continue

                # Compute metrics
                metrics = {}

                # 5D window
                if len(aligned) >= 5:
                    window_5d = aligned.tail(5)
                    metrics['corr_5d'] = self._pearson_correlation(
                        window_5d['stock'].values,
                        window_5d['market'].values
                    )

                # 20D window
                if len(aligned) >= 20:
                    window_20d = aligned.tail(20)
                    metrics['corr_20d'] = self._pearson_correlation(
                        window_20d['stock'].values,
                        window_20d['market'].values
                    )
                    metrics['beta_20d'] = self._calculate_beta(
                        window_20d['stock'].values,
                        window_20d['market'].values
                    )
                    metrics['rs_market_20d'] = self._calculate_relative_strength(
                        window_20d['stock'].values,
                        window_20d['market'].values
                    )

                # 60D window
                if len(aligned) >= 60:
                    window_60d = aligned.tail(60)
                    metrics['corr_60d'] = self._pearson_correlation(
                        window_60d['stock'].values,
                        window_60d['market'].values
                    )
                    metrics['beta_60d'] = self._calculate_beta(
                        window_60d['stock'].values,
                        window_60d['market'].values
                    )

                # Store metrics
                self.repo.upsert_market_metric(symbol, target_date, **metrics)

            except Exception as e:
                logger.error(f"Failed to compute metrics for {symbol}: {e}")
                continue

        logger.info(f"Computed rolling metrics for {len(symbols)} symbols")

    def _compute_sector_benchmarks(self, target_date: date):
        """Compute market-cap weighted sector benchmarks."""
        logger.info("Computing sector benchmarks...")

        # Get symbols with ICB classification
        symbols_df = self.listing.symbols_by_industries()

        # Get price board for market cap calculation
        price_board = self.market_service.get_price_board_batch(symbols_df['ticker'].tolist())

        # Merge price with ICB
        merged = symbols_df.merge(
            price_board,
            left_on='ticker',
            right_on='symbol',
            how='inner'
        )

        # Get daily returns
        returns_dict = {}
        for symbol in merged['ticker'].unique():
            returns = self.repo.get_daily_returns(symbol, target_date, target_date)
            if returns:
                returns_dict[symbol] = returns[0].return_1d

        merged['return_1d'] = merged['ticker'].map(returns_dict)
        merged = merged.dropna(subset=['return_1d', 'match_price', 'listed_share'])

        # Calculate market cap
        merged['market_cap'] = merged['match_price'] * merged['listed_share']

        # Group by ICB Level 2
        grouped = merged.groupby('icb_code2')

        for icb_code, group in grouped:
            try:
                # Market-cap weighted return
                total_mcap = group['market_cap'].sum()
                weighted_return = (group['return_1d'] * group['market_cap']).sum() / total_mcap

                self.repo.upsert_sector_benchmark(
                    icb_code=icb_code,
                    date=target_date,
                    mcap_weighted_return=float(weighted_return),
                    total_mcap=int(total_mcap),
                    stock_count=len(group)
                )

            except Exception as e:
                logger.error(f"Failed to compute benchmark for sector {icb_code}: {e}")
                continue

        logger.info(f"Computed sector benchmarks for {len(grouped)} sectors")

    def _compute_sector_ranks(self, target_date: date):
        """Compute stock rank within sector."""
        logger.info("Computing sector ranks...")

        symbols_df = self.listing.symbols_by_industries()

        # Group by sector
        grouped = symbols_df.groupby('icb_code2')

        for icb_code, group in grouped:
            try:
                # Get returns for all stocks in sector
                stock_returns = []
                for symbol in group['ticker']:
                    returns = self.repo.get_daily_returns(symbol, target_date, target_date)
                    if returns and returns[0].return_1d is not None:
                        stock_returns.append((symbol, returns[0].return_1d))

                # Sort by return descending
                stock_returns.sort(key=lambda x: x[1], reverse=True)

                # Assign ranks
                for rank, (symbol, _) in enumerate(stock_returns, start=1):
                    metric = self.repo.get_latest_metric(symbol)
                    if metric and metric.date == target_date:
                        self.repo.upsert_market_metric(
                            symbol,
                            target_date,
                            sector_rank=rank,
                            sector_total=len(stock_returns)
                        )

            except Exception as e:
                logger.error(f"Failed to compute ranks for sector {icb_code}: {e}")
                continue

        logger.info("Sector ranks computed")

    def _get_returns_series(self, symbol: str, end_date: date, lookback_days: int) -> Optional[pd.Series]:
        """Get returns series for symbol."""
        start_date = end_date - timedelta(days=lookback_days)
        returns = self.repo.get_daily_returns(symbol, start_date, end_date)

        if not returns:
            return None

        df = pd.DataFrame([{
            'date': r.date,
            'return_1d': r.return_1d
        } for r in returns])

        df = df.dropna(subset=['return_1d'])
        df = df.set_index('date')

        return df['return_1d']

    @staticmethod
    def _pearson_correlation(x: np.ndarray, y: np.ndarray) -> Optional[float]:
        """Calculate Pearson correlation coefficient."""
        try:
            if len(x) < 2 or len(y) < 2:
                return None
            corr = np.corrcoef(x, y)[0, 1]
            return float(corr) if not np.isnan(corr) else None
        except Exception:
            return None

    @staticmethod
    def _calculate_beta(stock_returns: np.ndarray, market_returns: np.ndarray) -> Optional[float]:
        """Calculate beta (covariance / variance)."""
        try:
            cov = np.cov(stock_returns, market_returns)[0, 1]
            var = np.var(market_returns)
            if var == 0:
                return None
            beta = cov / var
            return float(beta)
        except Exception:
            return None

    @staticmethod
    def _calculate_relative_strength(stock_returns: np.ndarray, market_returns: np.ndarray) -> Optional[float]:
        """Calculate relative strength (cumulative return ratio)."""
        try:
            stock_cum = (1 + stock_returns).prod() - 1
            market_cum = (1 + market_returns).prod() - 1
            if market_cum == 0:
                return None
            rs = stock_cum / market_cum
            return float(rs)
        except Exception:
            return None
```

### Step 2: Add Scheduled Job (30 min)

Update `/apps/api/src/stocks/jobs.py`:

```python
from datetime import datetime
from src.core.database import get_db
from .market_context_service import MarketContextService
import logging

logger = logging.getLogger(__name__)

def run_market_context_eod_job():
    """Scheduled job for market context EOD pipeline."""
    logger.info("Starting market context EOD job")

    try:
        db = next(get_db())
        service = MarketContextService(db)
        service.run_eod_pipeline()
        logger.info("Market context EOD job completed")

    except Exception as e:
        logger.error(f"Market context EOD job failed: {e}", exc_info=True)
    finally:
        db.close()
```

Update `/apps/api/src/core/scheduler.py`:

```python
from apscheduler.triggers.cron import CronTrigger

# Add to scheduler setup
scheduler.add_job(
    run_market_context_eod_job,
    trigger=CronTrigger(hour=15, minute=30, timezone='Asia/Ho_Chi_Minh'),
    id='market_context_eod',
    name='Market Context EOD Pipeline',
    replace_existing=True
)
```

### Step 3: Create Manual Trigger Endpoint (30 min)

Create `/apps/api/src/stocks/market_context_router.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date
from src.core.database import get_db
from .market_context_service import MarketContextService

router = APIRouter(prefix="/market-context", tags=["market-context"])

@router.post("/trigger-eod")
async def trigger_eod_pipeline(
    target_date: date = Query(None, description="Target date (default: today)"),
    db: Session = Depends(get_db)
):
    """Manually trigger EOD pipeline for market context metrics.

    Use for backfilling historical data or re-running failed jobs.
    """
    try:
        service = MarketContextService(db)
        service.run_eod_pipeline(target_date)
        return {
            "status": "success",
            "message": f"EOD pipeline completed for {target_date or 'today'}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/backfill")
async def backfill_historical_data(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    db: Session = Depends(get_db)
):
    """Backfill historical market context data for date range."""
    try:
        service = MarketContextService(db)
        current_date = start_date

        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() < 5:
                service.run_eod_pipeline(current_date)

            current_date += timedelta(days=1)

        return {
            "status": "success",
            "message": f"Backfilled data from {start_date} to {end_date}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

Add to `/apps/api/src/stocks/router.py`:

```python
from .market_context_router import router as market_context_router

router.include_router(market_context_router)
```

### Step 4: Add Logging and Monitoring (30 min)

Update `/apps/api/src/stocks/market_context_service.py` with structured logging:

```python
# Add at start of each major step
logger.info("Step started", extra={
    "step": "fetch_daily_returns",
    "target_date": str(target_date),
    "symbol_count": len(symbols)
})

# Add at end of each step
logger.info("Step completed", extra={
    "step": "fetch_daily_returns",
    "duration_seconds": time.time() - start_time,
    "success_count": success_count,
    "error_count": error_count
})
```

### Step 5: Write Integration Tests (1 hour)

Create `/apps/api/tests/test_market_context_service.py`:

```python
import pytest
from datetime import date, timedelta
from src.stocks.market_context_service import MarketContextService

def test_eod_pipeline_integration(db_session):
    """Test full EOD pipeline."""
    service = MarketContextService(db_session)

    # Run for yesterday (avoid today's incomplete data)
    target_date = date.today() - timedelta(days=1)
    service.run_eod_pipeline(target_date)

    # Verify daily returns stored
    returns = service.repo.get_daily_returns('VCB', target_date, target_date)
    assert len(returns) > 0
    assert returns[0].return_1d is not None

    # Verify metrics computed
    metric = service.repo.get_latest_metric('VCB')
    assert metric is not None
    assert metric.corr_20d is not None or metric.corr_5d is not None

def test_correlation_calculation():
    """Test Pearson correlation calculation."""
    import numpy as np

    x = np.array([1, 2, 3, 4, 5])
    y = np.array([2, 4, 6, 8, 10])

    corr = MarketContextService._pearson_correlation(x, y)
    assert corr == pytest.approx(1.0, abs=0.01)

def test_beta_calculation():
    """Test beta calculation."""
    import numpy as np

    stock = np.array([0.01, 0.02, -0.01, 0.03, 0.01])
    market = np.array([0.01, 0.015, -0.005, 0.02, 0.01])

    beta = MarketContextService._calculate_beta(stock, market)
    assert beta is not None
    assert 0.5 < beta < 2.0  # Reasonable range

def test_relative_strength_calculation():
    """Test RS calculation."""
    import numpy as np

    stock = np.array([0.02, 0.03, 0.01])  # 6% cumulative
    market = np.array([0.01, 0.015, 0.005])  # 3% cumulative

    rs = MarketContextService._calculate_relative_strength(stock, market)
    assert rs is not None
    assert rs > 1.0  # Stock outperformed
```

### Step 6: Add Error Handling and Retry Logic (30 min)

Add retry decorator to vnstock calls:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _fetch_history_with_retry(self, symbol: str, start: str, end: str):
    """Fetch history with retry logic."""
    quote = self.vnstock.stock(symbol=symbol, source='VCI').quote
    return quote.history(start=start, end=end, interval='1D')
```

## Success Criteria

- [ ] Pipeline runs daily at 15:30 ICT without errors
- [ ] All stocks processed (>1000 symbols)
- [ ] Daily returns computed correctly (validated against manual calc)
- [ ] Correlation values in valid range [-1, 1]
- [ ] Beta values reasonable (0.5 - 2.0 for most stocks)
- [ ] Sector benchmarks match manual calculation
- [ ] Manual trigger endpoint works
- [ ] Backfill endpoint works for historical data
- [ ] Logs provide visibility into pipeline progress
- [ ] Error isolation (one stock failure doesn't stop pipeline)

## Testing Checklist

- [ ] Unit tests for correlation/beta/RS calculations
- [ ] Integration test for full pipeline
- [ ] Test with missing data (weekends, holidays)
- [ ] Test with "Unclassified" sector stocks
- [ ] Test backfill for 30-day range
- [ ] Verify idempotency (re-run same date)
- [ ] Performance test (pipeline completes in < 10 min)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| vnstock API rate limits | High | Batch requests, add delays, retry logic |
| Pipeline timeout | Medium | Optimize queries, parallel processing |
| Data quality issues | High | Validation checks, outlier detection |
| Missing historical data | Medium | Graceful degradation, log warnings |
| Calculation errors | High | Unit tests, validate against known values |

## Performance Considerations

- Batch vnstock API calls (50-100 symbols per request)
- Use pandas vectorized operations
- Parallel processing for independent calculations
- Database connection pooling
- Target: Complete pipeline in < 10 minutes

## Dependencies

- Phase 1 completed (database tables exist)
- vnstock API accessible
- APScheduler configured
- pandas, numpy installed

## Next Phase

Phase 3: Backend API - Expose precomputed data via REST endpoint
