# VCI API Rate Limits & Caching Strategies

**Research Date:** 2025-12-28
**Focus:** vnstock VCI source rate limits, batch fetching, caching for sector peers

---

## 1. VCI API Rate Limits (2025)

### Observed Limits
- **60 requests/minute** (1 req/sec sustained)
- **3000 requests/hour** (50 req/min average)
- Per-source limits (VCI separate from TCBS)
- HTTP 429 error when exceeded
- vnstock shows "RateLimitExceed", recommends 15s retry

### Implications for Sector Comparison
- **Sector with 20 peers:** 20 API calls
- **At 1 req/sec:** 20 seconds total (safe)
- **5 sectors loaded:** 100 calls = ~2 minutes (risky)
- **Risk:** User browsing multiple sectors hits hourly cap quickly

### Mitigation Options
- Sponsorship package: 10x limit increase (600 req/min)
- Not recommended for MVP due to cost
- Focus on smart caching + batch strategies

---

## 2. Existing Codebase Infrastructure

### Current Implementation (Strengths)
```
apps/api/src/core/cache.py → TradingHoursCache
apps/api/src/core/vnstock_wrapper.py → safe_vnstock_call
```

**TradingHoursCache Features:**
- Upstash Redis backend (production-ready)
- Trading hours aware (9:00-15:00 VN)
- Dynamic TTL: `ttl_trading` vs `ttl_off_hours`
- JSON serialization with `default=str`
- Prefix-based key management

**safe_vnstock_call Features:**
- SystemExit protection (vnstock kills app on 429)
- Exponential backoff: 2s → 4s → 8s → 16s
- Adaptive delay based on failure tracking
- Max 3 retries default

### Gaps
- No batch fetching primitives
- No multi-symbol caching utilities
- No pre-warming strategies
- No sector-level cache invalidation

---

## 3. Recommended Caching Strategy

### A. Cache-Aside Pattern (Already Used)
```
1. Check cache → hit: return
2. Cache miss → fetch from VCI
3. Store in cache with TTL
4. Return data
```

### B. TTL Configuration for Sector Data

**Financial Statements (Quarterly):**
- Trading hours: 4 hours (data rarely changes intraday)
- Off hours: 24 hours (safe until next trading day)

**Sector Peers List:**
- Trading hours: 8 hours (sector composition stable)
- Off hours: 7 days (very stable)

**Peer FCF/Metrics:**
- Trading hours: 6 hours (same as financial data)
- Off hours: 24 hours

**Why These TTLs:**
- Financial data updates quarterly, not intraday
- Sector peers change rarely (quarterly rebalance)
- Off-hours can cache longer (no new data)

---

## 4. Batch Fetching Strategies

### Strategy 1: Sequential with Delay (Safest)
```python
def fetch_sector_peers_sequential(symbols: list[str], delay: float = 1.2):
    """Fetch peers with inter-request delay to respect rate limits."""
    results = {}
    for symbol in symbols:
        cached = cache.get(symbol)
        if cached:
            results[symbol] = cached
            continue

        # Fetch from API
        data = safe_vnstock_call(fetch_financial_data, symbol)
        if data:
            cache.set(symbol, data)
            results[symbol] = data

        time.sleep(delay)  # 1.2s = 50 req/min safe margin

    return results
```

**Pros:** Safe, never hits rate limit
**Cons:** 20 symbols × 1.2s = 24s latency
**Use Case:** Background jobs, pre-warming

### Strategy 2: Parallel with Semaphore (Faster)
```python
async def fetch_sector_peers_parallel(symbols: list[str], concurrency: int = 3):
    """Fetch with limited concurrency to stay under 60/min limit."""
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_one(symbol):
        async with semaphore:
            # Check cache first
            cached = cache.get(symbol)
            if cached:
                return symbol, cached

            # Fetch from API with delay
            await asyncio.sleep(1.2)  # Rate limit protection
            data = await async_safe_vnstock_call(fetch_financial_data, symbol)
            if data:
                cache.set(symbol, data)
            return symbol, data

    results = await asyncio.gather(*[fetch_one(s) for s in symbols])
    return dict(results)
```

**Pros:** 20 symbols in ~8s (3 concurrent batches)
**Cons:** More complex, needs async vnstock wrapper
**Use Case:** On-demand sector loads with cache misses

### Strategy 3: Cache-First Hybrid (Recommended)
```python
def fetch_sector_peers_hybrid(symbols: list[str]):
    """Immediate cache response, background refresh if needed."""
    # Phase 1: Return all cached immediately
    cached_results = {s: cache.get(s) for s in symbols if cache.get(s)}

    # Phase 2: Identify missing
    missing = [s for s in symbols if s not in cached_results]

    if not missing:
        return cached_results

    # Phase 3: Background job for missing (async task)
    schedule_background_fetch(missing)

    # Return partial results immediately
    return cached_results
```

**Pros:** Instant UX, progressive enhancement
**Cons:** Partial data on first load
**Use Case:** Dashboard initial load

---

## 5. Pre-Warming Cache Strategy

### When to Pre-Warm
- Daily at 8:00 AM (before market open)
- After market close (3:30 PM) for next day
- On sector composition changes

### What to Pre-Warm
**Tier 1: Top 30 VN30 stocks**
- Financial statements (quarterly)
- FCF metrics
- Estimated: 30 stocks × 2 calls = 60 calls (~1 min)

**Tier 2: Common sectors (5-7 sectors)**
- Technology, Banking, Real Estate, Manufacturing, Retail
- ~100 unique symbols × 2 calls = 200 calls (~4 min)

**Tier 3: Full peer data (on-demand)**
- All stocks with sector classification
- Run weekly or on-demand

### Implementation Approach
```python
# apps/api/src/stocks/jobs.py (already has APScheduler)

@scheduler.scheduled_job("cron", hour=8, minute=0)
async def prewarm_sector_cache():
    """Pre-warm cache for popular stocks before market open."""
    # Tier 1: VN30
    vn30_symbols = await get_vn30_symbols()
    await fetch_sector_peers_sequential(vn30_symbols, delay=1.0)

    # Tier 2: Top sectors (with longer delay to avoid hourly cap)
    top_sector_symbols = await get_top_sector_symbols(limit=100)
    await fetch_sector_peers_sequential(top_sector_symbols, delay=1.5)

    logger.info(f"Pre-warmed cache for {len(vn30_symbols) + len(top_sector_symbols)} symbols")
```

---

## 6. Implementation Recommendations

### Phase 1: Leverage Existing (Immediate)
- Use `TradingHoursCache` with sector-specific prefixes
- Key pattern: `sector:financial:{symbol}`, `sector:peers:{sector_code}`
- TTLs: 4h trading, 24h off-hours

### Phase 2: Batch Fetching (Week 1)
- Implement sequential batch fetcher with adaptive delay
- Use existing `safe_vnstock_call` + `get_adaptive_delay`
- Add progress tracking for UX feedback

### Phase 3: Pre-Warming (Week 2)
- Add daily pre-warm job to `apps/api/src/stocks/jobs.py`
- Start with VN30 only (30 stocks, safe)
- Monitor cache hit rate via Redis

### Phase 4: Optimization (Future)
- Async parallel fetching if needed
- Cache warming based on user analytics
- Redis pipeline for multi-set operations

---

## 7. Code Examples

### A. Sector Financial Cache Wrapper
```python
# apps/api/src/stocks/financial/cache.py (new)

from src.core.cache import TradingHoursCache

sector_financial_cache = TradingHoursCache(
    key_prefix="sector:financial:",
    ttl_trading=4 * 3600,   # 4 hours
    ttl_off_hours=24 * 3600 # 24 hours
)

sector_peers_cache = TradingHoursCache(
    key_prefix="sector:peers:",
    ttl_trading=8 * 3600,   # 8 hours
    ttl_off_hours=7 * 86400 # 7 days
)
```

### B. Batch Service Method
```python
# apps/api/src/stocks/financial/service.py

async def get_sector_peer_financials(sector_code: str) -> dict:
    """Get financial data for all peers in sector."""
    # Check sector peers cache
    cached_peers = sector_peers_cache.get(sector_code)
    if cached_peers:
        return cached_peers

    # Get peer symbols (from DB or vnstock)
    peer_symbols = await get_sector_peer_symbols(sector_code)

    # Batch fetch with cache-first
    results = {}
    for symbol in peer_symbols:
        cached = sector_financial_cache.get(symbol)
        if cached:
            results[symbol] = cached
        else:
            # Fetch from vnstock (with delay)
            data = safe_vnstock_call(fetch_financial_health, symbol)
            if data:
                sector_financial_cache.set(symbol, data)
                results[symbol] = data

            await asyncio.sleep(get_adaptive_delay())

    # Cache entire sector result
    sector_peers_cache.set(sector_code, results)
    return results
```

---

## Unresolved Questions

1. **Sector peer source:** Use vnstock `Listing().symbols_by_industries()` or maintain DB?
2. **Cache warming priority:** VN30 only or expand to VN100?
3. **Async vnstock:** Worth wrapping in `asyncio.to_thread()` or keep sync?
4. **Monitoring:** Add Upstash Redis metrics dashboard?
