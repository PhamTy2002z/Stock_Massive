---
title: "Smooth Section Loading Without Flash"
description: "Migrate from useSuspenseQuery to useQuery with keepPreviousData for smooth tab/filter transitions"
status: pending
priority: P1
effort: 8h
branch: feat/smooth-section-loading
tags: [ux, tanstack-query, loading-states, performance]
created: 2026-01-02
---

# Smooth Section Loading Without Flash

## Problem Statement

Tab/filter switches in dashboard sections trigger skeleton loading that replaces content, causing jarring UX. Root cause: `useSuspenseQuery` doesn't support `placeholderData`, so query key changes trigger Suspense boundary showing skeleton.

**Current behavior:**
- Tab switch → skeleton replaces chart → new data appears
- Creates blank state during loading
- Disrupts visual continuity

**Desired behavior:**
- Tab switch → previous chart stays visible with subtle opacity fade
- Loading indicator shows progress without hiding content
- Smooth, professional transition

## Solution Approach

Migrate from `useSuspenseQuery` to `useQuery` with `placeholderData: keepPreviousData` pattern. This keeps previous data visible during refetch while showing subtle loading indicators.

**Key changes:**
- Replace `useSuspenseQuery` → `useQuery` in hooks
- Add `placeholderData: keepPreviousData` option
- Handle `isPending` state manually for first load
- Use `isPlaceholderData` flag for opacity transitions
- Add subtle loading indicators without content replacement

## Implementation Phases

### [Phase 01: Sector Historical Fix](./phase-01-sector-historical-fix.md)
**Priority:** P1 | **Effort:** 2-3h

Critical fix for SectorHistoricalPerformance component with tab switching (1W/2W/1M). Migrate hook and component to use keepPreviousData pattern.

### [Phase 02: Enhance All Sections](./phase-02-enhance-all-sections.md) - DONE
**Priority:** P1 | **Effort:** 3-4h | **Completed:** 2026-01-02

Apply pattern to remaining sections: MarketIndices, VN30Overview, SectorPerformance. Standardize loading indicator patterns across dashboard.

### [Phase 03: Prefetch Optimization](./phase-03-prefetch-optimization.md)
**Priority:** P2 | **Effort:** 2h

Optional performance enhancement with prefetch strategies for tabs and hover-based prefetching.

## Success Criteria

**UX Improvements:**
- No skeleton flash during tab/filter switch
- Content remains visible during loading
- Smooth opacity transitions (200ms)
- Clear loading feedback without disruption

**Technical Validation:**
- `isPlaceholderData` flag works correctly
- First load shows skeleton (expected)
- Subsequent loads show opacity fade (smooth)
- Manual refresh doesn't flash content
- Auto-refetch doesn't disrupt user

## Related Resources

- Brainstorm: `/Users/typham/Documents/GitHub/Stock_Massive/plans/reports/brainstorm-260102-2227-smooth-section-loading.md`
- Research: `./research/researcher-01-tanstack-query-patterns.md`
- Research: `./research/researcher-02-component-refactoring.md`

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Error handling complexity | Medium | Copy FundCertificates error pattern |
| Stale data confusion | Low | Opacity fade clearly indicates loading |
| Breaking SSR hydration | Medium | Keep HydrationBoundary at page level |

## Total Effort

~8 hours (Phase 01: 2-3h, Phase 02: 3-4h, Phase 03: 2h)
