---
phase: 02
title: Frontend Components Implementation
status: done
completed: 2025-12-21
priority: P2
estimated_hours: 3
actual_hours: 2
dependencies: [phase-01-backend-api]
---

# Phase 02: Frontend Components Implementation

**Date**: 2025-12-21
**Description**: Create React components and hooks for VN30 overview table
**Priority**: P2
**Status**: Done (2025-12-21)

## Context

- **Research**: [UI Patterns Report](./research/researcher-ui-patterns-report.md)
- **Design Pattern**: ShareholdersTabContent table component
- **Data Fetching**: React Query with 1-minute auto-refresh
- **Styling**: ShadCN/UI + TailwindCSS with color-coded changes
- **Pagination Pattern**: ShareholdersTabContent (10/20/30 rows per page)

## Requirements

### Functional
1. Display VN30 stocks in table format with 6 columns (Mã, Tên công ty, Giá, %, Khối lượng, Vốn hóa)
2. Auto-refresh every 1 minute during trading hours
3. Color coding: green for positive, red for negative changes
4. Vietnamese locale number formatting
5. Loading skeleton and error states
6. Responsive design with horizontal scroll
7. Pagination at bottom (10 rows per page default, options: 10/20/30)

### Non-Functional
1. Type-safe with TypeScript interfaces
2. Accessible table markup
3. Smooth transitions and hover effects
4. Mobile-responsive (min-width enforcement)
5. Performance optimized (memoization)

## Related Code Files

### Files to Create
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-vn30-overview.ts`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/vn30-overview-table.tsx`

### Files to Modify
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/api.ts` (add API types and fetch function)
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/query-keys.ts` (add query key)
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/page.tsx` (integrate component)

### Reference Files
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/shareholders-tab-content.tsx` (table pattern)
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/stock-index-card.tsx` (color coding)
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-shareholders.ts` (hook pattern)

## Implementation Steps

### Step 1: Add API Types and Fetch Function
**File**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/api.ts`

Add after VolumeAnomalyResponse interface (around line 354):

```typescript
// VN30 Overview Types
export interface VN30OverviewItem {
  symbol: string
  company_name: string
  price: number | null
  change_pct: number | null
  volume: number | null
  market_cap: number | null
}

export interface VN30OverviewResponse {
  stocks: VN30OverviewItem[]
  generated_at: string
  total_count: number
}

export async function fetchVN30Overview(): Promise<VN30OverviewResponse> {
  return fetchApi<VN30OverviewResponse>("/stocks/vn30-overview")
}
```

**Validation**:
- Interfaces match backend Pydantic schemas
- Follows existing API pattern
- Uses generic fetchApi helper

### Step 2: Add Query Key
**File**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/query-keys.ts`

Add after fundCertificates key (around line 9):

```typescript
export const queryKeys = {
  // Market data
  marketIndices: ["market", "indices"] as const,
  priceBoard: (symbols: string[]) => ["market", "priceBoard", symbols] as const,
  sectorPerformance: ["market", "sectorPerformance"] as const,
  fundCertificates: (fundType?: string) =>
    ["market", "fundCertificates", fundType] as const,
  vn30Overview: ["market", "vn30Overview"] as const,  // Add this line

  // ... rest of keys
}
```

**Validation**:
- Follows existing query key pattern
- Placed in market data section
- Uses const assertion

### Step 3: Create React Query Hook
**File**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-vn30-overview.ts`

```typescript
"use client"

import { useQuery } from "@tanstack/react-query"
import { fetchVN30Overview } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useVN30Overview() {
  return useQuery({
    queryKey: queryKeys.vn30Overview,
    queryFn: fetchVN30Overview,
    staleTime: 5 * 60 * 1000,      // 5 minutes
    refetchInterval: 5 * 60 * 1000, // Auto-refresh every 5 minutes
  })
}
```

**Key Points**:
- Follows existing hook pattern (use-shareholders.ts)
- 5-minute stale time and auto-refresh
- No parameters needed (always fetches all VN30)
- Returns standard useQuery result

### Step 4: Create VN30 Overview Table Component
**File**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/vn30-overview-table.tsx`

```typescript
"use client"

import { useState, useMemo } from "react"
import { cn } from "@/lib/utils"
import { TrendingUp, TrendingDown, ChevronLeft, ChevronRight } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useVN30Overview } from "@/hooks/use-vn30-overview"

interface VN30OverviewTableProps {
  className?: string
}

// Format price in Vietnamese locale
function formatPrice(value: number | null): string {
  if (value === null) return "-"
  return value.toLocaleString("vi-VN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })
}

// Format percentage with sign
function formatPercent(value: number | null): string {
  if (value === null) return "-"
  const sign = value >= 0 ? "+" : ""
  return `${sign}${value.toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`
}

// Format volume (millions)
function formatVolume(value: number | null): string {
  if (value === null) return "-"
  const millions = value / 1_000_000
  return `${millions.toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}M`
}

// Format market cap (billion VND)
function formatMarketCap(value: number | null): string {
  if (value === null) return "-"
  return `${value.toLocaleString("vi-VN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })} tỷ`
}

export function VN30OverviewTable({ className }: VN30OverviewTableProps) {
  const [currentPage, setCurrentPage] = useState(1)
  const [rowsPerPage, setRowsPerPage] = useState(10)

  const { data, isLoading, error } = useVN30Overview()

  // Memoize stocks to prevent unnecessary re-renders
  const stocks = useMemo(() => data?.stocks ?? [], [data?.stocks])
  const totalItems = stocks.length
  const totalPages = Math.max(1, Math.ceil(totalItems / rowsPerPage))
  const startIndex = (currentPage - 1) * rowsPerPage
  const endIndex = Math.min(startIndex + rowsPerPage, totalItems)

  // Get current page data
  const currentData = useMemo(() => {
    return stocks.slice(startIndex, endIndex)
  }, [stocks, startIndex, endIndex])

  // Handle page change
  const goToPage = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page)
    }
  }

  // Handle rows per page change
  const handleRowsPerPageChange = (value: string) => {
    setRowsPerPage(Number(value))
    setCurrentPage(1) // Reset to first page
  }

  // Show skeleton while loading
  if (isLoading) {
    return <VN30OverviewTableSkeleton className={className} />
  }

  // Show error state
  if (error) {
    return (
      <div className={cn("space-y-4", className)}>
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
          <p className="text-sm text-destructive">
            Không thể tải dữ liệu VN30: {error.message}
          </p>
        </div>
      </div>
    )
  }

  // Show empty state
  if (totalItems === 0) {
    return (
      <div className={cn("space-y-4", className)}>
        <h3 className="text-lg font-semibold">Tổng quan VN30</h3>
        <div className="rounded-lg border border-border/50 bg-card/50 p-8 text-center">
          <p className="text-sm text-muted-foreground">
            Không có dữ liệu VN30
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Title */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Tổng quan VN30</h3>
        <span className="text-sm text-muted-foreground">
          {totalItems} cổ phiếu
        </span>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border/50 bg-card/50 overflow-hidden">
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full min-w-[800px] border-collapse">
            <thead>
              <tr className="border-b border-border/50 bg-muted/30">
                <th className="py-3 px-4 text-left text-sm font-medium text-muted-foreground">
                  Mã
                </th>
                <th className="py-3 px-4 text-left text-sm font-medium text-muted-foreground">
                  Tên công ty
                </th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">
                  Giá
                </th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">
                  %
                </th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">
                  Khối lượng
                </th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">
                  Vốn hóa
                </th>
              </tr>
            </thead>
            <tbody>
              {currentData.map((stock) => {
                const isPositive = (stock.change_pct ?? 0) >= 0
                const changeColor = isPositive
                  ? "text-green-500 dark:text-green-400"
                  : "text-red-500 dark:text-red-400"

                return (
                  <tr
                    key={stock.symbol}
                    className="border-b border-border/30 transition-colors hover:bg-muted/20"
                  >
                    {/* Symbol */}
                    <td className="py-3 px-4 text-sm font-semibold text-foreground">
                      {stock.symbol}
                    </td>

                    {/* Company Name */}
                    <td className="py-3 px-4 text-sm text-foreground/90">
                      {stock.company_name}
                    </td>

                    {/* Price */}
                    <td className="py-3 px-4 text-sm text-right tabular-nums font-medium text-foreground">
                      {formatPrice(stock.price)}
                    </td>

                    {/* Change Percent */}
                    <td className="py-3 px-4 text-sm text-right tabular-nums">
                      <div className="flex items-center justify-end gap-1">
                        {stock.change_pct !== null && (
                          <>
                            {isPositive ? (
                              <TrendingUp className={cn("h-3.5 w-3.5", changeColor)} />
                            ) : (
                              <TrendingDown className={cn("h-3.5 w-3.5", changeColor)} />
                            )}
                          </>
                        )}
                        <span className={cn("font-medium", changeColor)}>
                          {formatPercent(stock.change_pct)}
                        </span>
                      </div>
                    </td>

                    {/* Volume */}
                    <td className="py-3 px-4 text-sm text-right tabular-nums text-foreground/90">
                      {formatVolume(stock.volume)}
                    </td>

                    {/* Market Cap */}
                    <td className="py-3 px-4 text-sm text-right tabular-nums text-foreground/90">
                      {formatMarketCap(stock.market_cap)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-border/50 bg-muted/20">
          {/* Items info */}
          <span className="text-sm text-muted-foreground">
            {startIndex + 1}-{endIndex} trên {totalItems} cổ phiếu
          </span>

          {/* Right side controls */}
          <div className="flex items-center gap-4">
            {/* Rows per page */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground whitespace-nowrap">
                Hàng mỗi trang
              </span>
              <Select
                value={String(rowsPerPage)}
                onValueChange={handleRowsPerPageChange}
              >
                <SelectTrigger className="w-[70px] h-8 text-sm bg-background border-border/50">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10</SelectItem>
                  <SelectItem value="20">20</SelectItem>
                  <SelectItem value="30">30</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Page navigation */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => goToPage(currentPage - 1)}
                disabled={currentPage === 1}
                className={cn(
                  "p-1.5 rounded-md transition-colors",
                  "hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                )}
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>

              <span className="text-sm text-muted-foreground whitespace-nowrap min-w-[80px] text-center">
                Trang {currentPage}/{totalPages}
              </span>

              <button
                onClick={() => goToPage(currentPage + 1)}
                disabled={currentPage === totalPages}
                className={cn(
                  "p-1.5 rounded-md transition-colors",
                  "hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                )}
                aria-label="Next page"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Skeleton for loading state
export function VN30OverviewTableSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-4", className)}>
      {/* Title skeleton */}
      <div className="flex items-center justify-between">
        <div className="h-6 w-40 rounded bg-muted animate-pulse" />
        <div className="h-5 w-24 rounded bg-muted animate-pulse" />
      </div>

      {/* Table skeleton */}
      <div className="rounded-lg border border-border/50 bg-card/50 p-4 space-y-3">
        {/* Header */}
        <div className="flex gap-4 pb-2 border-b border-border/30">
          <div className="h-4 w-12 rounded bg-muted animate-pulse" />
          <div className="h-4 w-40 rounded bg-muted animate-pulse" />
          <div className="h-4 w-16 rounded bg-muted animate-pulse ml-auto" />
          <div className="h-4 w-12 rounded bg-muted animate-pulse" />
          <div className="h-4 w-16 rounded bg-muted animate-pulse" />
          <div className="h-4 w-20 rounded bg-muted animate-pulse" />
        </div>
        {/* Rows */}
        {[...Array(10)].map((_, i) => (
          <div key={i} className="flex gap-4">
            <div className="h-4 w-12 rounded bg-muted animate-pulse" />
            <div className="h-4 w-40 rounded bg-muted animate-pulse" />
            <div className="h-4 w-16 rounded bg-muted animate-pulse ml-auto" />
            <div className="h-4 w-12 rounded bg-muted animate-pulse" />
            <div className="h-4 w-16 rounded bg-muted animate-pulse" />
            <div className="h-4 w-20 rounded bg-muted animate-pulse" />
          </div>
        ))}
        {/* Pagination skeleton */}
        <div className="flex justify-between pt-3 border-t border-border/30">
          <div className="h-4 w-32 rounded bg-muted animate-pulse" />
          <div className="flex gap-2">
            <div className="h-8 w-24 rounded bg-muted animate-pulse" />
            <div className="h-8 w-24 rounded bg-muted animate-pulse" />
          </div>
        </div>
      </div>
    </div>
  )
}
```

**Key Features**:
- Follows ShareholdersTabContent pattern exactly
- 6 columns: Mã, Tên công ty, Giá, %, Khối lượng, Vốn hóa
- Color-coded changes with TrendingUp/Down icons
- Vietnamese locale formatting
- Responsive with horizontal scroll (min-w-[800px])
- Pagination at bottom (10/20/30 rows per page)
- Loading skeleton and error states
- Hover effects on rows
- Loading skeleton and error states
- Hover effects on rows
- Tabular numbers for alignment

### Step 5: Integrate into Dashboard
**File**: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/page.tsx`

Add import at top:
```typescript
import { VN30OverviewTable } from "@/components/dashboard/vn30-overview-table"
```

Add component in appropriate section (suggest after MarketIndices):
```typescript
export default function Home() {
  return (
    <main className="container mx-auto p-4 space-y-6">
      {/* Existing components */}
      <MarketIndices />

      {/* Add VN30 Overview */}
      <VN30OverviewTable />

      {/* Rest of components */}
      <SectorPerformance />
      {/* ... */}
    </main>
  )
}
```

**Validation**:
- Component placed in logical position
- Proper spacing maintained
- No layout conflicts

### Step 6: Test Component
**Manual Testing Checklist**:

1. **Visual Testing**:
   - [ ] Table displays with proper styling
   - [ ] 4 columns: Mã, Tên công ty, Giá, %
   - [ ] Green color for positive changes
   - [ ] Red color for negative changes
   - [ ] Icons display correctly (TrendingUp/Down)
   - [ ] Vietnamese number formatting works

2. **Responsive Testing**:
   - [ ] Desktop: Full table visible
   - [ ] Tablet: Horizontal scroll appears
   - [ ] Mobile: Scrollable with min-width enforced

3. **Interaction Testing**:
   - [ ] Hover effect on rows works
   - [ ] Loading skeleton displays initially
   - [ ] Error state displays on API failure
   - [ ] Auto-refresh works (check after 5 minutes)

4. **Data Testing**:
   - [ ] All 30 VN30 stocks displayed
   - [ ] Prices formatted correctly (no decimals)
   - [ ] Percentages show 2 decimals
   - [ ] Company names displayed
   - [ ] Sorted by market cap (largest first)

5. **Performance Testing**:
   - [ ] Initial load <3 seconds
   - [ ] No layout shift during load
   - [ ] Smooth transitions
   - [ ] No console errors

## Success Criteria

- [ ] Hook created with proper React Query configuration
- [ ] Table component follows existing design patterns
- [ ] Color coding matches design system (green-500/red-500)
- [ ] Vietnamese locale formatting applied
- [ ] Loading and error states implemented
- [ ] Responsive design with horizontal scroll
- [ ] Auto-refresh every 5 minutes
- [ ] Component integrated into dashboard
- [ ] All manual tests pass
- [ ] TypeScript compiles without errors

## Risk Assessment

**Low Risk**:
- Pattern well-established (ShareholdersTabContent)
- Design system components already available
- React Query setup proven

**Potential Issues**:
1. **Layout conflicts**: Mitigated by following existing spacing patterns
2. **Color contrast**: Using proven color classes from design system
3. **Mobile overflow**: Handled with scrollbar-thin and min-width

**Mitigation**:
- Test on multiple screen sizes
- Verify color contrast in both light/dark modes
- Use existing utility classes for consistency

## Testing Checklist

### Unit Testing (Optional)
- [ ] Hook returns correct data structure
- [ ] Formatting functions work correctly
- [ ] Color logic handles edge cases (zero, null)

### Integration Testing
- [ ] Component renders with real API data
- [ ] Error boundary catches API failures
- [ ] Loading state transitions smoothly
- [ ] Auto-refresh triggers correctly

### Visual Regression Testing
- [ ] Screenshot comparison with design
- [ ] Dark mode rendering correct
- [ ] Mobile layout acceptable

## Next Steps

After completion:
1. Update project documentation with new feature
2. Consider adding sorting/filtering (future enhancement)
3. Monitor API performance and cache hit rates
4. Gather user feedback for improvements

## Unresolved Questions

1. Should table support client-side sorting by columns?
2. Add pagination or show all 30 stocks at once? (Recommend: show all)
3. Display market cap column or keep it hidden? (Currently hidden)
4. Add click-through to stock detail page? (Future enhancement)
