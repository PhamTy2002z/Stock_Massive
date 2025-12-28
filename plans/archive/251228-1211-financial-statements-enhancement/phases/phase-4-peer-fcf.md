# Phase 4: Peer Comparison & FCF Analysis

## Context

- **Plan**: [plan.md](../plan.md)
- **Phase 1**: [Backend APIs](phase-1-backend-apis.md) (prerequisite)
- **Research**: [brainstorm-summary.md](../research/brainstorm-summary.md)

## Overview

Create Peer Comparison table with heatmap coloring and FCF Waterfall visualization.

## Key Insights

- Sector peers via ICB codes (icbCode3)
- Top 5 peers by market cap in same sector
- **Color per Design Guidelines:**
  - Orange accent for target stock highlight
  - Green/Red only for above/below average in heatmap
  - Use muted-foreground for secondary text
- FCF Waterfall: Net Income -> adjustments -> CFO -> CapEx -> FCF
- CCC (Cash Conversion Cycle) may be NULL for banks - show "N/A - Không áp dụng"
- **KPI Requirements (MANDATORY):**
  - Show benchmark context (sector average)
  - Show time range in card header

## Requirements

### 1. Peer Comparison Table

```
┌────────────────────────────────────────────────────────────────────┐
│  Peer Comparison - Thuc pham (ICB: 3577)                    VNM    │
├────────────────────────────────────────────────────────────────────┤
│  Symbol │ Company        │ ROE    │ ROA   │ P/E   │ P/B   │ MCap  │
├─────────┼────────────────┼────────┼───────┼───────┼───────┼───────┤
│  VNM    │ Vinamilk       │ ██18%  │ ██12% │ 15.2  │ 3.1   │ 150T  │
│  MSN    │ Masan          │ ░░12%  │ ░░8%  │ 18.5  │ 2.8   │ 120T  │
│  MCH    │ Masan Consumer │ ██15%  │ ██10% │ 14.2  │ 2.2   │ 80T   │
│  SAB    │ Sabeco         │ ██20%  │ ██15% │ 22.1  │ 4.5   │ 75T   │
│  QNS    │ Quang Ngai     │ ░░10%  │ ░░7%  │ 12.5  │ 1.8   │ 25T   │
└────────────────────────────────────────────────────────────────────┘
  Legend: ██ Above sector avg  ░░ Below sector avg
```

### 2. FCF Waterfall

```
┌────────────────────────────────────────────────────────────────────┐
│  FCF Analysis - Q4/2024                                     VNM    │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│      Net Income  ████████████████████  3,500B                     │
│           ↓                                                        │
│  + Deprec/Adj   ████████████████████████  +800B                   │
│  + WC Changes   ████████████████████████████  +500B               │
│           ↓                                                        │
│        CFO      ██████████████████████████████  4,800B            │
│           ↓                                                        │
│    - CapEx      ████████  -1,200B                                 │
│           ↓                                                        │
│        FCF      ████████████████████████  3,600B                  │
│                                                                    │
├────────────────────────────────────────────────────────────────────┤
│  FCF Margin: 27%  │  FCF Yield: 2.4%  │  CCC: 45 days             │
└────────────────────────────────────────────────────────────────────┘
```

## Architecture

```
apps/web/src/components/dashboard/
├── peer-comparison/
│   ├── peer-comparison-card.tsx      # Main container
│   └── peer-metrics-table.tsx        # Heatmap table
├── fcf-analysis/
│   ├── fcf-analysis-card.tsx         # Main container
│   ├── fcf-waterfall.tsx             # Waterfall chart
│   └── ccc-indicator.tsx             # CCC display
└── index.ts                          # Export
```

## Related Files

| File | Action |
|------|--------|
| `/apps/web/src/components/dashboard/peer-comparison/peer-comparison-card.tsx` | **NEW** |
| `/apps/web/src/components/dashboard/peer-comparison/peer-metrics-table.tsx` | **NEW** |
| `/apps/web/src/components/dashboard/fcf-analysis/fcf-analysis-card.tsx` | **NEW** |
| `/apps/web/src/components/dashboard/fcf-analysis/fcf-waterfall.tsx` | **NEW** |
| `/apps/web/src/components/dashboard/fcf-analysis/ccc-indicator.tsx` | **NEW** |
| `/apps/web/src/hooks/use-sector-peers.ts` | **NEW** |
| `/apps/web/src/hooks/use-fcf-analysis.ts` | **NEW** |
| `/apps/web/src/lib/api.ts` | Add `fetchSectorPeers()`, `fetchFCFAnalysis()` |

## Implementation Steps

### Step 1: Add API Types and Clients

**File: `/apps/web/src/lib/api.ts`**

```typescript
// Sector Peers
export interface PeerMetrics {
  symbol: string
  company_name: string | null
  roe: number | null
  roa: number | null
  pe: number | null
  pb: number | null
  market_cap: number | null
}

export interface SectorPeersResponse {
  symbol: string
  icb_code: string
  icb_name: string
  peers: PeerMetrics[]
}

export async function fetchSectorPeers(
  symbol: string,
  limit: number = 5
): Promise<SectorPeersResponse> {
  const response = await fetch(
    `${API_BASE_URL}/stocks/analytics/sector-peers?symbol=${symbol}&limit=${limit}`
  )
  if (!response.ok) throw new Error("Failed to fetch sector peers")
  return response.json()
}

// FCF Analysis
export interface FCFAnalysisResponse {
  symbol: string
  period: string
  net_income: number | null
  cfo: number | null
  capex: number | null
  fcf: number | null
  fcf_margin: number | null
  ccc: number | null
  dso: number | null
  dio: number | null
  dpo: number | null
  market_cap: number | null
  fcf_yield: number | null
}

export async function fetchFCFAnalysis(symbol: string): Promise<FCFAnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/stocks/${symbol}/fcf-analysis`)
  if (!response.ok) throw new Error("Failed to fetch FCF analysis")
  return response.json()
}
```

### Step 2: Create Query Hooks

**File: `/apps/web/src/hooks/use-sector-peers.ts`**

```typescript
import { useQuery } from "@tanstack/react-query"
import { fetchSectorPeers, type SectorPeersResponse } from "@/lib/api"

export function useSectorPeers(symbol: string | null, limit: number = 5) {
  return useQuery<SectorPeersResponse>({
    queryKey: ["sector-peers", symbol, limit],
    queryFn: () => fetchSectorPeers(symbol!, limit),
    enabled: !!symbol,
    staleTime: 1000 * 60 * 10, // 10 minutes
  })
}
```

**File: `/apps/web/src/hooks/use-fcf-analysis.ts`**

```typescript
import { useQuery } from "@tanstack/react-query"
import { fetchFCFAnalysis, type FCFAnalysisResponse } from "@/lib/api"

export function useFCFAnalysis(symbol: string | null) {
  return useQuery<FCFAnalysisResponse>({
    queryKey: ["fcf-analysis", symbol],
    queryFn: () => fetchFCFAnalysis(symbol!),
    enabled: !!symbol,
    staleTime: 1000 * 60 * 5,
  })
}
```

### Step 3: Create Peer Metrics Table

**File: `/apps/web/src/components/dashboard/peer-comparison/peer-metrics-table.tsx`**

```tsx
"use client"

import { cn } from "@/lib/utils"
import type { PeerMetrics } from "@/lib/api"

interface PeerMetricsTableProps {
  peers: PeerMetrics[]
  targetSymbol: string
}

function formatPercent(value: number | null): string {
  if (value === null) return "-"
  return `${(value * 100).toFixed(1)}%`
}

function formatRatio(value: number | null): string {
  if (value === null) return "-"
  return value.toFixed(1)
}

function formatMarketCap(value: number | null): string {
  if (value === null) return "-"
  if (value >= 1e12) return `${(value / 1e12).toFixed(0)}T`
  if (value >= 1e9) return `${(value / 1e9).toFixed(0)}B`
  return `${(value / 1e6).toFixed(0)}M`
}

function getHeatmapColor(value: number | null, avg: number, inverse: boolean = false): string {
  if (value === null) return ""
  const isAbove = inverse ? value < avg : value > avg
  return isAbove ? "bg-green-500/20 text-green-600 dark:text-green-400" : "bg-red-500/20 text-red-600 dark:text-red-400"
}

export function PeerMetricsTable({ peers, targetSymbol }: PeerMetricsTableProps) {
  // Calculate averages for heatmap
  const avgRoe = peers.reduce((s, p) => s + (p.roe || 0), 0) / peers.length
  const avgRoa = peers.reduce((s, p) => s + (p.roa || 0), 0) / peers.length
  const avgPe = peers.reduce((s, p) => s + (p.pe || 0), 0) / peers.length
  const avgPb = peers.reduce((s, p) => s + (p.pb || 0), 0) / peers.length

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border/50">
            <th className="py-2 px-3 text-left font-medium text-muted-foreground">Symbol</th>
            <th className="py-2 px-3 text-left font-medium text-muted-foreground">Company</th>
            <th className="py-2 px-3 text-right font-medium text-muted-foreground">ROE</th>
            <th className="py-2 px-3 text-right font-medium text-muted-foreground">ROA</th>
            <th className="py-2 px-3 text-right font-medium text-muted-foreground">P/E</th>
            <th className="py-2 px-3 text-right font-medium text-muted-foreground">P/B</th>
            <th className="py-2 px-3 text-right font-medium text-muted-foreground">MCap</th>
          </tr>
        </thead>
        <tbody>
          {peers.map((peer) => (
            <tr
              key={peer.symbol}
              className={cn(
                "border-b border-border/30 hover:bg-muted/20",
                // Use orange accent for target stock per Design Guidelines
                peer.symbol === targetSymbol && "bg-[hsl(var(--accent-orange))]/10 border-[hsl(var(--accent-orange))]/30"
              )}
            >
              <td className="py-2 px-3">
                <span className={cn(
                  "font-semibold",
                  peer.symbol === targetSymbol && "text-[hsl(var(--accent-orange))]"
                )}>
                  {peer.symbol}
                </span>
              </td>
              <td className="py-2 px-3 text-muted-foreground max-w-[150px] truncate">
                {peer.company_name || "-"}
              </td>
              <td className={cn("py-2 px-3 text-right tabular-nums rounded", getHeatmapColor(peer.roe, avgRoe))}>
                {formatPercent(peer.roe)}
              </td>
              <td className={cn("py-2 px-3 text-right tabular-nums rounded", getHeatmapColor(peer.roa, avgRoa))}>
                {formatPercent(peer.roa)}
              </td>
              <td className={cn("py-2 px-3 text-right tabular-nums rounded", getHeatmapColor(peer.pe, avgPe, true))}>
                {formatRatio(peer.pe)}
              </td>
              <td className={cn("py-2 px-3 text-right tabular-nums rounded", getHeatmapColor(peer.pb, avgPb, true))}>
                {formatRatio(peer.pb)}
              </td>
              <td className="py-2 px-3 text-right tabular-nums">
                {formatMarketCap(peer.market_cap)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-2 text-xs text-muted-foreground">
        Legend: <span className="text-green-500">Green</span> = Above avg, <span className="text-red-500">Red</span> = Below avg (P/E, P/B: lower is better)
      </div>
    </div>
  )
}
```

### Step 4: Create Peer Comparison Card

**File: `/apps/web/src/components/dashboard/peer-comparison/peer-comparison-card.tsx`**

```tsx
"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Users } from "lucide-react"
import { useSectorPeers } from "@/hooks/use-sector-peers"
import { PeerMetricsTable } from "./peer-metrics-table"

interface PeerComparisonCardProps {
  symbol: string | null
  className?: string
}

export function PeerComparisonCard({ symbol, className }: PeerComparisonCardProps) {
  const { data, isLoading, error } = useSectorPeers(symbol)

  if (!symbol) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center h-[250px] text-muted-foreground">
          Chon mot co phieu de xem Peer Comparison
        </CardContent>
      </Card>
    )
  }

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[180px]" />
        </CardContent>
      </Card>
    )
  }

  if (error || !data) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center h-[250px] text-destructive">
          Khong the tai Peer Comparison
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Users className="h-5 w-5" />
          Peer Comparison
          <span className="text-sm font-normal text-muted-foreground">
            - {data.icb_name} (ICB: {data.icb_code})
          </span>
          <span className="ml-auto text-primary font-bold">{data.symbol}</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <PeerMetricsTable peers={data.peers} targetSymbol={data.symbol} />
      </CardContent>
    </Card>
  )
}
```

### Step 5: Create FCF Waterfall

**File: `/apps/web/src/components/dashboard/fcf-analysis/fcf-waterfall.tsx`**

```tsx
"use client"

import { cn } from "@/lib/utils"
import type { FCFAnalysisResponse } from "@/lib/api"

interface FCFWaterfallProps {
  data: FCFAnalysisResponse
}

function formatBillions(value: number | null): string {
  if (value === null) return "-"
  const abs = Math.abs(value)
  const sign = value < 0 ? "-" : ""
  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(1)}T`
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(1)}B`
  return `${sign}${(abs / 1e6).toFixed(0)}M`
}

export function FCFWaterfall({ data }: FCFWaterfallProps) {
  const maxValue = Math.max(
    Math.abs(data.net_income || 0),
    Math.abs(data.cfo || 0),
    Math.abs(data.fcf || 0)
  )

  const getWidth = (value: number | null) => {
    if (!value || !maxValue) return 0
    return Math.abs(value) / maxValue * 100
  }

  const items = [
    { label: "Net Income", value: data.net_income, color: "bg-muted-foreground" },
    { label: "CFO", value: data.cfo, color: "bg-[hsl(var(--accent-orange))]" },
    { label: "CapEx", value: data.capex, color: "bg-red-500" },
    { label: "FCF", value: data.fcf, color: "bg-[hsl(var(--accent-orange))]" },
  ]

  return (
    <div className="space-y-4">
      {items.map((item) => (
        <div key={item.label} className="space-y-1">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">{item.label}</span>
            <span className={cn(
              "font-medium tabular-nums",
              (item.value || 0) >= 0 ? "text-green-500" : "text-red-500"
            )}>
              {formatBillions(item.value)}
            </span>
          </div>
          <div className="h-6 bg-muted rounded-full overflow-hidden">
            <div
              className={cn("h-full rounded-full transition-all", item.color)}
              style={{ width: `${getWidth(item.value)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
```

### Step 6: Create CCC Indicator

**File: `/apps/web/src/components/dashboard/fcf-analysis/ccc-indicator.tsx`**

```tsx
import { cn } from "@/lib/utils"

interface CCCIndicatorProps {
  ccc: number | null
  dso: number | null
  dio: number | null
  dpo: number | null
}

export function CCCIndicator({ ccc, dso, dio, dpo }: CCCIndicatorProps) {
  if (ccc === null) {
    return (
      <div className="text-center text-muted-foreground text-sm">
        CCC khong ap dung (ngan hang/tai chinh)
      </div>
    )
  }

  const getCCCColor = (days: number) => {
    // Use orange for good (<=30), yellow for moderate, red for poor
    if (days <= 30) return "text-[hsl(var(--accent-orange))]"
    if (days <= 60) return "text-yellow-500"
    return "text-red-500"
  }

  return (
    <div className="space-y-3">
      <div className="text-center">
        <div className="text-sm text-muted-foreground">Cash Conversion Cycle</div>
        <div className={cn("text-2xl font-bold", getCCCColor(ccc))}>
          {ccc.toFixed(0)} ngay
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div className="p-2 bg-muted/30 rounded">
          <div className="text-muted-foreground">DSO</div>
          <div className="font-medium">{dso?.toFixed(0) || "-"} ngay</div>
        </div>
        <div className="p-2 bg-muted/30 rounded">
          <div className="text-muted-foreground">DIO</div>
          <div className="font-medium">{dio?.toFixed(0) || "-"} ngay</div>
        </div>
        <div className="p-2 bg-muted/30 rounded">
          <div className="text-muted-foreground">DPO</div>
          <div className="font-medium">{dpo?.toFixed(0) || "-"} ngay</div>
        </div>
      </div>
    </div>
  )
}
```

### Step 7: Create FCF Analysis Card

**File: `/apps/web/src/components/dashboard/fcf-analysis/fcf-analysis-card.tsx`**

```tsx
"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Wallet } from "lucide-react"
import { useFCFAnalysis } from "@/hooks/use-fcf-analysis"
import { FCFWaterfall } from "./fcf-waterfall"
import { CCCIndicator } from "./ccc-indicator"

interface FCFAnalysisCardProps {
  symbol: string | null
  className?: string
}

export function FCFAnalysisCard({ symbol, className }: FCFAnalysisCardProps) {
  const { data, isLoading, error } = useFCFAnalysis(symbol)

  if (!symbol) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center h-[350px] text-muted-foreground">
          Chon mot co phieu de xem FCF Analysis
        </CardContent>
      </Card>
    )
  }

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[280px]" />
        </CardContent>
      </Card>
    )
  }

  if (error || !data) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center h-[350px] text-destructive">
          Khong the tai FCF Analysis
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Wallet className="h-5 w-5" />
          FCF Analysis
          <span className="text-sm font-normal text-muted-foreground">- {data.period}</span>
          <span className="ml-auto text-primary font-bold">{data.symbol}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <FCFWaterfall data={data} />

        {/* Metrics Row */}
        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border/50">
          <div className="text-center">
            <div className="text-sm text-muted-foreground">FCF Margin</div>
            <div className="text-xl font-bold text-[hsl(var(--accent-orange))]">
              {data.fcf_margin ? `${(data.fcf_margin * 100).toFixed(1)}%` : "-"}
            </div>
          </div>
          <div className="text-center">
            <div className="text-sm text-muted-foreground">FCF Yield</div>
            <div className="text-xl font-bold text-[hsl(var(--accent-orange))]">
              {data.fcf_yield ? `${(data.fcf_yield * 100).toFixed(2)}%` : "-"}
            </div>
          </div>
        </div>

        {/* CCC */}
        <CCCIndicator
          ccc={data.ccc}
          dso={data.dso}
          dio={data.dio}
          dpo={data.dpo}
        />
      </CardContent>
    </Card>
  )
}
```

### Step 8: Export Components

**File: `/apps/web/src/components/dashboard/index.ts`**

```typescript
// Add exports
export * from "./peer-comparison/peer-comparison-card"
export * from "./peer-comparison/peer-metrics-table"
export * from "./fcf-analysis/fcf-analysis-card"
export * from "./fcf-analysis/fcf-waterfall"
export * from "./fcf-analysis/ccc-indicator"
```

## Todo

- [x] Add API types for `SectorPeersResponse`, `FCFAnalysisResponse`
- [x] Add `fetchSectorPeers()`, `fetchFCFAnalysis()` to api.ts
- [x] Create `useSectorPeers`, `useFCFAnalysis` hooks
- [x] Create `PeerMetricsTable` with heatmap coloring
- [x] Create `PeerComparisonCard` container
- [x] Create `FCFWaterfall` visualization
- [x] Create `CCCIndicator` component
- [x] Create `FCFAnalysisCard` container
- [x] Export from index.ts

## Success Criteria

- [ ] Peer table shows top 5 sector peers
- [ ] Heatmap coloring: Green above avg, Red below
- [ ] FCF waterfall shows Net Income -> CFO -> FCF
- [ ] CCC displays with DSO, DIO, DPO breakdown
- [ ] Handle null CCC for banks gracefully
- [ ] Responsive layout

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| No sector peers found | Low | Medium | Show message, handle empty list |
| CCC null for banks | High | Low | Show "N/A - ngan hang" message |
| Negative values display | Medium | Low | Format with sign, use red color |
