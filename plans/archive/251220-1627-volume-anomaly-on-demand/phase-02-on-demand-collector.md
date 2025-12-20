# Phase 02: On-Demand Collector Integration

## Context

- [Plan Overview](plan.md)
- [Phase 01: TradingHoursCache](phase-01-trading-hours-cache.md)
- [vnstock API Research](research/researcher-01-vnstock-api.md)

## Overview

Modify the `/stocks/{symbol}/volume-anomalies` endpoint to automatically collect intraday data when cache is stale or data is missing. This enables users to get volume anomaly analysis for any symbol without requiring pre-collection.

## Requirements

1. Check cache freshness before querying DB
2. If stale/missing: collect from vnstock, save to DB, update cache
3. If fresh: return cached response directly
4. Add 1s delay for rate limiting protection
5. Handle collection errors gracefully

## Architecture

```
GET /stocks/{symbol}/volume-anomalies
    │
    ▼
┌─────────────────────────────────┐
│ Check volume_anomaly_cache      │
│ Key: "{symbol}:{days}"          │
└─────────────────────────────────┘
    │
    ├── Cache HIT (fresh) ──────────► Return cached response
    │
    ▼ Cache MISS (stale/missing)
┌─────────────────────────────────┐
│ IntradayCollector.collect_symbol│
│ (fetch from vnstock API)        │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ IntradayCollector.save_bars     │
│ (upsert to PostgreSQL)          │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ detect_volume_anomalies()       │
│ (compute from DB)               │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ Update cache with response      │
│ Return VolumeAnomalyResponse    │
└─────────────────────────────────┘
```

## Related Code Files

| File | Purpose | Action |
|------|---------|--------|
| `src/stocks/price/router.py` | Volume anomalies endpoint | **MODIFY** |
| `src/stocks/price/cache.py` | TradingHoursCache | Import (from Phase 01) |
| `src/stocks/intraday_collector.py` | Data collection | Use existing |

## Implementation Steps

### Step 1: Update router.py imports

Add cache import at top of `src/stocks/price/router.py`:

```python
from src.stocks.price.cache import volume_anomaly_cache
```

### Step 2: Modify get_volume_anomalies endpoint

Replace the existing endpoint (lines 127-142) with:

```python
@router.get("/{symbol}/volume-anomalies", response_model=VolumeAnomalyResponse)
async def get_volume_anomalies(
    symbol: str,
    days: int = Query(default=20, ge=5, le=60, description="Baseline period in days"),
    db: AsyncSession = Depends(get_db),
) -> VolumeAnomalyResponse:
    """Detect volume anomalies for all 5-minute time slots.

    Compares latest day's volume against N-day average baseline.
    Returns 72 time slots (09:00-14:55) with anomaly flags.

    Auto-collects intraday data if stale or missing.
    """
    symbol = symbol.upper()
    cache_key = f"{symbol}:{days}"

    # Check cache first
    cached = volume_anomaly_cache.get(cache_key)
    if cached is not None:
        return VolumeAnomalyResponse(**cached)

    # Cache miss - collect fresh data
    collector = IntradayCollector(db)

    try:
        # Fetch from vnstock and save to DB
        bars = await collector.collect_symbol(symbol)
        if bars:
            await collector.save_bars(bars)
            await db.commit()
    except Exception as e:
        # Log but continue - may have historical data
        import logging
        logging.getLogger(__name__).warning(
            f"Failed to collect intraday data for {symbol}: {e}"
        )

    # Compute anomalies from DB (includes any newly collected data)
    result = await collector.detect_volume_anomalies(symbol, days)

    # Cache the result
    volume_anomaly_cache.set(cache_key, result)

    return VolumeAnomalyResponse(**result)
```

### Step 3: Add logging import (if not present)

Ensure logging is imported at top of router.py:

```python
import logging
```

## Todo List

- [x] Add `from src.stocks.price.cache import volume_anomaly_cache` import
- [x] Add `import logging` if not present
- [x] Replace `get_volume_anomalies` endpoint with on-demand logic
- [x] Test endpoint with uncollected symbol
- [x] Verify cache hit on second request

## Success Criteria

1. First request for new symbol: collects data, returns results (~2-3s)
2. Second request within TTL: returns cached response (<100ms)
3. Request after TTL expires: re-collects fresh data
4. Collection failure: still returns historical data if available
5. No breaking changes to response schema

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Slow first request | High | Low | Accept 2-3s latency, document in API |
| vnstock API failure | Medium | Medium | Graceful fallback to historical data |
| Rate limiting | Low | Medium | Cache aggressively, 1 req/symbol/TTL |
| DB commit failure | Low | High | Let exception propagate (500 error) |

## Testing Checklist

1. Request symbol with no prior data → should collect and return
2. Request same symbol again → should return cached (check timing)
3. Wait for TTL expiry → should re-collect
4. Request during trading hours → 60s TTL
5. Request outside trading hours → 3600s TTL
6. Invalid symbol → should return appropriate error

## Notes

- `db.commit()` called explicitly after save_bars since we need data committed before detect_volume_anomalies query
- Collection errors logged but not raised - allows returning historical data
- Cache key includes `days` param to handle different baseline periods
