---
title: "On-Demand Volume Anomaly Data Collection"
description: "Auto-collect intraday data when user requests volume anomalies for a symbol"
status: completed
priority: P1
effort: 4h
branch: main
tags: [volume-anomaly, caching, on-demand, intraday, upstash-redis]
created: 2025-12-20
---

# On-Demand Volume Anomaly Data Collection

## Overview

Implement automatic data collection when user requests `/stocks/{symbol}/volume-anomalies`. If data is stale or missing, fetch from vnstock API, save to DB, then return results.

## Problem Statement

Current endpoint requires pre-collected data. Users get empty results if data hasn't been collected for a symbol.

## Solution

1. Add Upstash Redis-backed `TradingHoursCache` with dynamic TTL (60s trading, 3600s off-hours)
2. Modify endpoint to check freshness and auto-collect when needed
3. Return cached/DB results when fresh

## Architecture

```
Request → Check Upstash Redis → Fresh? → Return cached results
                            ↓ Stale
              Collect from vnstock → Save to DB → Update Upstash → Return
```

## Research Reports

- [vnstock API Research](research/researcher-01-vnstock-api.md) - Rate limits, intraday availability
- [Caching Strategy](research/researcher-02-caching-strategy.md) - TTL logic, trading hours detection

## Phases

| Phase | Description | Effort | Status | Link |
|-------|-------------|--------|--------|------|
| 01 | Upstash Redis TradingHoursCache | 1.5h | completed (2025-12-20) | [phase-01](phase-01-trading-hours-cache.md) |
| 02 | On-demand collector integration | 1.5h | completed (2025-12-20) | [phase-02](phase-02-on-demand-collector.md) |
| 03 | Testing | 1h | completed (2025-12-20) | [phase-03](phase-03-testing.md) |

## Key Files

- `src/core/redis.py` - Upstash Redis client setup
- `src/stocks/price/cache.py` - TradingHoursCache using Upstash
- `src/stocks/price/router.py` - Modified endpoint
- `src/stocks/intraday_collector.py` - Existing collector (no changes)

## Dependencies

```
upstash-redis>=1.0.0
```

## Environment Variables

```
UPSTASH_REDIS_REST_URL=https://xxx.upstash.io
UPSTASH_REDIS_REST_TOKEN=AXxxxx
```

## Success Criteria

1. Endpoint auto-collects data for symbols without prior collection
2. Cache respects trading hours (60s during, 3600s outside)
3. No duplicate API calls within TTL window
4. Cache persists across server restarts (Upstash Redis)
5. Existing functionality preserved

## Risks

| Risk | Mitigation |
|------|------------|
| vnstock rate limiting | 1s delay between calls, cache aggressively |
| Slow first request | Accept ~2-3s latency for fresh collection |
| Market holidays | Use off-hours TTL (acceptable for MVP) |
| Upstash unavailable | Fallback to direct DB query |

## Validation Summary

**Validated:** 2025-12-20
**Questions asked:** 5

### Confirmed Decisions
- TTL Strategy: 60s trading / 3600s off-hours
- Error Handling: Graceful fallback to historical data
- First Request Latency: Accept 2-3s (no pre-warming)
- Cache Backend: **Upstash Redis** (serverless, persists across restarts)
- Holiday Detection: Skip for MVP (use off-hours TTL)
