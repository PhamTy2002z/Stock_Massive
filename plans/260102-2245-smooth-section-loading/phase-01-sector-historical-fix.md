---
phase: 01
title: "Sector Historical Performance - Smooth Tab Switching"
parent_plan: "./plan.md"
priority: P1
effort: 2-3h
status:
  implementation: done
  review: done
  testing: done
completed: 2026-01-02
created: 2026-01-02
---

# Phase 01: Sector Historical Performance - Smooth Tab Switching

## Context

**Parent Plan:** [Smooth Section Loading Without Flash](./plan.md)

**Research References:**
- [TanStack Query Patterns](./research/researcher-01-tanstack-query-patterns.md)
- [Component Refactoring](./research/researcher-02-component-refactoring.md)
- [Brainstorm Report](/Users/typham/Documents/GitHub/Stock_Massive/plans/reports/brainstorm-260102-2227-smooth-section-loading.md)

## Overview

**Date:** 2026-01-02
**Description:** Fix jarring skeleton flash when switching tabs (1W/2W/1M) in SectorHistoricalPerformance component
**Priority:** P1 (Critical UX issue)
**Effort:** 2-3 hours

**Current Problem:**
- Tab switch triggers `useSuspenseQuery` with new query key
- Suspense boundary activates → skeleton replaces chart
- Creates blank state during 200-500ms fetch
- Disrupts visual continuity

**Solution:**
- Migrate to `useQuery` with `placeholderData: keepPreviousData`
- Previous chart stays visible with opacity fade
- Subtle loading indicator shows progress
- Smooth 200ms transition

## Key Insights from Research

1. **useSuspenseQuery Limitation:** Does NOT support `placeholderData` option (TanStack Query v5 design)
2. **keepPreviousData Pattern:** Keeps previous data visible during refetch, prevents flash
3. **State Flags:**
   - `isPending`: true only on first load (show skeleton)
   - `isFetching`: true during any fetch (show spinner)
   - `isPlaceholderData`: true when showing stale data (apply opacity)
4. **FundCertificates Reference:** Already uses this pattern successfully (line 13 in use-fund-certificates.ts)

## Requirements

### Functional Requirements
- [x] Tab switching shows previous chart with opacity fade
- [x] First load shows skeleton (expected behavior)
- [x] Loading indicator visible during fetch without hiding content
- [x] Chart animation disabled during placeholder state
- [x] Manual refresh button works smoothly

### Non-Functional Requirements
- [x] Transition duration: 200ms
- [x] Opacity during loading: 60%
- [x] No breaking changes to API
- [x] Maintain SSR compatibility

## Architecture Changes

### Hook Migration

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-sector-historical-performance.ts`

**Before (lines 3-23):**
```typescript
import { useSuspenseQuery } from "@tanstack/react-query"

export function useSectorHistoricalPerformance(period: SectorHistoricalPeriod = "1W") {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.sectorHistoricalPerformance(period),
    queryFn: () => fetchSectorHistoricalPerformance(period),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 10 * 60 * 1000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  })

  return { data, isFetching, refetch }
}
```

**After:**
```typescript
import { useQuery, keepPreviousData } from "@tanstack/react-query"

export function useSectorHistoricalPerformance(period: SectorHistoricalPeriod = "1W") {
  const query = useQuery({
    queryKey: queryKeys.sectorHistoricalPerformance(period),
    queryFn: () => fetchSectorHistoricalPerformance(period),
    placeholderData: keepPreviousData, // KEY CHANGE
    staleTime: 5 * 60 * 1000,
    refetchInterval: 10 * 60 * 1000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  })

  return {
    data: query.data,
    isPending: query.isPending,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    refetch: query.refetch,
  }
}
```

### Component Refactoring

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/sector-historical-performance.tsx`

**Changes to PeriodContent (lines 113-132):**

**Before:**
```typescript
function PeriodContent({ period }: { period: SectorHistoricalPeriod }) {
  const { data, isFetching } = useSectorHistoricalPerformance(period)

  const chartData = useMemo(() => {
    // ... data transformation
  }, [data])

  return <SectorHistoricalChart data={chartData} isPlaceholderData={isFetching} />
}
```

**After:**
```typescript
function PeriodContent({ period }: { period: SectorHistoricalPeriod }) {
  const { data, isPending, isFetching, isPlaceholderData } = useSectorHistoricalPerformance(period)

  // First load only - show skeleton
  if (isPending) {
    return <div className="h-[280px] bg-muted animate-pulse rounded" />
  }

  const chartData = useMemo(() => {
    const gainers = data.top_gainers.map((item) => ({
      name: item.icb_name.length > 18 ? item.icb_name.slice(0, 16) + "..." : item.icb_name,
      value: item.change_pct,
      isGainer: true,
    }))
    const losers = data.top_losers.map((item) => ({
      name: item.icb_name.length > 18 ? item.icb_name.slice(0, 16) + "..." : item.icb_name,
      value: item.change_pct,
      isGainer: false,
    }))
    return [...gainers, ...losers].sort((a, b) => b.value - a.value)
  }, [data])

  return (
    <div className="relative">
      {/* Chart stays visible during tab switch */}
      <div className={cn(
        "transition-opacity duration-200",
        isPlaceholderData && "opacity-60"
      )}>
        <SectorHistoricalChart data={chartData} isPlaceholderData={isPlaceholderData} />
      </div>

      {/* Subtle loading indicator */}
      {isFetching && !isPending && (
        <div className="absolute top-2 right-2 bg-background/80 backdrop-blur-sm rounded-full p-1.5">
          <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />
        </div>
      )}
    </div>
  )
}
```

**Add import (line 1):**
```typescript
import { RefreshCw } from "lucide-react"
```

## Related Code Files

### Primary Files
1. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-sector-historical-performance.ts` (lines 1-24)
2. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/sector-historical-performance.tsx` (lines 113-132)

### Reference Files
1. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-fund-certificates.ts` (lines 3-27) - Already uses keepPreviousData pattern
2. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/api.ts` - API functions (no changes needed)
3. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/query-keys.ts` - Query key factory (no changes needed)

## Implementation Steps

### Step 1: Update Hook (15 min)
1. Open `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-sector-historical-performance.ts`
2. Change import from `useSuspenseQuery` to `useQuery, keepPreviousData` (line 3)
3. Replace `useSuspenseQuery` call with `useQuery` (line 13)
4. Add `placeholderData: keepPreviousData` option (after queryFn)
5. Store query result in `query` variable
6. Update return statement to include `isPending`, `isPlaceholderData` (lines 22-23)
7. Save file

### Step 2: Update Component Imports (5 min)
1. Open `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/sector-historical-performance.tsx`
2. Add `RefreshCw` to lucide-react imports (line 1)
3. Save file

### Step 3: Refactor PeriodContent (30 min)
1. Update destructuring to include `isPending`, `isPlaceholderData` (line 114)
2. Add `isPending` check before chartData computation (after line 114)
3. Return skeleton div for first load
4. Wrap existing chart in relative container (after line 131)
5. Add opacity transition div with `isPlaceholderData` condition
6. Add loading indicator overlay with `isFetching && !isPending` condition
7. Update `SectorHistoricalChart` call to pass `isPlaceholderData` prop
8. Save file

### Step 4: Test Tab Switching (30 min)
1. Start dev server: `cd /Users/typham/Documents/GitHub/Stock_Massive && npm run dev`
2. Navigate to dashboard
3. Test scenarios:
   - First load: verify skeleton appears
   - Switch 1W → 2W: verify chart stays visible with opacity fade
   - Switch 2W → 1M: verify smooth transition
   - Rapid switching: verify no flashing
   - Manual refresh: verify loading indicator appears
4. Check browser console for errors
5. Verify network requests in DevTools

### Step 5: Verify Animation Behavior (15 min)
1. Confirm chart animation disabled during `isPlaceholderData` (line 96)
2. Test that animation plays on first load
3. Test that animation skipped during tab switch
4. Verify 200ms opacity transition timing

### Step 6: Edge Case Testing (15 min)
1. Test with slow network (Chrome DevTools throttling)
2. Test with cached data (should be instant)
3. Test with stale data (should refetch in background)
4. Test error scenarios (disconnect network)
5. Test auto-refetch interval (10 minutes)

## Todo List

- [x] Update use-sector-historical-performance.ts hook
  - [x] Change imports to useQuery + keepPreviousData
  - [x] Add placeholderData option
  - [x] Export isPending and isPlaceholderData states
- [x] Update sector-historical-performance.tsx component
  - [x] Add RefreshCw import
  - [x] Add isPending check for first load skeleton
  - [x] Wrap chart in opacity transition container
  - [x] Add loading indicator overlay
- [x] Test tab switching behavior
  - [x] Verify smooth transitions between 1W/2W/1M
  - [x] Verify no skeleton flash on tab switch
  - [x] Verify skeleton only on first load
- [x] Test edge cases
  - [x] Slow network conditions
  - [x] Rapid tab switching
  - [x] Manual refresh button
  - [x] Auto-refetch interval

## Success Criteria

### UX Validation
- [x] Tab switch shows previous chart with 60% opacity
- [x] Transition completes in 200ms
- [x] Loading spinner visible in top-right corner
- [x] No blank state during tab switch
- [x] First load shows skeleton (expected)

### Technical Validation
- [x] `isPlaceholderData` flag accurate during transitions
- [x] Chart animation disabled when `isPlaceholderData=true`
- [x] No TypeScript errors
- [x] No console warnings
- [x] Query cache working correctly

### Performance Validation
- [x] No unnecessary re-renders
- [x] Previous data kept in memory efficiently
- [x] Network requests only when needed
- [x] Stale time respected (5 minutes)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Data type mismatch (data can be undefined) | Medium | High | Add proper TypeScript checks, handle undefined case |
| Breaking existing tests | Low | Medium | Update test mocks to include new state flags |
| SSR hydration mismatch | Low | High | Keep HydrationBoundary at page level unchanged |
| Memory leak from keepPreviousData | Very Low | Medium | TanStack Query handles cleanup automatically |

## Security Considerations

- No security implications (client-side UI change only)
- No API changes
- No authentication/authorization changes
- Data validation remains unchanged

## Next Steps

After completing Phase 01:
1. Validate UX improvements with user
2. Proceed to Phase 02: Apply pattern to remaining sections
3. Document pattern in code standards
4. Consider adding to component library

## Unresolved Questions

None - pattern validated in FundCertificates component and research.
