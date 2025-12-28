---
phase: 3
title: Frontend - UI Updates
status: pending
estimated_files: 8
---

# Phase 3: Frontend - UI Updates

## Objective

Update the frontend to use the new endpoints and display data with clear limitations messaging.

## Tasks

### 3.1 Add API Types & Functions

**File:** `apps/web/src/lib/api.ts`

```typescript
// Add new types
export interface IntradayOrderStatsResponse {
  symbol: string
  date: string
  buy_orders: number
  sell_orders: number
  buy_volume: number
  sell_volume: number
  net_volume: number
  ato_volume: number
  atc_volume: number
  last_updated: string
}

export interface ForeignSnapshotResponse {
  symbol: string
  foreign_volume: number
  foreign_room: number
  ownership_ratio: number | null
  total_volume: number
  avg_volume_2w: number | null
  foreign_pct_of_volume: number | null
  last_updated: string
}

// Add new fetch functions
export async function fetchIntradayOrderStats(symbol: string): Promise<IntradayOrderStatsResponse> {
  return fetchApi<IntradayOrderStatsResponse>(`/stocks/${encodeURIComponent(symbol)}/intraday-order-stats`)
}

export async function fetchForeignSnapshot(symbol: string): Promise<ForeignSnapshotResponse> {
  return fetchApi<ForeignSnapshotResponse>(`/stocks/${encodeURIComponent(symbol)}/foreign-snapshot`)
}
```

### 3.2 Create New Hooks

**File:** `apps/web/src/hooks/use-intraday-order-stats.ts`

```typescript
import { useQuery } from "@tanstack/react-query"
import { fetchIntradayOrderStats } from "@/lib/api"

export function useIntradayOrderStats(symbol: string) {
  return useQuery({
    queryKey: ["intradayOrderStats", symbol],
    queryFn: () => fetchIntradayOrderStats(symbol),
    enabled: !!symbol,
    staleTime: 60_000, // 1 minute - short for real-time data
    refetchInterval: 120_000, // Auto-refresh every 2 min
  })
}
```

**File:** `apps/web/src/hooks/use-foreign-snapshot.ts`

```typescript
import { useQuery } from "@tanstack/react-query"
import { fetchForeignSnapshot } from "@/lib/api"

export function useForeignSnapshot(symbol: string) {
  return useQuery({
    queryKey: ["foreignSnapshot", symbol],
    queryFn: () => fetchForeignSnapshot(symbol),
    enabled: !!symbol,
    staleTime: 60_000,
    refetchInterval: 120_000,
  })
}
```

### 3.3 Create Intraday Order Stats Widget

**File:** `apps/web/src/components/dashboard/advanced-tab/widgets/intraday-order-stats.tsx`

```tsx
"use client"

import { Skeleton } from "@/components/ui/skeleton"
import type { IntradayOrderStatsResponse } from "@/lib/api"
import { TrendingUp, TrendingDown } from "lucide-react"

interface IntradayOrderStatsProps {
  data: IntradayOrderStatsResponse | undefined
  isLoading: boolean
}

function formatNumber(value: number): string {
  return value.toLocaleString("vi-VN")
}

function formatVolume(value: number): string {
  if (value >= 1000000) return `${(value / 1000000).toFixed(2)}M`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
  return value.toLocaleString("vi-VN")
}

export function IntradayOrderStats({ data, isLoading }: IntradayOrderStatsProps) {
  if (isLoading) return <IntradayOrderStatsSkeleton />

  if (!data) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <p className="text-sm">Dữ liệu intraday chưa khả dụng</p>
        <p className="text-xs mt-1 opacity-70">Chỉ có trong giờ giao dịch</p>
      </div>
    )
  }

  const netVolume = data.buy_volume - data.sell_volume
  const buyPct = data.buy_volume + data.sell_volume > 0
    ? (data.buy_volume / (data.buy_volume + data.sell_volume)) * 100
    : 50

  return (
    <div className="space-y-4">
      {/* Buy vs Sell Volume Bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>Mua ({buyPct.toFixed(1)}%)</span>
          <span>Bán ({(100 - buyPct).toFixed(1)}%)</span>
        </div>
        <div className="h-3 rounded-full overflow-hidden flex bg-muted/50">
          <div
            className="bg-green-500 transition-all duration-300"
            style={{ width: `${buyPct}%` }}
          />
          <div
            className="bg-red-500 transition-all duration-300"
            style={{ width: `${100 - buyPct}%` }}
          />
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4">
        <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="h-4 w-4 text-green-600" />
            <span className="text-xs font-medium text-green-600">Mua</span>
          </div>
          <p className="text-lg font-bold text-green-600">{formatNumber(data.buy_orders)}</p>
          <p className="text-xs text-muted-foreground">lệnh • {formatVolume(data.buy_volume)} CP</p>
        </div>

        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown className="h-4 w-4 text-red-600" />
            <span className="text-xs font-medium text-red-600">Bán</span>
          </div>
          <p className="text-lg font-bold text-red-600">{formatNumber(data.sell_orders)}</p>
          <p className="text-xs text-muted-foreground">lệnh • {formatVolume(data.sell_volume)} CP</p>
        </div>
      </div>

      {/* Net Volume */}
      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
        <div className="flex justify-between items-center">
          <span className="text-sm text-muted-foreground">KL Ròng</span>
          <span className={`text-lg font-bold ${netVolume >= 0 ? "text-green-600" : "text-red-600"}`}>
            {netVolume > 0 ? "+" : ""}{formatVolume(netVolume)}
          </span>
        </div>
      </div>

      {/* ATO/ATC */}
      <div className="grid grid-cols-2 gap-4 text-center">
        <div className="p-2 rounded bg-muted/20">
          <p className="text-xs text-muted-foreground">ATO</p>
          <p className="text-sm font-medium">{formatVolume(data.ato_volume)}</p>
        </div>
        <div className="p-2 rounded bg-muted/20">
          <p className="text-xs text-muted-foreground">ATC</p>
          <p className="text-sm font-medium">{formatVolume(data.atc_volume)}</p>
        </div>
      </div>
    </div>
  )
}

function IntradayOrderStatsSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-3 w-full rounded-full" />
      <div className="grid grid-cols-2 gap-4">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
      <Skeleton className="h-12" />
    </div>
  )
}
```

### 3.4 Create Foreign Snapshot Card

**File:** `apps/web/src/components/dashboard/advanced-tab/widgets/foreign-snapshot-card.tsx`

```tsx
"use client"

import { Skeleton } from "@/components/ui/skeleton"
import type { ForeignSnapshotResponse } from "@/lib/api"
import { Globe, TrendingUp, Users } from "lucide-react"

interface ForeignSnapshotCardProps {
  data: ForeignSnapshotResponse | undefined
  isLoading: boolean
}

function formatVolume(value: number): string {
  if (value >= 1000000000) return `${(value / 1000000000).toFixed(2)} tỷ`
  if (value >= 1000000) return `${(value / 1000000).toFixed(2)}M`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
  return value.toLocaleString("vi-VN")
}

function formatPct(value: number | null): string {
  if (value === null) return "N/A"
  return `${(value * 100).toFixed(2)}%`
}

export function ForeignSnapshotCard({ data, isLoading }: ForeignSnapshotCardProps) {
  if (isLoading) return <ForeignSnapshotCardSkeleton />

  if (!data) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <p className="text-sm">Dữ liệu NĐTNN chưa khả dụng</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Main Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20 text-center">
          <Globe className="h-5 w-5 mx-auto mb-2 text-blue-600" />
          <p className="text-xs text-muted-foreground mb-1">KL Nước Ngoài</p>
          <p className="text-lg font-bold text-blue-600">{formatVolume(data.foreign_volume)}</p>
        </div>

        <div className="p-4 rounded-lg bg-purple-500/10 border border-purple-500/20 text-center">
          <Users className="h-5 w-5 mx-auto mb-2 text-purple-600" />
          <p className="text-xs text-muted-foreground mb-1">Tỷ lệ sở hữu</p>
          <p className="text-lg font-bold text-purple-600">{formatPct(data.ownership_ratio)}</p>
        </div>

        <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/20 text-center">
          <TrendingUp className="h-5 w-5 mx-auto mb-2 text-green-600" />
          <p className="text-xs text-muted-foreground mb-1">% KL Giao dịch</p>
          <p className="text-lg font-bold text-green-600">
            {data.foreign_pct_of_volume?.toFixed(1) ?? "N/A"}%
          </p>
        </div>
      </div>

      {/* Additional Info */}
      <div className="p-3 rounded-lg bg-muted/30 border border-border/50 space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Room còn lại</span>
          <span className="font-medium">{formatVolume(data.foreign_room)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Tổng KL phiên</span>
          <span className="font-medium">{formatVolume(data.total_volume)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Trung bình 2 tuần</span>
          <span className="font-medium">{data.avg_volume_2w ? formatVolume(data.avg_volume_2w) : "N/A"}</span>
        </div>
      </div>

      {/* Timestamp */}
      <p className="text-xs text-center text-muted-foreground">
        Cập nhật: {new Date(data.last_updated).toLocaleTimeString("vi-VN")}
      </p>
    </div>
  )
}

function ForeignSnapshotCardSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-24" />
    </div>
  )
}
```

### 3.5 Update Order Flow Subtab

**File:** `apps/web/src/components/dashboard/advanced-tab/order-flow-subtab.tsx`

Replace the historical OrderStatsTable with IntradayOrderStats:

```tsx
"use client"

import { useIntradayOrderStats } from "@/hooks/use-intraday-order-stats"
import { usePriceDepth } from "@/hooks/use-price-depth"
import { IntradayOrderStats } from "./widgets/intraday-order-stats"
import { PriceDepthWidget } from "./widgets/price-depth-widget"
import { RefreshCw, Clock } from "lucide-react"
import { Button } from "@/components/ui/button"

interface OrderFlowSubtabProps {
  symbol: string
}

export default function OrderFlowSubtab({ symbol }: OrderFlowSubtabProps) {
  const orderStats = useIntradayOrderStats(symbol)
  const priceDepth = usePriceDepth(symbol)

  const handleRefresh = () => {
    orderStats.refetch()
    priceDepth.refetch()
  }

  const isLoading = orderStats.isLoading || priceDepth.isLoading
  const hasError = orderStats.error || priceDepth.error

  return (
    <div className="space-y-6">
      {/* Header with Refresh */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-medium text-muted-foreground">
            Dữ liệu hôm nay (real-time)
          </h3>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRefresh}
          disabled={isLoading}
          className="h-8"
        >
          <RefreshCw className={`h-4 w-4 mr-1 ${isLoading ? "animate-spin" : ""}`} />
          Làm mới
        </Button>
      </div>

      {hasError && (
        <div className="p-4 rounded-lg bg-destructive/10 text-destructive text-sm">
          Có lỗi khi tải dữ liệu. Vui lòng thử lại.
        </div>
      )}

      {/* Price Depth - Real-time */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <h4 className="text-base font-semibold">Price Depth</h4>
          <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/20 text-green-600 dark:text-green-400">
            Real-time
          </span>
        </div>
        <PriceDepthWidget data={priceDepth.data} isLoading={priceDepth.isLoading} />
      </section>

      {/* Intraday Order Stats - Today only */}
      <section>
        <div className="flex items-center gap-2 mb-4">
          <h4 className="text-base font-semibold">Order Stats</h4>
          <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-600 dark:text-amber-400">
            Hôm nay
          </span>
        </div>
        <IntradayOrderStats data={orderStats.data} isLoading={orderStats.isLoading} />
      </section>
    </div>
  )
}
```

### 3.6 Update Money Flow Subtab

**File:** `apps/web/src/components/dashboard/advanced-tab/money-flow-subtab.tsx`

Replace charts with snapshot view:

```tsx
"use client"

import { useForeignSnapshot } from "@/hooks/use-foreign-snapshot"
import { ForeignSnapshotCard } from "./widgets/foreign-snapshot-card"
import { RefreshCw, Info } from "lucide-react"
import { Button } from "@/components/ui/button"

interface MoneyFlowSubtabProps {
  symbol: string
}

export default function MoneyFlowSubtab({ symbol }: MoneyFlowSubtabProps) {
  const foreign = useForeignSnapshot(symbol)

  const handleRefresh = () => {
    foreign.refetch()
  }

  return (
    <div className="space-y-6">
      {/* Header with Refresh */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">
          Thông tin dòng tiền hiện tại
        </h3>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRefresh}
          disabled={foreign.isLoading}
          className="h-8"
        >
          <RefreshCw className={`h-4 w-4 mr-1 ${foreign.isLoading ? "animate-spin" : ""}`} />
          Làm mới
        </Button>
      </div>

      {foreign.error && (
        <div className="p-4 rounded-lg bg-destructive/10 text-destructive text-sm">
          Có lỗi khi tải dữ liệu. Vui lòng thử lại.
        </div>
      )}

      {/* Foreign Trading Snapshot */}
      <section className="rounded-lg border border-border/50 bg-card/50 p-4">
        <div className="flex items-center gap-2 mb-4">
          <h4 className="text-base font-semibold">Giao Dịch Nước Ngoài</h4>
          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-600 dark:text-blue-400">
            Snapshot
          </span>
        </div>
        <ForeignSnapshotCard data={foreign.data} isLoading={foreign.isLoading} />
      </section>

      {/* Info about limitations */}
      <div className="flex items-start gap-3 p-4 rounded-lg bg-muted/30 border border-border/50">
        <Info className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
        <div className="text-sm text-muted-foreground">
          <p className="font-medium mb-1">Giới hạn dữ liệu</p>
          <ul className="list-disc list-inside space-y-1 text-xs">
            <li>Dữ liệu NĐTNN chỉ là snapshot hiện tại (không có lịch sử)</li>
            <li>Dữ liệu giao dịch tự doanh hiện không khả dụng qua API</li>
            <li>Dữ liệu sẽ được cập nhật định kỳ trong giờ giao dịch</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
```

## Verification

1. Navigate to Advanced tab → Order Flow subtab
   - Should show real-time buy/sell stats
   - Should show "Hôm nay" badge
   - Price Depth should still work

2. Navigate to Advanced tab → Money Flow subtab
   - Should show foreign snapshot card
   - Should show limitations info box
   - No more empty charts

## Dependencies

- Phase 1 & 2 backend endpoints must be deployed first
- Existing TanStack Query setup

## Notes

- Removed Prop Trading section entirely (no data available)
- Clear messaging about data limitations
- Short refresh intervals for real-time feel
