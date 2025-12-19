# Phase 4: Frontend Component & Integration

## Context

Final phase of Sector Performance Tab feature. Create the UI component and integrate into dashboard.

## Overview

Build `sector-performance.tsx` component with sortable table, color-coded changes, and integrate as new tab/section on dashboard.

## Requirements

1. Create `SectorPerformance` component with:
   - Table displaying all sectors
   - Green/red color coding for positive/negative changes
   - Sortable columns (by change %, market cap)
   - Loading skeleton
   - Error state with retry
2. Export from dashboard index
3. Add to dashboard page as new section or tab

## Architecture

```
page.tsx
    ↓
<SectorPerformance />
    ↓
useSectorPerformance() hook
    ↓
Table with SectorPerformanceItem rows
```

## Related Files

| File | Action |
|------|--------|
| `apps/web/src/components/dashboard/sector-performance.tsx` | Create |
| `apps/web/src/components/dashboard/index.ts` | Add export |
| `apps/web/src/app/page.tsx` | Integrate |

## Implementation Steps

### Step 1: Create `sector-performance.tsx`

```tsx
"use client"

import { useState } from "react"
import { useSectorPerformance } from "@/hooks/use-sector-performance"
import { Skeleton } from "@/components/ui/skeleton"
import { AlertCircle, RefreshCw, TrendingUp, TrendingDown, ArrowUpDown } from "lucide-react"
import { cn } from "@/lib/utils"

type SortField = "change_pct" | "total_market_cap" | "stock_count" | "icb_name"
type SortOrder = "asc" | "desc"

interface SectorPerformanceProps {
  className?: string
}

export function SectorPerformance({ className }: SectorPerformanceProps) {
  const { data, isLoading, error, refetch, lastUpdated } = useSectorPerformance()
  const [sortField, setSortField] = useState<SortField>("change_pct")
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc")

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc")
    } else {
      setSortField(field)
      setSortOrder("desc")
    }
  }

  const sortedSectors = data?.sectors
    ? [...data.sectors].sort((a, b) => {
        const aVal = a[sortField]
        const bVal = b[sortField]
        if (typeof aVal === "string" && typeof bVal === "string") {
          return sortOrder === "asc" ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
        }
        return sortOrder === "asc" ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number)
      })
    : []

  if (isLoading && !data) {
    return <SectorPerformanceSkeleton />
  }

  if (error) {
    return (
      <div className="rounded-xl border bg-card p-6 text-center">
        <AlertCircle className="h-8 w-8 text-destructive mx-auto mb-2" />
        <p className="text-sm text-muted-foreground mb-3">{error.message}</p>
        <button
          onClick={refetch}
          className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
        >
          <RefreshCw className="h-4 w-4" />
          Retry
        </button>
      </div>
    )
  }

  if (!data || data.sectors.length === 0) {
    return (
      <div className="rounded-xl border bg-card p-6 text-center">
        <p className="text-sm text-muted-foreground">No sector data available</p>
      </div>
    )
  }

  return (
    <div className={cn("rounded-xl border bg-card", className)}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <h3 className="font-semibold">Sector Performance</h3>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-muted-foreground">
              Updated: {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={refetch}
            disabled={isLoading}
            className="p-1.5 rounded-md hover:bg-muted transition-colors"
            title="Refresh"
          >
            <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="text-left p-3 font-medium">
                <button
                  onClick={() => handleSort("icb_name")}
                  className="inline-flex items-center gap-1 hover:text-foreground"
                >
                  Sector
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="text-right p-3 font-medium">
                <button
                  onClick={() => handleSort("change_pct")}
                  className="inline-flex items-center gap-1 hover:text-foreground"
                >
                  Change %
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="text-right p-3 font-medium">
                <button
                  onClick={() => handleSort("total_market_cap")}
                  className="inline-flex items-center gap-1 hover:text-foreground"
                >
                  Market Cap
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="text-right p-3 font-medium">
                <button
                  onClick={() => handleSort("stock_count")}
                  className="inline-flex items-center gap-1 hover:text-foreground"
                >
                  Stocks
                  <ArrowUpDown className="h-3 w-3" />
                </button>
              </th>
              <th className="text-left p-3 font-medium hidden lg:table-cell">Top Movers</th>
            </tr>
          </thead>
          <tbody>
            {sortedSectors.map((sector) => (
              <tr key={sector.icb_code} className="border-b last:border-0 hover:bg-muted/30">
                <td className="p-3">
                  <div className="font-medium">{sector.icb_name}</div>
                  <div className="text-xs text-muted-foreground">{sector.icb_code}</div>
                </td>
                <td className="p-3 text-right">
                  <div
                    className={cn(
                      "inline-flex items-center gap-1 font-medium",
                      sector.change_pct > 0 && "text-green-600 dark:text-green-400",
                      sector.change_pct < 0 && "text-red-600 dark:text-red-400",
                      sector.change_pct === 0 && "text-muted-foreground"
                    )}
                  >
                    {sector.change_pct > 0 ? (
                      <TrendingUp className="h-4 w-4" />
                    ) : sector.change_pct < 0 ? (
                      <TrendingDown className="h-4 w-4" />
                    ) : null}
                    {sector.change_pct > 0 ? "+" : ""}
                    {sector.change_pct.toFixed(2)}%
                  </div>
                </td>
                <td className="p-3 text-right text-muted-foreground">
                  {formatMarketCap(sector.total_market_cap)}
                </td>
                <td className="p-3 text-right text-muted-foreground">{sector.stock_count}</td>
                <td className="p-3 hidden lg:table-cell">
                  <div className="flex gap-2 text-xs">
                    {sector.top_gainers.slice(0, 2).map((s) => (
                      <span key={s} className="text-green-600 dark:text-green-400">
                        {s}
                      </span>
                    ))}
                    {sector.top_losers.slice(0, 2).map((s) => (
                      <span key={s} className="text-red-600 dark:text-red-400">
                        {s}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SectorPerformanceSkeleton() {
  return (
    <div className="rounded-xl border bg-card">
      <div className="flex items-center justify-between p-4 border-b">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-4 w-24" />
      </div>
      <div className="p-4 space-y-3">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="flex items-center gap-4">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-16 ml-auto" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-12" />
          </div>
        ))}
      </div>
    </div>
  )
}

function formatMarketCap(value: number): string {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}T`
  }
  return `${value.toFixed(0)}B`
}

export { SectorPerformanceSkeleton }
```

### Step 2: Update `index.ts` Export

Add to `apps/web/src/components/dashboard/index.ts`:

```typescript
export { SectorPerformance, SectorPerformanceSkeleton } from "./sector-performance"
```

### Step 3: Integrate in `page.tsx`

Add import:
```typescript
import { SectorPerformance } from "@/components/dashboard"
```

Add section after Market Indices (around line 68):
```tsx
{/* Sector Performance Section */}
<section>
  <h2 className="text-lg font-semibold text-foreground mb-4">
    Sector Performance
  </h2>
  <SectorPerformance />
</section>
```

## Todo List

- [ ] Create `sector-performance.tsx` component
- [ ] Add skeleton loading state
- [ ] Implement sortable columns
- [ ] Add green/red color coding
- [ ] Export from dashboard index.ts
- [ ] Add section to page.tsx
- [ ] Test responsive layout
- [ ] Verify auto-refresh works

## Success Criteria

- [ ] Table displays all 10 ICB Level 2 sectors
- [ ] Positive changes show green, negative show red
- [ ] Columns sortable by clicking headers
- [ ] Loading skeleton shows during fetch
- [ ] Error state with retry button works
- [ ] Auto-refresh updates data every 5 min
- [ ] Responsive on mobile (hide some columns)
- [ ] Matches existing design patterns

## Risks

| Risk | Mitigation |
|------|------------|
| Table overflow on mobile | Use overflow-x-auto, hide columns |
| Color accessibility | Use sufficient contrast ratios |
| Too many re-renders | Memoize sorted data if needed |

## Design Notes

- Follow existing card pattern (rounded-xl border bg-card)
- Use muted-foreground for secondary text
- TrendingUp/TrendingDown icons from lucide-react
- Match existing table styles from finance-tab-content.tsx

## Testing Checklist

- [ ] Component renders without errors
- [ ] Loading state shows skeleton
- [ ] Error state shows message and retry
- [ ] Empty state handled gracefully
- [ ] Sort by each column works
- [ ] Colors correct for +/- changes
- [ ] Refresh button triggers refetch
- [ ] Auto-refresh after 5 minutes
- [ ] Mobile layout acceptable
