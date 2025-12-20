---
phase: 01
title: "Extended Caching for High-Traffic Endpoints"
description: "Cache market-indices, price-board, symbols, and sector-performance endpoints"
priority: P1
status: completed
effort: 2h
date: 2024-12-20
date_completed: 2024-12-20
---

# Phase 01: Extended Caching Implementation

## Context

**Plan:** `/Users/typham/Documents/GitHub/Stock_Massive/plans/251220-1800-upstash-redis-caching-ratelimit/plan.md`

**Research:** `/Users/typham/Documents/GitHub/Stock_Massive/plans/251220-1800-upstash-redis-caching-ratelimit/research/researcher-01-caching-patterns.md`

**Reference Implementation:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/cache.py` (TradingHoursCache)

## Overview

Extend Redis caching to 4 high-traffic endpoints using trading-hours-aware TTL strategy. Follow existing `TradingHoursCache` pattern with endpoint-specific TTL configurations.

## Requirements

### Endpoints to Cache

| Endpoint | Router | Lines | TTL Trading | TTL Off-Hours | Rationale |
|----------|--------|-------|-------------|---------------|-----------|
| `/market-indices` | price/router.py | 62-69 | 30s | 3600s | Real-time indices during trading |
| `/price-board` | price/router.py | 72-89 | 15s | 3600s | Most volatile, needs freshest data |
| `/symbols` | market/router.py | 18-27 | 3600s | 86400s | Static data, rarely changes |
| `/sector-performance` | market/router.py | 53-60 | 300s | 3600s | Aggregated data, moderate freshness |

### Cache Key Naming Convention

```
stock:{feature}:{identifier}
```

Examples:
- `stock:indices:all`
- `stock:price_board:VCB,ACB,TCB`
- `stock:symbols:HOSE`
- `stock:sector:performance`

## Related Code Files

**Core:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/redis.py` - Redis client singleton
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/config.py` - Redis config

**Cache:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/cache.py` - Existing TradingHoursCache

**Routers:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/router.py` - market-indices, price-board
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/market/router.py` - symbols, sector-performance

## Implementation Steps

### Step 1: Create Generic Cache Class

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/cache.py` (NEW)

Create reusable cache class with configurable TTL:

```python
"""Generic trading-hours-aware cache for stock market data."""
import json
import logging
from datetime import datetime, time
from typing import Any, Optional
from zoneinfo import ZoneInfo

from src.core.redis import get_redis

logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class TradingHoursCache:
    """Cache with trading-hours-aware TTL using Upstash Redis.

    Args:
        key_prefix: Redis key prefix (e.g., "stock:indices:")
        ttl_trading: TTL in seconds during trading hours
        ttl_off_hours: TTL in seconds outside trading hours
    """

    MARKET_OPEN = time(9, 0)
    MARKET_CLOSE = time(15, 0)

    def __init__(
        self,
        key_prefix: str,
        ttl_trading: int,
        ttl_off_hours: int,
    ):
        self.key_prefix = key_prefix
        self.ttl_trading = ttl_trading
        self.ttl_off_hours = ttl_off_hours

    def _is_trading_hours(self) -> bool:
        """Check if current time is within VN market hours."""
        now = datetime.now(VN_TZ)
        if now.weekday() > 4:  # Weekend (Sat=5, Sun=6)
            return False
        return self.MARKET_OPEN <= now.time() <= self.MARKET_CLOSE

    def _get_ttl(self) -> int:
        """Get TTL based on current trading status."""
        return self.ttl_trading if self._is_trading_hours() else self.ttl_off_hours

    def get(self, key: str) -> Optional[Any]:
        """Get cached data from Upstash Redis."""
        redis = get_redis()
        if not redis:
            return None

        try:
            full_key = f"{self.key_prefix}{key}"
            data = redis.get(full_key)
            if data is None:
                return None
            # Upstash returns string, parse JSON
            if isinstance(data, str):
                return json.loads(data)
            return data
        except Exception as e:
            logger.warning(f"Redis GET error for {key}: {e}")
            return None

    def set(self, key: str, value: Any) -> None:
        """Store data in Upstash Redis with dynamic TTL."""
        redis = get_redis()
        if not redis:
            return

        try:
            full_key = f"{self.key_prefix}{key}"
            ttl = self._get_ttl()
            # Serialize to JSON and set with expiration
            redis.set(full_key, json.dumps(value, default=str), ex=ttl)
        except Exception as e:
            logger.warning(f"Redis SET error for {key}: {e}")

    def delete(self, key: str) -> None:
        """Delete cached data."""
        redis = get_redis()
        if not redis:
            return

        try:
            full_key = f"{self.key_prefix}{key}"
            redis.delete(full_key)
        except Exception as e:
            logger.warning(f"Redis DELETE error for {key}: {e}")
```

**Actions:**
- Create new file `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/cache.py`
- Copy and adapt from existing `price/cache.py`
- Make TTL configurable via constructor

### Step 2: Update Existing Volume Anomaly Cache

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/cache.py`

Refactor to use new generic cache class:

```python
"""Volume anomaly cache using generic TradingHoursCache."""
from src.core.cache import TradingHoursCache

# Global instance for volume anomaly caching
volume_anomaly_cache = TradingHoursCache(
    key_prefix="stock:volume_anomaly:",
    ttl_trading=60,
    ttl_off_hours=3600,
)
```

**Actions:**
- Replace class definition with import
- Instantiate with specific TTL values
- Keep same interface (backward compatible)

### Step 3: Cache Market Indices Endpoint

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/router.py`

**Current code (lines 62-69):**
```python
@router.get("/market-indices", response_model=List[MarketIndexItem])
async def get_market_indices() -> List[MarketIndexItem]:
    """Get market indices data (VN-INDEX, VN30, HNX-INDEX, UPCOM-INDEX)."""
    try:
        service = get_stock_service()
        return service.get_market_indices()
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

**Updated code:**
```python
from src.core.cache import TradingHoursCache

# Cache instance at module level
market_indices_cache = TradingHoursCache(
    key_prefix="stock:indices:",
    ttl_trading=30,
    ttl_off_hours=3600,
)

@router.get("/market-indices", response_model=List[MarketIndexItem])
async def get_market_indices() -> List[MarketIndexItem]:
    """Get market indices data (VN-INDEX, VN30, HNX-INDEX, UPCOM-INDEX)."""
    cache_key = "all"

    # Check cache first
    cached = market_indices_cache.get(cache_key)
    if cached is not None:
        return [MarketIndexItem(**item) for item in cached]

    # Cache miss - fetch from service
    try:
        service = get_stock_service()
        result = service.get_market_indices()

        # Cache the result (serialize to dict)
        market_indices_cache.set(cache_key, [item.model_dump() for item in result])

        return result
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

**Actions:**
- Add cache instance at module level
- Wrap endpoint with cache check
- Serialize Pydantic models to dict for caching

### Step 4: Cache Price Board Endpoint

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/router.py`

**Current code (lines 72-89):**
```python
@router.get("/price-board", response_model=List[PriceBoardItem])
async def get_price_board(
    symbols: str = Query(..., description="Comma-separated list of symbols (e.g., VCB,ACB,TCB)"),
) -> List[PriceBoardItem]:
    """Get real-time price board for multiple stocks."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    if not symbol_list:
        raise HTTPException(status_code=400, detail="At least one symbol is required")

    if len(symbol_list) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols allowed")

    try:
        service = get_stock_service()
        return service.get_price_board(symbol_list)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

**Updated code:**
```python
# Cache instance at module level
price_board_cache = TradingHoursCache(
    key_prefix="stock:price_board:",
    ttl_trading=15,
    ttl_off_hours=3600,
)

@router.get("/price-board", response_model=List[PriceBoardItem])
async def get_price_board(
    symbols: str = Query(..., description="Comma-separated list of symbols (e.g., VCB,ACB,TCB)"),
) -> List[PriceBoardItem]:
    """Get real-time price board for multiple stocks."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    if not symbol_list:
        raise HTTPException(status_code=400, detail="At least one symbol is required")

    if len(symbol_list) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols allowed")

    # Use sorted symbols as cache key for consistency
    cache_key = ",".join(sorted(symbol_list))

    # Check cache first
    cached = price_board_cache.get(cache_key)
    if cached is not None:
        return [PriceBoardItem(**item) for item in cached]

    # Cache miss - fetch from service
    try:
        service = get_stock_service()
        result = service.get_price_board(symbol_list)

        # Cache the result
        price_board_cache.set(cache_key, [item.model_dump() for item in result])

        return result
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

**Actions:**
- Add cache instance with 15s trading TTL (most volatile)
- Sort symbols for consistent cache keys
- Handle variable symbol combinations

### Step 5: Cache Symbols Endpoint

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/market/router.py`

**Current code (lines 18-27):**
```python
@router.get("/symbols", response_model=List[StockSymbol])
async def list_symbols(
    exchange: Optional[str] = Query(None, description="Filter by exchange: HOSE, HNX, UPCOM"),
) -> List[StockSymbol]:
    """List all available stock symbols."""
    try:
        service = get_stock_service()
        return service.list_symbols(exchange=exchange)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

**Updated code:**
```python
from src.core.cache import TradingHoursCache

# Cache instance at module level
symbols_cache = TradingHoursCache(
    key_prefix="stock:symbols:",
    ttl_trading=3600,
    ttl_off_hours=86400,
)

@router.get("/symbols", response_model=List[StockSymbol])
async def list_symbols(
    exchange: Optional[str] = Query(None, description="Filter by exchange: HOSE, HNX, UPCOM"),
) -> List[StockSymbol]:
    """List all available stock symbols."""
    cache_key = exchange or "all"

    # Check cache first
    cached = symbols_cache.get(cache_key)
    if cached is not None:
        return [StockSymbol(**item) for item in cached]

    # Cache miss - fetch from service
    try:
        service = get_stock_service()
        result = service.list_symbols(exchange=exchange)

        # Cache the result
        symbols_cache.set(cache_key, [item.model_dump() for item in result])

        return result
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

**Actions:**
- Add cache with long TTL (static data)
- Cache per exchange filter
- Handle optional exchange parameter

### Step 6: Cache Sector Performance Endpoint

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/market/router.py`

**Current code (lines 53-60):**
```python
@router.get("/sector-performance", response_model=SectorPerformanceResponse)
async def get_sector_performance() -> SectorPerformanceResponse:
    """Get market-cap weighted sector performance (ICB Level 2)."""
    try:
        service = get_stock_service()
        return service.get_sector_performance()
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

**Updated code:**
```python
# Cache instance at module level
sector_performance_cache = TradingHoursCache(
    key_prefix="stock:sector:",
    ttl_trading=300,
    ttl_off_hours=3600,
)

@router.get("/sector-performance", response_model=SectorPerformanceResponse)
async def get_sector_performance() -> SectorPerformanceResponse:
    """Get market-cap weighted sector performance (ICB Level 2)."""
    cache_key = "performance"

    # Check cache first
    cached = sector_performance_cache.get(cache_key)
    if cached is not None:
        return SectorPerformanceResponse(**cached)

    # Cache miss - fetch from service
    try:
        service = get_stock_service()
        result = service.get_sector_performance()

        # Cache the result
        sector_performance_cache.set(cache_key, result.model_dump())

        return result
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

**Actions:**
- Add cache with 5min trading TTL
- Cache single response object
- Handle SectorPerformanceResponse model

## Todo List

- [ ] Create `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/cache.py` with generic TradingHoursCache
- [ ] Refactor `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/cache.py` to use generic class
- [ ] Add caching to `/market-indices` endpoint in price/router.py
- [ ] Add caching to `/price-board` endpoint in price/router.py
- [ ] Add caching to `/symbols` endpoint in market/router.py
- [ ] Add caching to `/sector-performance` endpoint in market/router.py
- [ ] Test all endpoints with Redis enabled
- [ ] Test all endpoints with Redis disabled (graceful degradation)
- [ ] Verify TTL behavior during/outside trading hours
- [ ] Monitor cache hit rates in logs

## Success Criteria

- [ ] All 4 endpoints return cached data on subsequent requests
- [ ] Cache keys follow naming convention: `stock:{feature}:{identifier}`
- [ ] TTL switches correctly based on trading hours
- [ ] App works without Redis (graceful degradation)
- [ ] No breaking changes to API responses
- [ ] Existing volume-anomaly cache still works
- [ ] Cache hit rate > 70% during trading hours

## Testing Checklist

**Functional:**
- [ ] `/market-indices` returns same data from cache
- [ ] `/price-board?symbols=VCB,ACB` caches correctly
- [ ] `/symbols` caches all exchanges
- [ ] `/symbols?exchange=HOSE` caches per exchange
- [ ] `/sector-performance` returns cached response

**Non-Functional:**
- [ ] Response time < 50ms for cached requests
- [ ] Redis errors logged but don't break app
- [ ] TTL = 30s for indices during trading hours
- [ ] TTL = 3600s for indices outside trading hours

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Cache stampede on popular endpoints | Medium | Low | Staggered TTL, short durations |
| Stale data during volatile markets | Medium | Medium | Short TTL (15-30s) during trading |
| Redis connection failures | Low | Low | Graceful degradation pattern |
| Memory usage on Redis | Low | Low | Short TTL, automatic expiration |
| Breaking existing volume cache | High | Low | Backward compatible refactor |

## Rollback Plan

If issues arise:
1. Remove cache checks from endpoints (revert to direct service calls)
2. Keep generic cache class for future use
3. Existing volume-anomaly cache unaffected

## Notes

- Follow existing pattern from volume-anomaly cache
- All cache operations wrapped in try-except
- Log cache hits/misses for monitoring
- Pydantic models serialized to dict before caching
- Cache keys use sorted symbols for consistency
