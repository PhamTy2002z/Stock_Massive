# Phase 1: Fix Flicker with TanStack Query

**Parent Plan:** [plan.md](./plan.md)
**Dependencies:** None

---

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-23 |
| Priority | P1 |
| Effort | 1h |
| Status | completed |

**Goal:** Eliminate UI flicker during data refetch by keeping previous data visible while new data loads.

---

## Requirements

1. Add `placeholderData: keepPreviousData` to all 7 hooks
2. Add `refetchIntervalInBackground: false` to stop wasteful background polling
3. Return `isPlaceholderData` flag for UI indication (optional opacity)

---

## Related Files

| File | Action |
|------|--------|
| `apps/web/src/hooks/use-market-indices.ts` | Modify |
| `apps/web/src/hooks/use-vn30-overview.ts` | Modify |
| `apps/web/src/hooks/use-stock-detail.ts` | Modify |
| `apps/web/src/hooks/use-fund-certificates.ts` | Modify |
| `apps/web/src/hooks/use-sector-performance.ts` | Modify |
| `apps/web/src/hooks/use-volume-spikes.ts` | Modify |
| `apps/web/src/hooks/use-financial-statements.ts` | Modify |

---

## Implementation Steps

### Step 1: Update `use-market-indices.ts`

```tsx
"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchMarketIndices } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useMarketIndices() {
  const query = useQuery({
    queryKey: queryKeys.marketIndices,
    queryFn: fetchMarketIndices,
    staleTime: 15 * 1000, // 15 seconds
    refetchInterval: 15 * 1000,
    placeholderData: keepPreviousData, // NEW: Keep old data while refetching
    refetchIntervalInBackground: false, // NEW: Stop polling when tab inactive
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData, // NEW: For UI opacity hint
    error: query.error,
    refetch: query.refetch,
  }
}
```

### Step 2: Update `use-vn30-overview.ts`

```tsx
"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchVN30Overview } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useVN30Overview() {
  const query = useQuery({
    queryKey: queryKeys.vn30Overview,
    queryFn: fetchVN30Overview,
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 30 * 1000,
    placeholderData: keepPreviousData,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    error: query.error,
    refetch: query.refetch,
  }
}
```

### Step 3: Update `use-stock-detail.ts`

```tsx
"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchStockDetail, type StockDetail } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

const SYMBOL_PATTERN = /^[A-Z0-9]{1,10}$/

interface UseStockDetailResult {
  data: StockDetail | null
  isLoading: boolean
  isFetching: boolean
  isPlaceholderData: boolean
  error: Error | null
  refetch: () => void
}

export function useStockDetail(symbol: string | null): UseStockDetailResult {
  const isValidSymbol = !!symbol && SYMBOL_PATTERN.test(symbol)

  const query = useQuery({
    queryKey: symbol ? queryKeys.stockDetail(symbol) : ["stock", "empty"],
    queryFn: async () => {
      if (!symbol || !isValidSymbol) {
        throw new Error("Invalid stock symbol format")
      }
      return fetchStockDetail(symbol)
    },
    enabled: isValidSymbol,
    staleTime: 15 * 1000,
    refetchInterval: 15 * 1000,
    placeholderData: keepPreviousData,
    refetchIntervalInBackground: false,
  })

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    error: query.error,
    refetch: query.refetch,
  }
}
```

### Step 4: Update `use-fund-certificates.ts`

```tsx
"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchFundCertificates } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useFundCertificates(fundType?: string) {
  const query = useQuery({
    queryKey: queryKeys.fundCertificates(fundType),
    queryFn: () => fetchFundCertificates(fundType),
    staleTime: 60 * 1000, // 1 minute
    refetchInterval: 60 * 1000,
    placeholderData: keepPreviousData,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    error: query.error,
    refetch: query.refetch,
  }
}
```

### Step 5: Update `use-sector-performance.ts`

```tsx
"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchSectorPerformance, type SectorPerformanceResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

interface UseSectorPerformanceResult {
  data: SectorPerformanceResponse | null
  isLoading: boolean
  isFetching: boolean
  isPlaceholderData: boolean
  error: Error | null
  refetch: () => void
  lastUpdated: Date | null
}

export function useSectorPerformance(): UseSectorPerformanceResult {
  const query = useQuery({
    queryKey: queryKeys.sectorPerformance,
    queryFn: fetchSectorPerformance,
    staleTime: 60 * 1000,
    refetchInterval: 120 * 1000, // 2 minutes
    placeholderData: keepPreviousData,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    error: query.error,
    refetch: query.refetch,
    lastUpdated: query.dataUpdatedAt ? new Date(query.dataUpdatedAt) : null,
  }
}
```

### Step 6: Update `use-volume-spikes.ts`

```tsx
"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchVolumeSpikes, type VolumeSpikeParams } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useVolumeSpikes(params: VolumeSpikeParams = {}) {
  const query = useQuery({
    queryKey: queryKeys.volumeSpikes(params),
    queryFn: () => fetchVolumeSpikes(params),
    staleTime: 2 * 60 * 1000,
    refetchInterval: 3 * 60 * 1000,
    placeholderData: keepPreviousData,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    error: query.error,
    refetch: query.refetch,
  }
}
```

### Step 7: Update `use-financial-statements.ts`

```tsx
"use client"

import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { fetchFinancialStatements } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useFinancialStatements(limit: number = 50, exchange?: string) {
  const query = useQuery({
    queryKey: queryKeys.financialStatements(limit, exchange),
    queryFn: () => fetchFinancialStatements(limit, exchange),
    staleTime: 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
    placeholderData: keepPreviousData,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isPlaceholderData: query.isPlaceholderData,
    error: query.error,
    refetch: query.refetch,
  }
}
```

---

## Success Criteria

- [x] All 7 hooks import `keepPreviousData` from `@tanstack/react-query`
- [x] All hooks have `placeholderData: keepPreviousData`
- [x] All hooks have `refetchIntervalInBackground: false`
- [x] All hooks return `isPlaceholderData` flag
- [x] No visible flicker when data auto-refreshes
- [x] TypeScript compiles without errors

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Stale data shown briefly | Low | Expected behavior, add subtle opacity indicator |
| Import path wrong | Low | Use exact TanStack Query v5 import |

---

## Testing Checklist

1. Open dashboard, wait for auto-refresh
2. Verify no skeleton flicker on refresh
3. Check DevTools Network tab - requests still fire
4. Switch tabs, return - verify data refreshes on focus
