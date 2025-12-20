# Brainstorm: Upstash Redis Integration Optimization

**Date:** 2024-12-20
**Status:** Analysis Complete
**Branch:** main

---

## 1. Problem Statement

User wants to expand Upstash Redis integration beyond current volume anomaly caching to include:
- Extended caching (market indices, price board, stock detail)
- Rate limiting (API protection)
- Session/Auth (JWT blacklist, user sessions)
- Real-time features (Pub/Sub for price updates)

**Priorities:** Performance, Cost efficiency, Reliability, Scalability

---

## 2. Current Implementation Analysis

### Existing Redis Setup

| Component | File | Status |
|-----------|------|--------|
| Client singleton | `src/core/redis.py` | ✅ Working |
| Config | `src/core/config.py` | ✅ Supports both naming conventions |
| Cache class | `src/stocks/price/cache.py` | ✅ Trading-hours-aware TTL |
| Usage | `src/stocks/price/router.py` | ✅ Volume anomaly only |

### Current Architecture Strengths
- Graceful degradation (returns None if Redis unavailable)
- Dynamic TTL based on VN market hours (60s trading / 3600s off-hours)
- Singleton pattern prevents connection overhead
- JSON serialization for complex objects

### Current Limitations
- Only caches volume anomaly data
- No rate limiting
- No session management
- No Pub/Sub implementation
- Synchronous client only (blocking I/O)

---

## 3. Evaluated Approaches

### 3.1 Extended Caching

#### Option A: Extend TradingHoursCache (Recommended)
**Pros:**
- Reuse existing pattern
- Minimal code changes
- Consistent TTL strategy

**Cons:**
- Same TTL logic for all endpoints (may not fit all cases)

**Implementation:**
```python
# Add key prefixes for different data types
KEY_PREFIXES = {
    "volume_anomaly": "va:",
    "market_indices": "mi:",
    "price_board": "pb:",
    "stock_detail": "sd:",
    "symbols": "sym:",
}
```

#### Option B: Create Specialized Cache Classes
**Pros:**
- Custom TTL per data type
- More granular control

**Cons:**
- More code duplication
- Higher maintenance

#### Recommendation: Option A
Extend existing `TradingHoursCache` with configurable prefixes and optional custom TTL overrides.

**Suggested TTL Strategy:**

| Endpoint | Trading Hours TTL | Off-Hours TTL | Rationale |
|----------|-------------------|---------------|-----------|
| `/market-indices` | 30s | 3600s | High-frequency updates |
| `/price-board` | 15s | 3600s | Real-time critical |
| `/{symbol}/detail` | 60s | 3600s | Moderate updates |
| `/symbols` | 3600s | 86400s | Rarely changes |
| `/sector-performance` | 300s | 3600s | Aggregated data |

---

### 3.2 Rate Limiting

#### Option A: Custom Python Implementation (Recommended for FastAPI)
**Pros:**
- Native Python, no JS dependency
- Full control over logic
- Uses existing Redis client

**Cons:**
- Need to implement algorithms manually

**Implementation Pattern:**
```python
# Sliding window using Redis INCR + EXPIRE
async def check_rate_limit(key: str, limit: int, window: int) -> bool:
    redis = get_redis()
    current = redis.incr(f"rl:{key}")
    if current == 1:
        redis.expire(f"rl:{key}", window)
    return current <= limit
```

#### Option B: Use upstash-ratelimit (JS only)
**Pros:**
- Battle-tested algorithms
- Analytics built-in

**Cons:**
- TypeScript only, no Python SDK
- Would need separate service or port to JS

#### Recommendation: Option A
Implement simple sliding window in Python. Upstash's ratelimit library is JS-only.

**Suggested Rate Limits:**

| Endpoint Type | Limit | Window | Identifier |
|---------------|-------|--------|------------|
| Public API | 100 | 60s | IP address |
| Authenticated | 500 | 60s | User ID |
| Heavy endpoints (financials) | 20 | 60s | IP + endpoint |

---

### 3.3 Session/Auth

#### Option A: JWT Blacklist Only (Recommended)
**Pros:**
- Minimal Redis usage
- Stateless JWT preserved
- Only store revoked tokens

**Cons:**
- Limited session features

**Implementation:**
```python
# Store revoked JWT IDs with TTL = token expiry
redis.set(f"jwt:blacklist:{jti}", "1", ex=jwt_expire_seconds)
```

#### Option B: Full Session Store
**Pros:**
- Rich session data
- Server-side session control

**Cons:**
- More Redis operations
- Higher cost
- Defeats JWT statelessness

#### Recommendation: Option A
JWT blacklist is sufficient for current auth scaffolding. Full sessions add unnecessary complexity.

---

### 3.4 Real-time Features (Pub/Sub)

#### Option A: Defer Implementation (Recommended)
**Rationale:**
- Upstash Redis Pub/Sub requires persistent connections
- HTTP-based Upstash not ideal for true Pub/Sub
- Current system has no WebSocket infrastructure
- YAGNI: No immediate use case

#### Option B: Use Upstash Realtime (Future)
When WebSocket support is added:
- Consider `@upstash/realtime` for Next.js frontend
- Use Redis Streams instead of Pub/Sub for durability

#### Recommendation: Option A
Defer until WebSocket infrastructure exists. Current polling with caching is sufficient.

---

## 4. Final Recommended Solution

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Rate Limit  │  │   Cache     │  │   JWT Blacklist     │  │
│  │ Middleware  │  │   Layer     │  │   (Auth Module)     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         └────────────────┼─────────────────────┘             │
│                          │                                   │
│                   ┌──────▼──────┐                            │
│                   │ Redis Client│ (src/core/redis.py)        │
│                   │  Singleton  │                            │
│                   └──────┬──────┘                            │
└──────────────────────────┼──────────────────────────────────┘
                           │ HTTPS (REST API)
                    ┌──────▼──────┐
                    │   Upstash   │
                    │    Redis    │
                    └─────────────┘
```

### Implementation Priority

| Priority | Feature | Effort | Impact |
|----------|---------|--------|--------|
| P1 | Extend caching to market-indices, price-board | Low | High |
| P2 | Rate limiting middleware | Medium | High |
| P3 | JWT blacklist | Low | Medium |
| P4 | Real-time (Pub/Sub) | High | Defer |

### Cost Optimization Tips

1. **Batch operations**: Use `MGET`/`MSET` for multiple keys
2. **Appropriate TTLs**: Longer TTL = fewer requests = lower cost
3. **Cache warming**: Pre-populate cache during off-hours
4. **Key compression**: Short prefixes (`va:` vs `volume_anomaly:`)

---

## 5. Implementation Considerations

### New Files to Create
- `src/core/rate_limit.py` - Rate limiting middleware
- `src/core/cache.py` - Generic cache utilities (move from price/cache.py)

### Files to Modify
- `src/stocks/price/router.py` - Add caching to more endpoints
- `src/stocks/market/router.py` - Cache market indices, symbols
- `src/main.py` - Add rate limit middleware

### Environment Variables (Already Configured)
```env
UPSTASH_REDIS_REST_URL=https://xxx.upstash.io
UPSTASH_REDIS_REST_TOKEN=xxx
```

---

## 6. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Redis unavailable | API still works | Graceful degradation (existing) |
| Cache stampede | High load on vnstock | Implement cache locking |
| Rate limit bypass | API abuse | Use IP + fingerprinting |
| Cost overrun | Budget | Monitor Upstash dashboard, set alerts |

---

## 7. Success Metrics

- **Performance**: API response time < 100ms for cached endpoints
- **Cost**: Stay within Upstash free tier (10K commands/day) or budget
- **Reliability**: 99.9% cache hit rate during trading hours
- **Scalability**: Handle 100 concurrent users without degradation

---

## 8. Next Steps

1. **Approve this plan** - Confirm priorities align with goals
2. **Create implementation plan** - Detailed tasks for P1-P3
3. **Implement P1** - Extend caching (1-2 hours)
4. **Implement P2** - Rate limiting (2-3 hours)
5. **Implement P3** - JWT blacklist (1 hour)
6. **Monitor & optimize** - Review Upstash analytics

---

## Unresolved Questions

1. **Rate limit granularity**: Should heavy endpoints (financials) have separate limits?
2. **Cache invalidation**: Manual invalidation needed for symbols list when new stocks added?
3. **Multi-region**: Is single Upstash region sufficient or need global replication?
4. **Async client**: Should we migrate to `upstash_redis.asyncio` for better FastAPI integration?
