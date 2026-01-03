---
title: "Sector Historical Performance Feature"
description: "Add 1W/2W/1M sector performance chart with top gainers/losers to Overview page"
status: DONE
priority: P2
effort: 6h
branch: main
tags: [feature, frontend, backend, analytics, recharts]
created: 2025-12-30
---

# Sector Historical Performance

## Overview

Thêm section "Hiệu suất ngành theo thời gian" vào trang Overview, hiển thị top 5 ngành tăng và top 5 ngành giảm trong các khoảng thời gian 1 tuần, 2 tuần, 1 tháng.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Scheduled Job (15:45 ICT daily)                            │
│  - Fetch VN100 symbols + ICB mapping                        │
│  - Get historical prices (1W/2W/1M ago + today)             │
│  - Calculate sector avg % change                            │
│  - Cache to Redis (24h TTL)                                 │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│  GET /api/v1/stocks/analytics/sector-historical?period=1W   │
│  - Read from Redis cache                                    │
│  - Return top_gainers[], top_losers[], generated_at         │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│  Frontend Component (SectorHistoricalPerformance)           │
│  - Tabs: 1 Tuần | 2 Tuần | 1 Tháng                          │
│  - Horizontal BarChart (green=gainers, red=losers)          │
└─────────────────────────────────────────────────────────────┘
```

## Phases

| Phase | Description | Effort | Files |
|-------|-------------|--------|-------|
| 1 | Backend: Scheduled Job & Service | 2h | service, jobs, scheduler |
| 2 | Backend: API Endpoint | 1h | router, schemas |
| 3 | Frontend: Component & Hook | 2h | hook, api, component, page |
| 4 | Testing | 1h | tests |

## Key Decisions

1. **Data Source**: VCI only (TCBS discontinued)
2. **Stock Universe**: VN100 (~100 stocks representative)
3. **Rate Limiting**: 1.2s delay between requests (~50 req/min)
4. **Calculation**: Equal-weighted average % change per sector (KISS)
5. **Caching**: Redis 24h TTL (data stale after market close)
6. **Schedule**: 15:45 ICT (after sector-performance job at 15:30)

## Success Criteria

- [x] Daily job runs after market close, completes within 3 min
- [x] API returns top 5 gainers + top 5 losers per period
- [x] Frontend displays horizontal bar chart with tabs
- [x] Error handling for empty data / job failures

## Dependencies

- vnstock (VCI source)
- Redis (Upstash)
- APScheduler
- Recharts (frontend)

## Unresolved Questions

1. **ICB mapping source**: Does `listing.symbols_by_industries()` include VN100 stocks with ICB Level 2?
2. **Market-cap vs Equal weight**: Start with equal-weighted, add market-cap option later if needed
3. **Holiday handling**: Skip weekends, but need Vietnam holiday calendar?

## Phase Files

- [Phase 1: Backend Job & Service](./phase-01-backend-job-service.md)
- [Phase 2: Backend API Endpoint](./phase-02-backend-api-endpoint.md)
- [Phase 3: Frontend Component](./phase-03-frontend-component.md)
- [Phase 4: Testing](./phase-04-testing.md)
