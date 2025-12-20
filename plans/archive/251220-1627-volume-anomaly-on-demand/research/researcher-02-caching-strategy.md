# Caching Strategy for On-Demand Volume Anomaly Detection

**Date:** 2024-12-20
**Scope:** In-memory caching for FastAPI volume anomaly endpoints

---

## 1. In-Memory Caching Options

### Option A: `functools.lru_cache` (Already in codebase)
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_cached_data(symbol: str) -> dict:
    return fetch_data(symbol)
```
**Pros:** Built-in, zero deps, simple
**Cons:** No TTL, no async support, cache forever until evicted by LRU

### Option B: `cachetools.TTLCache` (Recommended)
```python
from cachetools import TTLCache, cached

cache = TTLCache(maxsize=100, ttl=300)  # 5 min TTL

@cached(cache)
def get_volume_data(symbol: str) -> dict:
    return fetch_data(symbol)
```
**Pros:** TTL support, flexible, well-maintained
**Cons:** Extra dependency, sync-only decorator

### Option C: `fastapi-cache2` with InMemoryBackend
```python
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache

FastAPICache.init(InMemoryBackend(), prefix="volume")

@app.get("/volume/{symbol}")
@cache(expire=300)
async def get_volume(symbol: str):
    return await fetch_data(symbol)
```
**Pros:** Native FastAPI integration, async, HTTP cache headers
**Cons:** More setup, another dependency

---

## 2. Recommendation: Custom TTLCache with Trading Hours Logic

Best approach: **cachetools.TTLCache** with custom wrapper for trading hours awareness.

```python
from cachetools import TTLCache
from datetime import datetime
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Cache config
CACHE_TTL_TRADING = 60      # 1 min during trading
CACHE_TTL_OFF_HOURS = 3600  # 1 hour outside trading

cache = TTLCache(maxsize=200, ttl=CACHE_TTL_TRADING)
```

---

## 3. Vietnam Trading Hours Detection

```python
from datetime import datetime, time
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
MARKET_OPEN = time(9, 0)
MARKET_CLOSE = time(15, 0)

def is_trading_hours() -> bool:
    """Check if current time is within VN market hours."""
    now = datetime.now(VN_TZ)
    # Mon=0, Fri=4
    if now.weekday() > 4:  # Weekend
        return False
    current_time = now.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE

def get_cache_ttl() -> int:
    """Dynamic TTL based on trading hours."""
    return 60 if is_trading_hours() else 3600
```

---

## 4. Freshness Check Logic

### Decision Matrix

| Condition | Action | TTL |
|-----------|--------|-----|
| Trading hours + cache miss | Fetch fresh | 60s |
| Trading hours + cache hit < 60s | Use cache | - |
| Off-hours + cache miss | Fetch once | 3600s |
| Off-hours + cache hit | Use cache | - |
| Weekend | Use last Friday data | 86400s |

### Implementation Pattern

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class CachedData:
    data: dict
    fetched_at: datetime

class VolumeCache:
    def __init__(self):
        self._cache: dict[str, CachedData] = {}

    def get(self, symbol: str) -> Optional[dict]:
        entry = self._cache.get(symbol)
        if not entry:
            return None

        age = (datetime.now(VN_TZ) - entry.fetched_at).total_seconds()
        ttl = get_cache_ttl()

        if age > ttl:
            return None  # Expired
        return entry.data

    def set(self, symbol: str, data: dict):
        self._cache[symbol] = CachedData(
            data=data,
            fetched_at=datetime.now(VN_TZ)
        )

    def is_stale(self, symbol: str) -> bool:
        """Check if data needs refresh."""
        entry = self._cache.get(symbol)
        if not entry:
            return True

        age = (datetime.now(VN_TZ) - entry.fetched_at).total_seconds()
        return age > get_cache_ttl()
```

---

## 5. API Rate Limiting Strategy

To avoid hammering vnstock API:

```python
import asyncio
from datetime import datetime

class RateLimiter:
    def __init__(self, calls_per_minute: int = 30):
        self.calls_per_minute = calls_per_minute
        self.call_times: list[datetime] = []
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = datetime.now()
            # Remove calls older than 1 minute
            self.call_times = [t for t in self.call_times
                              if (now - t).total_seconds() < 60]

            if len(self.call_times) >= self.calls_per_minute:
                wait_time = 60 - (now - self.call_times[0]).total_seconds()
                await asyncio.sleep(wait_time)

            self.call_times.append(datetime.now())
```

---

## 6. Recommended Implementation

```python
# src/stocks/price/cache.py
from cachetools import TTLCache
from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import Optional, Any

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

class TradingHoursCache:
    """Cache with trading-hours-aware TTL."""

    MARKET_OPEN = time(9, 0)
    MARKET_CLOSE = time(15, 0)
    TTL_TRADING = 60
    TTL_OFF_HOURS = 3600

    def __init__(self, maxsize: int = 200):
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._maxsize = maxsize

    def _is_trading_hours(self) -> bool:
        now = datetime.now(VN_TZ)
        if now.weekday() > 4:
            return False
        return self.MARKET_OPEN <= now.time() <= self.MARKET_CLOSE

    def _get_ttl(self) -> int:
        return self.TTL_TRADING if self._is_trading_hours() else self.TTL_OFF_HOURS

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None
        data, timestamp = self._cache[key]
        age = (datetime.now(VN_TZ) - timestamp).total_seconds()
        if age > self._get_ttl():
            del self._cache[key]
            return None
        return data

    def set(self, key: str, value: Any):
        if len(self._cache) >= self._maxsize:
            # Evict oldest
            oldest = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest]
        self._cache[key] = (value, datetime.now(VN_TZ))

# Global instance
volume_cache = TradingHoursCache(maxsize=200)
```

---

## 7. Summary

| Component | Choice | Reason |
|-----------|--------|--------|
| Cache lib | cachetools or custom | TTL support, lightweight |
| TTL trading | 60s | Fresh data during market |
| TTL off-hours | 3600s | Reduce API calls |
| Rate limit | 30 calls/min | Protect vnstock API |
| Timezone | Asia/Ho_Chi_Minh | VN market hours |

---

## Unresolved Questions

1. Should cache persist across server restarts? (Redis vs in-memory)
2. How to handle market holidays? (Need holiday calendar)
3. Should different symbols have different TTLs based on liquidity?
