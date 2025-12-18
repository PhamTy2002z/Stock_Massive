# Phase 2: Frontend - State Management & Data Fetching

**Status:** Pending
**Effort:** 3-4 hours
**Priority:** High
**Depends On:** Phase 1 (Backend endpoint must be complete)

---

## Context

**Problem:** Dashboard page uses hardcoded stock data. No mechanism to fetch and manage selected stock state.

**Solution:** Create React state management for selected stock with custom hook for data fetching.

**Related Research:**
- `/plans/251218-2134-stock-detail-realtime/research/researcher-02-frontend-components.md`

---

## Overview

Implement state management and data fetching layer:
1. Create `useStockDetail` custom hook for API calls
2. Add state to page component for selected symbol
3. Implement loading and error states
4. Add TypeScript interfaces for API response

---

## Requirements

### Functional
- Fetch stock detail when symbol changes
- Display loading skeleton during fetch
- Show error message on API failure
- Default to VCB on initial page load
- Debounce rapid symbol changes (300ms)

### Non-Functional
- Type-safe API responses
- Reusable hook for future pages
- Clean error handling
- Accessible loading states

---

## Architecture

### Component Hierarchy
```
page.tsx (State Container)
├── selectedSymbol: string | null
├── useStockDetail(selectedSymbol)
│   ├── data: StockDetail | null
│   ├── isLoading: boolean
│   ├── error: Error | null
│   └── refetch: () => void
└── Pass data to child components
    ├── StockTickerHeader
    ├── StockDetailPanel
    ├── StockStatsTable
    └── StockCompanyInfo
```

### Data Flow
```
User selects stock from search
    ↓
setSelectedSymbol(symbol)
    ↓
useStockDetail hook detects change
    ↓
Fetch GET /stocks/{symbol}/detail
    ↓
Update state: data, isLoading, error
    ↓
Re-render components with new data
```

---

## Implementation Steps

### Step 1: Add TypeScript Interfaces (lib/api.ts)

**Add StockDetail interface:**
```typescript
export interface StockDetail {
  // Basic Info
  symbol: string
  company_name: string | null
  exchange: string | null
  industry: string | null

  // Real-time Price Data
  price: number | null
  change: number | null
  change_pct: number | null
  ceiling: number | null
  floor: number | null
  ref_price: number | null

  // Intraday Range
  open_price: number | null
  high_price: number | null
  low_price: number | null

  // Volume & Value
  volume: number | null
  trading_value: number | null

  // Market Cap & Shares
  market_cap: number | null
  outstanding_shares: number | null
  issue_share: number | null

  // 52-Week Data
  high_52_week: number | null
  low_52_week: number | null
  avg_volume_52_week: number | null

  // Financial Ratios
  eps: number | null
  pe: number | null
  pb: number | null
  beta: number | null
  dividend_yield: number | null
  roe: number | null
  roa: number | null

  // Company Details
  description: string | null
  website: string | null
  employees: number | null
  established_year: number | null
}
```

**Add API function:**
```typescript
export async function fetchStockDetail(symbol: string): Promise<StockDetail> {
  return fetchApi<StockDetail>(`/stocks/${encodeURIComponent(symbol)}/detail`)
}
```

### Step 2: Create Custom Hook (hooks/use-stock-detail.ts)

**Create new file:**
```typescript
"use client"

import { useEffect, useState } from "react"
import { fetchStockDetail, StockDetail } from "@/lib/api"

interface UseStockDetailResult {
  data: StockDetail | null
  isLoading: boolean
  error: Error | null
  refetch: () => void
}

export function useStockDetail(symbol: string | null): UseStockDetailResult {
  const [data, setData] = useState<StockDetail | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const fetchData = async (sym: string) => {
    setIsLoading(true)
    setError(null)

    try {
      const result = await fetchStockDetail(sym)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to fetch stock detail"))
      setData(null)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!symbol) {
      setData(null)
      return
    }

    // Debounce: wait 300ms before fetching
    const timeoutId = setTimeout(() => {
      fetchData(symbol)
    }, 300)

    return () => clearTimeout(timeoutId)
  }, [symbol])

  const refetch = () => {
    if (symbol) {
      fetchData(symbol)
    }
  }

  return { data, isLoading, error, refetch }
}
```

### Step 3: Create Loading Skeleton Components

**Create file: components/dashboard/stock-detail-skeleton.tsx**
```typescript
"use client"

import { Skeleton } from "@/components/ui/skeleton"

export function StockTickerHeaderSkeleton() {
  return (
    <div className="py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <Skeleton className="h-7 w-64" />
          <Skeleton className="mt-2 h-4 w-20" />
        </div>
        <div className="text-right shrink-0">
          <Skeleton className="h-8 w-24" />
          <Skeleton className="mt-2 h-4 w-32" />
        </div>
      </div>
    </div>
  )
}

export function StockDetailPanelSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="rounded-lg border bg-card p-3">
          <Skeleton className="h-3 w-16" />
          <Skeleton className="mt-2 h-4 w-20" />
        </div>
      ))}
    </div>
  )
}

export function StockStatsTableSkeleton() {
  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-border">
        {[1, 2, 3].map((col) => (
          <div key={col} className="divide-y divide-border">
            {[1, 2, 3, 4].map((row) => (
              <div key={row} className="flex items-center justify-between px-5 py-3.5">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 w-24" />
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

export function StockCompanyInfoSkeleton() {
  return (
    <div className="rounded-lg border bg-card">
      <div className="divide-y divide-border">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="flex items-center justify-between px-4 py-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-32" />
          </div>
        ))}
      </div>
      <div className="p-4 border-t border-border">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="mt-2 h-4 w-full" />
        <Skeleton className="mt-2 h-4 w-3/4" />
      </div>
    </div>
  )
}
```

### Step 4: Create Error Display Component

**Create file: components/dashboard/stock-detail-error.tsx**
```typescript
"use client"

import { AlertCircle } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"

interface StockDetailErrorProps {
  error: Error
  onRetry?: () => void
}

export function StockDetailError({ error, onRetry }: StockDetailErrorProps) {
  return (
    <Alert variant="destructive">
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Error Loading Stock Data</AlertTitle>
      <AlertDescription className="mt-2">
        {error.message || "Failed to fetch stock details. Please try again."}
      </AlertDescription>
      {onRetry && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          className="mt-3"
        >
          Retry
        </Button>
      )}
    </Alert>
  )
}
```

### Step 5: Update Page Component (app/page.tsx)

**Replace hardcoded data with state management:**
```typescript
"use client"

import { useState } from "react"
import { DashboardLayout } from "@/components/layout"
import {
  MarketIndices,
  StockTickerHeader,
  StockDetailPanel,
  StockStatsTable,
  StockCompanyInfo,
} from "@/components/dashboard"
import {
  StockTickerHeaderSkeleton,
  StockDetailPanelSkeleton,
  StockStatsTableSkeleton,
  StockCompanyInfoSkeleton,
} from "@/components/dashboard/stock-detail-skeleton"
import { StockDetailError } from "@/components/dashboard/stock-detail-error"
import { useStockDetail } from "@/hooks/use-stock-detail"

export default function Home() {
  // State for selected stock symbol
  const [selectedSymbol, setSelectedSymbol] = useState<string>("VCB")

  // Fetch stock detail data
  const { data, isLoading, error, refetch } = useStockDetail(selectedSymbol)

  return (
    <DashboardLayout onStockSelect={setSelectedSymbol}>
      <div className="flex flex-col gap-6">
        {/* Market Indices Section */}
        <section>
          <h2 className="text-lg font-semibold text-foreground mb-4">
            Chỉ số thị trường
          </h2>
          <MarketIndices />
        </section>

        {/* Selected Stock Detail */}
        <section className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
          {/* Left: Main Content */}
          <div className="space-y-4">
            {/* Error State */}
            {error && <StockDetailError error={error} onRetry={refetch} />}

            {/* Loading State */}
            {isLoading && (
              <>
                <StockTickerHeaderSkeleton />
                <StockDetailPanelSkeleton />
                <StockStatsTableSkeleton />
              </>
            )}

            {/* Data State */}
            {!isLoading && !error && data && (
              <>
                <StockTickerHeader
                  symbol={data.symbol}
                  companyName={data.company_name || data.symbol}
                  price={data.price || 0}
                  change={data.change || 0}
                  changePercent={data.change_pct || 0}
                />
                <StockDetailPanel
                  volume={data.volume || 0}
                  tradingValue={(data.trading_value || 0) / 1_000_000_000} // Convert to billion
                  marketCap={data.market_cap || 0}
                  industry={data.industry || "N/A"}
                />
                <StockStatsTable
                  openPrice={data.open_price || data.ref_price || 0}
                  highPrice={data.high_price || 0}
                  lowPrice={data.low_price || 0}
                  tradingVolume={data.volume || 0}
                  marketCap={data.market_cap || 0}
                  high52Week={data.high_52_week || 0}
                  low52Week={data.low_52_week || 0}
                  avgVolume52Week={data.avg_volume_52_week || 0}
                  eps={data.eps}
                  pe={data.pe}
                  beta={data.beta}
                  dividendYield={data.dividend_yield}
                />
              </>
            )}
          </div>

          {/* Right: Company Info Sidebar */}
          <div className="space-y-4">
            {isLoading && <StockCompanyInfoSkeleton />}
            {!isLoading && !error && data && (
              <StockCompanyInfo
                symbol={data.symbol}
                industry={data.industry || "N/A"}
                marketCap={data.market_cap || 0}
                outstandingShares={(data.outstanding_shares || 0) / 1_000_000_000} // Convert to billion
                exchange={data.exchange}
                vn30Rank={null} // TODO: Add VN30 rank logic
                description={data.description || "No description available."}
              />
            )}
          </div>
        </section>
      </div>
    </DashboardLayout>
  )
}
```

### Step 6: Update Dashboard Layout (components/layout/dashboard-layout.tsx)

**Add onStockSelect prop:**
```typescript
interface DashboardLayoutProps {
  children: React.ReactNode
  onStockSelect?: (symbol: string) => void
}

export function DashboardLayout({ children, onStockSelect }: DashboardLayoutProps) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <DashboardHeader onStockSelect={onStockSelect} />
        <main className="flex-1 overflow-y-auto">
          <div className="container mx-auto p-6 max-w-[1600px]">
            {children}
          </div>
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
```

### Step 7: Update Dashboard Header (components/layout/dashboard-header.tsx)

**Pass onStockSelect to search bar:**
```typescript
interface DashboardHeaderProps {
  onStockSelect?: (symbol: string) => void
}

export function DashboardHeader({ onStockSelect }: DashboardHeaderProps) {
  const handleStockSelect = (stock: StockSymbol) => {
    if (onStockSelect) {
      onStockSelect(stock.symbol)
    }
  }

  return (
    <header className="...">
      {/* ... */}
      <StockSearchBar
        onSelect={handleStockSelect}
        placeholder="Search stocks, markets..."
      />
      {/* ... */}
    </header>
  )
}
```

---

## Todo List

- [ ] Add `StockDetail` interface to `lib/api.ts`
- [ ] Add `fetchStockDetail()` function to `lib/api.ts`
- [ ] Create `hooks/use-stock-detail.ts` custom hook
- [ ] Create `components/dashboard/stock-detail-skeleton.tsx`
- [ ] Create `components/dashboard/stock-detail-error.tsx`
- [ ] Update `app/page.tsx` with state management
- [ ] Update `components/layout/dashboard-layout.tsx` with onStockSelect prop
- [ ] Update `components/layout/dashboard-header.tsx` to pass callback
- [ ] Export skeleton components from `components/dashboard/index.ts`
- [ ] Test loading states (throttle network in DevTools)
- [ ] Test error states (invalid symbol, network error)
- [ ] Test data display with VCB, ACB, HAG symbols

---

## Success Criteria

- [ ] Page loads with VCB data by default
- [ ] Loading skeletons display during fetch
- [ ] Error message displays on API failure
- [ ] Retry button refetches data
- [ ] All components update when new stock selected
- [ ] No console errors or warnings
- [ ] TypeScript compiles without errors
- [ ] Debounce prevents rapid API calls

---

## Testing Checklist

**Loading States:**
- [ ] Throttle network to "Slow 3G" in DevTools
- [ ] Verify skeletons display during fetch
- [ ] Check smooth transition from skeleton to data

**Error States:**
- [ ] Test with invalid symbol (e.g., "INVALID123")
- [ ] Disconnect network and verify error message
- [ ] Click retry button and verify refetch

**Data Display:**
- [ ] Select VCB from search → verify all fields populate
- [ ] Select HAG from search → verify data updates
- [ ] Check null handling (Beta, dividend_yield)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Race condition on rapid symbol changes | Medium | Low | Debounce 300ms |
| Memory leak from unmounted fetch | Low | Medium | Cleanup in useEffect |
| Null data crashes components | Medium | High | Null checks, default values |
| Slow API response (> 3s) | Medium | Medium | Show loading state, add timeout |

---

## Related Files

**New Files:**
- `/apps/web/src/hooks/use-stock-detail.ts`
- `/apps/web/src/components/dashboard/stock-detail-skeleton.tsx`
- `/apps/web/src/components/dashboard/stock-detail-error.tsx`

**Modified Files:**
- `/apps/web/src/lib/api.ts`
- `/apps/web/src/app/page.tsx`
- `/apps/web/src/components/layout/dashboard-layout.tsx`
- `/apps/web/src/components/layout/dashboard-header.tsx`
- `/apps/web/src/components/dashboard/index.ts`

---

## Next Phase

After completion, proceed to Phase 3: Search Integration & Component Updates
