# Phase 1: TanStack Query Setup

## Context
- **Parent Plan**: [plan.md](./plan.md)
- **Dependencies**: None (first phase)
- **Next Phase**: [phase-02-hooks-migration.md](./phase-02-hooks-migration.md)

## Overview
- **Date**: 2024-12-19
- **Description**: Install TanStack Query v5, create QueryClientProvider with SSR config, setup query key factory
- **Priority**: P1
- **Status**: pending
- **Effort**: 1h

## Requirements
1. Install @tanstack/react-query v5 and @tanstack/react-query-devtools
2. Create QueryClientProvider wrapper with SSR-compatible config
3. Integrate QueryClientProvider into root layout
4. Create query key factory for organized, type-safe keys
5. Enable React Query DevTools in development

## Related Code Files
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/layout.tsx` - Root layout
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/providers/theme-provider.tsx` - Existing provider pattern
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/package.json` - Dependencies

## Implementation Steps

### Step 1: Install Dependencies
```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/web
pnpm add @tanstack/react-query@^5.0.0
pnpm add -D @tanstack/react-query-devtools@^5.0.0
```

### Step 2: Create Query Provider
Create `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/providers/query-provider.tsx`:

```typescript
"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { useState } from "react"

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            gcTime: 5 * 60 * 1000, // 5 minutes (formerly cacheTime)
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}
```

### Step 3: Update Root Layout
Edit `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/layout.tsx`:

Add import:
```typescript
import { QueryProvider } from "@/components/providers/query-provider"
```

Wrap children with QueryProvider (inside ThemeProvider):
```typescript
<ThemeProvider
  attribute="class"
  defaultTheme="dark"
  enableSystem={false}
  disableTransitionOnChange
>
  <QueryProvider>
    {children}
    <Toaster />
  </QueryProvider>
</ThemeProvider>
```

### Step 4: Create Query Key Factory
Create `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/query-keys.ts`:

```typescript
import type { PeriodType, OfficerFilterType } from "./api"

export const queryKeys = {
  // Market data
  marketIndices: ["market", "indices"] as const,
  priceBoard: (symbols: string[]) => ["market", "priceBoard", symbols] as const,
  sectorPerformance: ["market", "sectorPerformance"] as const,
  fundCertificates: (fundType?: string) =>
    ["market", "fundCertificates", fundType] as const,

  // Stock detail
  stock: (symbol: string) => ["stock", symbol] as const,
  stockDetail: (symbol: string) => [...queryKeys.stock(symbol), "detail"] as const,

  // Financials
  incomeStatement: (symbol: string, period: PeriodType, limit: number) =>
    [...queryKeys.stock(symbol), "income", period, limit] as const,
  balanceSheet: (symbol: string, period: PeriodType, limit: number) =>
    [...queryKeys.stock(symbol), "balance", period, limit] as const,
  cashFlow: (symbol: string, period: PeriodType, limit: number) =>
    [...queryKeys.stock(symbol), "cashFlow", period, limit] as const,

  // Ownership
  shareholders: (symbol: string) =>
    [...queryKeys.stock(symbol), "shareholders"] as const,
  officers: (symbol: string, filterBy: OfficerFilterType) =>
    [...queryKeys.stock(symbol), "officers", filterBy] as const,
  insiderDeals: (symbol: string) =>
    [...queryKeys.stock(symbol), "insiderDeals"] as const,

  // Search
  stockSearch: (query: string, limit: number) =>
    ["search", "stocks", query, limit] as const,
} as const
```

### Step 5: Verify Installation
```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/web
pnpm dev
```

Check:
- No build errors
- DevTools panel appears (bottom-left corner)
- Console shows no React Query warnings

## Success Criteria
- [x] @tanstack/react-query v5 installed
- [x] QueryClientProvider created with SSR-safe config
- [x] QueryProvider integrated in layout.tsx
- [x] Query key factory created with all endpoints
- [x] DevTools visible in development
- [x] App runs without errors

## Risk Assessment

**Low Risk**:
- TanStack Query is stable, well-documented
- Provider pattern already used (ThemeProvider)
- No breaking changes to existing code

**Mitigations**:
- Use useState for QueryClient (prevents SSR issues)
- Set conservative staleTime/gcTime defaults
- Disable refetchOnWindowFocus (avoid excessive requests)
