---
title: "Upstash Redis Caching & Rate Limiting"
description: "Extend Redis caching to more endpoints and add API rate limiting"
status: completed
priority: P1
effort: 4h
branch: main
tags: [redis, caching, rate-limiting, performance]
created: 2024-12-20
---

# Upstash Redis Caching & Rate Limiting Implementation Plan

## Overview

Extend existing Upstash Redis integration to improve API performance and protect against abuse through comprehensive caching and rate limiting.

## Context

**Research Reports:**
- `/Users/typham/Documents/GitHub/Stock_Massive/plans/251220-1800-upstash-redis-caching-ratelimit/research/researcher-01-caching-patterns.md`
- `/Users/typham/Documents/GitHub/Stock_Massive/plans/251220-1800-upstash-redis-caching-ratelimit/research/researcher-02-ratelimit-patterns.md`

**Existing Implementation:**
- Redis client: `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/redis.py`
- Config: `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/config.py`
- Cache class: `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/cache.py`
- Usage: `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/router.py:129-170`

## Objectives

### Phase 01: Extended Caching (P1)
Cache 4 additional high-traffic endpoints with trading-hours-aware TTL:
- `/market-indices` - Market indices (VN-INDEX, VN30, etc.)
- `/price-board` - Real-time price board
- `/symbols` - Stock symbols list
- `/sector-performance` - Sector performance data

### Phase 02: Rate Limiting (P2)
Implement API rate limiting using `upstash-ratelimit`:
- Public endpoints: 100 req/min per IP
- Heavy endpoints: 20 req/min per IP
- Response headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset

## Architecture Principles

1. **Graceful Degradation** - App works without Redis
2. **Trading-Hours Awareness** - Dynamic TTL based on market hours
3. **Singleton Pattern** - Reuse Redis client instance
4. **Type Safety** - Full type hints on all functions
5. **Logging** - Comprehensive error logging

## Implementation Phases

| Phase | Description | Priority | Effort | Status |
|-------|-------------|----------|--------|--------|
| 01 | Extended Caching | P1 | 2h | completed |
| 02 | Rate Limiting | P2 | 2h | completed |

## Success Criteria

- [x] All 4 endpoints cached with appropriate TTL
- [x] Cache hit rate > 70% during trading hours
- [x] Rate limiting active on all public endpoints
- [x] Zero breaking changes to existing functionality
- [x] All tests passing
- [x] Documentation updated

## Dependencies

**Python Packages:**
```bash
pip install upstash-redis upstash-ratelimit
```

**Environment Variables:**
```env
UPSTASH_REDIS_REST_URL=https://xxx.upstash.io
UPSTASH_REDIS_REST_TOKEN=AXxxxx
```

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Redis downtime | Medium | Graceful degradation pattern |
| Cache stampede | Low | Staggered TTL, trading-hours logic |
| Rate limit false positives | Medium | Conservative limits, monitoring |
| Memory usage | Low | Short TTL, automatic expiration |

## Related Files

**Core:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/redis.py`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/config.py`

**Caching:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/cache.py`

**Routers:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/price/router.py`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/market/router.py`

## Validation Summary

**Validated:** 2024-12-20
**Questions asked:** 7

### Confirmed Decisions
- **TTL Strategy:** Short TTL as planned (15s price-board, 30s indices during trading)
- **Rate Limits:** 100 req/min standard, 20 req/min heavy endpoints
- **Identifier:** IP-based only (sufficient for current public API)
- **Health Endpoints:** Exclude /health, /docs, /openapi.json from rate limiting
- **Cache Location:** Centralize in src/core/cache.py
- **Dependencies:** Use upstash-ratelimit package
- **Execution Order:** Sequential (Phase 01 → Phase 02)

### Action Items
- [x] Add exclusion for health endpoints in rate limiting implementation
- [x] Document rate limit behavior for users behind NAT/proxy

---

## Next Steps

1. ~~Review and approve plan~~ ✅ Validated
2. ~~Execute Phase 01 - Extended Caching~~ ✅ Completed
3. ~~Execute Phase 02 - Rate Limiting~~ ✅ Completed
4. ~~Test and validate~~ ✅ 23 tests passing
5. Deploy to production
