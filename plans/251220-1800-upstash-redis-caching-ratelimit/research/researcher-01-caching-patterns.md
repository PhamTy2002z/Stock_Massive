# Upstash Redis Caching Patterns for FastAPI

**Research ID:** researcher-01-caching-patterns
**Date:** 2024-12-20
**Focus:** HTTP-based Redis caching patterns for stock market data

---

## 1. HTTP-Based Redis Client Setup

### Installation
```bash
pip install upstash-redis
```

### Client Configuration
```python
from upstash_redis import Redis

# From environment variables (recommended)
redis = Redis.from_env()

# Full configuration with retry settings
redis = Redis(
    url="UPSTASH_REDIS_REST_URL",
    token="UPSTASH_REDIS_REST_TOKEN",
    rest_encoding="base64",      # or None for valid JSON (faster)
    rest_retries=3,              # Retry failed requests
    rest_retry_interval=1        # Wait 1 second between retries
)
```

---

## 2. Cache Key Naming Conventions

### Recommended Prefix Structure
```
{app}:{feature}:{entity}:{identifier}
```

### Stock Market Examples
```python
# Price data
f"stock:price:history:{symbol}"        # VNM historical data
f"stock:price:intraday:{symbol}"       # VNM intraday ticks
f"stock:price:board:{exchange}"        # HOSE price board

# Market indices
f"stock:index:{index_code}"            # VN-INDEX, VN30

# Company data
f"stock:company:{symbol}"              # Company overview
f"stock:financials:{symbol}:{report}"  # income, balance, cashflow

# Sector/market-wide
f"stock:sector:performance"            # Sector performance
f"stock:symbols:all"                   # All symbols list
```

---

## 3. Trading-Hours-Aware TTL Strategies

### Vietnam Stock Market Hours
- **Trading:** 9:00 AM - 3:00 PM (Mon-Fri)
- **Pre-market:** 8:30 AM - 9:00 AM
- **Lunch break:** 11:30 AM - 1:00 PM

### Dynamic TTL Calculator
```python
from datetime import datetime, time
import pytz

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

def get_market_aware_ttl(data_type: str) -> int:
    """Return TTL in seconds based on market hours and data type."""
    now = datetime.now(VN_TZ)
    current_time = now.time()
    weekday = now.weekday()

    # Weekend: cache until Monday 9 AM
    if weekday >= 5:
        return 86400 * (7 - weekday)  # Days until Monday

    market_open = time(9, 0)
    market_close = time(15, 0)
    is_trading = market_open <= current_time <= market_close

    # TTL by data type
    ttl_config = {
        "intraday": 30 if is_trading else 3600,      # 30s during trading
        "price_board": 15 if is_trading else 3600,   # 15s during trading
        "history": 3600 if is_trading else 86400,    # 1h/24h
        "company": 86400,                             # 24h (static)
        "financials": 86400 * 7,                      # 7 days (quarterly)
        "symbols": 86400,                             # 24h
        "sector": 300 if is_trading else 3600,       # 5min/1h
    }

    return ttl_config.get(data_type, 3600)
```

### Setting TTL
```python
# Using SET with EX option
redis.set(f"stock:price:board:HOSE", data, ex=get_market_aware_ttl("price_board"))

# Using SETEX equivalent
redis.set("key", "value", ex=600)  # 10 minutes

# Using EXPIRE separately
redis.set("key", "value")
redis.expire("key", 600)
```

---

## 4. Batch Operations (MGET/MSET) for Cost Optimization

### MSET - Set Multiple Keys
```python
# Set multiple stock prices at once (1 HTTP request)
redis.mset({
    "stock:price:VNM": '{"price": 85000}',
    "stock:price:FPT": '{"price": 120000}',
    "stock:price:VIC": '{"price": 45000}',
})
```

### MGET - Get Multiple Keys
```python
# Fetch multiple stocks in single request
symbols = ["VNM", "FPT", "VIC", "VHM", "HPG"]
keys = [f"stock:price:{s}" for s in symbols]
values = redis.mget(keys)  # Returns list, None for missing keys

# Zip results with symbols
results = dict(zip(symbols, values))
```

### Pipeline for Complex Operations
```python
# Group multiple commands into single HTTP request
pipeline = redis.pipeline()
pipeline.set("stock:price:VNM", data1)
pipeline.set("stock:price:FPT", data2)
pipeline.expire("stock:price:VNM", 300)
pipeline.expire("stock:price:FPT", 300)
pipeline.get("stock:index:VNINDEX")
results = pipeline.exec()
```

---

## 5. Graceful Degradation Patterns

### Error Handling with Fallback
```python
from upstash_redis.errors import UpstashError
from typing import Optional, TypeVar, Callable

T = TypeVar("T")

async def cache_get_or_fetch(
    cache_key: str,
    fetch_fn: Callable[[], T],
    ttl: int = 3600,
    redis_client: Redis = None
) -> T:
    """Get from cache or fetch from source with graceful degradation."""

    # Try cache first
    try:
        cached = redis_client.get(cache_key)
        if cached is not None:
            return cached
    except UpstashError as e:
        # Log error, continue to fetch
        logger.warning(f"Redis error: {e}, falling back to source")
    except Exception as e:
        logger.error(f"Unexpected cache error: {e}")

    # Fetch from source
    data = fetch_fn()

    # Try to cache (non-blocking failure)
    try:
        redis_client.set(cache_key, data, ex=ttl)
    except Exception as e:
        logger.warning(f"Failed to cache: {e}")

    return data
```

### FastAPI Dependency with Fallback
```python
from fastapi import Depends, Request
from functools import lru_cache

def get_redis_client(request: Request) -> Optional[Redis]:
    """Get Redis client with graceful fallback to None."""
    try:
        return Redis.from_env()
    except Exception:
        return None

@app.get("/stock/{symbol}/price")
async def get_stock_price(
    symbol: str,
    redis: Optional[Redis] = Depends(get_redis_client)
):
    cache_key = f"stock:price:{symbol}"

    # Try cache if available
    if redis:
        try:
            cached = redis.get(cache_key)
            if cached:
                return {"source": "cache", "data": cached}
        except Exception:
            pass  # Graceful degradation

    # Fetch from vnstock
    data = fetch_from_vnstock(symbol)

    # Cache if redis available
    if redis:
        try:
            redis.set(cache_key, data, ex=get_market_aware_ttl("price_board"))
        except Exception:
            pass

    return {"source": "api", "data": data}
```

### Circuit Breaker Pattern (Simple)
```python
import time

class RedisCircuitBreaker:
    def __init__(self, failure_threshold=5, reset_timeout=60):
        self.failures = 0
        self.threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure = 0
        self.is_open = False

    def call(self, fn, *args, **kwargs):
        if self.is_open:
            if time.time() - self.last_failure > self.reset_timeout:
                self.is_open = False
                self.failures = 0
            else:
                return None  # Skip Redis call

        try:
            result = fn(*args, **kwargs)
            self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure = time.time()
            if self.failures >= self.threshold:
                self.is_open = True
            raise e
```

---

## 6. FastAPI Integration Pattern

```python
from fastapi import FastAPI
from upstash_redis import Redis
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize Redis
    app.state.redis = Redis.from_env(rest_retries=3, rest_retry_interval=1)
    yield
    # Shutdown: cleanup if needed

app = FastAPI(lifespan=lifespan)

@app.get("/weather/{city}")
def get_weather(city: str):
    cache_key = f"weather:{city}"
    cached = app.state.redis.get(cache_key)
    if cached:
        return {"source": "cache", "data": cached}

    data = fetch_weather_api(city)
    app.state.redis.set(cache_key, data, ex=600)
    return {"source": "api", "data": data}
```

---

## Summary

| Pattern | Use Case | Key Benefit |
|---------|----------|-------------|
| `MGET/MSET` | Batch price fetches | Reduce HTTP requests |
| `Pipeline` | Complex multi-op | Single round-trip |
| Dynamic TTL | Market-aware caching | Fresh data during trading |
| Circuit Breaker | High availability | Prevent cascade failures |
| Graceful Degradation | Resilience | App works without cache |

---

## Unresolved Questions

1. Should we use `rest_encoding=None` for JSON data to improve performance?
2. Optimal retry configuration for Vietnam network conditions?
3. Consider using hash structures (`HSET/HGET`) for grouped stock data vs separate keys?
