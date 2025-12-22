# Phase 4: Frontend UI

## Context

- **Parent Plan:** [plan.md](./plan.md)
- **Dependencies:** Phase 3 (API Endpoint)
- **Docs:** [design-guidelines.md](../../docs/design-guidelines.md)
- **Research:** [UI Patterns](./research/researcher-ui-patterns-report.md)

## Overview

- **Priority:** P1
- **Effort:** 2.5h
- **Status:** Pending
- **Description:** Build responsive table UI for top performers with TanStack Query, sorting, pagination

## Key Insights

From UI patterns research:
- Reuse VN30OverviewTable patterns exactly
- TanStack Query with 10s auto-refresh
- Client-side sorting (three-state toggle)
- Skeleton component matching table structure
- Vietnamese number formatting
- Color-coded profit indicators

## Requirements

### Functional
- Display top 50 performers in sortable table
- Columns: Rank, Symbol, Company, Net Profit, Revenue, Margin, EPS
- Sort by any column (client-side)
- Pagination (10/20/30 per page)
- Show last updated timestamp
- Refresh button with loading state

### Non-Functional
- Mobile responsive (horizontal scroll)
- Skeleton loading states
- Dark/light theme support
- Accessible (keyboard nav, ARIA)

## Architecture

```
TopPerformersPage
    │
    ├── Header (title, last updated, refresh button)
    │
    ├── TopPerformersTable
    │       ├── useTopPerformers() hook
    │       ├── Client-side sorting
    │       ├── Pagination
    │       └── TopPerformersTableSkeleton
    │
    └── Error/Empty states
```

## Related Code Files

### Create
- `apps/web/src/app/analytics/top-performers/page.tsx` (update existing)
- `apps/web/src/components/dashboard/top-performers-table.tsx` (new)
- `apps/web/src/hooks/use-top-performers.ts` (new)

### Modify
- `apps/web/src/lib/query-keys.ts` (add query key)
- `apps/web/src/lib/api.ts` (add API function)

## Implementation Steps

### Step 1: Add Query Key

In `apps/web/src/lib/query-keys.ts`:

```typescript
export const queryKeys = {
  // ... existing keys
  topPerformers: ['topPerformers'] as const,
}
```

### Step 2: Add API Function

In `apps/web/src/lib/api.ts`:

```typescript
export interface TopPerformerItem {
  rank: number
  symbol: string
  company_name: string | null
  exchange: string | null
  net_profit: number | null
  revenue: number | null
  profit_margin: number | null
  eps: number | null
  year: number
  quarter: number
}

export interface TopPerformersResponse {
  period: string
  updated_at: string | null
  total: number
  data: TopPerformerItem[]
}

export async function fetchTopPerformers(
  limit = 50,
  exchange?: string
): Promise<TopPerformersResponse> {
  const params = new URLSearchParams()
  params.set('limit', limit.toString())
  if (exchange) params.set('exchange', exchange)

  const res = await fetch(`${API_BASE}/stocks/analytics/top-performers?${params}`)
  if (!res.ok) throw new Error('Failed to fetch top performers')
  return res.json()
}
```

### Step 3: Create TanStack Query Hook

Create `apps/web/src/hooks/use-top-performers.ts`:

```typescript
"use client"

import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/lib/query-keys"
import { fetchTopPerformers, TopPerformersResponse } from "@/lib/api"

export function useTopPerformers(limit = 50, exchange?: string) {
  const query = useQuery<TopPerformersResponse>({
    queryKey: [...queryKeys.topPerformers, limit, exchange],
    queryFn: () => fetchTopPerformers(limit, exchange),
    staleTime: 60 * 1000,              // 1 min (data doesn't change often)
    refetchInterval: 5 * 60 * 1000,    // 5 min auto-refresh
    refetchOnWindowFocus: true,
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    refetch: query.refetch,
  }
}
```

### Step 4: Create Table Component

Create `apps/web/src/components/dashboard/top-performers-table.tsx`:

```typescript
"use client"

import { useState, useMemo } from "react"
import { RefreshCw, ArrowUpDown, ArrowDown, ArrowUp, TrendingUp, TrendingDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"
import { useTopPerformers } from "@/hooks/use-top-performers"
import { TopPerformerItem } from "@/lib/api"

type SortField = 'rank' | 'net_profit' | 'revenue' | 'profit_margin' | 'eps'
type SortDirection = 'asc' | 'desc' | null

// Formatters
function formatProfit(value: number | null): string {
  if (value === null) return "-"
  const billions = value / 1_000_000_000
  return `${billions.toLocaleString('vi-VN', { maximumFractionDigits: 1 })} tỷ`
}

function formatPercent(value: number | null): string {
  if (value === null) return "-"
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

function formatEps(value: number | null): string {
  if (value === null) return "-"
  return value.toLocaleString('vi-VN', { maximumFractionDigits: 0 })
}

export function TopPerformersTable() {
  const { data, isLoading, isFetching, error, refetch } = useTopPerformers(100)
  const [sortField, setSortField] = useState<SortField>('rank')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')
  const [currentPage, setCurrentPage] = useState(1)
  const [rowsPerPage, setRowsPerPage] = useState(10)

  // Sort data
  const sortedData = useMemo(() => {
    if (!data?.data) return []
    if (sortDirection === null) return data.data

    return [...data.data].sort((a, b) => {
      const aVal = a[sortField] ?? -Infinity
      const bVal = b[sortField] ?? -Infinity
      return sortDirection === 'asc' ? (aVal > bVal ? 1 : -1) : (aVal < bVal ? 1 : -1)
    })
  }, [data?.data, sortField, sortDirection])

  // Pagination
  const totalPages = Math.max(1, Math.ceil(sortedData.length / rowsPerPage))
  const startIndex = (currentPage - 1) * rowsPerPage
  const paginatedData = sortedData.slice(startIndex, startIndex + rowsPerPage)

  const toggleSort = (field: SortField) => {
    if (sortField !== field) {
      setSortField(field)
      setSortDirection('desc')
    } else {
      setSortDirection(prev => prev === 'desc' ? 'asc' : prev === 'asc' ? null : 'desc')
    }
    setCurrentPage(1)
  }

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ArrowUpDown className="h-3 w-3 ml-1 opacity-50" />
    if (sortDirection === 'desc') return <ArrowDown className="h-3 w-3 ml-1" />
    if (sortDirection === 'asc') return <ArrowUp className="h-3 w-3 ml-1" />
    return <ArrowUpDown className="h-3 w-3 ml-1 opacity-50" />
  }

  if (isLoading) return <TopPerformersTableSkeleton />

  if (error) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-8 text-center">
        <p className="text-destructive mb-4">Failed to load top performers</p>
        <Button onClick={() => refetch()} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" /> Retry
        </Button>
      </div>
    )
  }

  if (!data?.data?.length) {
    return (
      <div className="rounded-lg border border-border/50 bg-card/50 p-8 text-center text-muted-foreground">
        <p>No data available. Run the scheduled job first.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {data.period} • Updated: {data.updated_at ? new Date(data.updated_at).toLocaleDateString('vi-VN') : 'N/A'}
        </div>
        <Button onClick={() => refetch()} variant="ghost" size="sm">
          <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
        </Button>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border/50 bg-card/50 overflow-hidden">
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full min-w-[800px] border-collapse">
            <thead>
              <tr className="bg-muted/30">
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                  <button onClick={() => toggleSort('rank')} className="flex items-center">
                    # <SortIcon field="rank" />
                  </button>
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Symbol</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Company</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">
                  <button onClick={() => toggleSort('net_profit')} className="flex items-center justify-end ml-auto">
                    Net Profit <SortIcon field="net_profit" />
                  </button>
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">
                  <button onClick={() => toggleSort('revenue')} className="flex items-center justify-end ml-auto">
                    Revenue <SortIcon field="revenue" />
                  </button>
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">
                  <button onClick={() => toggleSort('profit_margin')} className="flex items-center justify-end ml-auto">
                    Margin <SortIcon field="profit_margin" />
                  </button>
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">
                  <button onClick={() => toggleSort('eps')} className="flex items-center justify-end ml-auto">
                    EPS <SortIcon field="eps" />
                  </button>
                </th>
              </tr>
            </thead>
            <tbody>
              {paginatedData.map((item) => (
                <tr key={item.symbol} className="border-t border-border/30 hover:bg-muted/20">
                  <td className="px-4 py-3 text-sm font-medium">{item.rank}</td>
                  <td className="px-4 py-3">
                    <span className="text-sm font-semibold text-primary">{item.symbol}</span>
                    <span className="ml-2 text-xs text-muted-foreground">{item.exchange}</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground max-w-[200px] truncate">
                    {item.company_name || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-right tabular-nums">
                    <span className={item.net_profit && item.net_profit > 0 ? "text-green-500" : "text-red-500"}>
                      {formatProfit(item.net_profit)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-right tabular-nums">
                    {formatProfit(item.revenue)}
                  </td>
                  <td className="px-4 py-3 text-sm text-right tabular-nums">
                    <span className={item.profit_margin && item.profit_margin > 0 ? "text-green-500" : "text-red-500"}>
                      {formatPercent(item.profit_margin)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-right tabular-nums">
                    {formatEps(item.eps)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-border/30 bg-muted/10">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>Show</span>
            <Select value={rowsPerPage.toString()} onValueChange={(v) => { setRowsPerPage(Number(v)); setCurrentPage(1) }}>
              <SelectTrigger className="w-[70px] h-8">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="10">10</SelectItem>
                <SelectItem value="20">20</SelectItem>
                <SelectItem value="50">50</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {startIndex + 1}-{Math.min(startIndex + rowsPerPage, sortedData.length)} of {sortedData.length}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
            >
              ←
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
            >
              →
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

function TopPerformersTableSkeleton() {
  return (
    <div className="rounded-lg border border-border/50 bg-card/50 p-4 space-y-3">
      <div className="flex justify-between">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-8 w-8" />
      </div>
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <Skeleton className="h-4 w-8" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-4 w-24 ml-auto" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-16" />
        </div>
      ))}
    </div>
  )
}
```

### Step 5: Update Page

Update `apps/web/src/app/analytics/top-performers/page.tsx`:

```typescript
import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import { TopPerformersTable } from "@/components/dashboard/top-performers-table"

export default function TopPerformersPage() {
  return (
    <DashboardLayoutClient>
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Top Performers</h1>
            <p className="text-sm text-muted-foreground">
              Top 50 most profitable companies from HOSE & HNX (quarterly)
            </p>
          </div>
        </div>
        <TopPerformersTable />
      </div>
    </DashboardLayoutClient>
  )
}
```

## Todo List

- [ ] Add query key to query-keys.ts
- [ ] Add API function and types to api.ts
- [ ] Create use-top-performers.ts hook
- [ ] Create top-performers-table.tsx component
- [ ] Update page.tsx to use component
- [ ] Test loading/error/empty states
- [ ] Test sorting functionality
- [ ] Test pagination
- [ ] Verify responsive design (mobile)
- [ ] Verify dark mode

## Success Criteria

- [ ] Page displays table with data
- [ ] Sorting works on all columns
- [ ] Pagination works correctly
- [ ] Refresh button shows spinner while fetching
- [ ] Skeleton shows during initial load
- [ ] Error state shows retry button
- [ ] Mobile horizontal scroll works
- [ ] Dark mode styling correct

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Large data causes lag | Low | Client-side pagination limits rendered rows |
| API not ready | Medium | Show "no data" state with clear message |

## Security Considerations

- No user input stored
- API validates query params
- XSS prevented by React's escaping

## Next Steps

- Feature complete! Test end-to-end flow
- Optional: Add exchange filter dropdown
- Optional: Add export to CSV
