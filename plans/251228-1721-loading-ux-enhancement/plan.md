---
title: "Loading UX Enhancement"
description: "Improve loading smoothness, error handling, and data transitions"
status: completed
priority: P2
effort: 12h
branch: main
tags: [frontend, ux, refactor]
created: 2025-12-28
completed: 2025-12-28
---

# Loading UX Enhancement

## Overview

Entirely Upgrade Loading UX With Error Boundary system, smooth transitions, va Suspense migration. Solve problem: unhandled errors, jarring loading states, manual loading/error checks.

## Current State Analysis

### Strengths
- TanStack Query v5.90 with staleTime/gcTime
- `use-stock-detail.ts` da co `keepPreviousData`
- Skeleton patterns consistent (26 hooks, inline skeletons)
- Chart lazy load with `next/dynamic`

### Gaps
| Gap | Impact |
|-----|--------|
| No Error Boundary | App crash on errors |
| No useSuspenseQuery | Manual checks everywhere |
| No loading.tsx | Missing streaming |
| No global loading indicator | User confused on refetch |

## Implementation Phases

| Phase | Focus | Effort | Dependency | Status |
|-------|-------|--------|------------|--------|
| [Phase 1](./phases/phase-01-error-boundary-setup.md) | Error Boundary System | 2.5h | None | DONE |
| [Phase 2](./phases/phase-02-smooth-transitions.md) | Smooth Transitions | 2h | Phase 1 | DONE |
| [Phase 3](./phases/phase-03-suspense-migration.md) | Suspense Migration | 5h | Phase 1, 2 | DONE |
| [Phase 4](./phases/phase-04-polish-optimization.md) | Polish & Optimization | 2.5h | Phase 3 | DONE (2025-12-28) |

## Key Decisions

1. **Error Boundary Strategy**: Component-level granular (not page-level) for dashboard
2. **Suspense Migration**: Start with leaf components, move up
3. **Skeleton Approach**: Keep inline skeletons, add centralized exports
4. **Chart Animation**: Disable during placeholder data transitions

## Files Changed Summary

### New Files (8)
- `components/providers/query-error-boundary.tsx`
- `components/ui/error-fallback.tsx`
- `components/layout/global-loading-indicator.tsx`
- `app/loading.tsx`
- `app/analytics/deep-dive/loading.tsx`
- `app/analytics/volume-spikes/loading.tsx`
- `app/analytics/financial-statements/loading.tsx`
- `components/ui/skeletons/index.ts`

### Modified Files (20+)
- `app/layout.tsx` - Add ErrorBoundary wrapper
- `components/providers/query-provider.tsx` - Add throwOnError config
- `hooks/use-*.ts` (26 files) - Add placeholderData, migrate to Suspense
- `components/dashboard/*-chart.tsx` (4 files) - Animation optimization

## Dependencies

| Package | Version | Status |
|---------|---------|--------|
| react-error-boundary | ^4.x | Need install |
| @tanstack/react-query | 5.90 | Installed |

## Success Criteria

- [x] Zero unhandled query errors
- [x] No flash content on tab/period switch
- [x] Charts animate smoothly, no remount flash
- [x] Clear loading feedback (skeleton + indicator)
- [x] Error recovery works (retry button)
- [x] TypeScript: No `data!` assertions needed

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| useSuspenseQuery breaks SSR | Medium | High | Test HydrationBoundary |
| ErrorBoundary catches too much | Low | Medium | Use granular boundaries |
| Breaking existing tests | Medium | Medium | Update test utilities |

## Unresolved Questions

1. Error logging integration (Sentry?) - defer to future
2. Retry limit strategy (infinite vs 3x) - default to 3
3. Offline support - out of scope

## Validation Summary

**Validated:** 2025-12-28
**Questions asked:** 6

### Confirmed Decisions

| Decision | User Choice |
|----------|-------------|
| Error Boundary granularity | Component-level (dashboard widgets isolated) |
| throwOnError config | Yes, enable globally in QueryClient |
| Error message language | Vietnamese |
| Suspense migration scope | Full migration (all 14 hooks) |
| Conditional queries pattern | Wrapper pattern (check before render) |
| Chart animation strategy | Disable during refetch (isPlaceholderData) |

### Action Items

- [x] All decisions align with plan - no changes needed

---

## Related Files

- Brainstorm: `plans/reports/brainstorm-251228-1714-loading-ux-enhancement.md`
- Research 1: `research/researcher-01-error-boundary.md`
- Research 2: `research/researcher-02-suspense-query.md`
