---
feature: Volume Spike Dashboard by Industry
status: pending
priority: P2
created: 2025-12-22
owner: planner-agent
phases: 2
estimated_effort: 3-4 days
---

# Volume Spike Dashboard by Industry - Implementation Plan

## Overview
Dashboard in "Deep Dive" tab showing stocks with volume spikes (>1.5x 20-day avg) in latest session, grouped by ICB Level 2 industry. Enables quick identification of sector-wide volume anomalies.

## Context
- **Research Reports:**
  - [vnstock API Research](/Users/typham/Documents/GitHub/Stock_Massive/plans/251222-2111-volume-spike-dashboard/research/researcher-vnstock-api-report.md)
  - [Frontend Patterns Research](/Users/typham/Documents/GitHub/Stock_Massive/plans/251222-2111-volume-spike-dashboard/research/researcher-frontend-patterns-report.md)
- **Codebase:** FastAPI + Next.js 15 + TanStack Query v5 + ShadCN/UI
- **Data Source:** VCI via vnstock (no built-in volume spike API)

## Key Decisions
| Decision | Value | Rationale |
|----------|-------|-----------|
| UPCOM | Exclude by default | Low liquidity, toggle for advanced users |
| ICB Level | Level 2 default | Balance granularity vs clutter |
| Threshold | 1.5x default | Configurable (1.5x, 2x, 2.5x, 3x) |
| Click Action | Navigate to Deep Dive | Leverage existing detail page |
| Cache Strategy | TradingHoursCache | 5min trading, 1hr off-hours |

## Technical Constraints
- VCI rate limit: 100/60s standard, 20/60s heavy
- No built-in `top.volume()` API - must calculate manually
- Must batch API calls for ~1,700 symbols
- Use existing TradingHoursCache infrastructure

## Implementation Phases

### [Phase 1: Backend API](/Users/typham/Documents/GitHub/Stock_Massive/plans/251222-2111-volume-spike-dashboard/phase-01-backend-api.md)
**Effort:** 1.5-2 days | **Priority:** P0 (blocking)

- New endpoint: `GET /api/v1/stocks/analytics/volume-spikes`
- Custom volume spike calculation (no vnstock built-in)
- ICB industry grouping via `listing.symbols_by_industries()`
- TradingHoursCache integration (5min/1hr TTL)
- Pydantic schemas: `VolumeSpikeItem`, `VolumeSpikeResponse`

### [Phase 2: Frontend Dashboard](/Users/typham/Documents/GitHub/Stock_Massive/plans/251222-2111-volume-spike-dashboard/phase-02-frontend-dashboard.md)
**Effort:** 1.5-2 days | **Priority:** P1

- Component: `volume-spike-dashboard.tsx` in Deep Dive tab
- TanStack Query hook: `useVolumeSpikes(date, minRatio)`
- Collapsible groups by anomaly level (Very High, High, Elevated)
- Recharts visualization (ComposedChart with volume bars)
- Filters: Date, threshold, exchange, UPCOM toggle

## Success Criteria
- [ ] Backend returns volume spikes grouped by ICB Level 2 (<3s response)
- [ ] Frontend displays collapsible industry groups with stock tables
- [ ] Click stock symbol navigates to Deep Dive page
- [ ] Cache reduces API load by 80% during trading hours
- [ ] Handles 1,700+ symbols without timeout

## Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| VCI rate limits | High | Batch requests, exponential backoff |
| Slow calculation | Medium | Cache aggressively, async processing |
| ICB data missing | Low | Fallback to "Uncategorized" group |
| Large payload | Medium | Pagination, limit to top 200 spikes |

## Dependencies
- Existing: `TradingHoursCache`, `listing.symbols_by_industries()`
- New: Volume spike calculation logic, ICB grouping service

## Validation Summary

**Validated:** 2025-12-22
**Questions asked:** 8

### Confirmed Decisions
| Question | Decision |
|----------|----------|
| Calculation Strategy | Real-time calculation with 5min cache |
| Historical Data Source | Store in PostgreSQL (new `daily_ohlcv` table) |
| New IPOs (<20 days) | Exclude from results |
| UI Grouping | Group by ICB Industry |
| Page Location | Separate page at `/analytics/volume-spikes` |
| Chart Visualization | Bar chart by Industry (spike count per sector) |
| DB Schema | New `daily_ohlcv` table + daily collection job |
| MVP Filters | All 4: Threshold, Exchange, UPCOM toggle, Date picker |

### Action Items (Plan Updates Required)
- [ ] Add Phase 0: Database schema + daily OHLCV collection job
- [ ] Update Phase 1: Query from `daily_ohlcv` table instead of vnstock API
- [ ] Update Phase 2: Page location is `/analytics/volume-spikes` (not tab in Deep Dive)
- [ ] Update Phase 2: Chart shows spike count per industry (not individual stocks)

## Next Steps
1. Update phase documents with validated decisions
2. Create database migration for `daily_ohlcv` table
3. Begin Phase 0: Daily OHLCV collection job
4. Continue with Phase 1 backend API
5. Implement Phase 2 frontend dashboard
