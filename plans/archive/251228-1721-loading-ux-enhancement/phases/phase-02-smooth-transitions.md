# Phase 2: Smooth Transitions

## Context

- **Parent Plan**: [plan.md](../plan.md)
- **Depends On**: Phase 1 (Error Boundary)
- **Research**: [researcher-02-suspense-query.md](../research/researcher-02-suspense-query.md)

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-28 |
| Description | Add placeholderData + global loading indicator |
| Priority | HIGH |
| Effort | 2h |
| Status | done |
| Completed | 2025-12-28 |

## Key Insights (from Research)

1. `keepPreviousData` giu data cu trong khi fetch moi, tranh flash
2. `isFetching` + `isPlaceholderData` de show loading hints
3. `useIsFetching()` hook de track global fetching state
4. Visual hints: opacity dim, spinner overlay

## Requirements

### Functional
- F1: Tab switching khong flash skeleton
- F2: Period change (1D, 1W, 1M) giu data cu, show refetching
- F3: Global indicator visible khi any query fetching
- F4: Symbol change giu layout, swap data

### Non-Functional
- NF1: Indicator position fixed top, non-intrusive
- NF2: Transitions feel smooth, <300ms visual delay

## Related Code Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/web/src/components/layout/global-loading-indicator.tsx` | CREATE | Top bar indicator |
| `apps/web/src/app/layout.tsx` | MODIFY | Add GlobalLoadingIndicator |
| `apps/web/src/hooks/use-volume-analysis.ts` | MODIFY | Add keepPreviousData |
| `apps/web/src/hooks/use-market-indices.ts` | MODIFY | Add keepPreviousData |
| `apps/web/src/hooks/use-vn30-overview.ts` | MODIFY | Add keepPreviousData |
| `apps/web/src/hooks/use-sector-performance.ts` | MODIFY | Add keepPreviousData |
| `apps/web/src/hooks/use-income-statement.ts` | MODIFY | Add keepPreviousData |
| `apps/web/src/hooks/use-balance-sheet.ts` | MODIFY | Add keepPreviousData |
| `apps/web/src/hooks/use-cash-flow.ts` | MODIFY | Add keepPreviousData |
| `apps/web/src/hooks/use-shareholders.ts` | MODIFY | Add keepPreviousData |
| `apps/web/src/hooks/use-volume-spikes.ts` | MODIFY | Add keepPreviousData |
| `apps/web/src/hooks/use-financial-statements.ts` | MODIFY | Add keepPreviousData |
| `apps/web/src/hooks/use-health-score.ts` | MODIFY | Add keepPreviousData |
| `apps/web/src/hooks/use-trend-metrics.ts` | MODIFY | Add keepPreviousData |

Note: `use-stock-detail.ts` da co `keepPreviousData` - skip

## Implementation Steps

### Step 1: Create GlobalLoadingIndicator (20 min)

**Path**: `apps/web/src/components/layout/global-loading-indicator.tsx`

```tsx
"use client"

import { useIsFetching } from "@tanstack/react-query"

export function GlobalLoadingIndicator() {
  const isFetching = useIsFetching()

  if (!isFetching) return null

  return (
    <div className="fixed top-0 left-0 right-0 h-0.5 z-50 overflow-hidden">
      <div
        className="h-full w-1/3 bg-primary animate-[loading_1s_ease-in-out_infinite]"
        style={{
          animation: "loading 1s ease-in-out infinite"
        }}
      />
      <style jsx>{`
        @keyframes loading {
          0% { transform: translateX(-100%); }
          50% { transform: translateX(150%); }
          100% { transform: translateX(400%); }
        }
      `}</style>
    </div>
  )
}
```

### Step 2: Add to layout.tsx (5 min)

```tsx
import { GlobalLoadingIndicator } from "@/components/layout/global-loading-indicator"

// Inside body, before children:
<GlobalLoadingIndicator />
```

### Step 3: Update hooks - Template pattern (45 min)

Apply to all hooks that don't have `keepPreviousData`:

```tsx
import { keepPreviousData } from "@tanstack/react-query"

// In useQuery options:
placeholderData: keepPreviousData,

// Return values (add if not present):
return {
  ...query.data,
  isPlaceholderData: query.isPlaceholderData,
  isFetching: query.isFetching,
}
```

**Hooks to update** (12 hooks, ~4 min each):
1. `use-volume-analysis.ts`
2. `use-market-indices.ts`
3. `use-vn30-overview.ts`
4. `use-sector-performance.ts`
5. `use-income-statement.ts`
6. `use-balance-sheet.ts`
7. `use-cash-flow.ts`
8. `use-shareholders.ts`
9. `use-volume-spikes.ts`
10. `use-financial-statements.ts`
11. `use-health-score.ts`
12. `use-trend-metrics.ts`

### Step 4: Add visual hints in components (30 min)

Add dim effect when showing placeholder data:

```tsx
// In components using these hooks:
const { data, isPlaceholderData, isFetching } = useVolumeAnalysis(symbol)

return (
  <div className={cn(
    "transition-opacity duration-200",
    isPlaceholderData && "opacity-60"
  )}>
    {isFetching && <RefetchingBadge />}
    <Chart data={data} />
  </div>
)
```

### Step 5: Test transitions (20 min)

1. Switch stock symbol - verify no flash
2. Switch tabs in stock detail - verify smooth
3. Change period selector - verify data persists
4. Verify global indicator shows during fetch

## Todo List

- [x] Create GlobalLoadingIndicator component
- [x] Add GlobalLoadingIndicator to layout.tsx
- [x] Add CSS animation for loading bar
- [x] Update use-volume-analysis with keepPreviousData
- [x] Update use-market-indices with keepPreviousData (already done)
- [x] Update use-vn30-overview with keepPreviousData (already done)
- [x] Update use-sector-performance with keepPreviousData (already done)
- [x] Update use-income-statement with keepPreviousData
- [x] Update use-balance-sheet with keepPreviousData
- [x] Update use-cash-flow with keepPreviousData
- [x] Update use-shareholders with keepPreviousData
- [x] Update use-volume-spikes with keepPreviousData (already done)
- [x] Update use-financial-statements with keepPreviousData (already done)
- [x] Update use-health-score with keepPreviousData
- [x] Update use-trend-metrics with keepPreviousData
- [x] Add isPlaceholderData visual hints (via hook returns)
- [x] Test all transition scenarios

## Success Criteria

- [x] Symbol switch: no skeleton flash, data swap smooth
- [x] Tab switch: old data visible while fetching
- [x] Period change: chart dims briefly, no remount
- [x] Global indicator: visible during any fetch
- [x] Visual feedback: users know refetch happening

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Stale data confusion | Clear visual hint (opacity dim) |
| Indicator too subtle | Make primary color prominent |

## Next Steps

Phase 3: Suspense Migration - Convert hooks to useSuspenseQuery
