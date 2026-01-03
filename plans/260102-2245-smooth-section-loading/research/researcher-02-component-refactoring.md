# Component Refactoring: Suspense to Manual Loading States

## 1. Suspense Boundary Patterns

### How Suspense + useSuspenseQuery Works
- `useSuspenseQuery` throws a Promise during fetch, caught by nearest `<Suspense>` boundary
- Data is **always defined** after component renders (no `undefined` check needed)
- ErrorBoundary catches thrown errors from failed queries

### Why Suspense Triggers Skeleton on Query Key Changes
- When query key changes (e.g., filter param), new Promise thrown
- Suspense boundary re-renders fallback until Promise resolves
- **Problem**: Every param change shows skeleton, even with cached data nearby

### Current Codebase Pattern (Page-Level Suspense)
```tsx
// apps/web/src/app/page.tsx
<HydrationBoundary state={dehydratedState}>
  <Suspense fallback={<DashboardSkeleton />}>
    <DashboardLayoutClient>
      <MarketIndices />
      <SectorPerformanceSection />
      <VN30OverviewTable />
    </DashboardLayoutClient>
  </Suspense>
</HydrationBoundary>
```

**Issue**: Single Suspense wraps all sections; any section refetch triggers full skeleton.

---

## 2. Manual Loading State Patterns

### Migration: useSuspenseQuery -> useQuery
```tsx
// Before (Suspense)
const { data, isFetching, refetch } = useSuspenseQuery({
  queryKey: queryKeys.marketIndices,
  queryFn: fetchMarketIndices,
})

// After (Manual)
const { data, isPending, isFetching, isError, error, refetch } = useQuery({
  queryKey: queryKeys.marketIndices,
  queryFn: fetchMarketIndices,
})
```

### Key State Differences
| State | Description | Use Case |
|-------|-------------|----------|
| `isPending` | No data yet (initial load) | Show skeleton |
| `isFetching` | Fetching (initial or background) | Show spinner overlay |
| `isError` | Query failed | Show error UI |
| `data` | Can be `undefined` | Must check before render |

### Conditional Rendering Strategy
```tsx
function MarketIndices({ className }: Props) {
  const { data, isPending, isFetching, isError, error, refetch } = useMarketIndices()

  // 1. Initial load - show skeleton
  if (isPending) {
    return <MarketIndicesSkeleton className={className} />
  }

  // 2. Error state - show error UI
  if (isError) {
    return <ErrorCard error={error} onRetry={refetch} className={className} />
  }

  // 3. Success - render with optional fetching indicator
  return (
    <div className={cn(className, isFetching && "opacity-70")}>
      <RefreshButton isFetching={isFetching} onRefresh={refetch} />
      <MarketIndicesContent indices={data} />
    </div>
  )
}
```

### Background Refetch Indicator Patterns
```tsx
// Pattern A: Opacity reduction
<div className={cn(isFetching && "opacity-60 pointer-events-none")}>

// Pattern B: Spinner overlay
<div className="relative">
  {isFetching && <SpinnerOverlay />}
  <Content />
</div>

// Pattern C: Header spinner (current codebase pattern)
<RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
```

---

## 3. Error Handling Migration

### Before: ErrorBoundary with Suspense
```tsx
// apps/web/src/components/providers/query-error-boundary.tsx
<QueryErrorResetBoundary>
  {({ reset }) => (
    <ErrorBoundary onReset={reset} fallbackRender={ErrorFallback}>
      {children}
    </ErrorBoundary>
  )}
</QueryErrorResetBoundary>
```

### After: Manual Error Handling
```tsx
function SectionWithError() {
  const { data, isError, error, refetch } = useQuery({...})

  if (isError) {
    return (
      <div className="rounded-xl border bg-card p-6 text-center">
        <p className="text-destructive">{error.message}</p>
        <Button onClick={() => refetch()} variant="outline" size="sm">
          Retry
        </Button>
      </div>
    )
  }
  // ...
}
```

### Hybrid Approach (Recommended)
- Keep global `QueryErrorBoundary` for unexpected errors
- Use `throwOnError: false` (default) for component-level handling
- Graceful degradation per section

---

## 4. Hook Migration Template

```tsx
// Before: use-market-indices.ts
export function useMarketIndices() {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.marketIndices,
    queryFn: fetchMarketIndices,
    staleTime: 15 * 1000,
  })
  return { data, isFetching, refetch }
}

// After: use-market-indices.ts
export function useMarketIndices() {
  const { data, isPending, isFetching, isError, error, refetch } = useQuery({
    queryKey: queryKeys.marketIndices,
    queryFn: fetchMarketIndices,
    staleTime: 15 * 1000,
    placeholderData: keepPreviousData, // Smooth transitions
  })
  return { data, isPending, isFetching, isError, error, refetch }
}
```

### placeholderData: keepPreviousData
- Keeps previous data visible during refetch
- Prevents flash of skeleton on param changes
- Import: `import { keepPreviousData } from "@tanstack/react-query"`

---

## 5. Testing Considerations

### Testing Loading States
```tsx
// Mock isPending state
vi.mocked(useMarketIndices).mockReturnValue({
  data: undefined,
  isPending: true,
  isFetching: true,
  isError: false,
  error: null,
  refetch: vi.fn(),
})
expect(screen.getByTestId("skeleton")).toBeInTheDocument()
```

### Testing Error States
```tsx
vi.mocked(useMarketIndices).mockReturnValue({
  data: undefined,
  isPending: false,
  isFetching: false,
  isError: true,
  error: new Error("Network error"),
  refetch: mockRefetch,
})
expect(screen.getByText(/network error/i)).toBeInTheDocument()
fireEvent.click(screen.getByRole("button", { name: /retry/i }))
expect(mockRefetch).toHaveBeenCalled()
```

### Testing Transitions
```tsx
// Initial render with data
const { rerender } = render(<Component />)
expect(screen.queryByTestId("skeleton")).not.toBeInTheDocument()

// Simulate background refetch
vi.mocked(useHook).mockReturnValue({ ...mockData, isFetching: true })
rerender(<Component />)
expect(screen.getByTestId("content")).toHaveClass("opacity-70")
```

---

## 6. Migration Checklist

1. [ ] Update hook: `useSuspenseQuery` -> `useQuery`
2. [ ] Add `isPending`, `isError`, `error` to return
3. [ ] Add `placeholderData: keepPreviousData` for smooth transitions
4. [ ] Update component: Add loading/error conditional renders
5. [ ] Create/reuse skeleton component for `isPending`
6. [ ] Add error UI with retry button
7. [ ] Add `isFetching` indicator (spinner/opacity)
8. [ ] Remove Suspense wrapper if section-level
9. [ ] Update tests for new states

---

## Unresolved Questions

1. Should we keep page-level Suspense for SSR hydration benefits?
2. Per-section ErrorBoundary vs inline error handling preference?
3. Standardize fetching indicator pattern across all sections?
