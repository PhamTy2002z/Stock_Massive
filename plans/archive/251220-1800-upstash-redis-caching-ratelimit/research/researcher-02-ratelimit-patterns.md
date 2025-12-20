# Rate Limiting Implementation Patterns for FastAPI with Upstash Redis

## Overview

Research on rate limiting patterns using Upstash Redis HTTP-based client with FastAPI, focusing on sliding window algorithm, middleware patterns, and cost-effective implementation.

---

## 1. Sliding Window Algorithm Implementation

### Algorithm Concept
Sliding window combines benefits of fixed window with smoother rate limiting by considering requests from both current and previous windows.

### Calculation Formula
```python
limit = 10
# Requests from old window weighted by remaining time + current window requests
rate = previous_window_requests * ((window_size - elapsed_time) / window_size) + current_window_requests
return rate < limit  # True = allow request
```

### Upstash Python Implementation
```python
from upstash_ratelimit import Ratelimit, SlidingWindow
from upstash_redis import Redis

ratelimit = Ratelimit(
    redis=Redis.from_env(),
    limiter=SlidingWindow(max_requests=10, window=10),  # 10 req per 10 sec
    prefix="@upstash/ratelimit",
)
```

### Available Algorithms
| Algorithm | Use Case | Pros | Cons |
|-----------|----------|------|------|
| **FixedWindow** | Simple rate limiting | Low memory, fast | Burst at window edges |
| **SlidingWindow** | Smooth rate limiting | No edge bursts | Approximation-based |
| **TokenBucket** | Burst-tolerant APIs | Allows controlled bursts | More complex |

---

## 2. FastAPI Middleware Patterns

### Pattern A: Dependency Injection (Recommended)
```python
from fastapi import FastAPI, HTTPException, Depends, Request
from upstash_ratelimit import Ratelimit, SlidingWindow
from upstash_redis import Redis

app = FastAPI()
redis = Redis.from_env()

ratelimit = Ratelimit(
    redis=redis,
    limiter=SlidingWindow(max_requests=100, window=60),
)

async def rate_limit_dependency(request: Request):
    identifier = request.client.host  # IP-based
    response = ratelimit.limit(identifier)
    if not response.allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return response

@app.get("/api/data", dependencies=[Depends(rate_limit_dependency)])
async def get_data():
    return {"data": "result"}
```

### Pattern B: Reusable Rate Limiter Class
```python
class RateLimitDep:
    def __init__(self, max_requests: int, window: int):
        self.limiter = Ratelimit(
            redis=Redis.from_env(),
            limiter=SlidingWindow(max_requests=max_requests, window=window),
        )

    async def __call__(self, request: Request):
        identifier = request.client.host
        response = self.limiter.limit(identifier)
        if not response.allowed:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        return response

# Usage
strict_limit = RateLimitDep(max_requests=10, window=60)
relaxed_limit = RateLimitDep(max_requests=100, window=60)

@app.get("/api/expensive", dependencies=[Depends(strict_limit)])
async def expensive_endpoint():
    return {"result": "expensive operation"}
```

### Pattern C: Multiple Limiters (Tiered)
```python
class MultiRL:
    def __init__(self):
        redis = Redis.from_env()
        self.free = Ratelimit(
            redis=redis,
            limiter=SlidingWindow(max_requests=10, window=60),
            prefix="ratelimit:free",
        )
        self.paid = Ratelimit(
            redis=redis,
            limiter=SlidingWindow(max_requests=100, window=60),
            prefix="ratelimit:paid",
        )

multi_rl = MultiRL()
```

---

## 3. Identifier Strategies

### Strategy Options
| Strategy | Identifier | Use Case |
|----------|------------|----------|
| **IP Address** | `request.client.host` | Public APIs, anonymous users |
| **User ID** | `current_user.id` | Authenticated endpoints |
| **API Key** | `request.headers["X-API-Key"]` | Third-party integrations |
| **Composite** | `f"{user_id}:{endpoint}"` | Per-user per-endpoint limits |

### Implementation Example
```python
def get_identifier(request: Request, user: User = None, api_key: str = None) -> str:
    if api_key:
        return f"apikey:{api_key}"
    if user:
        return f"user:{user.id}"
    return f"ip:{request.client.host}"
```

---

## 4. Response Headers Implementation

### Standard Headers
```python
from fastapi import Response

async def rate_limit_with_headers(request: Request, response: Response):
    identifier = request.client.host
    result = ratelimit.limit(identifier)

    # Set rate limit headers
    response.headers["X-RateLimit-Limit"] = str(result.limit)
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["X-RateLimit-Reset"] = str(result.reset)

    if not result.allowed:
        response.headers["Retry-After"] = str(int(result.reset - time.time()))
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return result
```

### Response Object Properties
- `allowed`: Boolean - request permitted
- `limit`: Total requests allowed in window
- `remaining`: Requests left in current window
- `reset`: Unix timestamp when window resets

---

## 5. Cost-Effective HTTP-Based Redis

### Upstash Advantages
- **Connectionless**: HTTP-based, no persistent connections
- **Pay-per-request**: Only pay for actual Redis commands
- **Serverless-friendly**: No connection pool management
- **Global replication**: Low latency worldwide

### Configuration Best Practices
```python
from upstash_redis import Redis

redis = Redis(
    url="UPSTASH_REDIS_REST_URL",
    token="UPSTASH_REDIS_REST_TOKEN",
    rest_encoding="base64",      # Secure encoding
    rest_retries=3,              # Retry on failure
    rest_retry_interval=1,       # 1 sec between retries
)
```

### Async Client for FastAPI
```python
from upstash_redis.asyncio import Redis

redis = Redis.from_env()

async def rate_limit_async(identifier: str):
    # Async operations for better performance
    result = await ratelimit.limit(identifier)
    return result
```

---

## 6. Complete FastAPI Integration Example

```python
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from upstash_ratelimit import Ratelimit, SlidingWindow
from upstash_redis import Redis
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
redis = Redis.from_env()

ratelimit = Ratelimit(
    redis=redis,
    limiter=SlidingWindow(max_requests=100, window=60),
    prefix="stock_massive:ratelimit",
)

async def rate_limiter(request: Request, response: Response):
    identifier = request.client.host
    result = ratelimit.limit(identifier)

    response.headers["X-RateLimit-Limit"] = str(result.limit)
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["X-RateLimit-Reset"] = str(result.reset)

    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(int(result.reset))}
        )

@app.get("/api/stocks/{symbol}", dependencies=[Depends(rate_limiter)])
async def get_stock(symbol: str):
    return {"symbol": symbol, "price": 150.00}
```

---

## Key Recommendations

1. **Use SlidingWindow** for smooth rate limiting without edge bursts
2. **Dependency injection** pattern for clean, testable code
3. **Composite identifiers** for granular control (user + endpoint)
4. **Always include headers** for client transparency
5. **Async Redis client** for FastAPI performance
6. **Prefix keys** to avoid collisions in shared Redis instances

## Dependencies
```bash
pip install fastapi upstash-redis upstash-ratelimit uvicorn[standard]
```

## Environment Variables
```
UPSTASH_REDIS_REST_URL=https://xxx.upstash.io
UPSTASH_REDIS_REST_TOKEN=AXxxxx
```
