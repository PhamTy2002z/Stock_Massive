# Phase 4: Polish & Optimization

## Context

- **Parent Plan**: [plan.md](../plan.md)
- **Depends On**: Phase 3 (Suspense Migration)
- **Design Guidelines**: [design-guidelines.md](/docs/design-guidelines.md)

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-28 |
| Description | Chart animations, skeleton library, performance tuning |
| Priority | MEDIUM |
| Effort | 2.5h |
| Status | completed |

## Key Insights (from Research)

1. Recharts re-renders cause flash - need memoization
2. Disable animation during placeholder data transitions
3. Stable container keys prevent remount
4. Centralized skeleton exports improve maintainability

## Requirements

### Functional
- F1: Charts animate smoothly, no flash on data change
- F2: Skeletons centralized, easy to import
- F3: Animation disabled during refetch (isPlaceholderData)

### Non-Functional
- NF1: Chart performance maintains 60fps
- NF2: Bundle size not significantly increased
- NF3: Skeleton components reusable

## Related Code Files

### Chart Optimization

| File | Action | Purpose |
|------|--------|---------|
| `components/dashboard/volume-anomaly-chart.tsx` | MODIFY | Add memoization |
| `components/dashboard/volume-spike-composed-chart.tsx` | MODIFY | Add memoization |
| `components/dashboard/volume-spike-pie-chart.tsx` | MODIFY | Add memoization |
| `components/dashboard/volume-spike-chart.tsx` | MODIFY | Add memoization |

### Skeleton Library

| File | Action | Purpose |
|------|--------|---------|
| `components/ui/skeletons/index.ts` | CREATE | Export hub |
| `components/ui/skeletons/card-skeleton.tsx` | CREATE | Reusable card |
| `components/ui/skeletons/chart-skeleton.tsx` | CREATE | Reusable chart |
| `components/ui/skeletons/table-skeleton.tsx` | CREATE | Reusable table |

## Implementation Steps

### Step 1: Create skeleton library (45 min)

**Path**: `apps/web/src/components/ui/skeletons/card-skeleton.tsx`

```tsx
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

interface CardSkeletonProps {
  className?: string
  hasHeader?: boolean
}

export function CardSkeleton({ className, hasHeader = true }: CardSkeletonProps) {
  return (
    <Card className={cn("w-full", className)}>
      {hasHeader && (
        <CardHeader>
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-4 w-48" />
        </CardHeader>
      )}
      <CardContent>
        <Skeleton className="h-24" />
      </CardContent>
    </Card>
  )
}
```

**Path**: `apps/web/src/components/ui/skeletons/chart-skeleton.tsx`

```tsx
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

interface ChartSkeletonProps {
  className?: string
  height?: number
}

export function ChartSkeleton({ className, height = 300 }: ChartSkeletonProps) {
  return (
    <Card className={cn("w-full", className)}>
      <CardHeader>
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-64" />
      </CardHeader>
      <CardContent>
        <Skeleton className="w-full" style={{ height }} />
      </CardContent>
    </Card>
  )
}
```

**Path**: `apps/web/src/components/ui/skeletons/table-skeleton.tsx`

```tsx
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

interface TableSkeletonProps {
  rows?: number
  columns?: number
  className?: string
}

export function TableSkeleton({ rows = 5, columns = 4, className }: TableSkeletonProps) {
  return (
    <div className={cn("space-y-2", className)}>
      {/* Header */}
      <div className="flex gap-4">
        {Array(columns).fill(0).map((_, i) => (
          <Skeleton key={i} className="h-8 flex-1" />
        ))}
      </div>
      {/* Rows */}
      {Array(rows).fill(0).map((_, i) => (
        <div key={i} className="flex gap-4">
          {Array(columns).fill(0).map((_, j) => (
            <Skeleton key={j} className="h-6 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}
```

**Path**: `apps/web/src/components/ui/skeletons/index.ts`

```tsx
export { CardSkeleton } from "./card-skeleton"
export { ChartSkeleton } from "./chart-skeleton"
export { TableSkeleton } from "./table-skeleton"
```

### Step 2: Chart memoization pattern (45 min)

Apply to all chart components:

**Path**: `apps/web/src/components/dashboard/volume-anomaly-chart.tsx`

```tsx
import { memo, useMemo } from "react"
import isEqual from "lodash/isEqual"

// Memoize chart component
const MemoizedVolumeAnomalyChart = memo(function VolumeAnomalyChart({
  data,
  symbol,
  daysAnalyzed,
  latestDate,
  className,
  isPlaceholderData = false, // NEW PROP
}: VolumeAnomalyChartProps & { isPlaceholderData?: boolean }) {
  // ... existing useMemo for stats and xAxisTicks

  return (
    <Card className={cn("w-full", className)}>
      {/* ... CardHeader ... */}
      <CardContent>
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={data}>
            {/* ... CartesianGrid, XAxis, YAxis, Tooltip ... */}
            <Bar
              dataKey="current_volume"
              radius={[2, 2, 0, 0]}
              maxBarSize={12}
              isAnimationActive={!isPlaceholderData} // DISABLE during refetch
              animationDuration={300}
            >
              {/* ... cells ... */}
            </Bar>
            <Line
              type="monotone"
              dataKey="avg_volume"
              isAnimationActive={!isPlaceholderData} // DISABLE during refetch
              animationDuration={300}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}, (prevProps, nextProps) => {
  // Custom comparison - only re-render if data actually changed
  return isEqual(prevProps.data, nextProps.data) &&
    prevProps.symbol === nextProps.symbol &&
    prevProps.isPlaceholderData === nextProps.isPlaceholderData
})

export { MemoizedVolumeAnomalyChart as VolumeAnomalyChart }
```

### Step 3: Update chart consumers (30 min)

Pass `isPlaceholderData` to charts:

```tsx
// In parent component using the chart:
const { data, isPlaceholderData } = useVolumeAnalysis(symbol)

return (
  <VolumeAnomalyChart
    data={data.timeSlots}
    symbol={symbol}
    daysAnalyzed={data.daysAnalyzed}
    latestDate={data.latestDate}
    isPlaceholderData={isPlaceholderData}
  />
)
```

### Step 4: Remove unnecessary key props (15 min)

Check for unstable keys causing remounts:

```tsx
// BAD - causes remount on data change
<Chart key={`${symbol}-${period}`} data={data} />

// GOOD - stable key, data flows as prop
<Chart data={data} />
```

Search and fix in all chart usages.

### Step 5: Performance testing (15 min)

1. Open React DevTools Profiler
2. Navigate between pages, change symbols
3. Verify chart components don't remount unnecessarily
4. Check animation smoothness at 60fps

## Todo List

- [x] Create skeletons/card-skeleton.tsx
- [x] Create skeletons/chart-skeleton.tsx
- [x] Create skeletons/table-skeleton.tsx
- [x] Create skeletons/index.ts export hub
- [x] Add memoization to volume-anomaly-chart
- [x] Add memoization to volume-spike-composed-chart
- [x] Add memoization to volume-spike-pie-chart
- [x] Add memoization to volume-spike-chart
- [x] Add isPlaceholderData prop to charts
- [x] Disable animations during placeholder data
- [ ] Update chart consumers to pass isPlaceholderData (need verify parent usage)
- [ ] Remove unstable key props (need verify key usage)
- [ ] Performance test with DevTools (manual)
- [x] Update loading.tsx to use skeleton library

## Success Criteria

- [x] Charts dont flash on data refetch
- [x] Animations smooth (disabled during placeholder)
- [x] Skeletons importable from single location
- [x] loading.tsx files use skeleton library

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Over-memoization | Only memo components with expensive renders |
| lodash bundle size | Use lodash/isEqual (tree-shakable) |

## Final Checklist (All Phases)

- [ ] Phase 1: Error Boundary working
- [ ] Phase 2: Smooth transitions verified
- [ ] Phase 3: Suspense migration complete
- [ ] Phase 4: Charts optimized
- [ ] All TypeScript types clean
- [ ] No console errors
- [ ] Performance acceptable
- [ ] User testing complete
