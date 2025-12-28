# Phase 1: Error Boundary System Setup

## Context

- **Parent Plan**: [plan.md](../plan.md)
- **Research**: [researcher-01-error-boundary.md](../research/researcher-01-error-boundary.md)
- **Code Standards**: [code-standards.md](/docs/code-standards.md)

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-28 |
| Description | Setup react-error-boundary + QueryErrorResetBoundary |
| Priority | HIGH |
| Effort | 2.5h |
| Status | completed (2025-12-28) |

## Key Insights (from Research)

1. `react-error-boundary` v4.x + `QueryErrorResetBoundary` la combo chuan
2. Component-level boundaries tot nhat cho dashboards (granular isolation)
3. Can set `throwOnError: true` trong QueryClient de errors propagate
4. Hook-based pattern (`useQueryErrorResetBoundary`) clean hon cho global

## Requirements

### Functional
- F1: Catch va hien thi query errors khong crash app
- F2: Retry button reset query va retry fetch
- F3: Error UI hien thi thong bao than thien bang tieng Viet
- F4: Network errors nhan dien rieng voi message khac

### Non-Functional
- NF1: Error fallback phai theo design-guidelines.md
- NF2: Error boundary khong anh huong performance

## Architecture

```
layout.tsx
├── GlobalErrorBoundary (root catch-all)
│   └── QueryProvider
│       └── page.tsx
│           ├── ChartBoundary (granular)
│           ├── StatsBoundary (granular)
│           └── TableBoundary (granular)
```

## Related Code Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/web/src/components/providers/query-error-boundary.tsx` | CREATE | Main wrapper component |
| `apps/web/src/components/ui/error-fallback.tsx` | CREATE | Reusable error UI |
| `apps/web/src/components/providers/query-provider.tsx` | MODIFY | Add throwOnError |
| `apps/web/src/app/layout.tsx` | MODIFY | Wrap with ErrorBoundary |

## Implementation Steps

### Step 1: Install dependency (5 min)
```bash
cd apps/web && npm install react-error-boundary
```

### Step 2: Create ErrorFallback component (30 min)

**Path**: `apps/web/src/components/ui/error-fallback.tsx`

```tsx
"use client"

import { AlertCircle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

interface ErrorFallbackProps {
  error: Error
  resetErrorBoundary: () => void
  compact?: boolean
}

export function ErrorFallback({ error, resetErrorBoundary, compact }: ErrorFallbackProps) {
  const isNetworkError = error.message.toLowerCase().includes("network")

  if (compact) {
    return (
      <div className="flex items-center gap-2 p-3 rounded-lg border border-destructive/50 bg-destructive/10">
        <AlertCircle className="h-4 w-4 text-destructive" />
        <span className="text-sm text-destructive">{error.message}</span>
        <Button variant="ghost" size="sm" onClick={resetErrorBoundary}>
          <RefreshCw className="h-3 w-3" />
        </Button>
      </div>
    )
  }

  return (
    <Card className="border-destructive/50 bg-destructive/5">
      <CardContent className="flex flex-col items-center gap-4 p-8">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <div className="text-center space-y-1">
          <h3 className="font-semibold">Da xay ra loi</h3>
          <p className="text-sm text-muted-foreground">
            {isNetworkError ? "Kiem tra ket noi mang" : error.message}
          </p>
        </div>
        <Button onClick={resetErrorBoundary} variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Thu lai
        </Button>
      </CardContent>
    </Card>
  )
}
```

### Step 3: Create QueryErrorBoundary wrapper (30 min)

**Path**: `apps/web/src/components/providers/query-error-boundary.tsx`

```tsx
"use client"

import { QueryErrorResetBoundary } from "@tanstack/react-query"
import { ErrorBoundary } from "react-error-boundary"
import { ErrorFallback } from "@/components/ui/error-fallback"

interface QueryErrorBoundaryProps {
  children: React.ReactNode
  compact?: boolean
}

export function QueryErrorBoundary({ children, compact }: QueryErrorBoundaryProps) {
  return (
    <QueryErrorResetBoundary>
      {({ reset }) => (
        <ErrorBoundary
          onReset={reset}
          fallbackRender={({ error, resetErrorBoundary }) => (
            <ErrorFallback
              error={error}
              resetErrorBoundary={resetErrorBoundary}
              compact={compact}
            />
          )}
        >
          {children}
        </ErrorBoundary>
      )}
    </QueryErrorResetBoundary>
  )
}
```

### Step 4: Update QueryProvider (15 min)

**Path**: `apps/web/src/components/providers/query-provider.tsx`

Add `throwOnError` to defaultOptions:

```tsx
new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 10 * 60 * 1000,
      refetchOnWindowFocus: false,
      retry: 1,
      throwOnError: true, // ADD THIS
    },
  },
})
```

### Step 5: Wrap layout with ErrorBoundary (15 min)

**Path**: `apps/web/src/app/layout.tsx`

```tsx
import { QueryErrorBoundary } from "@/components/providers/query-error-boundary"

// Inside RootLayout:
<ThemeProvider ...>
  <QueryProvider>
    <QueryErrorBoundary>
      {children}
    </QueryErrorBoundary>
    <Toaster />
  </QueryProvider>
</ThemeProvider>
```

### Step 6: Test error handling (30 min)

1. Disconnect network, reload page - verify error UI
2. Click retry - verify refetch works
3. Verify other components not affected by one error
4. Test error toast NOT showing (avoid duplicate)

## Todo List

- [ ] Install react-error-boundary
- [ ] Create ErrorFallback component
- [ ] Create QueryErrorBoundary wrapper
- [ ] Update QueryProvider with throwOnError
- [ ] Wrap layout.tsx with ErrorBoundary
- [ ] Test error scenarios
- [ ] Verify no duplicate error toasts

## Success Criteria

- [ ] Network disconnect shows error UI, not crash
- [ ] API 500 shows error UI with retry
- [ ] Retry button works, refetches data
- [ ] Error UI matches design guidelines
- [ ] No duplicate error messages (toast + boundary)

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| throwOnError breaks existing code | Test thoroughly, can use conditional |
| Double error handling | Remove toast on query error, only boundary |

## Next Steps

Phase 2: Smooth Transitions - Add placeholderData va global loading indicator
