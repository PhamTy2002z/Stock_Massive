# Migration: useQuery → useSuspenseQuery (Next.js 15 + TanStack Query v5)

## Trade-offs Overview

### useSuspenseQuery Benefits
- **Type Safety**: `data` always defined, no `undefined` checks needed
- **Cleaner Code**: Eliminates manual `isLoading`, `isError` state checks
- **Native Suspense**: Works with React 18+ Suspense boundaries
- **Streaming**: Integrates with Next.js 15 streaming/loading.tsx

### Trade-offs
- **Error Boundaries Required**: Errors throw, must wrap with ErrorBoundary
- **No Progressive Loading**: Can't show partial data while refetching
- **Harder Debugging**: Suspense throws break standard flow

## Migration Patterns

### 1. Basic useQuery → useSuspenseQuery

**Before:**
```tsx
function StockChart({ symbol }: { symbol: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['stock', symbol],
    queryFn: () => fetchStockData(symbol),
  })

  if (isLoading) return <ChartSkeleton />
  if (error) return <ErrorMessage error={error} />

  return <Chart data={data} />
}
```

**After:**
```tsx
function StockChart({ symbol }: { symbol: string }) {
  const { data } = useSuspenseQuery({
    queryKey: ['stock', symbol],
    queryFn: () => fetchStockData(symbol),
  })
  // data is always defined - no undefined checks needed
  return <Chart data={data} />
}

// In parent:
<Suspense fallback={<ChartSkeleton />}>
  <ErrorBoundary fallback={<ErrorMessage />}>
    <StockChart symbol="AAPL" />
  </ErrorBoundary>
</Suspense>
```

### 2. Parallel Queries → useSuspenseQueries

**Before:**
```tsx
const { data: stock } = useQuery({ queryKey: ['stock', symbol], queryFn: fetchStock })
const { data: news } = useQuery({ queryKey: ['news', symbol], queryFn: fetchNews })
const { data: financials } = useQuery({ queryKey: ['financials', symbol], queryFn: fetchFinancials })
```

**After:**
```tsx
const [
  { data: stock },
  { data: news },
  { data: financials }
] = useSuspenseQueries({
  queries: [
    { queryKey: ['stock', symbol], queryFn: fetchStock },
    { queryKey: ['news', symbol], queryFn: fetchNews },
    { queryKey: ['financials', symbol], queryFn: fetchFinancials },
  ]
})
```

**Benefits**: All queries suspend together, single loading state

### 3. Smooth Transitions with placeholderData

**Problem**: useSuspenseQuery suspends on refetch, causing jarring loading states

**Solution**: Use `placeholderData` to keep old data visible during refetch

```tsx
const { data } = useSuspenseQuery({
  queryKey: ['stocks', filter],
  queryFn: () => fetchStocks(filter),
  placeholderData: keepPreviousData, // v5 import
})
```

**Note**: `keepPreviousData` replaces v4's `keepPreviousData: true` boolean

### 4. Next.js 15 Integration Patterns

#### Pattern A: Route-level loading.tsx

```tsx
// app/stocks/[symbol]/loading.tsx
export default function Loading() {
  return <StockPageSkeleton />
}

// app/stocks/[symbol]/page.tsx
export default function StockPage({ params }) {
  // Entire page wrapped in implicit Suspense boundary
  return <StockDashboard symbol={params.symbol} />
}

// components/StockDashboard.tsx
'use client'
function StockDashboard({ symbol }: { symbol: string }) {
  const { data } = useSuspenseQuery({
    queryKey: ['stock', symbol],
    queryFn: () => fetchStock(symbol),
  })
  return <div>{/* render data */}</div>
}
```

#### Pattern B: Granular Suspense boundaries

```tsx
export default function StockPage({ params }) {
  return (
    <>
      <Header /> {/* Static - renders immediately */}

      <Suspense fallback={<ChartSkeleton />}>
        <StockChart symbol={params.symbol} />
      </Suspense>

      <Suspense fallback={<NewsSkeleton />}>
        <NewsSection symbol={params.symbol} />
      </Suspense>
    </>
  )
}
```

**Benefits**: Header visible immediately, chart/news stream independently

## TypeScript Benefits

```tsx
// useQuery - data can be undefined
const { data } = useQuery({ ... })
data?.toFixed(2) // Optional chaining required

// useSuspenseQuery - data always defined
const { data } = useSuspenseQuery({ ... })
data.toFixed(2) // No optional chaining needed
```

## Caveats & Gotchas

### 1. ErrorBoundary Required
useSuspenseQuery throws errors, must catch with ErrorBoundary or app crashes

```tsx
import { ErrorBoundary } from 'react-error-boundary'

<ErrorBoundary fallback={<ErrorUI />}>
  <ComponentWithSuspenseQuery />
</ErrorBoundary>
```

### 2. No Partial Loading States
Can't show "Refreshing..." badge while refetching without `placeholderData`

**Workaround**: Use `isFetching` flag with placeholderData

```tsx
const { data, isFetching } = useSuspenseQuery({
  queryKey: ['stock', symbol],
  queryFn: fetchStock,
  placeholderData: keepPreviousData,
})

return (
  <>
    {isFetching && <RefreshingBadge />}
    <Chart data={data} />
  </>
)
```

### 3. Client Component Requirement
useSuspenseQuery only works in Client Components ('use client')

### 4. Context Prop Removed (v5)
Pass custom `queryClient` directly instead of `context`

```tsx
const { data } = useSuspenseQuery(
  { queryKey, queryFn },
  customQueryClient // 2nd argument
)
```

## Recommended Migration Order

### Phase 1: Leaf Components (Low Risk)
Start with isolated components without complex interactions
- Individual charts, stats cards, data tables

### Phase 2: Parallel Queries
Migrate components using multiple independent queries
- Dashboard components fetching stock + news + financials
- Use `useSuspenseQueries` for cleaner code

### Phase 3: User-Interactive Components
Components with filters, search, pagination
- **Critical**: Add `placeholderData: keepPreviousData` to prevent jarring suspensions

### Phase 4: Route Pages
Migrate top-level pages, add ErrorBoundaries
- Decide: route-level `loading.tsx` vs granular `<Suspense>` boundaries

## Unresolved Questions

1. **Optimistic Updates**: How do useSuspenseQuery mutations interact with Suspense? Test needed.
2. **Prefetching**: Does `queryClient.prefetchQuery` work with useSuspenseQueries waterfall? Verify.
3. **Error Recovery**: Can ErrorBoundary `resetKeys` trigger useSuspenseQuery refetch? Needs testing.
4. **Streaming SSR**: Do Next.js 15 Server Components prefetch work with client-side useSuspenseQuery? Check hydration.
