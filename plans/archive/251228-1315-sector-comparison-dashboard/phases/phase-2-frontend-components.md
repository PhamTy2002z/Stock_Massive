# Phase 2: Frontend UI Components

## Context

- **Parent Plan:** [plan.md](../plan.md)
- **Depends On:** [Phase 1](./phase-1-backend-enhancement.md)
- **Research:** [UI Patterns](../research/researcher-01-ui-patterns.md)
- **Docs:** [Design Guidelines](../../../../docs/design-guidelines.md)

## Overview

| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Status | Done (2025-12-28) |
| Effort | 2.5h |
| Description | Build Sector Comparison subtab với peer table, premium/discount badges |

## Key Insights

From UI research + design-guidelines.md:
- Horizontal scroll table with sticky first column (freezeColumns)
- Semantic colors: `--stock-up` (green), `--stock-down` (red), muted (neutral)
- Right-align numeric values with `tabular-nums`, left-align company names
- Mobile: horizontal scroll preferred over card layout
- KPI requirements: label, value, unit, benchmark context, time range
- Table standards: enableSorting, stickyHeader, enableExport (CSV)
- Feedback: Last updated timestamp, refresh button, error states

## Requirements

### Functional
1. New "Sector" subtab in Advanced Tab
2. Peer comparison table with sortable columns
3. Premium/discount badges with color coding
4. Sector overview card (ICB name, peer count, medians)
5. Highlight target stock row

### Non-Functional
1. Responsive: horizontal scroll on mobile
2. Loading skeleton state
3. Error/empty states
4. WCAG AA color contrast

## Architecture

```
AdvancedTab
└── SectorSubtab
    ├── SectorOverviewCard    # ICB info + medians
    └── PeerComparisonTable
        ├── TableHeader       # Sortable columns
        ├── TableRow          # Peer data
        └── PremiumBadge      # Color-coded %
```

## Related Code Files

**Create:**
- `apps/web/src/components/dashboard/advanced-tab/sector-subtab.tsx`
- `apps/web/src/components/dashboard/advanced-tab/widgets/peer-comparison-table.tsx`
- `apps/web/src/components/dashboard/advanced-tab/widgets/sector-overview-card.tsx`
- `apps/web/src/hooks/use-sector-peers.ts`

**Modify:**
- `apps/web/src/components/dashboard/advanced-tab/index.tsx` - Add subtab
- `apps/web/src/lib/api.ts` - Add fetchSectorPeers()
- `apps/web/src/lib/query-keys.ts` - Add sectorPeers key

## Implementation Steps

### 1. Add API Function (10 min)

```typescript
// apps/web/src/lib/api.ts

export interface SectorMedian {
  pe: number | null
  pb: number | null
  roe: number | null
  roa: number | null
  market_cap: number | null
}

export interface PeerMetrics {
  symbol: string
  company_name: string | null
  roe: number | null
  roa: number | null
  pe: number | null
  pb: number | null
  market_cap: number | null
  premium_pe: number | null
  premium_pb: number | null
  premium_roe: number | null
  premium_roa: number | null
}

export interface SectorPeersResponse {
  symbol: string
  icb_code: string
  icb_name: string
  peers: PeerMetrics[]
  sector_median: SectorMedian
  target_premium: Record<string, number | null>
}

export async function fetchSectorPeers(
  symbol: string,
  limit: number = 10
): Promise<SectorPeersResponse> {
  return fetchApi<SectorPeersResponse>(
    `/stocks/${symbol}/sector-peers?limit=${limit}`
  )
}
```

### 2. Add Query Key (5 min)

```typescript
// apps/web/src/lib/query-keys.ts

export const queryKeys = {
  // ... existing
  sectorPeers: (symbol: string) => ["sector-peers", symbol] as const,
}
```

### 3. Create Hook (15 min)

```typescript
// apps/web/src/hooks/use-sector-peers.ts

import { useQuery } from "@tanstack/react-query"
import { fetchSectorPeers, SectorPeersResponse } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useSectorPeers(symbol: string) {
  return useQuery<SectorPeersResponse>({
    queryKey: queryKeys.sectorPeers(symbol),
    queryFn: () => fetchSectorPeers(symbol),
    enabled: !!symbol,
    staleTime: 4 * 60 * 60 * 1000, // 4 hours
    gcTime: 24 * 60 * 60 * 1000,   // 24 hours
  })
}
```

### 4. Create Premium Badge Component (20 min)

```typescript
// apps/web/src/components/dashboard/advanced-tab/widgets/premium-badge.tsx

"use client"

import { cn } from "@/lib/utils"

interface PremiumBadgeProps {
  value: number | null
  className?: string
}

/**
 * Color coding per design-guidelines.md:
 * - Premium (above median): --stock-up (green)
 * - Neutral (±5%): muted foreground (gray)
 * - Discount (below median): --stock-down (red)
 */
const getPremiumStyles = (value: number) => {
  if (value > 5) {
    return {
      bg: "bg-[hsl(var(--stock-up))]/10",
      text: "text-[hsl(var(--stock-up))]",
    }
  }
  if (value >= -5) {
    return {
      bg: "bg-muted",
      text: "text-muted-foreground",
    }
  }
  return {
    bg: "bg-[hsl(var(--stock-down))]/10",
    text: "text-[hsl(var(--stock-down))]",
  }
}

export function PremiumBadge({ value, className }: PremiumBadgeProps) {
  if (value === null) {
    return <span className="text-muted-foreground">-</span>
  }

  const styles = getPremiumStyles(value)

  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold tabular-nums",
        styles.bg,
        styles.text,
        className
      )}
    >
      {value > 0 ? "+" : ""}{value.toFixed(1)}%
    </span>
  )
}
```

### 5. Create Sector Overview Card (25 min)

```typescript
// apps/web/src/components/dashboard/advanced-tab/widgets/sector-overview-card.tsx

"use client"

import { Card, CardContent } from "@/components/ui/card"
import { SectorMedian } from "@/lib/api"
import { Building2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface SectorOverviewCardProps {
  icbCode: string
  icbName: string
  peerCount: number
  median: SectorMedian
  targetPremium?: Record<string, number | null>
}

/**
 * KPI format per design-guidelines.md:
 * - label: KPI name
 * - value: Main metric
 * - unit: Required suffix
 * - benchmark: Comparison context (sector median)
 */
interface MetricItemProps {
  label: string
  value: number | null
  unit: string
  premium?: number | null // Target stock premium vs median
}

function MetricItem({ label, value, unit, premium }: MetricItemProps) {
  const formattedValue = value !== null ? value.toFixed(2) : "-"

  // Premium indicator color per design-guidelines.md
  const getPremiumColor = (p: number) => {
    if (p > 5) return "text-[hsl(var(--stock-up))]"
    if (p < -5) return "text-[hsl(var(--stock-down))]"
    return "text-muted-foreground"
  }

  return (
    <div className="space-y-1">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm font-semibold tabular-nums">
        {formattedValue}{unit}
      </p>
      {premium !== null && premium !== undefined && (
        <p className={cn("text-xs tabular-nums", getPremiumColor(premium))}>
          {premium > 0 ? "+" : ""}{premium.toFixed(1)}% vs median
        </p>
      )}
    </div>
  )
}

export function SectorOverviewCard({
  icbCode,
  icbName,
  peerCount,
  median,
  targetPremium,
}: SectorOverviewCardProps) {
  return (
    <Card className="bg-muted/30 border-border/50">
      <CardContent className="p-4">
        {/* Header with ICB info */}
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded-lg bg-primary/10">
            <Building2 className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h4 className="font-semibold text-foreground">{icbName}</h4>
            <p className="text-xs text-muted-foreground">
              ICB: {icbCode} • {peerCount} công ty
            </p>
          </div>
        </div>

        {/* Sector Median KPIs - 4-column grid per design-guidelines.md */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <MetricItem
            label="P/E Median"
            value={median.pe}
            unit="x"
            premium={targetPremium?.pe}
          />
          <MetricItem
            label="P/B Median"
            value={median.pb}
            unit="x"
            premium={targetPremium?.pb}
          />
          <MetricItem
            label="ROE Median"
            value={median.roe}
            unit="%"
            premium={targetPremium?.roe}
          />
          <MetricItem
            label="ROA Median"
            value={median.roa}
            unit="%"
            premium={targetPremium?.roa}
          />
        </div>

        {/* Time range context - Required per KPI standards */}
        <p className="mt-3 text-xs text-muted-foreground text-right">
          Dữ liệu: TTM (12 tháng gần nhất)
        </p>
      </CardContent>
    </Card>
  )
}
```

### 6. Create Peer Comparison Table (45 min)

```typescript
// apps/web/src/components/dashboard/advanced-tab/widgets/peer-comparison-table.tsx

"use client"

import { useState } from "react"
import { PeerMetrics } from "@/lib/api"
import { PremiumBadge } from "./premium-badge"
import { cn } from "@/lib/utils"
import { ArrowUpDown, ArrowUp, ArrowDown, Download } from "lucide-react"
import { Button } from "@/components/ui/button"

interface PeerComparisonTableProps {
  peers: PeerMetrics[]
  targetSymbol: string
}

type SortKey = "symbol" | "pe" | "pb" | "roe" | "roa" | "market_cap"
type SortDir = "asc" | "desc"

/**
 * Table standards per design-guidelines.md:
 * - stickyHeader: true
 * - enableSorting: true
 * - freezeColumns: ["symbol"]
 * - enableExport: true (CSV)
 * - onRowClick: navigate to detail
 */
export function PeerComparisonTable({
  peers,
  targetSymbol,
}: PeerComparisonTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("market_cap")
  const [sortDir, setSortDir] = useState<SortDir>("desc")

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc")
    } else {
      setSortKey(key)
      setSortDir("desc")
    }
  }

  const sortedPeers = [...peers].sort((a, b) => {
    const aVal = a[sortKey] ?? 0
    const bVal = b[sortKey] ?? 0
    return sortDir === "asc" ? aVal - bVal : bVal - aVal
  })

  // Export to CSV - per design-guidelines.md enableExport requirement
  const handleExport = () => {
    const headers = ["Mã CP", "Tên công ty", "P/E", "P/B", "ROE (%)", "ROA (%)", "vs Sector (%)"]
    const rows = sortedPeers.map((p) => [
      p.symbol,
      p.company_name ?? "",
      p.pe?.toFixed(2) ?? "",
      p.pb?.toFixed(2) ?? "",
      p.roe?.toFixed(2) ?? "",
      p.roa?.toFixed(2) ?? "",
      p.premium_pe?.toFixed(1) ?? "",
    ])
    const csv = [headers, ...rows].map((r) => r.join(",")).join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `sector-peers-${targetSymbol}.csv`
    a.click()
  }

  const SortIcon = ({ column }: { column: SortKey }) => {
    if (sortKey !== column) return <ArrowUpDown className="h-3 w-3 opacity-50" />
    return sortDir === "asc" ? (
      <ArrowUp className="h-3 w-3" />
    ) : (
      <ArrowDown className="h-3 w-3" />
    )
  }

  const SortableHeader = ({
    column,
    children,
    align = "right",
  }: {
    column: SortKey
    children: React.ReactNode
    align?: "left" | "right"
  }) => (
    <th
      className={cn(
        "px-3 py-2 font-medium cursor-pointer hover:bg-muted/80 transition-colors",
        align === "right" ? "text-right" : "text-left"
      )}
      onClick={() => handleSort(column)}
    >
      <span className={cn(
        "flex items-center gap-1",
        align === "right" && "justify-end"
      )}>
        {children}
        <SortIcon column={column} />
      </span>
    </th>
  )

  return (
    <div className="space-y-2">
      {/* Export button - Required per table standards */}
      <div className="flex justify-end">
        <Button
          variant="outline"
          size="sm"
          onClick={handleExport}
          className="h-8 gap-1.5"
        >
          <Download className="h-3.5 w-3.5" />
          <span className="text-xs">Xuất CSV</span>
        </Button>
      </div>

      {/* Table with horizontal scroll for mobile */}
      <div className="overflow-x-auto rounded-lg border border-border/50">
        <table className="w-full text-sm">
          {/* Sticky header per design-guidelines.md */}
          <thead className="bg-muted/50 sticky top-0">
            <tr>
              {/* Frozen first column */}
              <th className="sticky left-0 z-10 bg-muted/50 px-3 py-2 text-left font-medium min-w-[140px]">
                Mã CP
              </th>
              <SortableHeader column="pe">P/E</SortableHeader>
              <SortableHeader column="pb">P/B</SortableHeader>
              <SortableHeader column="roe">ROE</SortableHeader>
              <SortableHeader column="roa">ROA</SortableHeader>
              <th className="px-3 py-2 text-right font-medium">vs Sector</th>
            </tr>
          </thead>
          <tbody>
            {sortedPeers.map((peer) => (
              <tr
                key={peer.symbol}
                className={cn(
                  "border-t border-border/30 hover:bg-muted/30 transition-colors cursor-pointer",
                  peer.symbol === targetSymbol && "bg-primary/5 font-semibold"
                )}
                onClick={() => {
                  // Navigate to stock detail per drill-down requirement
                  window.location.href = `/stocks/${peer.symbol}`
                }}
              >
                {/* Frozen first column with sticky positioning */}
                <td className="sticky left-0 z-10 bg-background px-3 py-2 min-w-[140px]">
                  <div>
                    <span className={cn(
                      "font-medium",
                      peer.symbol === targetSymbol && "text-primary"
                    )}>
                      {peer.symbol}
                    </span>
                    {peer.company_name && (
                      <p className="text-xs text-muted-foreground truncate max-w-[120px]">
                        {peer.company_name}
                      </p>
                    )}
                  </div>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {peer.pe?.toFixed(2) ?? "-"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {peer.pb?.toFixed(2) ?? "-"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {peer.roe?.toFixed(2) ?? "-"}%
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {peer.roa?.toFixed(2) ?? "-"}%
                </td>
                <td className="px-3 py-2 text-right">
                  <PremiumBadge value={peer.premium_pe} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

### 7. Create Sector Subtab (25 min)

```typescript
// apps/web/src/components/dashboard/advanced-tab/sector-subtab.tsx

"use client"

import { useSectorPeers } from "@/hooks/use-sector-peers"
import { SectorOverviewCard } from "./widgets/sector-overview-card"
import { PeerComparisonTable } from "./widgets/peer-comparison-table"
import { RefreshCw, AlertCircle, Building2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

interface SectorSubtabProps {
  symbol: string
}

function SectorSubtabSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-8 w-24" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}

export default function SectorSubtab({ symbol }: SectorSubtabProps) {
  const { data, isLoading, error, refetch, dataUpdatedAt } = useSectorPeers(symbol)

  if (isLoading) return <SectorSubtabSkeleton />

  if (error) {
    return (
      <div className="flex items-center gap-3 p-4 rounded-lg bg-destructive/10 border border-destructive/20">
        <AlertCircle className="h-4 w-4 text-destructive shrink-0" />
        <p className="text-sm text-destructive">
          Có lỗi khi tải dữ liệu. Vui lòng thử lại.
        </p>
        <Button variant="ghost" size="sm" onClick={() => refetch()}>
          Thử lại
        </Button>
      </div>
    )
  }

  if (!data || data.peers.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <Building2 className="h-12 w-12 text-muted-foreground mb-4" />
        <p className="text-muted-foreground">Không tìm thấy công ty cùng ngành</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Thử chọn mã cổ phiếu khác để so sánh
        </p>
      </div>
    )
  }

  // Format last updated time per design-guidelines.md feedback requirements
  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : null

  return (
    <div className="space-y-6">
      {/* Header with refresh - per design-guidelines.md feedback section */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-1 h-5 bg-primary rounded-full" />
          <h3 className="text-sm font-semibold text-foreground">
            So sánh ngành
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-xs text-muted-foreground">
              Cập nhật: {lastUpdated}
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading}
            className={cn(
              "h-8 gap-1.5 text-muted-foreground hover:text-foreground",
              "hover:bg-muted/50 transition-colors"
            )}
          >
            <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
            <span className="text-xs">Làm mới</span>
          </Button>
        </div>
      </div>

      {/* Sector Overview - passes targetPremium for KPI context */}
      <SectorOverviewCard
        icbCode={data.icb_code}
        icbName={data.icb_name}
        peerCount={data.peers.length}
        median={data.sector_median}
        targetPremium={data.target_premium}
      />

      {/* Peer Table with export functionality */}
      <PeerComparisonTable
        peers={data.peers}
        targetSymbol={symbol}
      />

      {/* Legend - Using semantic colors per design-guidelines.md */}
      <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-[hsl(var(--stock-up))]/20 border border-[hsl(var(--stock-up))]" />
          Premium (trên +5%)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-muted border border-border" />
          Trung bình (±5%)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded bg-[hsl(var(--stock-down))]/20 border border-[hsl(var(--stock-down))]" />
          Discount (dưới -5%)
        </span>
      </div>
    </div>
  )
}
```

### 8. Update Advanced Tab Index (10 min)

```typescript
// apps/web/src/components/dashboard/advanced-tab/index.tsx

// Add to imports
const SectorSubtab = lazy(() => import("./sector-subtab"))
import { Building2 } from "lucide-react"

// Add to subTabs array
{
  value: "sector" as const,
  label: "Sector",
  icon: Building2,
  description: "So sánh với công ty cùng ngành",
}

// Add to content render
{activeSubTab === "sector" && (
  <Suspense fallback={<SubtabSkeleton />}>
    <SectorSubtab symbol={symbol} />
  </Suspense>
)}
```

## Todo List

- [ ] Add `fetchSectorPeers()` to `lib/api.ts`
- [ ] Add query key to `query-keys.ts`
- [ ] Create `use-sector-peers.ts` hook
- [ ] Create `premium-badge.tsx` component
- [ ] Create `sector-overview-card.tsx` component
- [ ] Create `peer-comparison-table.tsx` component
- [ ] Create `sector-subtab.tsx` component
- [ ] Update `advanced-tab/index.tsx` with new subtab
- [ ] Test responsive behavior (mobile horizontal scroll)
- [ ] Verify color contrast accessibility

## Success Criteria

- [ ] Sector subtab visible in Advanced Tab
- [ ] Table displays 10 peers with metrics
- [ ] Target stock row highlighted
- [ ] Sort by any column works
- [ ] Premium badges use semantic colors (`--stock-up`/`--stock-down`)
- [ ] KPIs show unit suffix and benchmark context
- [ ] CSV export button functional
- [ ] Last updated timestamp displayed
- [ ] Mobile: horizontal scroll works

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Table overflow on mobile | Medium | Horizontal scroll with custom scrollbar |
| No peers returned | Low | Empty state with helpful message |
| Slow initial load | Medium | Cache + skeleton loading |

## Security Considerations

- No user input handling
- Data from trusted API
- No sensitive data exposed

## Next Steps

After completion → [Phase 3: Integration & Testing](./phase-3-integration-testing.md)
