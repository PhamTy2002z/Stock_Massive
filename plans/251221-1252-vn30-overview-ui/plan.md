---
status: in-progress
priority: P2
feature: VN30 Overview UI
created: 2025-12-21
estimated_hours: 6
---

# VN30 Overview UI Implementation Plan

## Overview

Create "Tổng quan VN30" (VN30 Overview) section displaying real-time data for VN30 index stocks with columns: Symbol, Company Name, Price, and Change Percent. Implementation follows existing design patterns using ShadCN/UI + TailwindCSS and vnstock API integration.

## Context

- **Research Reports**:
  - [vnstock API Report](./research/researcher-vnstock-api-report.md)
  - [UI Patterns Report](./research/researcher-ui-patterns-report.md)
- **Tech Stack**: Next.js 14 + FastAPI + vnstock 3.0
- **Design System**: ShadCN/UI + TailwindCSS + TanStack Query v5
- **API Pattern**: Feature-based modular architecture

## Implementation Phases

### [Phase 01: Backend API](./phase-01-backend-api.md)
**Status**: Done (2025-12-21) | **Priority**: P2 | **Est**: 3 hours | **Actual**: 2 hours

Create FastAPI endpoint `/api/v1/stocks/vn30-overview` that:
- Fetches VN30 symbols using `listing.symbols_by_group('VN30')`
- Retrieves batch price data via `trading.price_board()`
- Returns structured response with symbol, company_name, price, change_pct
- Implements caching with TradingHoursCache (5min trading, 1hr off-hours)

**Deliverables** (Completed):
- Pydantic schema: `VN30OverviewItem`, `VN30OverviewResponse`
- Router endpoint in `apps/api/src/stocks/market/router.py`
- Service method in `apps/api/src/stocks/market/service.py`
- Testing: 30/30 VN30 stocks returned, sorted by market cap

### [Phase 02: Frontend Components](./phase-02-frontend-components.md)
**Status**: Pending | **Priority**: P2 | **Est**: 3 hours

Create React components and hooks:
- Hook: `use-vn30-overview.ts` with React Query (1min auto-refresh)
- Component: `vn30-overview-table.tsx` following ShareholdersTabContent pattern
- Integration: Add to dashboard page with proper error/loading states

**Deliverables**:
- React Query hook with query key
- Table component with color-coded changes (green/red)
- Vietnamese locale formatting
- Responsive design with horizontal scroll

## Success Criteria

1. Backend endpoint returns VN30 data in <3s
2. Frontend displays all 30 stocks with real-time prices
3. Color coding: green for positive, red for negative changes
4. Auto-refresh every 1 minute during trading hours
5. Proper error handling and loading states
6. Mobile-responsive table with horizontal scroll

## Dependencies

- vnstock 3.0 library (already installed)
- Existing market service infrastructure
- ShadCN/UI table components
- TanStack Query v5

## Risk Assessment

**Low Risk**:
- Existing patterns well-established
- vnstock API proven reliable
- Similar features already implemented

**Mitigation**:
- Batch API calls to avoid rate limits
- Cache responses to reduce API load
- Graceful degradation on API failures

## Related Documentation

- [System Architecture](/Users/typham/Documents/GitHub/Stock_Massive/docs/system-architecture.md)
- [Code Standards](/Users/typham/Documents/GitHub/Stock_Massive/docs/code-standards.md)
- [Design Guidelines](/Users/typham/Documents/GitHub/Stock_Massive/docs/design-guidelines.md)

## Validation Summary

**Validated:** 2025-12-21
**Questions asked:** 6

### Confirmed Decisions
- **Table display**: Paginated with 10 rows per page (options: 10/20/30)
- **Sorting**: By market cap descending (largest first)
- **Click action**: No navigation on row click (keep simple)
- **Extra columns**: Add Volume and Market cap columns (6 columns total)
- **Placement**: After Market Indices, before Sector Performance
- **Refresh rate**: Every 1 minute (changed from 5 min)

### Action Items
- [x] Update phase-02 hook: change refetchInterval from 5min to 1min
- [x] Update phase-02 component: add Volume and Market cap columns
- [x] Update phase-02 component: add pagination at bottom
- [x] Backend already returns volume and market_cap - no changes needed

## Progress Summary

| Phase | Status | Est Hours | Actual | Completion |
|-------|--------|-----------|--------|------------|
| Phase 01: Backend API | Done | 3h | 2h | 100% |
| Phase 02: Frontend Components | Pending | 3h | - | 0% |
| **Total** | In Progress | 6h | 2h | **50%** |
