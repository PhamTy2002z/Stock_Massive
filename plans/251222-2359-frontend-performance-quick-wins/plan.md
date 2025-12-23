---
title: "Frontend Performance Quick Wins"
description: "Optimize React/Next.js performance with minimal code changes"
status: pending
priority: P1
effort: 1h
branch: main
tags: [performance, frontend, quick-wins]
created: 2025-12-22
---

# Frontend Performance Quick Wins

## Overview
High-impact, low-effort performance optimizations targeting professional traders who need responsive, battery-efficient dashboards. Focus on eliminating unnecessary background polling, lazy loading heavy chart libraries, and memoizing expensive components.

## Target Metrics
- Reduce bundle size by ~400KB (Recharts lazy load)
- Eliminate background polling waste (3 hooks × 10s intervals)
- Prevent unnecessary re-renders in volume spike dashboard
- Improve battery life on inactive tabs

## Research Context
- [React Performance Patterns](./research/researcher-01-react-performance.md)
- [Next.js Optimization Strategies](./research/researcher-02-nextjs-optimization.md)

## Implementation Phases

### Phase 1: Fix TanStack Query Polling ⏳ pending
**File:** [phase-01-fix-tanstack-query-polling.md](./phase-01-fix-tanstack-query-polling.md)
- **Effort:** 5 min
- **Impact:** HIGH - Stops wasteful background requests
- **Files:** 3 hooks (use-market-indices.ts, use-vn30-overview.ts, use-stock-detail.ts)
- **Change:** `refetchIntervalInBackground: true` → `false`

### Phase 2: Lazy Load Chart Components ⏳ pending
**File:** [phase-02-lazy-load-chart-components.md](./phase-02-lazy-load-chart-components.md)
- **Effort:** 15 min
- **Impact:** HIGH - Reduces initial bundle by ~400KB
- **Files:** volume-spike-dashboard.tsx
- **Change:** Dynamic imports with `next/dynamic` for Recharts components

### Phase 3: Memoize Heavy Components ⏳ pending
**File:** [phase-03-memoize-heavy-components.md](./phase-03-memoize-heavy-components.md)
- **Effort:** 20 min
- **Impact:** MEDIUM - Prevents unnecessary re-renders
- **Files:** volume-spike-dashboard.tsx
- **Change:** Wrap components with React.memo, add useCallback

### Phase 4: Minor Optimizations ⏳ pending
**File:** [phase-04-minor-optimizations.md](./phase-04-minor-optimizations.md)
- **Effort:** 10 min
- **Impact:** LOW - Small improvements
- **Files:** dashboard-header.tsx
- **Change:** Move Supabase client outside component

## Success Criteria
- [ ] No background polling when tab inactive
- [ ] Charts load on-demand (not in initial bundle)
- [ ] No unnecessary re-renders in volume spike dashboard
- [ ] Lighthouse performance score improvement
- [ ] No functional regressions

## Rollback Plan
All changes are non-breaking and easily reversible via git revert.

## Notes
- All changes maintain existing functionality
- No API changes required
- Compatible with current Next.js 15.5.9 + TanStack Query v5
- Follows existing code standards (kebab-case, DRY/KISS)

---

## Validation Summary

**Validated:** 2025-12-22
**Questions asked:** 4

### Confirmed Decisions
1. **Polling interval:** Keep 10 seconds - optimal for professional traders
2. **Trading hours optimization:** YES - disable polling outside 9:00-15:00 ICT
3. **Chart lazy loading:** On tab click - load Recharts when user needs it
4. **Implementation scope:** All 4 phases

### Action Items
- [ ] **NEW:** Add trading hours check to Phase 1 - disable polling outside 9:00-15:00 ICT
  - Create `isTradingHours()` utility function
  - Set `refetchInterval` to `false` when outside trading hours
  - This is an enhancement to Phase 1, not a new phase

### Implementation Ready
Plan validated and ready for implementation. Proceed with all 4 phases.
