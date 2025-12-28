---
phase: 1
title: Backend - Intraday Order Stats Endpoint
status: completed
estimated_files: 3
completed_date: 2024-12-27
---

# Phase 1: Backend - Intraday Order Stats Endpoint

## Objective

Create a new API endpoint that uses `quote.intraday()` to calculate current-day buy/sell order statistics.

## Tasks

### 1.1 Add Response Schema

**File:** `apps/api/src/stocks/trading/schemas.py`

```python
class IntradayOrderStatsResponse(BaseModel):
    """Current-day order statistics from intraday data."""
    symbol: str
    date: str  # Current trading date
    buy_orders: int
    sell_orders: int
    buy_volume: int
    sell_volume: int
    net_volume: int
    ato_volume: int  # Auction at open
    atc_volume: int  # Auction at close
    last_updated: str  # ISO timestamp
```

### 1.2 Add Service Method

**File:** `apps/api/src/stocks/trading/service.py`

```python
def get_intraday_order_stats(self, symbol: str) -> IntradayOrderStatsResponse:
    """Get current-day order stats from intraday tick data."""
    symbol = validate_symbol(symbol)
    try:
        stock = Vnstock().stock(symbol=symbol, source=self.source)
        df = stock.quote.intraday(page_size=10000)

        if df is None or df.empty:
            return IntradayOrderStatsResponse(
                symbol=symbol,
                date=date.today().isoformat(),
                buy_orders=0,
                sell_orders=0,
                buy_volume=0,
                sell_volume=0,
                net_volume=0,
                ato_volume=0,
                atc_volume=0,
                last_updated=datetime.now().isoformat()
            )

        # Aggregate by match_type
        stats = df.groupby('match_type').agg({
            'volume': ['count', 'sum']
        }).reset_index()

        buy_orders = int(stats[stats['match_type'] == 'Buy']['volume']['count'].sum())
        sell_orders = int(stats[stats['match_type'] == 'Sell']['volume']['count'].sum())
        buy_volume = int(stats[stats['match_type'] == 'Buy']['volume']['sum'].sum())
        sell_volume = int(stats[stats['match_type'] == 'Sell']['volume']['sum'].sum())
        ato_volume = int(stats[stats['match_type'] == 'ATO']['volume']['sum'].sum())
        atc_volume = int(stats[stats['match_type'] == 'ATC']['volume']['sum'].sum())

        return IntradayOrderStatsResponse(
            symbol=symbol,
            date=date.today().isoformat(),
            buy_orders=buy_orders,
            sell_orders=sell_orders,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            net_volume=buy_volume - sell_volume,
            ato_volume=ato_volume,
            atc_volume=atc_volume,
            last_updated=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Error fetching intraday order stats for {symbol}: {e}")
        raise StockServiceError(f"Failed to fetch intraday order stats: {e}")
```

### 1.3 Add Router Endpoint

**File:** `apps/api/src/stocks/trading/router.py`

```python
@router.get(
    "/{symbol}/intraday-order-stats",
    response_model=IntradayOrderStatsResponse,
    dependencies=[Depends(standard_rate_limit)],
)
async def get_intraday_order_stats(symbol: str) -> IntradayOrderStatsResponse:
    """Get current-day order statistics from intraday tick data.

    Returns aggregated buy/sell order counts and volumes for today.
    Only available during and after trading hours.
    """
    cache_key = f"{symbol}:intraday"
    cached = order_stats_cache.get(cache_key)
    if cached:
        return IntradayOrderStatsResponse(**cached)

    try:
        service = get_trading_service()
        result = service.get_intraday_order_stats(symbol)
        order_stats_cache.set(cache_key, result.model_dump())
        return result
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

## Verification

```bash
# Test endpoint
curl http://localhost:8000/api/v1/stocks/VNM/intraday-order-stats

# Expected response
{
  "symbol": "VNM",
  "date": "2024-12-27",
  "buy_orders": 1487,
  "sell_orders": 1600,
  "buy_volume": 1128200,
  "sell_volume": 1069500,
  "net_volume": 58700,
  "ato_volume": 15500,
  "atc_volume": 185700,
  "last_updated": "2024-12-27T14:30:00"
}
```

## Dependencies

- vnstock `Vnstock().stock().quote.intraday()` method
- Existing cache infrastructure

## Notes

- Data only available for current trading day
- Empty result outside trading hours
- Cache TTL should be short (1-2 minutes) during trading hours

## Implementation Deviations

### 1. Aggregation Logic (Approved)
**Plan suggested:** `df.groupby('match_type').agg({'volume': ['count', 'sum']})`
**Implemented:** Mask-based aggregation (`df["match_type"] == "Buy"`)

**Reason:** Better readability without performance penalty
**Benchmark:** Both methods ~4ms for 10k rows, identical results

### 2. Cache Configuration (Improvement)
**Plan suggested:** Reuse `order_stats_cache` (L107)
**Implemented:** Dedicated `intraday_order_stats_cache` with shorter TTL

**Reason:** Real-time data needs faster refresh
**TTL:** 2min trading (vs 15min for historical order_stats), 30min off-hours

### 3. Import Cleanup Needed
**Issue:** Duplicate datetime imports in service.py L4-9
**Fix:** Consolidate to single import line
**Priority:** Low (cosmetic only)

## Code Review Result

**Status:** ✓ APPROVED
**Reviewer:** code-reviewer
**Date:** 2024-12-27
**Report:** `plans/reports/code-reviewer-251227-1641-advanced-tab-phase1.md`

**Summary:**
- Security: ✓ PASS (input validation, no injection vectors)
- Performance: ✓ PASS (efficient aggregation, appropriate caching)
- Architecture: ✓ PASS (follows domain patterns)
- YAGNI/KISS/DRY: ✓ PASS

**Recommendations:**
1. Fix duplicate import (cosmetic)
2. Add integration test for new endpoint
3. Monitor vnstock page_size limits in production
