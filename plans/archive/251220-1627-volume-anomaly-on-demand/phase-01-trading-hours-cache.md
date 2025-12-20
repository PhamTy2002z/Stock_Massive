# Phase 01: Upstash Redis TradingHoursCache

## Context

- [Plan Overview](plan.md)
- [Caching Strategy Research](research/researcher-02-caching-strategy.md)

## Overview

Create a trading-hours-aware cache utility using **Upstash Redis** (serverless, HTTP-based). Dynamic TTL based on Vietnam market hours: 60s during trading (09:00-15:00 Mon-Fri), 3600s off-hours.

## Requirements

1. Setup Upstash Redis client with environment variables
2. Detect Vietnam trading hours (Asia/Ho_Chi_Minh timezone)
3. Dynamic TTL: 60s during trading, 3600s off-hours
4. Simple get/set interface using Redis SET with EX option
5. Graceful fallback when Upstash unavailable

## Architecture

```
TradingHoursCache (using Upstash Redis)
├── _is_trading_hours() → bool
├── _get_ttl() → int (60 or 3600)
├── get(key) → Optional[dict]  # Redis GET + JSON decode
├── set(key, value) → None     # Redis SET with dynamic EX
└── delete(key) → None
```

## Related Code Files

| File | Purpose | Action |
|------|---------|--------|
| `src/core/redis.py` | **NEW** - Upstash Redis client setup |
| `src/stocks/price/cache.py` | **NEW** - TradingHoursCache class |
| `src/core/config.py` | Add Upstash env vars | **MODIFY** |
| `requirements.txt` | Add upstash-redis | **MODIFY** |

## Implementation Steps

### Step 1: Add dependency

Add to `requirements.txt`:
```
upstash-redis>=1.0.0
```

### Step 2: Update config.py

Add to `src/core/config.py` Settings class:
```python
# Upstash Redis
upstash_redis_url: str = ""
upstash_redis_token: str = ""
```

### Step 3: Create redis.py

Create `src/core/redis.py`:

```python
"""Upstash Redis client setup."""
import logging
from typing import Optional

from upstash_redis import Redis

from src.core.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: Optional[Redis] = None


def get_redis() -> Optional[Redis]:
    """Get Upstash Redis client singleton.

    Returns None if not configured (graceful degradation).
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    settings = get_settings()

    if not settings.upstash_redis_url or not settings.upstash_redis_token:
        logger.warning("Upstash Redis not configured, caching disabled")
        return None

    try:
        _redis_client = Redis(
            url=settings.upstash_redis_url,
            token=settings.upstash_redis_token,
        )
        logger.info("Upstash Redis client initialized")
        return _redis_client
    except Exception as e:
        logger.error(f"Failed to initialize Upstash Redis: {e}")
        return None
```

### Step 4: Create cache.py

Create `src/stocks/price/cache.py`:

```python
"""Trading-hours-aware cache using Upstash Redis."""
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

    During VN market hours (09:00-15:00 Mon-Fri):
        TTL = 60 seconds (fresh data needed)
    Outside market hours:
        TTL = 3600 seconds (data won't change)
    """

    MARKET_OPEN = time(9, 0)
    MARKET_CLOSE = time(15, 0)
    TTL_TRADING = 60
    TTL_OFF_HOURS = 3600
    KEY_PREFIX = "volume_anomaly:"

    def _is_trading_hours(self) -> bool:
        """Check if current time is within VN market hours."""
        now = datetime.now(VN_TZ)
        if now.weekday() > 4:  # Weekend (Sat=5, Sun=6)
            return False
        return self.MARKET_OPEN <= now.time() <= self.MARKET_CLOSE

    def _get_ttl(self) -> int:
        """Get TTL based on current trading status."""
        return self.TTL_TRADING if self._is_trading_hours() else self.TTL_OFF_HOURS

    def get(self, key: str) -> Optional[Any]:
        """Get cached data from Upstash Redis."""
        redis = get_redis()
        if not redis:
            return None

        try:
            full_key = f"{self.KEY_PREFIX}{key}"
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
            full_key = f"{self.KEY_PREFIX}{key}"
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
            full_key = f"{self.KEY_PREFIX}{key}"
            redis.delete(full_key)
        except Exception as e:
            logger.warning(f"Redis DELETE error for {key}: {e}")


# Global instance for volume anomaly caching
volume_anomaly_cache = TradingHoursCache()
```

## Environment Variables

Add to `.env`:
```
UPSTASH_REDIS_REST_URL=https://your-instance.upstash.io
UPSTASH_REDIS_REST_TOKEN=AXxxxxxxxxxxxxx
```

## Todo List

- [ ] Add `upstash-redis>=1.0.0` to requirements.txt
- [ ] Add Upstash env vars to `src/core/config.py`
- [ ] Create `src/core/redis.py` with client setup
- [ ] Create `src/stocks/price/cache.py` with TradingHoursCache
- [ ] Add `.env` variables for Upstash credentials
- [ ] Test Redis connection

## Success Criteria

1. `get_redis()` returns client when configured, None otherwise
2. `is_trading_hours()` returns True during 09:00-15:00 Mon-Fri VN time
3. `set()` stores data with correct TTL (60s or 3600s)
4. `get()` returns None for expired/missing keys
5. Graceful fallback when Upstash unavailable (no crashes)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Upstash connection failure | Low | Low | Graceful fallback, return None |
| Timezone issues | Low | Medium | Use `zoneinfo.ZoneInfo` (Python 3.9+) |
| JSON serialization errors | Low | Low | Use `default=str` for datetime |

## Notes

- Upstash Redis is HTTP-based, no connection pooling needed
- Key prefix `volume_anomaly:` prevents collision with other caches
- Cache key format: `volume_anomaly:{symbol}:{days}` (e.g., "volume_anomaly:VCB:20")
