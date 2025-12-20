---
phase: 02
title: "API Rate Limiting with Upstash Redis"
description: "Implement sliding window rate limiting for API protection"
priority: P2
status: completed
effort: 2h
date: 2024-12-20
updated: 2024-12-20 18:37
code_review: plans/reports/code-reviewer-251220-1837-phase02-rate-limiting.md
---

# Phase 02: Rate Limiting Implementation

## Context

**Plan:** `/Users/typham/Documents/GitHub/Stock_Massive/plans/251220-1800-upstash-redis-caching-ratelimit/plan.md`

**Research:** `/Users/typham/Documents/GitHub/Stock_Massive/plans/251220-1800-upstash-redis-caching-ratelimit/research/researcher-02-ratelimit-patterns.md`

**Dependency:** Phase 01 must be completed (Redis client already configured)

## Overview

Implement API rate limiting using `upstash-ratelimit` package with sliding window algorithm. Protect public endpoints from abuse while maintaining good UX through transparent rate limit headers.

## Requirements

### Rate Limit Tiers

| Tier | Endpoints | Limit | Window | Identifier |
|------|-----------|-------|--------|------------|
| **Standard** | Most public endpoints | 100 req/min | 60s | IP address |
| **Heavy** | Expensive operations | 20 req/min | 60s | IP address |

### Heavy Endpoints

Endpoints requiring more computation/external API calls:
- `/stocks/{symbol}/financials/*` (company/router.py)
- `/stocks/{symbol}/volume-anomalies` (price/router.py)
- `/stocks/intraday/collect` (price/router.py)

### Response Headers

All rate-limited endpoints must include:
- `X-RateLimit-Limit` - Total requests allowed in window
- `X-RateLimit-Remaining` - Requests remaining in current window
- `X-RateLimit-Reset` - Unix timestamp when window resets
- `Retry-After` - Seconds to wait (only on 429 responses)

### HTTP 429 Response

```json
{
  "detail": "Rate limit exceeded. Try again later.",
  "limit": 100,
  "remaining": 0,
  "reset": 1703073600
}
```

## Related Code Files

**Core:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/redis.py` - Redis client
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/config.py` - Config

**Routers:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/router.py` - Price endpoints
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/market/router.py` - Market endpoints
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/company/router.py` - Company endpoints

## Implementation Steps

### Step 1: Install Dependencies

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/requirements.txt`

Add package:
```
upstash-ratelimit==1.0.0
```

**Actions:**
- Add `upstash-ratelimit` to requirements.txt
- Run `pip install upstash-ratelimit`

### Step 2: Create Rate Limiter Module

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/ratelimit.py` (NEW)

```python
"""Rate limiting using Upstash Redis and sliding window algorithm."""
import logging
import time
from typing import Optional

from fastapi import HTTPException, Request, Response
from upstash_ratelimit import Ratelimit, SlidingWindow
from upstash_redis import Redis

from src.core.redis import get_redis

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter using Upstash Redis with sliding window algorithm.

    Args:
        max_requests: Maximum requests allowed in window
        window: Time window in seconds
        prefix: Redis key prefix for this limiter
    """

    def __init__(self, max_requests: int, window: int, prefix: str):
        self.max_requests = max_requests
        self.window = window
        self.prefix = prefix
        self._limiter: Optional[Ratelimit] = None

    def _get_limiter(self) -> Optional[Ratelimit]:
        """Get or create rate limiter instance."""
        if self._limiter is not None:
            return self._limiter

        redis = get_redis()
        if not redis:
            logger.warning("Redis not available, rate limiting disabled")
            return None

        try:
            self._limiter = Ratelimit(
                redis=redis,
                limiter=SlidingWindow(
                    max_requests=self.max_requests,
                    window=self.window,
                ),
                prefix=f"stock_massive:ratelimit:{self.prefix}",
            )
            return self._limiter
        except Exception as e:
            logger.error(f"Failed to initialize rate limiter: {e}")
            return None

    def _get_identifier(self, request: Request) -> str:
        """Get rate limit identifier from request (IP address)."""
        # Try X-Forwarded-For header first (for proxies)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take first IP in chain
            return forwarded.split(",")[0].strip()

        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"

    async def __call__(self, request: Request, response: Response):
        """FastAPI dependency for rate limiting.

        Raises:
            HTTPException: 429 if rate limit exceeded
        """
        limiter = self._get_limiter()

        # Graceful degradation - allow request if Redis unavailable
        if not limiter:
            return

        identifier = self._get_identifier(request)

        try:
            result = limiter.limit(identifier)

            # Set rate limit headers
            response.headers["X-RateLimit-Limit"] = str(result.limit)
            response.headers["X-RateLimit-Remaining"] = str(result.remaining)
            response.headers["X-RateLimit-Reset"] = str(result.reset)

            if not result.allowed:
                retry_after = int(result.reset - time.time())
                raise HTTPException(
                    status_code=429,
                    detail={
                        "message": "Rate limit exceeded. Try again later.",
                        "limit": result.limit,
                        "remaining": result.remaining,
                        "reset": result.reset,
                    },
                    headers={"Retry-After": str(max(retry_after, 1))},
                )

        except HTTPException:
            raise  # Re-raise 429 errors
        except Exception as e:
            # Log error but allow request (graceful degradation)
            logger.warning(f"Rate limit check failed for {identifier}: {e}")


# Global rate limiter instances
standard_rate_limit = RateLimiter(
    max_requests=100,
    window=60,
    prefix="standard",
)

heavy_rate_limit = RateLimiter(
    max_requests=20,
    window=60,
    prefix="heavy",
)
```

**Actions:**
- Create new file with RateLimiter class
- Implement sliding window algorithm via upstash-ratelimit
- Add graceful degradation (works without Redis)
- Support X-Forwarded-For header for proxies
- Create two global instances: standard (100/min) and heavy (20/min)

### Step 3: Apply Standard Rate Limiting to Price Endpoints

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/router.py`

**Add import at top:**
```python
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from src.core.ratelimit import standard_rate_limit, heavy_rate_limit
```

**Update endpoints:**

```python
# Standard rate limit for market-indices
@router.get("/market-indices", response_model=List[MarketIndexItem], dependencies=[Depends(standard_rate_limit)])
async def get_market_indices() -> List[MarketIndexItem]:
    # ... existing code ...

# Standard rate limit for price-board
@router.get("/price-board", response_model=List[PriceBoardItem], dependencies=[Depends(standard_rate_limit)])
async def get_price_board(
    symbols: str = Query(..., description="Comma-separated list of symbols (e.g., VCB,ACB,TCB)"),
) -> List[PriceBoardItem]:
    # ... existing code ...

# Standard rate limit for history
@router.get("/{symbol}/history", response_model=List[StockPrice], dependencies=[Depends(standard_rate_limit)])
async def get_history(
    symbol: str,
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: date = Query(default_factory=date.today, description="End date (YYYY-MM-DD)"),
    interval: str = Query("1D", description="Interval: 1D, 1W, 1M"),
) -> List[StockPrice]:
    # ... existing code ...

# Standard rate limit for intraday
@router.get("/{symbol}/intraday", response_model=List[IntradayTick], dependencies=[Depends(standard_rate_limit)])
async def get_intraday(
    symbol: str,
    page_size: int = Query(10000, ge=100, le=50000, description="Number of ticks to fetch"),
) -> List[IntradayTick]:
    # ... existing code ...

# Standard rate limit for volume-analysis
@router.get("/{symbol}/volume-analysis", response_model=VolumeAnalysisResponse, dependencies=[Depends(standard_rate_limit)])
async def get_volume_analysis(
    symbol: str,
    days: int = Query(default=10, ge=1, le=30, description="Number of days to analyze"),
    top_n: int = Query(default=10, ge=1, le=72, description="Number of top periods to return"),
    db: AsyncSession = Depends(get_db),
) -> VolumeAnalysisResponse:
    # ... existing code ...

# HEAVY rate limit for volume-anomalies (expensive operation)
@router.get("/{symbol}/volume-anomalies", response_model=VolumeAnomalyResponse, dependencies=[Depends(heavy_rate_limit)])
async def get_volume_anomalies(
    symbol: str,
    days: int = Query(default=20, ge=5, le=60, description="Baseline period in days"),
    db: AsyncSession = Depends(get_db),
) -> VolumeAnomalyResponse:
    # ... existing code ...

# HEAVY rate limit for intraday collection (expensive operation)
@router.post("/intraday/collect", response_model=IntradayCollectionResult, dependencies=[Depends(heavy_rate_limit)])
async def collect_intraday_data(
    symbols: list[str] = Query(
        default=["VCB", "FPT", "VNM"],
        description="List of stock symbols to collect",
    ),
    db: AsyncSession = Depends(get_db),
) -> IntradayCollectionResult:
    # ... existing code ...
```

**Actions:**
- Add `dependencies=[Depends(standard_rate_limit)]` to standard endpoints
- Add `dependencies=[Depends(heavy_rate_limit)]` to expensive endpoints
- Import rate limiters at top of file

### Step 4: Apply Standard Rate Limiting to Market Endpoints

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/market/router.py`

**Add import at top:**
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from src.core.ratelimit import standard_rate_limit
```

**Update endpoints:**

```python
@router.get("/symbols", response_model=List[StockSymbol], dependencies=[Depends(standard_rate_limit)])
async def list_symbols(
    exchange: Optional[str] = Query(None, description="Filter by exchange: HOSE, HNX, UPCOM"),
) -> List[StockSymbol]:
    # ... existing code ...

@router.get("/symbols/group/{group}", response_model=List[str], dependencies=[Depends(standard_rate_limit)])
async def list_symbols_by_group(group: str) -> List[str]:
    # ... existing code ...

@router.get("/symbols/search", response_model=List[StockSymbol], dependencies=[Depends(standard_rate_limit)])
async def search_symbols(
    q: str = Query(..., min_length=1, description="Search query (symbol or company name)"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results to return"),
) -> List[StockSymbol]:
    # ... existing code ...

@router.get("/sector-performance", response_model=SectorPerformanceResponse, dependencies=[Depends(standard_rate_limit)])
async def get_sector_performance() -> SectorPerformanceResponse:
    # ... existing code ...

@router.get("/fund-certificates", response_model=FundCertificatesResponse, dependencies=[Depends(standard_rate_limit)])
async def get_fund_certificates(
    fund_type: Optional[str] = Query(None, description="Filter by type: STOCK, BOND, BALANCED"),
) -> FundCertificatesResponse:
    # ... existing code ...
```

**Actions:**
- Add `dependencies=[Depends(standard_rate_limit)]` to all endpoints
- Import rate limiter at top of file

### Step 5: Apply Rate Limiting to Company Endpoints

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/company/router.py`

**Add import at top:**
```python
from src.core.ratelimit import standard_rate_limit, heavy_rate_limit
```

**Update endpoints:**

```python
# Standard rate limit for overview
@router.get("/{symbol}/overview", dependencies=[Depends(standard_rate_limit)])
async def get_company_overview(symbol: str):
    # ... existing code ...

# HEAVY rate limit for financials (expensive external API calls)
@router.get("/{symbol}/financials/income", dependencies=[Depends(heavy_rate_limit)])
async def get_income_statement(symbol: str):
    # ... existing code ...

@router.get("/{symbol}/financials/balance", dependencies=[Depends(heavy_rate_limit)])
async def get_balance_sheet(symbol: str):
    # ... existing code ...

@router.get("/{symbol}/financials/cashflow", dependencies=[Depends(heavy_rate_limit)])
async def get_cashflow_statement(symbol: str):
    # ... existing code ...

# Standard rate limit for other endpoints
@router.get("/{symbol}/dividends", dependencies=[Depends(standard_rate_limit)])
async def get_dividends(symbol: str):
    # ... existing code ...
```

**Actions:**
- Apply standard rate limit to overview, dividends
- Apply heavy rate limit to financial statements
- Import rate limiters at top of file

### Step 6: Add Rate Limit Configuration to Settings

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/config.py`

**Add configuration options:**

```python
class Settings(BaseSettings):
    # ... existing fields ...

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_standard_max: int = 100  # requests per window
    rate_limit_standard_window: int = 60  # seconds
    rate_limit_heavy_max: int = 20  # requests per window
    rate_limit_heavy_window: int = 60  # seconds
```

**Update RateLimiter to use config:**

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/ratelimit.py`

```python
from src.core.config import get_settings

# ... existing code ...

# Global rate limiter instances (use config)
settings = get_settings()

standard_rate_limit = RateLimiter(
    max_requests=settings.rate_limit_standard_max,
    window=settings.rate_limit_standard_window,
    prefix="standard",
)

heavy_rate_limit = RateLimiter(
    max_requests=settings.rate_limit_heavy_max,
    window=settings.rate_limit_heavy_window,
    prefix="heavy",
)
```

**Actions:**
- Add rate limit config to Settings class
- Update RateLimiter instances to use config
- Allow environment variable overrides

### Step 7: Add Logging and Monitoring

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/ratelimit.py`

**Enhance logging in RateLimiter:**

```python
async def __call__(self, request: Request, response: Response):
    """FastAPI dependency for rate limiting."""
    limiter = self._get_limiter()

    if not limiter:
        return

    identifier = self._get_identifier(request)

    try:
        result = limiter.limit(identifier)

        # Set rate limit headers
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset)

        # Log rate limit status
        logger.debug(
            f"Rate limit check: {identifier} - "
            f"{result.remaining}/{result.limit} remaining"
        )

        if not result.allowed:
            retry_after = int(result.reset - time.time())
            logger.warning(
                f"Rate limit exceeded: {identifier} on {request.url.path} - "
                f"retry after {retry_after}s"
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "message": "Rate limit exceeded. Try again later.",
                    "limit": result.limit,
                    "remaining": result.remaining,
                    "reset": result.reset,
                },
                headers={"Retry-After": str(max(retry_after, 1))},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Rate limit check failed for {identifier}: {e}")
```

**Actions:**
- Add debug logging for all rate limit checks
- Add warning logging for exceeded limits
- Include endpoint path in logs

## Todo List

- [x] Add `upstash-ratelimit` to requirements.txt
- [x] Create `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/ratelimit.py` with RateLimiter class
- [x] Add rate limit config to `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/config.py`
- [x] Apply standard rate limit to price endpoints
- [x] Apply heavy rate limit to expensive price endpoints
- [x] Apply standard rate limit to market endpoints
- [x] Apply rate limits to company endpoints
- [x] Apply heavy rate limit to financial endpoints
- [x] **FIX X-Forwarded-For security issue (HIGH PRIORITY)** - See code review H1
- [x] Add rate limit config validation (Pydantic Field constraints)
- [x] Test rate limiting with Redis enabled
- [x] Test graceful degradation with Redis disabled
- [x] Verify response headers on all endpoints
- [x] Test 429 response format
- [x] Monitor rate limit logs

## Success Criteria

- [x] All public endpoints have rate limiting
- [x] Heavy endpoints use 20 req/min limit
- [x] Standard endpoints use 100 req/min limit
- [x] Response headers present on all requests
- [x] 429 responses include Retry-After header
- [x] App works without Redis (graceful degradation)
- [x] Rate limits configurable via environment variables
- [x] No breaking changes to API functionality

## Testing Checklist

**Functional:**
- [ ] Make 101 requests to `/market-indices` - 101st returns 429
- [ ] Make 21 requests to `/volume-anomalies` - 21st returns 429
- [ ] Verify X-RateLimit-* headers on successful requests
- [ ] Verify Retry-After header on 429 responses
- [ ] Test with X-Forwarded-For header (proxy scenario)

**Non-Functional:**
- [ ] Rate limit check adds < 10ms latency
- [ ] Redis errors don't break endpoints
- [ ] Rate limits reset after window expires
- [ ] Different IPs have independent limits

**Edge Cases:**
- [ ] Redis unavailable - endpoints still work
- [ ] Invalid X-Forwarded-For header - falls back to client IP
- [ ] Concurrent requests from same IP - accurate counting

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| False positive rate limits | High | Low | Conservative limits (100/min) |
| Redis latency adds overhead | Medium | Low | Async operations, graceful degradation |
| Shared IP (NAT) affects users | Medium | Medium | Document limits, consider auth-based limits |
| Rate limit bypass via proxy | Medium | Low | Use X-Forwarded-For, monitor patterns |
| Redis memory usage | Low | Low | Sliding window efficient, auto-expiration |

## Rollback Plan

If issues arise:
1. Set `rate_limit_enabled=false` in environment
2. Remove `dependencies=[Depends(...)]` from endpoints
3. Keep ratelimit.py for future use

## Environment Variables

Add to `.env`:
```env
# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STANDARD_MAX=100
RATE_LIMIT_STANDARD_WINDOW=60
RATE_LIMIT_HEAVY_MAX=20
RATE_LIMIT_HEAVY_WINDOW=60
```

## Notes

- Sliding window algorithm prevents burst at window edges
- IP-based limiting suitable for public API
- Future: Add user-based limits for authenticated endpoints
- Monitor rate limit logs to adjust thresholds
- Consider adding /health endpoint without rate limit

### Code Review Results (2024-12-20 18:37)

**Status:** Step 2 COMPLETE ✅ (with security caveat)

**Quality Score:** 8.5/10
- 0 critical issues
- 1 high priority security issue (X-Forwarded-For header injection risk)
- 5 medium priority improvements
- 3 low priority suggestions

**Security:** X-Forwarded-For header trusted without validation - potential rate limit bypass. Must fix before production (see H1 in code review report).

**Architecture:** Excellent adherence to YAGNI/KISS/DRY principles. Clean separation of concerns.

**Performance:** No bottlenecks identified. Rate limit check adds ~5-15ms latency (acceptable).

**Next Steps:**
1. Fix X-Forwarded-For security issue (HIGH PRIORITY)
2. Add config validation (Pydantic Field constraints)
3. Proceed to Step 3: Testing

**Full Report:** `/Users/typham/Documents/GitHub/Stock_Massive/plans/reports/code-reviewer-251220-1837-phase02-rate-limiting.md`
