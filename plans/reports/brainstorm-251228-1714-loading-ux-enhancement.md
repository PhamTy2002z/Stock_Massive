# Brainstorm Report: Loading UX Enhancement

**Date:** 2024-12-28
**Status:** Recommendation Complete
**Scope:** Major Refactor - All balanced improvements

---

## 1. Problem Statement

Cải thiện độ mượt mà trong:
- Loading states (initial load, refetch, pagination)
- Chart loading (Recharts với data changes)
- Data loading patterns (React Query)
- Error state handling (recovery, retry, graceful degradation)

---

## 2. Current State Analysis

### Strengths ✅
| Area | Implementation |
|------|---------------|
| Data fetching | React Query v5.90 với staleTime, gcTime |
| Skeleton pattern | Consistent inline/exported skeletons |
| Chart lazy load | next/dynamic với SSR:false |
| Server prefetch | HydrationBoundary cho initial data |

### Gaps ❌
| Gap | Impact |
|-----|--------|
| No Error Boundary | Unhandled errors crash entire app |
| No useSuspenseQuery | Manual loading/error checks everywhere |
| No loading.tsx files | Missing Next.js streaming benefits |
| Inconsistent skeleton exports | Code duplication, hard to maintain |
| No global loading indicator | User confused during background refetch |
| No useTransition for navigation | Jarring page transitions |

---

## 3. Recommended Upgrades

### 3.1 Error Boundary System (Priority: HIGH)

**Package:** `react-error-boundary` (đã proven, maintained)

**Implementation:**
```tsx
// components/providers/query-error-boundary.tsx
import { QueryErrorResetBoundary } from "@tanstack/react-query"
import { ErrorBoundary } from "react-error-boundary"

export function QueryErrorBoundary({ children }: { children: React.ReactNode }) {
  return (
    <QueryErrorResetBoundary>
      {({ reset }) => (
        <ErrorBoundary
          onReset={reset}
          fallbackRender={({ error, resetErrorBoundary }) => (
            <ErrorFallback error={error} onRetry={resetErrorBoundary} />
          )}
        >
          {children}
        </ErrorBoundary>
      )}
    </QueryErrorResetBoundary>
  )
}
```

**Placement Strategy:**
- Root level: `app/layout.tsx` - catch-all
- Feature level: Each analytics page - isolated failures
- Component level: Chart containers - granular recovery

---

### 3.2 Migrate to useSuspenseQuery (Priority: HIGH)

**Before:**
```tsx
// Current pattern - verbose, repetitive
function StockDetail({ symbol }) {
  const { data, isLoading, error } = useQuery(...)

  if (isLoading) return <Skeleton />
  if (error) return <Error />
  if (!data) return <Empty />

  return <Content data={data} />
}
```

**After:**
```tsx
// With useSuspenseQuery - clean, declarative
function StockDetail({ symbol }) {
  const { data } = useSuspenseQuery(...)
  return <Content data={data} /> // data guaranteed!
}

// Parent handles loading/error via boundaries
<QueryErrorBoundary>
  <Suspense fallback={<StockDetailSkeleton />}>
    <StockDetail symbol={symbol} />
  </Suspense>
</QueryErrorBoundary>
```

**Benefits:**
- TypeScript: `data` không bao giờ undefined
- Cleaner components: No loading/error checks
- Colocated concerns: Parent controls UX
- Better streaming: Works with Next.js SSR streaming

**Migration Strategy:**
1. Start with leaf components (charts, widgets)
2. Move up to feature components (tabs, panels)
3. Finally pages

---

### 3.3 Next.js loading.tsx Convention (Priority: MEDIUM)

**Add streaming loading states:**
```
app/
├── loading.tsx                    # Global spinner/skeleton
├── analytics/
│   ├── loading.tsx               # Analytics shared skeleton
│   ├── deep-dive/
│   │   └── loading.tsx           # Deep dive specific
│   ├── volume-spikes/
│   │   └── loading.tsx           # Volume spikes specific
│   └── financial-statements/
│       └── loading.tsx           # Financial specific
```

**Benefits:**
- Automatic Suspense wrapping by Next.js
- Instant navigation feedback
- Static shell streaming

---

### 3.4 placeholderData for Smooth Transitions (Priority: HIGH)

**Current issue:** Flash content khi queryKey thay đổi (switch tabs, pagination)

**Solution:**
```tsx
import { keepPreviousData, useQuery } from "@tanstack/react-query"

const { data, isPlaceholderData, isFetching } = useQuery({
  queryKey: ["stock", symbol, period],
  queryFn: () => fetchData(symbol, period),
  placeholderData: keepPreviousData, // Keep old data while fetching new
})

// UI hint: Show subtle loading indicator
return (
  <div className={isPlaceholderData ? "opacity-70" : ""}>
    {isFetching && <RefetchIndicator />}
    <Chart data={data} />
  </div>
)
```

**Use cases:**
- Tab switching trong stock detail
- Period changes (1D, 1W, 1M, 3M, 1Y)
- Pagination (nếu có)
- Symbol changes (giữ layout, swap data)

---

### 3.5 Global Loading Indicator (Priority: MEDIUM)

**Problem:** User không biết khi nào background refetch đang xảy ra

**Solution:** Global isFetching indicator

```tsx
// components/layout/global-loading-indicator.tsx
import { useIsFetching } from "@tanstack/react-query"

export function GlobalLoadingIndicator() {
  const isFetching = useIsFetching()

  if (!isFetching) return null

  return (
    <div className="fixed top-0 left-0 right-0 h-0.5 z-50">
      <div className="h-full bg-primary animate-pulse" />
    </div>
  )
}
```

**Alternative:** NProgress-style loading bar

---

### 3.6 useTransition for Navigation (Priority: MEDIUM)

**Problem:** Page transitions feel jarring

**Solution:**
```tsx
// hooks/use-navigation.ts
import { useTransition } from "react"
import { useRouter } from "next/navigation"

export function useNavigateWithTransition() {
  const router = useRouter()
  const [isPending, startTransition] = useTransition()

  const navigate = (href: string) => {
    startTransition(() => {
      router.push(href)
    })
  }

  return { navigate, isPending }
}
```

**Benefits:**
- Keep current UI while loading next
- Show loading state without blocking UI
- Better perceived performance

---

### 3.7 Skeleton Component Library (Priority: LOW)

**Standardize skeleton components:**

```tsx
// components/ui/skeletons/index.ts
export { CardSkeleton } from "./card-skeleton"
export { ChartSkeleton } from "./chart-skeleton"
export { TableSkeleton } from "./table-skeleton"
export { StatsSkeleton } from "./stats-skeleton"

// Composable skeletons
export function DashboardSkeleton() {
  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-4 gap-4">
        {Array(4).fill(0).map((_, i) => <CardSkeleton key={i} />)}
      </div>
      <TableSkeleton rows={10} />
    </div>
  )
}
```

---

### 3.8 Chart-Specific Optimizations (Priority: MEDIUM)

**Problem:** Recharts re-renders cause flash

**Solutions:**

1. **Memoization:**
```tsx
const MemoizedChart = React.memo(function Chart({ data }) {
  return <ResponsiveContainer>...</ResponsiveContainer>
}, (prev, next) => isEqual(prev.data, next.data))
```

2. **Stable animation config:**
```tsx
<LineChart data={data}>
  <Line
    type="monotone"
    isAnimationActive={!isPlaceholderData} // Disable animation during transition
    animationDuration={300}
  />
</LineChart>
```

3. **Container key stability:**
```tsx
// BAD: key changes cause remount
<Chart key={`${symbol}-${period}`} data={data} />

// GOOD: stable key, data flows as prop
<Chart data={data} />
```

---

## 4. Implementation Priority Matrix

| Priority | Upgrade | Effort | Impact |
|----------|---------|--------|--------|
| 🔴 HIGH | Error Boundary System | 2-3h | Critical for production |
| 🔴 HIGH | placeholderData (keepPreviousData) | 1-2h | Immediate UX improvement |
| 🔴 HIGH | useSuspenseQuery migration | 4-6h | Clean code, better DX |
| 🟡 MEDIUM | loading.tsx files | 1-2h | Better streaming |
| 🟡 MEDIUM | Global loading indicator | 30min | User feedback |
| 🟡 MEDIUM | Chart optimizations | 2-3h | Smoother charts |
| 🟢 LOW | Skeleton library | 2-3h | Maintainability |
| 🟢 LOW | useTransition navigation | 1h | Polish |

---

## 5. Recommended Implementation Order

### Phase 1: Foundation (1 day)
1. Install `react-error-boundary`
2. Create `QueryErrorBoundary` component
3. Add Error Boundary to layout.tsx
4. Create `ErrorFallback` component với retry

### Phase 2: Smooth Transitions (1 day)
1. Update all hooks với `placeholderData: keepPreviousData`
2. Add `isPlaceholderData` visual hints
3. Add `GlobalLoadingIndicator`
4. Test tab switching, period changes

### Phase 3: Suspense Migration (2-3 days)
1. Create new hooks với `useSuspenseQuery`
2. Migrate chart components first
3. Migrate feature components
4. Add `loading.tsx` files
5. Test error boundaries work correctly

### Phase 4: Polish (1 day)
1. Standardize skeleton library
2. Chart animation optimizations
3. useTransition for navigation
4. Performance testing

---

## 6. Files to Modify

### New Files
- `components/providers/query-error-boundary.tsx`
- `components/ui/error-fallback.tsx`
- `components/layout/global-loading-indicator.tsx`
- `app/loading.tsx`
- `app/analytics/*/loading.tsx` (multiple)

### Modified Files
- `app/layout.tsx` - Add Error Boundary
- `components/providers/query-provider.tsx` - Update config
- `hooks/use-*.ts` (14 files) - Add placeholderData, migrate to Suspense
- `components/dashboard/*-chart.tsx` (15+ files) - Animation configs

---

## 7. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| react-error-boundary | ^4.0.0 | Error boundary with reset |
| @tanstack/react-query | 5.90.12 | Already installed ✅ |

---

## 8. Success Metrics

- [ ] Zero unhandled errors reaching user
- [ ] No flash content khi switch tabs/periods
- [ ] Charts animate smoothly, no remount flash
- [ ] Clear loading feedback (skeleton + indicator)
- [ ] Error recovery works (retry button)
- [ ] TypeScript: No more `data!` assertions

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| useSuspenseQuery breaks SSR | Test với HydrationBoundary |
| Error Boundary catches too much | Use granular boundaries |
| Performance regression | Profile before/after |
| Breaking existing tests | Update test utilities |

---

## 10. Unresolved Questions

1. **Sonner vs Toast:** Có muốn show error toast ngoài Error Boundary fallback không?
2. **Retry strategy:** Infinite retry hay limit 3 lần?
3. **Skeleton fidelity:** Match exact layout hay generic shapes?
4. **Offline support:** Có cần offline-first với service worker không?

---

## Next Steps

Bạn có muốn tôi tạo **implementation plan chi tiết** cho các phases trên không?
