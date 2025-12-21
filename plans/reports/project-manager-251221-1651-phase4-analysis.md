# Phase 4 Frontend Analysis: Market Context Tab

**Date**: 2025-12-21
**Plan**: `/plans/251221-1440-market-sector-context/plan.md`
**Phase**: Phase 4 - Frontend Components
**Status**: Pending (blocked by Phase 3 verification)
**Analyzer**: project-manager

---

## Executive Summary

Phase 4 implements "Market Context" tab in Deep Dive page. 10 implementation steps identified. Phase 3 API marked "DONE" but requires verification before Phase 4 start.

---

## Task Breakdown

### Total Steps: 10
| # | Task | Est. Time | Complexity |
|---|------|-----------|------------|
| 1 | Add query key + type definitions | 20 min | Low |
| 2 | Create data fetching hook | 30 min | Low |
| 3 | Create period selector component | 30 min | Low |
| 4 | Create relative performance chart | 1.5 hrs | Medium |
| 5 | Create correlation card | 45 min | Medium |
| 6 | Create sector context card | 45 min | Medium |
| 7 | Create main tab component | 1 hr | Medium |
| 8 | Integrate into Deep Dive page | 30 min | Low |
| 9 | Add responsive styles | 30 min | Low |
| 10 | Write component tests | 1 hr | Medium |

**Total Effort**: 6.5-7 hours (aligns with plan estimate: 2-3 days)

---

## Dependencies Analysis

### Critical Blocker
**Phase 3 API** - Plan marked ✅ DONE (2025-12-21), **BUT:**
- Git status shows `52b004e feat(market-context): implement Phase 3 backend API endpoint`
- **Verification needed**: API endpoint functional test, response contract validation
- **Action**: Test `GET /stocks/{symbol}/market-context?period=3M` before Phase 4 start

### External Dependencies (Confirmed)
- ✅ Recharts - Already in project
- ✅ TanStack Query - Configured
- ✅ ShadCN/UI - Available
- ✅ PostgreSQL - Running
- ✅ APScheduler - Configured

### Internal Dependencies
- Phase 1 ✅ DONE - Database schema
- Phase 2 ✅ DONE - EOD pipeline
- Existing Deep Dive page structure
- Query key factory pattern
- API client setup

---

## Files to Create (7 new files)

### Data Layer
1. `/apps/web/src/types/market-context.ts` - TypeScript interfaces
2. `/apps/web/src/hooks/use-market-context.ts` - React Query hook

### UI Components
3. `/apps/web/src/components/dashboard/period-selector.tsx`
4. `/apps/web/src/components/dashboard/relative-performance-chart.tsx`
5. `/apps/web/src/components/dashboard/correlation-card.tsx`
6. `/apps/web/src/components/dashboard/sector-context-card.tsx`
7. `/apps/web/src/components/dashboard/market-context-tab.tsx` - Main container

### Test
8. `/apps/web/src/components/dashboard/__tests__/market-context-tab.test.tsx`

### Files to Modify (3 existing)
1. `/apps/web/src/lib/query-keys.ts` - Add `marketContext` key
2. `/apps/web/src/app/analytics/deep-dive/page.tsx` - Add tab integration
3. (Optional) `/apps/web/src/lib/api.ts` - If endpoint mapping needed

---

## Technical Requirements

### Functional
- 4 period options (1M/3M/6M/1Y) with URL param persistence
- 3-line chart (stock, VNINDEX, sector) normalized to base 100
- Correlation metrics: beta, correlation, RS (20D/60D windows)
- Sector rank display, top 3 peers
- Performance badges (outperform market/sector)
- Graceful handling of "Unclassified" sector (hide sector line, show market-only)

### Non-Functional
- Chart render \< 1s
- Loading skeleton during fetch
- Error handling with retry button
- Mobile responsive (chart 300px, grid stacks)
- Accessible (keyboard nav, ARIA labels, 4.5:1 contrast)

---

## Ambiguities & Risks

### Ambiguities
1. **Chart height on mobile** - Plan shows `window.innerWidth < 768 ? 300 : 400` - requires client-side check, may cause SSR hydration mismatch
   - **Recommendation**: Use CSS `@media` queries or `useEffect` hook

2. **Top peers data source** - Step 6 shows `top_peers = []  # TODO: Fetch from price board` in API service
   - **Status**: API may return empty array
   - **Frontend impact**: Card should handle empty peers gracefully

3. **Test data setup** - Tests require mock data, no fixtures provided
   - **Recommendation**: Create test fixtures in `/apps/web/src/__fixtures__/market-context.ts`

4. **Skeleton component** - Uses `<Skeleton>` but no testId attribute in implementation
   - **Fix**: Add `data-testid="market-context-skeleton"` for tests

### Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| Phase 3 API incomplete | **HIGH** | Verify endpoint before start |
| Chart performance with 365 data points (1Y) | Medium | Recharts handles well, use `dot={false}` |
| Mobile chart readability | Medium | Reduce height, simplify tooltip |
| API timeout/errors | Medium | Implemented (retry button) |
| Type mismatch (API vs frontend) | Low | Generated from same schema |

---

## Skills/Tools Required

### Primary Skills
1. **typescript-expert** - Type definitions, interfaces, generics
2. **react-expert** - Hooks, state management, composition
3. **shadcn-expert** - Card, Badge, Button, Skeleton, Alert components
4. **recharts-expert** - LineChart, responsive container, custom tooltip

### Secondary Skills
5. **tanstack-query-expert** - useQuery, cache config, error handling
6. **nextjs-expert** - App router, client components, URL params
7. **tailwind-expert** - Responsive grid, mobile-first classes
8. **testing-expert** - React Testing Library, mock API, user events

---

## Pre-Implementation Checklist

### Before Starting Phase 4
- [ ] **Verify Phase 3 API endpoint functional**
  - [ ] Test `GET /api/v1/stocks/VCB/market-context?period=3M`
  - [ ] Validate response matches `MarketContextResponse` schema
  - [ ] Test edge cases (Unclassified sector, invalid period)
- [ ] **Verify EOD pipeline has run at least once**
  - [ ] Check DB tables populated: `stock_daily_returns`, `stock_market_metrics`, `sector_daily_benchmark`
- [ ] **Verify existing Deep Dive page structure**
  - [ ] Check tab implementation pattern
  - [ ] Verify Recharts installed (`package.json`)
- [ ] **Create test fixtures**
  - [ ] Mock API response data
  - [ ] Mock query client setup

---

## Success Criteria (from plan)

**Functional**
- [ ] Tab renders without errors
- [ ] Chart displays 3 lines (stock, VNINDEX, sector)
- [ ] Period selector changes data
- [ ] Metrics cards show correct values
- [ ] Handles "Unclassified" sector (hides sector line)
- [ ] Loading skeleton displays during fetch
- [ ] Error state with retry button

**Non-Functional**
- [ ] Mobile responsive (chart scales, cards stack)
- [ ] Accessible (keyboard navigation, ARIA labels)
- [ ] Performance badges update correctly
- [ ] Chart render time \< 1s
- [ ] Component mount time \< 500ms

---

## Recommended Implementation Sequence

### Phase 4A: Foundation (Steps 1-3, ~1.5 hrs)
1. Add type definitions + query key
2. Create data fetching hook
3. Create period selector
- **Milestone**: Can fetch data, switch periods

### Phase 4B: Visualizations (Steps 4-6, ~3 hrs)
4. Create chart component
5. Create correlation card
6. Create sector card
- **Milestone**: All UI components ready

### Phase 4C: Integration (Steps 7-9, ~2 hrs)
7. Create main tab component
8. Integrate into Deep Dive
9. Add responsive styles
- **Milestone**: Feature functional end-to-end

### Phase 4D: Quality (Step 10, ~1 hr)
10. Write component tests
- **Milestone**: Tests pass, coverage \> 80%

---

## Critical Next Actions

### Immediate (Before Phase 4)
1. **Delegate to tester**: Verify Phase 3 API endpoint
   - Test all periods, symbols, edge cases
   - Confirm response matches contract
   - Document any discrepancies

2. **Delegate to backend-developer**: If Phase 3 issues found
   - Fix response schema mismatches
   - Implement top_peers data (currently TODO)
   - Add error handling for missing data

### Phase 4 Start (After verification)
1. **Delegate to frontend-developer**:
   - Implement Steps 1-10 in sequence
   - Follow ShadCN + TailwindCSS priority
   - Use reusable component pattern
   - Maintain type safety

2. **Delegate to docs-manager**: After Phase 4 completion
   - Update `/docs/codebase-summary.md` with new components
   - Update `/docs/project-roadmap.md` progress
   - Document market context tab usage

---

## Unresolved Questions

1. **API Response Time** - Plan states \< 100ms (precomputed), but Phase 3 implementation shows complex calculations in `_build_chart_data()`. Has this been benchmarked?

2. **Top Peers Implementation** - API service has `# TODO: Fetch from price board`. Is this feature deferred? Should frontend hide section if empty?

3. **Cache Invalidation** - Who triggers cache clear after EOD pipeline completes? Should frontend force refetch?

4. **Error Telemetry** - Should frontend log API errors to monitoring service? Not mentioned in plan.

5. **Date Locale** - Chart uses `toLocaleDateString('vi-VN')`. Is Vietnamese locale always correct, or should it be user-configurable?

---

## Conclusion

Phase 4 well-structured, clear requirements, comprehensive implementation steps. **Critical blocker**: Phase 3 API verification. Recommend:
1. Run API functional tests immediately
2. Fix any schema/data issues in Phase 3
3. Start Phase 4 only after API confirmed working

Estimated timeline: 2-3 days (matches plan) after verification complete.
