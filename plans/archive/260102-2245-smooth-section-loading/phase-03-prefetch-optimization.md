---
phase: 03
title: "Prefetch Optimization for Instant Tab Switching"
parent_plan: "./plan.md"
priority: P2
effort: 2h
status:
  implementation: done
  review: done
  testing: done
created: 2026-01-02
dependencies: ["phase-01-sector-historical-fix.md", "phase-02-enhance-all-sections.md"]
---

# Phase 03: Prefetch Optimization for Instant Tab Switching

## Context

**Parent Plan:** [Smooth Section Loading Without Flash](./plan.md)
**Depends On:**
- [Phase 01 - Sector Historical Fix](./phase-01-sector-historical-fix.md)
- [Phase 02 - Enhance All Sections](./phase-02-enhance-all-sections.md)

**Research References:**
- [TanStack Query Patterns](./research/researcher-01-tanstack-query-patterns.md)

## Overview

**Date:** 2026-01-02
**Description:** Optional performance enhancement using prefetch strategies for near-instant tab switching
**Priority:** P2 (Nice-to-have optimization)
**Effort:** 2 hours

**Goal:** Reduce perceived loading time to near-zero by prefetching likely user interactions

**Approach:**
1. Prefetch adjacent tabs on mount
2. Prefetch on tab hover (predictive loading)
3. Prefetch next page in pagination
4. Smart prefetch based on user patterns

**Note:** This phase is optional and should only be implemented after Phase 01 and 02 are validated.

## Key Insights from Research

1. **TanStack Query Prefetch:** `queryClient.prefetchQuery()` populates cache without triggering component render
2. **Cache Hit Behavior:** If data in cache, `useQuery` returns instantly (no loading state)
3. **Hover Intent:** 200-300ms hover delay indicates user intent to switch
4. **Memory Trade-off:** Prefetching uses more memory but improves perceived performance
5. **Stale Time Coordination:** Prefetch should respect same staleTime as query

## Requirements

### Functional Requirements
- [ ] Prefetch adjacent tabs on component mount
- [ ] Prefetch on tab hover with 200ms delay
- [ ] Prefetch respects staleTime (don't refetch fresh data)
- [ ] Prefetch doesn't block main thread
- [ ] Prefetch cancellable on unmount

### Non-Functional Requirements
- [ ] Memory usage acceptable (< 5MB additional)
- [ ] Network usage reasonable (only prefetch likely interactions)
- [ ] No impact on initial page load performance
- [ ] Works with existing keepPreviousData pattern

## Architecture Changes

### 1. SectorHistoricalPerformance - Tab Prefetch

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/sector-historical-performance.tsx`

**Add Prefetch Hook (after line 133):**

```typescript
import { useQueryClient } from "@tanstack/react-query"

function usePrefetchAdjacentPeriods(currentPeriod: SectorHistoricalPeriod) {
  const queryClient = useQueryClient()

  useEffect(() => {
    const periods: SectorHistoricalPeriod[] = ["1W", "2W", "1M"]
    const currentIndex = periods.indexOf(currentPeriod)

    // Prefetch adjacent periods
    const toPrefetch = [
      periods[currentIndex - 1],
      periods[currentIndex + 1],
    ].filter(Boolean) as SectorHistoricalPeriod[]

    toPrefetch.forEach((period) => {
      queryClient.prefetchQuery({
        queryKey: queryKeys.sectorHistoricalPerformance(period),
        queryFn: () => fetchSectorHistoricalPerformance(period),
        staleTime: 5 * 60 * 1000, // Match main query staleTime
      })
    })
  }, [currentPeriod, queryClient])
}
```

**Update Component (line 134):**

```typescript
export function SectorHistoricalPerformance({ className }: { className?: string }) {
  const [period, setPeriod] = useState<SectorHistoricalPeriod>("1W")

  // Prefetch adjacent periods
  usePrefetchAdjacentPeriods(period)

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Hiệu suất ngành theo thời gian</CardTitle>
          <Tabs value={period} onValueChange={(v) => setPeriod(v as SectorHistoricalPeriod)}>
            <TabsList className="h-8">
              <TabsTrigger
                value="1W"
                className="text-xs px-3"
                onMouseEnter={() => prefetchPeriod("1W")}
              >
                1 Tuần
              </TabsTrigger>
              <TabsTrigger
                value="2W"
                className="text-xs px-3"
                onMouseEnter={() => prefetchPeriod("2W")}
              >
                2 Tuần
              </TabsTrigger>
              <TabsTrigger
                value="1M"
                className="text-xs px-3"
                onMouseEnter={() => prefetchPeriod("1M")}
              >
                1 Tháng
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </CardHeader>
      <CardContent>
        <PeriodContent period={period} />
      </CardContent>
    </Card>
  )
}
```

**Add Hover Prefetch Helper:**

```typescript
function SectorHistoricalPerformance({ className }: { className?: string }) {
  const [period, setPeriod] = useState<SectorHistoricalPeriod>("1W")
  const queryClient = useQueryClient()
  const hoverTimeoutRef = useRef<NodeJS.Timeout>()

  usePrefetchAdjacentPeriods(period)

  const prefetchPeriod = useCallback((targetPeriod: SectorHistoricalPeriod) => {
    // Clear existing timeout
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current)
    }

    // Prefetch after 200ms hover (indicates intent)
    hoverTimeoutRef.current = setTimeout(() => {
      queryClient.prefetchQuery({
        queryKey: queryKeys.sectorHistoricalPerformance(targetPeriod),
        queryFn: () => fetchSectorHistoricalPerformance(targetPeriod),
        staleTime: 5 * 60 * 1000,
      })
    }, 200)
  }, [queryClient])

  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) {
        clearTimeout(hoverTimeoutRef.current)
      }
    }
  }, [])

  // ... rest of component
}
```

### 2. FundCertificates - Pagination Prefetch

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/fund-certificates.tsx`

**Add Next Page Prefetch:**

```typescript
function usePrefetchNextPage(currentPage: number, hasMore: boolean, fundType?: string) {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (hasMore) {
      queryClient.prefetchQuery({
        queryKey: queryKeys.fundCertificates(fundType, currentPage + 1),
        queryFn: () => fetchFundCertificates(fundType, currentPage + 1),
        staleTime: 60 * 1000,
      })
    }
  }, [currentPage, hasMore, fundType, queryClient])
}
```

### 3. Smart Prefetch Strategy

**Create Shared Hook:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-smart-prefetch.ts`

```typescript
import { useEffect, useCallback, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"

interface PrefetchConfig {
  queryKey: unknown[]
  queryFn: () => Promise<unknown>
  staleTime?: number
  hoverDelay?: number
}

export function useSmartPrefetch(configs: PrefetchConfig[]) {
  const queryClient = useQueryClient()
  const hoverTimeouts = useRef<Map<string, NodeJS.Timeout>>(new Map())

  // Prefetch all on mount
  useEffect(() => {
    configs.forEach(({ queryKey, queryFn, staleTime }) => {
      queryClient.prefetchQuery({
        queryKey,
        queryFn,
        staleTime,
      })
    })
  }, [configs, queryClient])

  // Hover-based prefetch
  const prefetchOnHover = useCallback((key: string, config: PrefetchConfig) => {
    const existingTimeout = hoverTimeouts.current.get(key)
    if (existingTimeout) {
      clearTimeout(existingTimeout)
    }

    const timeout = setTimeout(() => {
      queryClient.prefetchQuery({
        queryKey: config.queryKey,
        queryFn: config.queryFn,
        staleTime: config.staleTime,
      })
    }, config.hoverDelay || 200)

    hoverTimeouts.current.set(key, timeout)
  }, [queryClient])

  // Cleanup
  useEffect(() => {
    return () => {
      hoverTimeouts.current.forEach((timeout) => clearTimeout(timeout))
      hoverTimeouts.current.clear()
    }
  }, [])

  return { prefetchOnHover }
}
```

## Related Code Files

### Files to Modify
1. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/sector-historical-performance.tsx` (lines 134-156)
2. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/fund-certificates.tsx` (pagination section)

### New Files to Create
1. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-smart-prefetch.ts` (optional shared hook)

### Reference Files
1. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/query-keys.ts` - Query key factory
2. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/api.ts` - API functions

## Implementation Steps

### Step 1: SectorHistorical Adjacent Prefetch (30 min)
1. Open `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/sector-historical-performance.tsx`
2. Import `useQueryClient` from @tanstack/react-query
3. Create `usePrefetchAdjacentPeriods` hook
4. Add hook call in main component
5. Test: Switch tabs, verify instant transitions when cached

### Step 2: SectorHistorical Hover Prefetch (30 min)
1. Add `useRef` for hover timeout tracking
2. Create `prefetchPeriod` callback with 200ms delay
3. Add `onMouseEnter` handlers to TabsTrigger components
4. Add cleanup in useEffect
5. Test: Hover over tabs, verify prefetch in Network tab

### Step 3: Performance Measurement (20 min)
1. Add performance marks for tab switching
2. Measure time from click to render
3. Compare with/without prefetch
4. Document performance improvements
5. Verify memory usage acceptable

### Step 4: Optional Shared Hook (20 min)
1. Create `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-smart-prefetch.ts`
2. Extract common prefetch logic
3. Add TypeScript types
4. Add JSDoc documentation
5. Refactor SectorHistorical to use shared hook

### Step 5: Testing & Validation (20 min)
1. Test with slow network (verify prefetch helps)
2. Test with fast network (verify no negative impact)
3. Test rapid interactions (verify no race conditions)
4. Test memory usage (verify no leaks)
5. Test cache invalidation (verify stale data handled)

## Todo List

- [ ] Implement adjacent period prefetch
  - [ ] Create usePrefetchAdjacentPeriods hook
  - [ ] Add to SectorHistoricalPerformance component
  - [ ] Test instant tab switching
- [ ] Implement hover-based prefetch
  - [ ] Add hover timeout tracking
  - [ ] Add onMouseEnter handlers to tabs
  - [ ] Test 200ms delay behavior
- [ ] Measure performance improvements
  - [ ] Add performance marks
  - [ ] Compare before/after metrics
  - [ ] Document improvements
- [ ] Optional: Create shared hook
  - [ ] Extract common logic
  - [ ] Add TypeScript types
  - [ ] Add documentation
- [ ] Testing
  - [ ] Test various network conditions
  - [ ] Test memory usage
  - [ ] Test edge cases

## Success Criteria

### Performance Validation
- [ ] Tab switch < 50ms when prefetched (vs 200-500ms without)
- [ ] Hover prefetch triggers after 200ms
- [ ] No prefetch on rapid mouse movement
- [ ] Memory usage increase < 5MB
- [ ] No impact on initial page load

### UX Validation
- [ ] Instant tab switching when hovering first
- [ ] Smooth fallback when not prefetched (keepPreviousData)
- [ ] No visual glitches
- [ ] No network request spam

### Technical Validation
- [ ] Prefetch respects staleTime
- [ ] Prefetch cancels on unmount
- [ ] No race conditions
- [ ] TypeScript types correct
- [ ] No console warnings

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Excessive network requests | Medium | Medium | Only prefetch adjacent/likely tabs |
| Memory leaks from prefetch | Low | High | Proper cleanup in useEffect |
| Cache thrashing | Low | Medium | Respect staleTime, don't over-prefetch |
| Slower initial load | Low | Medium | Prefetch after mount, not during |
| User confusion from instant switch | Very Low | Low | Keep loading indicators for feedback |

## Security Considerations

- No security implications (client-side optimization only)
- No additional API exposure
- Prefetch uses same authentication as regular queries
- No sensitive data cached differently

## Performance Metrics

### Before Prefetch (Phase 01/02)
- Tab switch with keepPreviousData: 200-500ms
- First load: 200-500ms
- Memory usage: baseline

### After Prefetch (Phase 03)
- Tab switch (prefetched): < 50ms (instant)
- Tab switch (not prefetched): 200-500ms (fallback to keepPreviousData)
- First load: 200-500ms (unchanged)
- Memory usage: baseline + 2-5MB (acceptable)

### Target Improvements
- 80% reduction in perceived loading time for common interactions
- 90% of tab switches instant (when prefetched)
- < 5MB memory overhead

## Next Steps

After completing Phase 03:
1. Monitor real-world performance metrics
2. Gather user feedback on perceived speed
3. Consider expanding prefetch to other sections
4. Document prefetch patterns in code standards
5. Consider A/B testing prefetch strategies

## Unresolved Questions

1. Should we prefetch all tabs or only adjacent ones?
2. What's the optimal hover delay (200ms vs 300ms)?
3. Should we track user patterns and prefetch accordingly?
4. Should we disable prefetch on slow connections (navigator.connection)?
5. Should we add prefetch to other sections beyond SectorHistorical?
