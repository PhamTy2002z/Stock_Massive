# Phase 3: Frontend - Component & Hook

## Overview

| Field | Value |
|-------|-------|
| Priority | P1 |
| Effort | 2h |
| Status | DONE |
| Dependencies | Phase 2 complete |

## Files to Modify/Create

| Action | File |
|--------|------|
| CREATE | `apps/web/src/hooks/use-sector-historical-performance.ts` |
| CREATE | `apps/web/src/components/dashboard/sector-historical-performance.tsx` |
| MODIFY | `apps/web/src/lib/api.ts` |
| MODIFY | `apps/web/src/lib/query-keys.ts` |
| MODIFY | `apps/web/src/components/dashboard/index.ts` |
| MODIFY | `apps/web/src/app/page.tsx` |

## Implementation Steps

### Step 1: Add API Types & Function

**File**: `apps/web/src/lib/api.ts` (MODIFY)

```typescript
// === Sector Historical Performance Types ===

export type SectorHistoricalPeriod = "1W" | "2W" | "1M"

export interface SectorHistoricalItem {
  icb_code: string
  icb_name: string
  change_pct: number
}

export interface SectorHistoricalResponse {
  period: string
  top_gainers: SectorHistoricalItem[]
  top_losers: SectorHistoricalItem[]
  generated_at: string | null
}

export async function fetchSectorHistoricalPerformance(
  period: SectorHistoricalPeriod = "1W"
): Promise<SectorHistoricalResponse> {
  return fetchApi<SectorHistoricalResponse>(
    `/stocks/analytics/sector-historical?period=${period}`
  )
}
```

### Step 2: Add Query Key

**File**: `apps/web/src/lib/query-keys.ts` (MODIFY)

```typescript
import type { SectorHistoricalPeriod } from "./api"

export const queryKeys = {
  // ... existing keys ...

  // Sector Historical Performance
  sectorHistoricalPerformance: (period: SectorHistoricalPeriod) =>
    ["analytics", "sectorHistorical", period] as const,
}
```

### Step 3: Create Hook

**File**: `apps/web/src/hooks/use-sector-historical-performance.ts` (CREATE)

```typescript
"use client"

import { useSuspenseQuery } from "@tanstack/react-query"
import {
  fetchSectorHistoricalPerformance,
  type SectorHistoricalPeriod,
} from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"

export function useSectorHistoricalPerformance(
  period: SectorHistoricalPeriod = "1W"
) {
  const { data, isFetching, refetch } = useSuspenseQuery({
    queryKey: queryKeys.sectorHistoricalPerformance(period),
    queryFn: () => fetchSectorHistoricalPerformance(period),
    staleTime: 5 * 60 * 1000, // 5 minutes (historical data)
    refetchInterval: 10 * 60 * 1000, // 10 minutes
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  })

  return { data, isFetching, refetch }
}
```

### Step 4: Create Component

**File**: `apps/web/src/components/dashboard/sector-historical-performance.tsx` (CREATE)

```tsx
"use client"

import { useState, useMemo, memo } from "react"
import { isEqual } from "lodash-es"
import {
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Cell,
  ReferenceLine,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"
import { useSectorHistoricalPerformance } from "@/hooks/use-sector-historical-performance"
import type { SectorHistoricalPeriod, SectorHistoricalItem } from "@/lib/api"

// Custom tooltip
function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: { name: string; value: number; isGainer: boolean } }>
}) {
  if (!active || !payload?.length) return null
  const data = payload[0].payload

  return (
    <Card className="shadow-lg border-border/50">
      <CardContent className="p-3 space-y-1">
        <p className="font-semibold text-sm">{data.name}</p>
        <div className="flex justify-between gap-4 text-xs">
          <span className="text-muted-foreground">Thay đổi:</span>
          <span
            className={cn(
              "font-medium",
              data.value >= 0 ? "text-green-600" : "text-red-600"
            )}
          >
            {data.value >= 0 ? "+" : ""}
            {data.value.toFixed(2)}%
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

interface ChartProps {
  data: { name: string; value: number; isGainer: boolean }[]
  isPlaceholderData?: boolean
}

const SectorHistoricalChart = memo(
  function SectorHistoricalChart({ data, isPlaceholderData = false }: ChartProps) {
    if (data.length === 0) {
      return (
        <div className="h-[280px] flex items-center justify-center text-muted-foreground">
          Chưa có dữ liệu
        </div>
      )
    }

    return (
      <ResponsiveContainer width="100%" height={280}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: 11 }}
            className="text-muted-foreground"
            tickFormatter={(v) => `${v}%`}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 11 }}
            className="text-muted-foreground"
            width={130}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "hsl(var(--muted) / 0.3)" }} />
          <ReferenceLine x={0} stroke="hsl(var(--muted-foreground))" strokeWidth={1} />
          <Bar
            dataKey="value"
            radius={[0, 4, 4, 0]}
            maxBarSize={20}
            isAnimationActive={!isPlaceholderData}
            animationDuration={300}
          >
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.isGainer ? "hsl(142 71% 45%)" : "hsl(0 84% 60%)"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    )
  },
  (prev, next) => isEqual(prev.data, next.data) && prev.isPlaceholderData === next.isPlaceholderData
)

function PeriodContent({ period }: { period: SectorHistoricalPeriod }) {
  const { data, isFetching } = useSectorHistoricalPerformance(period)

  const chartData = useMemo(() => {
    const gainers = data.top_gainers.map((item) => ({
      name: item.icb_name.length > 18 ? item.icb_name.slice(0, 16) + "..." : item.icb_name,
      value: item.change_pct,
      isGainer: true,
    }))
    const losers = data.top_losers.map((item) => ({
      name: item.icb_name.length > 18 ? item.icb_name.slice(0, 16) + "..." : item.icb_name,
      value: item.change_pct,
      isGainer: false,
    }))
    // Sort all by value descending (gainers at top)
    return [...gainers, ...losers].sort((a, b) => b.value - a.value)
  }, [data])

  return <SectorHistoricalChart data={chartData} isPlaceholderData={isFetching} />
}

export function SectorHistoricalPerformance({ className }: { className?: string }) {
  const [period, setPeriod] = useState<SectorHistoricalPeriod>("1W")

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Hiệu suất ngành theo thời gian</CardTitle>
          <Tabs value={period} onValueChange={(v) => setPeriod(v as SectorHistoricalPeriod)}>
            <TabsList className="h-8">
              <TabsTrigger value="1W" className="text-xs px-3">1 Tuần</TabsTrigger>
              <TabsTrigger value="2W" className="text-xs px-3">2 Tuần</TabsTrigger>
              <TabsTrigger value="1M" className="text-xs px-3">1 Tháng</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>
      </CardHeader>
      <CardContent>
        <PeriodContent period={period} />
      </CardContent>
    </Card>
  )
}

export function SectorHistoricalPerformanceSkeleton({ className }: { className?: string }) {
  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="h-5 w-48 bg-muted animate-pulse rounded" />
          <div className="h-8 w-36 bg-muted animate-pulse rounded" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[280px] bg-muted animate-pulse rounded" />
      </CardContent>
    </Card>
  )
}
```

### Step 5: Export from Index

**File**: `apps/web/src/components/dashboard/index.ts` (MODIFY)

```typescript
export { SectorHistoricalPerformance, SectorHistoricalPerformanceSkeleton } from "./sector-historical-performance"
```

### Step 6: Integrate into Page

**File**: `apps/web/src/app/page.tsx` (MODIFY)

Add import:
```tsx
import {
  MarketIndices,
  SectorPerformanceSection,
  FundCertificates,
  VN30OverviewTable,
  SectorHistoricalPerformance,  // ADD
} from "@/components/dashboard"
```

Add section after VN30OverviewTable:
```tsx
{/* Sector Historical Performance */}
<section>
  <SectorHistoricalPerformance />
</section>
```

## Todo List

- [x] Add types and fetch function to `api.ts`
- [x] Add query key to `query-keys.ts`
- [x] Create `use-sector-historical-performance.ts` hook
- [x] Create `sector-historical-performance.tsx` component
- [x] Export from `dashboard/index.ts`
- [x] Add section to `page.tsx`
- [x] Verify Tabs component from shadcn exists

## Success Criteria

- Component renders horizontal bar chart
- Tabs switch between 1W/2W/1M periods
- Green bars for gainers, red for losers
- Tooltip shows sector name + change %
- Empty state when no data

## Risks

| Risk | Mitigation |
|------|------------|
| Tabs not installed | Run `npx shadcn@latest add tabs` |
| Data not available | Show "Chưa có dữ liệu" message |
| Long sector names | Truncate to 18 chars + "..." |
