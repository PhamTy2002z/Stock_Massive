---
phase: 02
title: "Apply Smooth Loading Pattern to All Dashboard Sections"
parent_plan: "./plan.md"
priority: P1
effort: 3-4h
status:
  implementation: done
  review: done
  testing: done
completed: 2026-01-02T23:15:00+07:00
created: 2026-01-02
dependencies: ["phase-01-sector-historical-fix.md"]
---

# Phase 02: Apply Smooth Loading Pattern to All Dashboard Sections

## Context

**Parent Plan:** [Smooth Section Loading Without Flash](./plan.md)
**Depends On:** [Phase 01 - Sector Historical Fix](./phase-01-sector-historical-fix.md)

**Research References:**
- [TanStack Query Patterns](./research/researcher-01-tanstack-query-patterns.md)
- [Component Refactoring](./research/researcher-02-component-refactoring.md)

## Overview

**Date:** 2026-01-02
**Description:** Apply keepPreviousData pattern to remaining dashboard sections for consistent smooth loading UX
**Priority:** P1 (Consistency across dashboard)
**Effort:** 3-4 hours

**Scope:**
Apply Phase 01 pattern to 3 remaining sections using `useSuspenseQuery`:
1. MarketIndices (auto-refetch every 15s)
2. VN30Overview (auto-refetch every 30s)
3. SectorPerformance (auto-refetch every 2min)

**Note:** FundCertificates already uses `keepPreviousData` pattern (no changes needed)

## Key Insights from Research

1. **Consistent Pattern:** All sections should handle loading states identically
2. **Auto-Refetch Behavior:** Sections with frequent auto-refetch benefit most from smooth transitions
3. **Loading Indicator Placement:** Top-right corner spinner for consistency
4. **Opacity Level:** 60% during placeholder state (matches Phase 01)
5. **Transition Duration:** 200ms for smooth feel

## Requirements

### Functional Requirements
- [ ] All sections use `useQuery` with `keepPreviousData`
- [ ] Consistent loading indicator pattern (top-right spinner)
- [ ] Consistent opacity transition (60%, 200ms)
- [ ] First load shows skeleton for each section
- [ ] Manual refresh buttons work smoothly
- [ ] Auto-refetch doesn't disrupt user

### Non-Functional Requirements
- [ ] No breaking changes to existing APIs
- [ ] Maintain SSR compatibility
- [ ] Type safety preserved
- [ ] Performance not degraded

## Architecture Changes

### 1. MarketIndices Migration

**Hook File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-market-indices.ts`

**Current (lines 1-25):**
```typescript
import { useSuspenseQuery } from "@tanstack/react-query"

export function useMarketIndices() {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.marketIndices,
    queryFn: fetchMarketIndices,
    staleTime: 15 * 1000,
    refetchInterval: 15 * 1000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return { data, isFetching, refetch }
}
```

**Updated:**
```typescript
import { useQuery, keepPreviousData } from "@tanstack/react-query"

export function useMarketIndices() {
  const query = useQuery({
    queryKey: queryKeys.marketIndices,
    queryFn: fetchMarketIndices,
    placeholderData: keepPreviousData,
    staleTime: 15 * 1000,
    refetchInterval: 15 * 1000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
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

**Component File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/market-indices.tsx`

**Pattern to Apply:**
```typescript
export function MarketIndices({ className }: { className?: string }) {
  const { data, isPending, isFetching, isPlaceholderData, refetch } = useMarketIndices()

  // First load - show skeleton
  if (isPending) {
    return <MarketIndicesSkeleton className={className} />
  }

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Chỉ số thị trường</CardTitle>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => refetch()}
            disabled={isFetching}
            className="h-8 w-8"
          >
            <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="relative">
          <div className={cn(
            "transition-opacity duration-200",
            isPlaceholderData && "opacity-60"
          )}>
            {/* Existing content */}
          </div>
          {isFetching && !isPending && (
            <div className="absolute top-2 right-2 bg-background/80 backdrop-blur-sm rounded-full p-1.5">
              <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
```

### 2. VN30Overview Migration

**Hook File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-vn30-overview.ts`

**Current (lines 1-25):**
```typescript
import { useSuspenseQuery } from "@tanstack/react-query"

export function useVN30Overview() {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.vn30Overview,
    queryFn: fetchVN30Overview,
    staleTime: 30 * 1000,
    refetchInterval: 30 * 1000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return { data, isFetching, refetch }
}
```

**Updated:**
```typescript
import { useQuery, keepPreviousData } from "@tanstack/react-query"

export function useVN30Overview() {
  const query = useQuery({
    queryKey: queryKeys.vn30Overview,
    queryFn: fetchVN30Overview,
    placeholderData: keepPreviousData,
    staleTime: 30 * 1000,
    refetchInterval: 30 * 1000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
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

**Component Pattern:** Same as MarketIndices - add isPending check, opacity transition, loading overlay

### 3. SectorPerformance Migration

**Hook File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-sector-performance.ts`

**Current (lines 1-34):**
```typescript
import { useSuspenseQuery } from "@tanstack/react-query"

export function useSectorPerformance(): UseSectorPerformanceResult {
  const { data, isFetching, refetch, dataUpdatedAt } = useSuspenseQuery({
    queryKey: queryKeys.sectorPerformance,
    queryFn: fetchSectorPerformance,
    staleTime: 60 * 1000,
    refetchInterval: 120 * 1000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data,
    isFetching,
    refetch,
    lastUpdated: dataUpdatedAt ? new Date(dataUpdatedAt) : null,
  }
}
```

**Updated:**
```typescript
import { useQuery, keepPreviousData } from "@tanstack/react-query"

interface UseSectorPerformanceResult {
  data: SectorPerformanceResponse | undefined
  isPending: boolean
  isFetching: boolean
  isPlaceholderData: boolean
  refetch: () => void
  lastUpdated: Date | null
}

export function useSectorPerformance(): UseSectorPerformanceResult {
  const query = useQuery({
    queryKey: queryKeys.sectorPerformance,
    queryFn: fetchSectorPerformance,
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
    refetchInterval: 120 * 1000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data: query.data,
    isPending: query.isPending,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    refetch: query.refetch,
    lastUpdated: query.dataUpdatedAt ? new Date(query.dataUpdatedAt) : null,
  }
}
```

**Component Pattern:** Same as above - add isPending check, opacity transition, loading overlay

## Related Code Files

### Hooks to Modify
1. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-market-indices.ts` (lines 1-25)
2. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-vn30-overview.ts` (lines 1-25)
3. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-sector-performance.ts` (lines 1-34)

### Components to Modify
1. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/market-indices.tsx`
2. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/vn30-overview-table.tsx`
3. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/sector-performance-section.tsx`

### Reference Files (No Changes)
1. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-fund-certificates.ts` - Already correct
2. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-sector-historical-performance.ts` - Fixed in Phase 01

## Implementation Steps

### Step 1: MarketIndices (45 min)
1. Update hook `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-market-indices.ts`
   - Change imports (line 3)
   - Add placeholderData option
   - Update return statement with new states
2. Find MarketIndices component file
3. Add isPending check for first load
4. Wrap content in opacity transition container
5. Add loading indicator overlay
6. Test auto-refetch behavior (15s interval)

### Step 2: VN30Overview (45 min)
1. Update hook `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-vn30-overview.ts`
   - Change imports (line 3)
   - Add placeholderData option
   - Update return statement with new states
2. Find VN30OverviewTable component file
3. Add isPending check for first load
4. Wrap table in opacity transition container
5. Add loading indicator overlay
6. Test auto-refetch behavior (30s interval)

### Step 3: SectorPerformance (45 min)
1. Update hook `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-sector-performance.ts`
   - Change imports (line 3)
   - Update interface to include new states (line 7-12)
   - Add placeholderData option
   - Update return statement with new states
2. Find SectorPerformanceSection component file
3. Add isPending check for first load
4. Wrap content in opacity transition container
5. Add loading indicator overlay
6. Test auto-refetch behavior (2min interval)

### Step 4: Integration Testing (30 min)
1. Start dev server
2. Load dashboard - verify all sections show skeletons on first load
3. Wait for data to load - verify smooth transitions
4. Test manual refresh on each section
5. Wait for auto-refetch intervals - verify no disruption
6. Test rapid interactions (scrolling, clicking)
7. Check browser console for errors

### Step 5: Cross-Section Consistency (15 min)
1. Verify all loading indicators in same position (top-right)
2. Verify all opacity transitions same duration (200ms)
3. Verify all opacity levels consistent (60%)
4. Verify all skeletons match design system
5. Document pattern for future sections

## Todo List

- [ ] Update MarketIndices
  - [ ] Migrate use-market-indices.ts hook
  - [ ] Update MarketIndices component
  - [ ] Test auto-refetch (15s interval)
- [ ] Update VN30Overview
  - [ ] Migrate use-vn30-overview.ts hook
  - [ ] Update VN30OverviewTable component
  - [ ] Test auto-refetch (30s interval)
- [ ] Update SectorPerformance
  - [ ] Migrate use-sector-performance.ts hook
  - [ ] Update SectorPerformanceSection component
  - [ ] Test auto-refetch (2min interval)
- [ ] Integration testing
  - [ ] Test all sections together
  - [ ] Verify consistent UX across dashboard
  - [ ] Test edge cases (slow network, errors)
- [ ] Documentation
  - [ ] Update code standards with pattern
  - [ ] Add JSDoc comments to hooks

## Success Criteria

### UX Validation
- [ ] All sections show skeleton only on first load
- [ ] All sections use 60% opacity during refetch
- [ ] All sections have 200ms transition duration
- [ ] All loading indicators in top-right corner
- [ ] No content flash during auto-refetch
- [ ] Manual refresh buttons work smoothly

### Technical Validation
- [ ] All hooks export isPending, isPlaceholderData
- [ ] All components handle undefined data correctly
- [ ] No TypeScript errors
- [ ] No console warnings
- [ ] Query cache working efficiently

### Performance Validation
- [ ] Auto-refetch intervals respected
- [ ] No unnecessary re-renders
- [ ] Memory usage stable
- [ ] Network requests optimized

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Component files not found | Low | Medium | Use Grep to locate component files |
| Different component structures | Medium | Medium | Adapt pattern to each component's structure |
| Breaking existing tests | Medium | Medium | Update test mocks for all affected components |
| Type errors from undefined data | Medium | High | Add proper TypeScript guards in all components |
| Inconsistent UX across sections | Low | Medium | Use shared constants for opacity/duration |

## Security Considerations

- No security implications (client-side UI changes only)
- No API changes
- No authentication/authorization changes
- Data validation remains unchanged

## Next Steps

After completing Phase 02:
1. Validate consistent UX across all dashboard sections
2. Update code standards documentation
3. Proceed to Phase 03 (optional prefetch optimization)
4. Consider creating shared loading indicator component

## Unresolved Questions

1. Should we create a shared `useSmoothedQuery` wrapper hook to reduce boilerplate?
2. Should loading indicator be a reusable component?
3. Should we add loading state to page title/favicon?
