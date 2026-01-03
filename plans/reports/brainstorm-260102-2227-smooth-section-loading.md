# Brainstorm: Smooth Section Loading Without Full Page Reload

**Date:** 2026-01-02
**Priority:** Critical
**Status:** Solution Agreed

---

## Problem Statement

When switching tabs/filters in dashboard sections (e.g., Sector Historical Performance 1W/2W/1M), skeleton loading appears and replaces content, causing jarring UX. User wants smooth transitions where only selected section updates without full content flash.

**Current Behavior:**
- Tab switch → skeleton replaces chart → new data appears
- Creates blank state during loading
- Disrupts visual continuity

**Desired Behavior:**
- Tab switch → previous chart stays visible with subtle opacity fade
- Loading indicator shows progress without hiding content
- Smooth, professional transition

---

## Current Implementation Analysis

### Architecture Overview

**State Management:** TanStack Query v5 (React Query)

**Two Query Patterns in Use:**

| Pattern | Hook | Loading Handling | Components |
|---------|------|------------------|------------|
| Suspense | `useSuspenseQuery` | React Suspense boundary | MarketIndices, VN30Overview, SectorPerformance, **SectorHistorical** |
| Standard | `useQuery` | Manual isLoading check | **FundCertificates** |

### Problem Components

**1. SectorHistoricalPerformance** (`apps/web/src/components/dashboard/sector-historical-performance.tsx:134`)
- Uses `useSuspenseQuery` without `placeholderData`
- Tab switching triggers Suspense boundary → skeleton appears
- Hook: `use-sector-historical-performance.ts:13`

**2. FundCertificates** (`apps/web/src/components/dashboard/fund-certificates.tsx:12`)
- Already uses `keepPreviousData` correctly
- But manual loading check shows skeleton on first load
- Hook: `use-fund-certificates.ts:13` ✓ (already has `placeholderData: keepPreviousData`)

**3. All Manual Refresh Buttons**
- RefreshCw icon spins during `isFetching`
- But content may flash if not using `placeholderData`

---

## Root Cause

**useSuspenseQuery Limitation:**
- `useSuspenseQuery` doesn't support `placeholderData` option
- When query key changes (tab switch), Suspense boundary triggers
- Suspense fallback (skeleton) replaces content during fetch
- No way to keep previous data visible with Suspense pattern

**Source:** TanStack Query v5 docs - `useSuspenseQuery` doesn't accept `placeholderData` parameter

---

## Evaluated Solutions

### Solution 1: Migrate to useQuery with keepPreviousData ✅ RECOMMENDED

**Approach:**
- Replace `useSuspenseQuery` → `useQuery` with `placeholderData: keepPreviousData`
- Handle loading states manually with `isPending` vs `isFetching`
- Keep Suspense boundary at page level for SSR hydration
- Use `isPlaceholderData` flag for visual feedback

**Implementation:**

```tsx
// Hook: use-sector-historical-performance.ts
export function useSectorHistoricalPerformance(period: SectorHistoricalPeriod = "1W") {
  const query = useQuery({
    queryKey: queryKeys.sectorHistoricalPerformance(period),
    queryFn: () => fetchSectorHistoricalPerformance(period),
    placeholderData: keepPreviousData,  // ← KEY CHANGE
    staleTime: 5 * 60 * 1000,
    refetchInterval: 10 * 60 * 1000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  })

  return {
    data: query.data,
    isPending: query.isPending,        // ← First load
    isFetching: query.isFetching,      // ← Background refetch
    isPlaceholderData: query.isPlaceholderData,  // ← Showing stale data
    refetch: query.refetch,
  }
}

// Component: sector-historical-performance.tsx
function PeriodContent({ period }: { period: SectorHistoricalPeriod }) {
  const { data, isPending, isFetching, isPlaceholderData } = useSectorHistoricalPerformance(period)

  // First load only - show skeleton
  if (isPending) {
    return <div className="h-[280px] bg-muted animate-pulse rounded" />
  }

  return (
    <div className="relative">
      {/* Chart stays visible during tab switch */}
      <div className={cn(
        "transition-opacity duration-200",
        isPlaceholderData && "opacity-60"  // ← Subtle fade during loading
      )}>
        <SectorHistoricalChart data={chartData} isPlaceholderData={isPlaceholderData} />
      </div>

      {/* Optional: subtle loading indicator */}
      {isFetching && !isPending && (
        <div className="absolute top-2 right-2">
          <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />
        </div>
      )}
    </div>
  )
}
```

**Pros:**
- ✅ Smooth transitions - no content flash
- ✅ Previous data visible during fetch
- ✅ Subtle opacity fade provides feedback
- ✅ Minimal code changes
- ✅ Consistent with FundCertificates pattern
- ✅ Works with all query types (tab switch, manual refresh, auto-refetch)

**Cons:**
- ⚠️ Lose automatic Suspense error boundary handling (need manual error handling)
- ⚠️ Need to handle `isPending` state manually
- ⚠️ Slightly more boilerplate than Suspense

**Effort:** Low (2-3 hours)
- Modify 1 hook file
- Update 1 component file
- Test tab switching behavior

---

### Solution 2: Keep Suspense + Prefetch Strategy

**Approach:**
- Keep `useSuspenseQuery`
- Prefetch next tab data on hover/mount
- Data already in cache → instant switch, no Suspense trigger

**Implementation:**

```tsx
export function SectorHistoricalPerformance() {
  const queryClient = useQueryClient()
  const [period, setPeriod] = useState<SectorHistoricalPeriod>("1W")

  // Prefetch all periods on mount
  useEffect(() => {
    const periods: SectorHistoricalPeriod[] = ["1W", "2W", "1M"]
    periods.forEach(p => {
      if (p !== period) {
        queryClient.prefetchQuery({
          queryKey: queryKeys.sectorHistoricalPerformance(p),
          queryFn: () => fetchSectorHistoricalPerformance(p),
        })
      }
    })
  }, [period, queryClient])

  return (
    <Tabs value={period} onValueChange={(v) => setPeriod(v as SectorHistoricalPeriod)}>
      <Suspense fallback={<Skeleton />}>
        <PeriodContent period={period} />
      </Suspense>
    </Tabs>
  )
}
```

**Pros:**
- ✅ Keep Suspense pattern (simpler error handling)
- ✅ Instant tab switch if prefetch succeeds
- ✅ No manual loading state management

**Cons:**
- ❌ Still shows skeleton if prefetch fails/slow
- ❌ Extra network requests (prefetch all tabs)
- ❌ Doesn't solve manual refresh button issue
- ❌ Doesn't work for dynamic filters (only works for known tabs)
- ❌ Race conditions if user switches tabs quickly

**Effort:** Medium (3-4 hours)

---

### Solution 3: Hybrid - Suspense at Page Level, useQuery in Components

**Approach:**
- Keep Suspense boundary at page level for SSR
- Use `useQuery` with `placeholderData` in individual components
- Best of both worlds

**Implementation:**

```tsx
// page.tsx - Suspense for initial SSR hydration
export default async function Home() {
  const dehydratedState = await prefetchData()

  return (
    <HydrationBoundary state={dehydratedState}>
      <Suspense fallback={<DashboardSkeleton />}>
        <DashboardLayoutClient>
          {/* Components use useQuery internally */}
          <SectorHistoricalPerformance />
        </DashboardLayoutClient>
      </Suspense>
    </HydrationBoundary>
  )
}

// Component uses useQuery (not useSuspenseQuery)
function SectorHistoricalPerformance() {
  const { data, isPending, isFetching, isPlaceholderData } = useQuery({
    queryKey: ['sector-historical', period],
    queryFn: () => fetchData(period),
    placeholderData: keepPreviousData,
  })

  if (isPending) return <Skeleton />

  return (
    <div className={isPlaceholderData ? 'opacity-60' : ''}>
      <Chart data={data} />
    </div>
  )
}
```

**Pros:**
- ✅ Smooth transitions after initial load
- ✅ Keep SSR benefits
- ✅ Suspense handles initial page load
- ✅ useQuery handles subsequent interactions

**Cons:**
- ⚠️ More complex mental model
- ⚠️ Need to ensure prefetch matches query keys

**Effort:** Low-Medium (same as Solution 1)

---

## Recommended Solution

**Solution 1: Migrate to useQuery with keepPreviousData**

**Rationale:**
1. **Simplest implementation** - minimal code changes
2. **Solves all use cases** - tab switch, manual refresh, auto-refetch
3. **Consistent pattern** - FundCertificates already uses this
4. **Best UX** - guaranteed smooth transitions
5. **Future-proof** - works with dynamic filters, not just tabs

**Trade-off Accepted:**
- Manual error handling instead of ErrorBoundary (acceptable - already doing this in FundCertificates)

---

## Implementation Plan

### Phase 1: Fix SectorHistoricalPerformance (Critical)

**Files to modify:**
1. `apps/web/src/hooks/use-sector-historical-performance.ts`
   - Replace `useSuspenseQuery` → `useQuery`
   - Add `placeholderData: keepPreviousData`
   - Export `isPending`, `isPlaceholderData` states

2. `apps/web/src/components/dashboard/sector-historical-performance.tsx`
   - Update `PeriodContent` to handle `isPending` state
   - Add opacity transition on `isPlaceholderData`
   - Add optional loading indicator overlay

**Testing:**
- Switch between 1W/2W/1M tabs rapidly
- Verify chart stays visible with opacity fade
- Verify skeleton only on first load
- Test manual refresh button

---

### Phase 2: Enhance All Manual Refresh Buttons (High Priority)

**Pattern to apply:**

```tsx
// All components with RefreshCw button
<div className="relative">
  <div className={cn(
    "transition-opacity duration-200",
    isPlaceholderData && "opacity-60"
  )}>
    {/* Content */}
  </div>

  {isFetching && !isPending && (
    <div className="absolute top-2 right-2 bg-background/80 backdrop-blur-sm rounded-full p-1">
      <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />
    </div>
  )}
</div>
```

**Components to update:**
- MarketIndices
- VN30OverviewTable
- SectorPerformanceSection
- FundCertificates (already has keepPreviousData, just add overlay)

---

### Phase 3: Optimize with Prefetching (Optional Enhancement)

**Add prefetch for common user flows:**

```tsx
// Prefetch next page in pagination
useEffect(() => {
  if (data?.hasMore) {
    queryClient.prefetchQuery({
      queryKey: ['items', page + 1],
      queryFn: () => fetchItems(page + 1),
    })
  }
}, [page, data, queryClient])

// Prefetch on tab hover
<TabsTrigger
  onMouseEnter={() => {
    queryClient.prefetchQuery({
      queryKey: ['sector-historical', '2W'],
      queryFn: () => fetchSectorHistoricalPerformance('2W'),
    })
  }}
>
  2 Tuần
</TabsTrigger>
```

---

## Success Metrics

**UX Improvements:**
- ✅ No skeleton flash during tab switch
- ✅ Content remains visible during loading
- ✅ Smooth opacity transitions
- ✅ Clear loading feedback without disruption

**Technical Validation:**
- ✅ `isPlaceholderData` flag works correctly
- ✅ First load shows skeleton (expected)
- ✅ Subsequent loads show opacity fade (smooth)
- ✅ Manual refresh doesn't flash content
- ✅ Auto-refetch doesn't disrupt user

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Error handling complexity | Medium | Copy FundCertificates error pattern |
| Stale data confusion | Low | Opacity fade clearly indicates loading |
| Performance with large data | Low | keepPreviousData is memory-efficient |
| Breaking SSR hydration | Medium | Keep HydrationBoundary at page level |

---

## Alternative Considered & Rejected

**CSS-only solution (opacity on entire section):**
- ❌ Doesn't prevent skeleton from appearing
- ❌ Doesn't keep previous data visible
- ❌ Only cosmetic, doesn't solve root cause

**Disable Suspense entirely:**
- ❌ Lose SSR benefits
- ❌ More complex initial loading state
- ❌ Unnecessary - hybrid approach works better

---

## Next Steps

1. **User approval** - Confirm Solution 1 approach
2. **Create implementation plan** - Use `/plan` command to generate detailed plan
3. **Implement Phase 1** - Fix SectorHistoricalPerformance (critical)
4. **Test & validate** - Verify smooth transitions
5. **Roll out Phase 2** - Apply to all sections
6. **Optional Phase 3** - Add prefetching optimizations

---

## Unresolved Questions

None - solution is clear and validated against TanStack Query best practices.
