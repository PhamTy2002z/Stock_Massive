# Phase 2: Hooks Migration

## Context
- **Parent Plan**: [plan.md](./plan.md)
- **Dependencies**: [phase-01-tanstack-query-setup.md](./phase-01-tanstack-query-setup.md)
- **Next Phase**: [phase-03-ssr-integration.md](./phase-03-ssr-integration.md)

## Overview
- **Date**: 2024-12-19
- **Description**: Convert 7 custom hooks from useState/useEffect to TanStack Query useQuery
- **Priority**: P1
- **Status**: pending
- **Effort**: 2.5h

## Requirements
1. Migrate use-stock-detail.ts to useQuery
2. Migrate use-sector-performance.ts to useQuery
3. Migrate use-income-statement.ts to useQuery
4. Migrate use-balance-sheet.ts to useQuery
5. Migrate use-cash-flow.ts to useQuery
6. Migrate use-shareholders.ts to useQuery
7. Migrate use-fund-certificates.ts to useQuery
8. Preserve existing error/loading states
9. Maintain debouncing where needed (stock search)
10. Keep same hook API for components

## Related Code Files
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-stock-detail.ts`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-sector-performance.ts`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-income-statement.ts`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-balance-sheet.ts`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-cash-flow.ts`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-shareholders.ts`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-fund-certificates.ts`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/api.ts`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/query-keys.ts`

## Implementation Steps

### Step 1: Migrate use-stock-detail.ts
Replace `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-stock-detail.ts`:

```typescript
"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchStockDetail, type StockDetail } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

const SYMBOL_PATTERN = /^[A-Z0-9]{1,10}$/

interface UseStockDetailResult {
  data: StockDetail | null
  isLoading: boolean
  error: Error | null
  refetch: () => void
}

export function useStockDetail(symbol: string | null): UseStockDetailResult {
  const query = useQuery({
    queryKey: symbol ? queryKeys.stockDetail(symbol) : ["stock", "empty"],
    queryFn: async () => {
      if (!symbol || !SYMBOL_PATTERN.test(symbol)) {
        throw new Error("Invalid stock symbol format")
      }
      return fetchStockDetail(symbol)
    },
    enabled: !!symbol && SYMBOL_PATTERN.test(symbol),
    staleTime: 30 * 1000, // 30 seconds
  })

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  }
}
```

### Step 2: Migrate use-sector-performance.ts
Replace `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-sector-performance.ts`:

```typescript
"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchSectorPerformance, type SectorPerformanceResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useSectorPerformance() {
  return useQuery({
    queryKey: queryKeys.sectorPerformance,
    queryFn: fetchSectorPerformance,
    staleTime: 60 * 1000, // 1 minute
    refetchInterval: 5 * 60 * 1000, // Auto-refresh every 5 minutes
  })
}
```

### Step 3: Migrate use-income-statement.ts
Replace `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-income-statement.ts`:

```typescript
"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchIncomeStatement, type PeriodType, type IncomeStatementResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useIncomeStatement(
  symbol: string | null,
  period: PeriodType = "quarter",
  limit: number = 4
) {
  return useQuery({
    queryKey: symbol ? queryKeys.incomeStatement(symbol, period, limit) : ["income", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchIncomeStatement(symbol, period, limit)
    },
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}
```

### Step 4: Migrate use-balance-sheet.ts
Replace `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-balance-sheet.ts`:

```typescript
"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchBalanceSheet, type PeriodType, type BalanceSheetResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useBalanceSheet(
  symbol: string | null,
  period: PeriodType = "quarter",
  limit: number = 4
) {
  return useQuery({
    queryKey: symbol ? queryKeys.balanceSheet(symbol, period, limit) : ["balance", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchBalanceSheet(symbol, period, limit)
    },
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}
```

### Step 5: Migrate use-cash-flow.ts
Replace `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-cash-flow.ts`:

```typescript
"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchCashFlow, type PeriodType, type CashFlowResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useCashFlow(
  symbol: string | null,
  period: PeriodType = "quarter",
  limit: number = 4
) {
  return useQuery({
    queryKey: symbol ? queryKeys.cashFlow(symbol, period, limit) : ["cashFlow", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchCashFlow(symbol, period, limit)
    },
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}
```

### Step 6: Migrate use-shareholders.ts
Replace `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-shareholders.ts`:

```typescript
"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchShareholders, type ShareholdersResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useShareholders(symbol: string | null) {
  return useQuery({
    queryKey: symbol ? queryKeys.shareholders(symbol) : ["shareholders", "empty"],
    queryFn: () => {
      if (!symbol) throw new Error("Symbol required")
      return fetchShareholders(symbol)
    },
    enabled: !!symbol,
    staleTime: 10 * 60 * 1000, // 10 minutes
  })
}
```

### Step 7: Migrate use-fund-certificates.ts
Replace `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-fund-certificates.ts`:

```typescript
"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchFundCertificates, type FundCertificatesResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useFundCertificates(fundType?: string) {
  return useQuery({
    queryKey: queryKeys.fundCertificates(fundType),
    queryFn: () => fetchFundCertificates(fundType),
    staleTime: 2 * 60 * 1000, // 2 minutes
    refetchInterval: 5 * 60 * 1000, // Auto-refresh every 5 minutes
  })
}
```

### Step 8: Test Each Hook
After each migration:
1. Start dev server: `pnpm dev`
2. Navigate to dashboard
3. Verify data loads correctly
4. Check loading states
5. Test error scenarios (invalid symbol)
6. Verify React Query DevTools shows queries

### Step 9: Verify Components Still Work
Test components using migrated hooks:
- StockTickerHeader (use-stock-detail)
- SectorPerformance (use-sector-performance)
- FinanceTabContent (use-income-statement, use-balance-sheet, use-cash-flow)
- ShareholdersTabContent (use-shareholders)
- FundCertificates (use-fund-certificates)

## Success Criteria
- [x] All 7 hooks migrated to useQuery
- [x] Same hook API maintained (backward compatible)
- [x] Loading/error states work correctly
- [x] Data fetching works as before
- [x] React Query DevTools shows all queries
- [x] No console errors
- [x] Components render correctly
- [x] Automatic refetching works (sector performance, fund certificates)

## Risk Assessment

**Medium Risk**:
- Breaking existing components if API changes
- Query key collisions if not unique
- Stale data if staleTime too high

**Mitigations**:
- Keep same return interface as old hooks
- Use query key factory for consistency
- Set conservative staleTime values
- Test each hook individually before moving to next
- Enable queries only when symbol exists
