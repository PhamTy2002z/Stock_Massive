# Phase 3: Suspense Migration

## Context

- **Parent Plan**: [plan.md](../plan.md)
- **Depends On**: Phase 1 (Error Boundary), Phase 2 (Smooth Transitions)
- **Research**: [researcher-02-suspense-query.md](../research/researcher-02-suspense-query.md)

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-28 |
| Description | Migrate useQuery to useSuspenseQuery |
| Priority | HIGH |
| Effort | 5h |
| Status | completed |

## Key Insights (from Research)

1. `useSuspenseQuery` guarantees `data` defined - no undefined checks
2. Requires Suspense boundary for loading, ErrorBoundary for errors
3. Migration order: leaf components -> parent components -> pages
4. Still use `keepPreviousData` de tranh suspend on refetch
5. `useSuspenseQueries` cho parallel queries

## Requirements

### Functional
- F1: Components khong can manual isLoading/error checks
- F2: TypeScript: data never undefined
- F3: Suspense fallback show skeleton
- F4: Error boundary catch errors

### Non-Functional
- NF1: No breaking changes to existing behavior
- NF2: Gradual migration, not all-at-once
- NF3: Keep backward compat during migration

## Architecture

### Before (Current Pattern)
```tsx
function StockChart({ symbol }) {
  const { data, isLoading, error } = useQuery(...)

  if (isLoading) return <Skeleton />
  if (error) return <Error />

  return <Chart data={data} /> // data can be undefined
}
```

### After (Suspense Pattern)
```tsx
function StockChart({ symbol }) {
  const { data } = useSuspenseQuery(...) // data always defined
  return <Chart data={data} />
}

// Parent wrapper:
<QueryErrorBoundary>
  <Suspense fallback={<ChartSkeleton />}>
    <StockChart symbol={symbol} />
  </Suspense>
</QueryErrorBoundary>
```

## Related Code Files

### New Files (loading.tsx)

| File | Action | Purpose |
|------|--------|---------|
| `apps/web/src/app/loading.tsx` | CREATE | Root loading skeleton |
| `apps/web/src/app/analytics/deep-dive/loading.tsx` | CREATE | Deep dive skeleton |
| `apps/web/src/app/analytics/volume-spikes/loading.tsx` | CREATE | Volume spikes skeleton |
| `apps/web/src/app/analytics/financial-statements/loading.tsx` | CREATE | Financial skeleton |

### Hook Migrations (Priority Order)

**Tier 1 - Leaf Components (Simple, low risk)**
| File | Action |
|------|--------|
| `hooks/use-market-indices.ts` | MODIFY |
| `hooks/use-vn30-overview.ts` | MODIFY |
| `hooks/use-sector-performance.ts` | MODIFY |

**Tier 2 - Feature Components**
| File | Action |
|------|--------|
| `hooks/use-volume-analysis.ts` | MODIFY |
| `hooks/use-volume-spikes.ts` | MODIFY |
| `hooks/use-financial-statements.ts` | MODIFY |
| `hooks/use-health-score.ts` | MODIFY |
| `hooks/use-trend-metrics.ts` | MODIFY |

**Tier 3 - Complex Components (Higher risk)**
| File | Action |
|------|--------|
| `hooks/use-stock-detail.ts` | MODIFY |
| `hooks/use-income-statement.ts` | MODIFY |
| `hooks/use-balance-sheet.ts` | MODIFY |
| `hooks/use-cash-flow.ts` | MODIFY |

## Implementation Steps

### Step 1: Create loading.tsx files (30 min)

**Path**: `apps/web/src/app/loading.tsx`
```tsx
import { Skeleton } from "@/components/ui/skeleton"

export default function Loading() {
  return (
    <div className="flex-1 p-6 space-y-4">
      <Skeleton className="h-8 w-48" />
      <div className="grid gap-4 md:grid-cols-4">
        {Array(4).fill(0).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-96" />
    </div>
  )
}
```

**Path**: `apps/web/src/app/analytics/deep-dive/loading.tsx`
```tsx
import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

export default function Loading() {
  return (
    <div className="p-6 space-y-6">
      <Skeleton className="h-8 w-64" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><Skeleton className="h-6 w-32" /></CardHeader>
          <CardContent><Skeleton className="h-80" /></CardContent>
        </Card>
        <Card>
          <CardHeader><Skeleton className="h-6 w-32" /></CardHeader>
          <CardContent><Skeleton className="h-80" /></CardContent>
        </Card>
      </div>
    </div>
  )
}
```

Repeat for `volume-spikes/loading.tsx` and `financial-statements/loading.tsx`

### Step 2: Create Suspense-enabled hook pattern (20 min)

Create a template for suspense hooks:

```tsx
// Example: use-market-indices.ts migration
"use client"

import { useSuspenseQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchMarketIndices } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useMarketIndices() {
  const { data, isFetching, isPlaceholderData } = useSuspenseQuery({
    queryKey: queryKeys.marketIndices(),
    queryFn: fetchMarketIndices,
    staleTime: 60 * 1000,
    placeholderData: keepPreviousData,
  })

  // data is ALWAYS defined - no null check needed
  return {
    data, // MarketIndex[], never undefined
    isFetching,
    isPlaceholderData,
  }
}
```

### Step 3: Migrate Tier 1 hooks (45 min)

Apply pattern to:
1. `use-market-indices.ts`
2. `use-vn30-overview.ts`
3. `use-sector-performance.ts`

**Key changes**:
- `useQuery` -> `useSuspenseQuery`
- Remove `isLoading`, `error` from return
- Remove `enabled` option (not supported)
- Keep `placeholderData: keepPreviousData`

### Step 4: Update parent components with Suspense (45 min)

Wrap components using migrated hooks:

```tsx
// Example: Dashboard page
import { Suspense } from "react"
import { QueryErrorBoundary } from "@/components/providers/query-error-boundary"

export function MarketOverviewSection() {
  return (
    <QueryErrorBoundary compact>
      <Suspense fallback={<MarketIndicesSkeleton />}>
        <MarketIndicesCard />
      </Suspense>
    </QueryErrorBoundary>
  )
}
```

### Step 5: Migrate Tier 2 hooks (1h)

Apply to feature hooks:
- `use-volume-analysis.ts`
- `use-volume-spikes.ts`
- `use-financial-statements.ts`
- `use-health-score.ts`
- `use-trend-metrics.ts`

### Step 6: Migrate Tier 3 hooks (1h 30 min)

Complex hooks with conditional enabling:

**Problem**: `useSuspenseQuery` khong support `enabled` option

**Solution for use-stock-detail.ts**:
```tsx
// Option 1: Check before calling
function StockDetailContent({ symbol }: { symbol: string }) {
  const { data } = useSuspenseQuery({
    queryKey: queryKeys.stockDetail(symbol),
    queryFn: () => fetchStockDetail(symbol),
    placeholderData: keepPreviousData,
  })
  return <Detail data={data} />
}

// Wrapper checks validity
function StockDetail({ symbol }: { symbol: string | null }) {
  if (!symbol || !isValidSymbol(symbol)) {
    return <EmptyState />
  }

  return (
    <Suspense fallback={<StockDetailSkeleton />}>
      <StockDetailContent symbol={symbol} />
    </Suspense>
  )
}
```

### Step 7: Test all migrations (30 min)

1. Navigate to each page - verify loading states work
2. Trigger errors - verify boundaries catch
3. Verify no TypeScript errors (data always defined)
4. Test refetch scenarios

## Todo List

- [x] Create app/loading.tsx
- [x] Create analytics/deep-dive/loading.tsx
- [x] Create analytics/volume-spikes/loading.tsx
- [x] Create analytics/financial-statements/loading.tsx
- [x] Migrate use-market-indices to useSuspenseQuery
- [x] Migrate use-vn30-overview to useSuspenseQuery
- [x] Migrate use-sector-performance to useSuspenseQuery
- [x] Add Suspense wrappers for Tier 1 components
- [x] Migrate use-volume-analysis to useSuspenseQuery
- [x] Migrate use-volume-spikes to useSuspenseQuery
- [x] Migrate use-financial-statements to useSuspenseQuery
- [x] Migrate use-health-score to useSuspenseQuery
- [x] Migrate use-trend-metrics to useSuspenseQuery
- [x] Add Suspense wrappers for Tier 2 components
- [x] Migrate use-stock-detail (conditional pattern)
- [x] Migrate use-income-statement
- [x] Migrate use-balance-sheet
- [x] Migrate use-cash-flow
- [x] Migrate use-shareholders
- [x] Test all pages
- [x] Remove unused isLoading/error checks

## Success Criteria

- [x] All hooks use useSuspenseQuery
- [x] loading.tsx files work with Next.js streaming
- [x] TypeScript: No `data!` or `data?.` needed
- [x] Components have no manual loading/error checks
- [x] Suspense + ErrorBoundary wrappers in place

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| useSuspenseQuery breaks SSR | Test with HydrationBoundary |
| enabled option not supported | Use conditional rendering pattern |
| Double suspending | Use keepPreviousData |

## Next Steps

Phase 4: Polish & Optimization - Chart animations, skeleton library
