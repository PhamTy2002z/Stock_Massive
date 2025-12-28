# Research: react-error-boundary + TanStack Query Integration

**Research Date:** 2025-12-28
**Stack:** Next.js 15, TanStack Query v5.90, TypeScript
**Researcher:** a576511

---

## Package Information

**react-error-boundary:** Latest stable v4.x
**Installation:**
```bash
npm install react-error-boundary
```

**Note:** TanStack Query v5.90 already includes `QueryErrorResetBoundary` and `useQueryErrorResetBoundary` - no additional deps needed.

---

## Integration Patterns

### Pattern 1: Component-Based (Recommended for isolated boundaries)

```tsx
import { QueryErrorResetBoundary } from '@tanstack/react-query'
import { ErrorBoundary } from 'react-error-boundary'

export function StockDataBoundary({ children }: { children: React.ReactNode }) {
  return (
    <QueryErrorResetBoundary>
      {({ reset }) => (
        <ErrorBoundary
          onReset={reset}
          fallbackRender={({ error, resetErrorBoundary }) => (
            <div className="error-container">
              <h3>Không thể tải dữ liệu</h3>
              <p>{error.message}</p>
              <button onClick={resetErrorBoundary}>Thử lại</button>
            </div>
          )}
        >
          {children}
        </ErrorBoundary>
      )}
    </QueryErrorResetBoundary>
  )
}
```

### Pattern 2: Hook-Based (Cleaner for global boundaries)

```tsx
import { useQueryErrorResetBoundary } from '@tanstack/react-query'
import { ErrorBoundary } from 'react-error-boundary'

export function GlobalErrorBoundary({ children }: { children: React.ReactNode }) {
  const { reset } = useQueryErrorResetBoundary() // Resets all queries in scope

  return (
    <ErrorBoundary
      onReset={reset}
      fallbackRender={({ error, resetErrorBoundary }) => (
        <ErrorFallback error={error} onReset={resetErrorBoundary} />
      )}
    >
      {children}
    </ErrorBoundary>
  )
}
```

---

## Placement Strategy

### Option A: Root Layout (apps/web/src/app/layout.tsx)
**Pros:**
- Single boundary catches all query errors app-wide
- Simplest implementation
- Consistent UX across routes

**Cons:**
- Entire app UI replaced on error (poor UX)
- Cannot isolate errors to specific features
- Breaks unrelated features when one fails

**Use when:** Small apps, proof-of-concept

---

### Option B: Page-Level (apps/web/src/app/(dashboard)/stocks/[symbol]/page.tsx)
**Pros:**
- Errors isolated to specific routes
- Other pages remain functional
- Aligns with Next.js 15 error.tsx pattern

**Cons:**
- Multiple navigation/sidebar instances if layout outside boundary
- Repetitive if many pages need boundaries

**Use when:** Route-specific data dependencies, independent pages

---

### Option C: Component-Level (Recommended for this app)
**Pros:**
- Granular error isolation (e.g., price chart fails, news still loads)
- Best UX - minimal UI disruption
- Reusable boundaries per feature

**Cons:**
- More boundaries to manage
- Need clear ownership per component

**Use when:** Complex dashboards with independent data widgets

**Example structure:**
```
app/(dashboard)/stocks/[symbol]/page.tsx
├── <PriceChartBoundary>      ← Catches chart query errors
├── <NewsListBoundary>         ← Catches news query errors
└── <FinancialStatsBoundary>   ← Catches stats query errors
```

---

## Error Fallback UI Patterns

### Minimal Fallback (Quick wins)
```tsx
function ErrorFallback({ error, resetErrorBoundary }: FallbackProps) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4">
      <p className="text-sm text-red-800">{error.message}</p>
      <button onClick={resetErrorBoundary} className="mt-2 text-sm underline">
        Thử lại
      </button>
    </div>
  )
}
```

### Enhanced Fallback (Production-ready)
```tsx
function ErrorFallback({ error, resetErrorBoundary }: FallbackProps) {
  const isNetworkError = error.message.includes('Network')

  return (
    <div className="flex flex-col items-center gap-4 p-8">
      <AlertCircle className="h-12 w-12 text-red-500" />
      <div className="text-center">
        <h3 className="font-semibold">Đã xảy ra lỗi</h3>
        <p className="text-sm text-muted-foreground">
          {isNetworkError ? 'Kiểm tra kết nối mạng' : error.message}
        </p>
      </div>
      <button onClick={resetErrorBoundary} className="btn-primary">
        Thử lại
      </button>
    </div>
  )
}
```

---

## QueryClient Configuration

Enable error throwing for boundaries to catch errors:

```tsx
// apps/web/src/lib/query-client.ts
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      throwOnError: true, // Critical: errors propagate to boundaries
      retry: 2,
      staleTime: 5 * 60 * 1000,
    },
  },
})
```

**Alternative (granular control):**
```tsx
throwOnError: (error, query) => {
  // Only throw for critical queries
  return query.queryKey[0] === 'stockPrice'
}
```

---

## Trade-offs Summary

| Aspect | Root Boundary | Page Boundary | Component Boundary |
|--------|---------------|---------------|-------------------|
| Setup complexity | Low | Medium | High |
| Error isolation | None | Route-level | Widget-level |
| UX quality | Poor | Good | Excellent |
| Maintenance | Easy | Medium | Requires discipline |
| Recommended for | Prototypes | Multi-page apps | Dashboards |

---

## Implementation Recommendation for Stock_Massive

**Strategy:** Component-level boundaries for dashboard features

**Rationale:**
1. Dashboard has independent data widgets (chart, stats, news)
2. One widget failing shouldn't break others
3. Better UX than full-page error screens

**Next Steps:**
1. Create `ErrorBoundary` wrapper components per feature area
2. Set `throwOnError: true` in QueryClient
3. Design fallback UI matching design-guidelines.md

---

## Unresolved Questions

1. **Error logging:** Integrate Sentry/LogRocket in `onError` callback?
2. **Retry limits:** Should boundaries disable after N consecutive failures?
3. **Next.js 15 error.tsx:** Use native error.tsx OR react-error-boundary? (Likely use both: error.tsx for routing errors, ErrorBoundary for query errors)
4. **Suspense interaction:** How do ErrorBoundary + Suspense compose? (Need testing with useSuspenseQuery)
