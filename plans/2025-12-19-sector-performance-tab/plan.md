# Sector Performance Tab - Implementation Plan

## Overview

Add Sector Performance Tab to dashboard showing ICB Level 2 (10 sectors) with market cap weighted performance, auto-refresh every 5 minutes.

## Objective

Display real-time sector performance data aggregated from individual stocks, weighted by market capitalization.

## Scope

| In Scope | Out of Scope |
|----------|--------------|
| ICB Level 2 sectors (10) | ICB Level 3/4 drill-down |
| Market cap weighting | Historical sector trends |
| 5-min auto-refresh | Sector comparison charts |
| Table with green/red colors | Export functionality |

## Technical Approach

**Data Flow:**
```
vnstock Listing().symbols_by_industries() → Get symbols per sector
vnstock Trading().price_board() → Get prices + market cap
Aggregate → Market cap weighted change per sector
```

**Key vnstock APIs:**
- `Listing().symbols_by_industries()` - ICB classification
- `Trading().price_board()` - Real-time prices

## Implementation Phases

| Phase | Description | Status | File |
|-------|-------------|--------|------|
| 1 | Backend Schema & Service | ✅ DONE | [phase-01-backend-schema-service.md](./phase-01-backend-schema-service.md) |
| 2 | Backend API Endpoint | ✅ DONE | [phase-02-backend-api-endpoint.md](./phase-02-backend-api-endpoint.md) |
| 3 | Frontend API & Hook | ✅ DONE | [phase-03-frontend-api-hook.md](./phase-03-frontend-api-hook.md) |
| 4 | Frontend Component & Integration | ✅ DONE | [phase-04-frontend-component-integration.md](./phase-04-frontend-component-integration.md) |

## Progress

**Overall:** 100% (4/4 phases complete)
**Last Updated:** 2025-12-19

### Phase 1 Summary (DONE)
- Files: `schemas.py`, `service.py`, `test_sector_performance.py`
- Tests: 18/18 passed
- Review: 0 critical issues

### Phase 2 Summary (DONE)
- Files: `router.py` (added endpoint)
- Tests: 18/18 passed
- Review: 0 critical issues

### Phase 3 Summary (DONE)
- Files: `api.ts` (added types/fetch), `use-sector-performance.ts` (new)
- Tests: 7/7 passed
- Review: 0 critical issues

### Phase 4 Summary (DONE)
- Files: `sector-performance.tsx` (new), `index.ts` (updated), `page.tsx` (updated)
- Tests: TypeScript passed, build passed
- Review: 0 critical issues

## Success Criteria

- [x] API returns 10 ICB Level 2 sectors with weighted performance
- [x] Response time < 500ms
- [x] Frontend displays sortable table with color-coded changes
- [x] Auto-refresh works at 5-min intervals
- [x] Loading/error states handled

## Estimated Effort

| Phase | Estimate |
|-------|----------|
| Phase 1 | 1-2 hours |
| Phase 2 | 0.5 hour |
| Phase 3 | 0.5 hour |
| Phase 4 | 1-2 hours |
| **Total** | **3-5 hours** |

## Dependencies

- vnstock >= 3.0.0 (already installed)
- Existing StockService pattern
- ShadCN Table component

## Risks

| Risk | Mitigation |
|------|------------|
| vnstock API rate limits | Batch requests, consider caching |
| Large symbol list performance | Limit to top N stocks per sector |
| ICB data availability | Fallback to available classification |

## Files to Create/Modify

**Backend:**
- `apps/api/src/stocks/schemas.py` - Add schemas
- `apps/api/src/stocks/service.py` - Add service method
- `apps/api/src/stocks/router.py` - Add endpoint

**Frontend:**
- `apps/web/src/lib/api.ts` - Add fetch function
- `apps/web/src/hooks/use-sector-performance.ts` - New hook
- `apps/web/src/components/dashboard/sector-performance.tsx` - New component
- `apps/web/src/components/dashboard/index.ts` - Export
- `apps/web/src/app/page.tsx` - Integration
