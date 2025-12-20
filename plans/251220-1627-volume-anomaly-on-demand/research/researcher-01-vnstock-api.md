# Vnstock API Rate Limits & Intraday Data Research

**Date:** 2024-12-20
**Focus:** Rate limits, intraday availability, caching best practices

## 1. Rate Limits

### VCI Source (Current Implementation)
- **Standard rate limit:** Not officially documented
- **Sponsored members:** 10x higher rate limit than VND source
- **Recommended practice:** 1 second delay between API calls

### VND Source (Alternative)
- Lower rate limit than VCI
- Same API interface, different backend

### Practical Observations
- No hard rate limit numbers published
- Codebase currently has **no delay** between symbol fetches in `collect_and_save()`
- Risk: Batch fetching multiple symbols may trigger throttling

## 2. Intraday Data Availability

| Aspect | Detail |
|--------|--------|
| **Data scope** | Current trading session only |
| **Trading hours** | 09:00 - 15:00 Vietnam time |
| **Max records** | ~10,000 per call (pagination available) |
| **Granularity** | Tick-level (second-accurate timestamps) |
| **Historical** | NOT available - must collect daily |

### Data Fields Returned
- `time`: Transaction timestamp
- `price`: Transaction price
- `volume`: Shares traded
- `match_type`: Buy/Sell/ATO/ATC
- `accumulated_vol`: Running total volume
- `accumulated_val`: Running total value

## 3. Best Practices for Caching/Storage

### Collection Strategy
1. **Timing:** Run at 15:05 (after ATC session closes)
2. **Frequency:** Once daily per symbol
3. **Delay:** Add 1s between symbol API calls
4. **Storage:** PostgreSQL with upsert (current impl uses ON CONFLICT)

### Current Codebase Pattern
```python
# src/stocks/intraday_collector.py
async def collect_and_save(self, symbols: list[str]) -> dict:
    for symbol in symbols:  # No delay between calls!
        bars = await self.collect_symbol(symbol)
        count = await self.save_bars(bars)
```

### Recommended Improvement
```python
import asyncio
for symbol in symbols:
    bars = await self.collect_symbol(symbol)
    await self.save_bars(bars)
    await asyncio.sleep(1.0)  # Rate limit protection
```

## 4. Known Issues with Intraday Endpoint

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Current day only | No historical intraday | Daily collection + DB storage |
| Undocumented rate limits | Potential throttling | Add delays, monitor errors |
| Data during holidays | Unknown behavior | Skip collection on holidays |
| Order amendments | May not reflect in tick data | Accept as limitation |

## 5. On-Demand Fetching Considerations

For real-time/on-demand volume anomaly detection:

| Approach | Pros | Cons |
|----------|------|------|
| **Direct API call** | Fresh data | Rate limit risk, latency |
| **Cached + refresh** | Fast, rate-safe | Stale data possible |
| **Hybrid** | Balance | More complex |

### Recommendation for On-Demand
1. Check if cached data exists and is < 5 min old
2. If stale/missing, fetch fresh from vnstock
3. Store in DB for baseline comparison
4. Return computed anomalies

## 6. Summary

| Topic | Finding |
|-------|---------|
| Rate limit | ~1 req/sec recommended, no hard docs |
| Intraday data | Current session only, tick-level |
| Storage | PostgreSQL upsert pattern works well |
| Main gap | No delay in current batch collection |

## Unresolved Questions

1. Exact rate limit thresholds for VCI source
2. Behavior during market holidays/half-days
3. Whether rate limits are per-IP or per-session
4. Maximum concurrent connections allowed
