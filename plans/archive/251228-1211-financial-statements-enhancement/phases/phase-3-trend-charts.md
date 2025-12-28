# Phase 3: Trend Charts

## Context

- **Plan**: [plan.md](../plan.md)
- **Phase 1**: [Backend APIs](phase-1-backend-apis.md) (prerequisite)
- **Research**: [researcher-01-recharts-financial-viz.md](../research/researcher-01-recharts-financial-viz.md)

## Overview

Create 4 trend analysis charts showing 8 quarters of historical data:
1. Revenue & Profit (ComposedChart: Bar + Line)
2. Margins (AreaChart: Gross%, Net%)
3. ROE/ROA (LineChart)
4. Cash Flow (StackedBar: CFO, CFI, CFF)

## Key Insights

- ComposedChart combines multiple chart types (Bar + Line) for revenue/profit
- AreaChart with gradient fill for margin visualization
- StackedBar for cash flow breakdown (CFO positive, CFI/CFF typically negative)
- Use `ResponsiveContainer` with explicit height
- Format Y-axis with M/B suffixes for large numbers
- **Color per Design Guidelines:**
  - Use `--accent-orange` for primary data series
  - Use muted colors for secondary series
  - Green/Red only for stock up/down indicators
- **KPI Requirements (MANDATORY):**
  - Show time range in card header
  - Show Last Updated timestamp with Refresh button

## Requirements

### Visual Design

```
┌─────────────────────────────────────────────────────────────┐
│  Trend Analysis                                      VNM    │
├─────────────────────────────────────────────────────────────┤
│  [Revenue & Profit] [Margins] [ROE/ROA] [Cash Flow]         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │     ▓▓▓  ▓▓▓  ▓▓▓  ▓▓▓  ▓▓▓  ▓▓▓  ▓▓▓  ▓▓▓       │   │
│  │  ▓▓▓▓▓ ▓▓▓▓▓ ▓▓▓▓▓ ▓▓▓▓▓ ▓▓▓▓▓ ▓▓▓▓▓ ▓▓▓▓▓ ▓▓▓▓▓   │   │
│  │  █████ █████ █████ █████ █████ █████ █████ █████   │   │
│  │  ─────●─────●─────●─────●─────●─────●─────●─────● │   │
│  │   Q1   Q2   Q3   Q4   Q1   Q2   Q3   Q4         │   │
│  │        2023              2024                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Legend: ███ Revenue  ▓▓▓ Gross Profit  ─●─ Net Profit     │
└─────────────────────────────────────────────────────────────┘
```

### Tab Structure

| Tab | Chart Type | Data Series |
|-----|------------|-------------|
| Revenue & Profit | ComposedChart | revenue (Bar), gross_profit (Bar), net_profit (Line) |
| Margins | AreaChart | gross_margin, operating_margin, net_margin |
| ROE/ROA | LineChart | roe, roa |
| Cash Flow | StackedBar | cfo, cfi, cff |

## Architecture

```
apps/web/src/components/dashboard/
├── financial-trends/
│   ├── trend-charts-card.tsx         # Main container with tabs
│   ├── revenue-profit-chart.tsx      # ComposedChart
│   ├── margin-trend-chart.tsx        # AreaChart
│   ├── roe-roa-chart.tsx             # LineChart
│   └── cash-flow-chart.tsx           # StackedBar
└── index.ts                          # Export
```

## Related Files

| File | Action |
|------|--------|
| `/apps/web/src/components/dashboard/financial-trends/trend-charts-card.tsx` | **NEW** |
| `/apps/web/src/components/dashboard/financial-trends/revenue-profit-chart.tsx` | **NEW** |
| `/apps/web/src/components/dashboard/financial-trends/margin-trend-chart.tsx` | **NEW** |
| `/apps/web/src/components/dashboard/financial-trends/roe-roa-chart.tsx` | **NEW** |
| `/apps/web/src/components/dashboard/financial-trends/cash-flow-chart.tsx` | **NEW** |
| `/apps/web/src/hooks/use-trend-metrics.ts` | **NEW** |
| `/apps/web/src/lib/api.ts` | Add `fetchTrendMetrics()` |

## Implementation Steps

### Step 1: Add API Types and Client

**File: `/apps/web/src/lib/api.ts`**

```typescript
export interface TrendMetricsResponse {
  symbol: string
  periods: string[]
  revenue: (number | null)[]
  net_profit: (number | null)[]
  gross_margin: (number | null)[]
  net_margin: (number | null)[]
  roe: (number | null)[]
  roa: (number | null)[]
  cfo: (number | null)[]
  cfi: (number | null)[]
  cff: (number | null)[]
}

export async function fetchTrendMetrics(
  symbol: string,
  periods: number = 8
): Promise<TrendMetricsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/stocks/${symbol}/trend-metrics?periods=${periods}`
  )
  if (!response.ok) throw new Error("Failed to fetch trend metrics")
  return response.json()
}
```

### Step 2: Create TanStack Query Hook

**File: `/apps/web/src/hooks/use-trend-metrics.ts`**

```typescript
import { useQuery } from "@tanstack/react-query"
import { fetchTrendMetrics, type TrendMetricsResponse } from "@/lib/api"

export function useTrendMetrics(symbol: string | null, periods: number = 8) {
  return useQuery<TrendMetricsResponse>({
    queryKey: ["trend-metrics", symbol, periods],
    queryFn: () => fetchTrendMetrics(symbol!, periods),
    enabled: !!symbol,
    staleTime: 1000 * 60 * 5,
  })
}
```

### Step 3: Create Revenue & Profit Chart

**File: `/apps/web/src/components/dashboard/financial-trends/revenue-profit-chart.tsx`**

```tsx
"use client"

import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"
import type { TrendMetricsResponse } from "@/lib/api"

interface RevenueProfitChartProps {
  data: TrendMetricsResponse
}

function formatBillions(value: number): string {
  if (value >= 1e12) return `${(value / 1e12).toFixed(1)}T`
  if (value >= 1e9) return `${(value / 1e9).toFixed(1)}B`
  if (value >= 1e6) return `${(value / 1e6).toFixed(1)}M`
  return value.toString()
}

export function RevenueProfitChart({ data }: RevenueProfitChartProps) {
  const chartData = data.periods.map((period, i) => ({
    period,
    revenue: data.revenue[i],
    net_profit: data.net_profit[i],
  }))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="period"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <YAxis
          yAxisId="left"
          tickFormatter={formatBillions}
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <YAxis
          yAxisId="right"
          orientation="right"
          tickFormatter={formatBillions}
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
          }}
          formatter={(value: number, name: string) => [
            formatBillions(value),
            name === "revenue" ? "Doanh thu" : "Loi nhuan rong",
          ]}
        />
        <Legend
          formatter={(value) =>
            value === "revenue" ? "Doanh thu" : "Loi nhuan rong"
          }
        />
        <Bar
          yAxisId="left"
          dataKey="revenue"
          fill="hsl(var(--accent-orange))"
          radius={[4, 4, 0, 0]}
        />
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="net_profit"
          stroke="hsl(var(--muted-foreground))"
          strokeWidth={2}
          dot={{ fill: "hsl(var(--muted-foreground))", strokeWidth: 2 }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
```

### Step 4: Create Margin Trend Chart

**File: `/apps/web/src/components/dashboard/financial-trends/margin-trend-chart.tsx`**

```tsx
"use client"

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts"
import type { TrendMetricsResponse } from "@/lib/api"

interface MarginTrendChartProps {
  data: TrendMetricsResponse
}

export function MarginTrendChart({ data }: MarginTrendChartProps) {
  const chartData = data.periods.map((period, i) => ({
    period,
    gross_margin: data.gross_margin[i] ? data.gross_margin[i]! * 100 : null,
    net_margin: data.net_margin[i] ? data.net_margin[i]! * 100 : null,
  }))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
        <defs>
          <linearGradient id="grossMarginGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="hsl(var(--accent-orange))" stopOpacity={0.3} />
            <stop offset="95%" stopColor="hsl(var(--accent-orange))" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="netMarginGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="hsl(var(--muted-foreground))" stopOpacity={0.3} />
            <stop offset="95%" stopColor="hsl(var(--muted-foreground))" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="period"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <YAxis
          tickFormatter={(v) => `${v}%`}
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
          }}
          formatter={(value: number, name: string) => [
            `${value?.toFixed(1)}%`,
            name === "gross_margin" ? "Bien LN gop" : "Bien LN rong",
          ]}
        />
        <Legend
          formatter={(value) =>
            value === "gross_margin" ? "Bien LN gop" : "Bien LN rong"
          }
        />
        <Area
          type="monotone"
          dataKey="gross_margin"
          stroke="hsl(var(--accent-orange))"
          fill="url(#grossMarginGradient)"
          strokeWidth={2}
        />
        <Area
          type="monotone"
          dataKey="net_margin"
          stroke="hsl(var(--muted-foreground))"
          fill="url(#netMarginGradient)"
          strokeWidth={2}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
```

### Step 5: Create ROE/ROA Chart

**File: `/apps/web/src/components/dashboard/financial-trends/roe-roa-chart.tsx`**

```tsx
"use client"

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts"
import type { TrendMetricsResponse } from "@/lib/api"

interface RoeRoaChartProps {
  data: TrendMetricsResponse
}

export function RoeRoaChart({ data }: RoeRoaChartProps) {
  const chartData = data.periods.map((period, i) => ({
    period,
    roe: data.roe[i] ? data.roe[i]! * 100 : null,
    roa: data.roa[i] ? data.roa[i]! * 100 : null,
  }))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="period"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <YAxis
          tickFormatter={(v) => `${v}%`}
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
          }}
          formatter={(value: number) => [`${value?.toFixed(1)}%`]}
        />
        <Legend />
        <ReferenceLine
          y={15}
          stroke="hsl(var(--muted-foreground))"
          strokeDasharray="3 3"
          label={{ value: "Benchmark 15%", position: "right", fontSize: 10 }}
        />
        <Line
          type="monotone"
          dataKey="roe"
          name="ROE"
          stroke="hsl(var(--accent-orange))"
          strokeWidth={2}
          dot={{ fill: "hsl(var(--accent-orange))", strokeWidth: 2 }}
        />
        <Line
          type="monotone"
          dataKey="roa"
          name="ROA"
          stroke="hsl(var(--muted-foreground))"
          strokeWidth={2}
          dot={{ fill: "hsl(var(--muted-foreground))", strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
```

### Step 6: Create Cash Flow Chart

**File: `/apps/web/src/components/dashboard/financial-trends/cash-flow-chart.tsx`**

```tsx
"use client"

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts"
import type { TrendMetricsResponse } from "@/lib/api"

interface CashFlowChartProps {
  data: TrendMetricsResponse
}

function formatBillions(value: number): string {
  if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(1)}T`
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(1)}B`
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`
  return value.toString()
}

export function CashFlowChart({ data }: CashFlowChartProps) {
  const chartData = data.periods.map((period, i) => ({
    period,
    cfo: data.cfo[i],
    cfi: data.cfi[i],
    cff: data.cff[i],
  }))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="period"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <YAxis
          tickFormatter={formatBillions}
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
          }}
          formatter={(value: number, name: string) => {
            const labels: Record<string, string> = {
              cfo: "Hoat dong KD",
              cfi: "Hoat dong DT",
              cff: "Hoat dong TC",
            }
            return [formatBillions(value), labels[name] || name]
          }}
        />
        <Legend
          formatter={(value) => {
            const labels: Record<string, string> = {
              cfo: "Hoat dong KD",
              cfi: "Hoat dong DT",
              cff: "Hoat dong TC",
            }
            return labels[value] || value
          }}
        />
        <ReferenceLine y={0} stroke="hsl(var(--foreground))" />
        {/* Use orange accent for primary (CFO), muted for others */}
        <Bar dataKey="cfo" stackId="a" fill="hsl(var(--accent-orange))" radius={[4, 4, 0, 0]} />
        <Bar dataKey="cfi" stackId="b" fill="hsl(var(--muted-foreground))" radius={[4, 4, 0, 0]} />
        <Bar dataKey="cff" stackId="c" fill="hsl(var(--border))" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
```

### Step 7: Create Main Container with Tabs

**File: `/apps/web/src/components/dashboard/financial-trends/trend-charts-card.tsx`**

```tsx
"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Skeleton } from "@/components/ui/skeleton"
import { TrendingUp, BarChart3, LineChart, Wallet } from "lucide-react"
import { useTrendMetrics } from "@/hooks/use-trend-metrics"
import { RevenueProfitChart } from "./revenue-profit-chart"
import { MarginTrendChart } from "./margin-trend-chart"
import { RoeRoaChart } from "./roe-roa-chart"
import { CashFlowChart } from "./cash-flow-chart"

interface TrendChartsCardProps {
  symbol: string | null
  className?: string
}

export function TrendChartsCard({ symbol, className }: TrendChartsCardProps) {
  const { data, isLoading, error } = useTrendMetrics(symbol)

  if (!symbol) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center h-[400px] text-muted-foreground">
          Chon mot co phieu de xem Trend Charts
        </CardContent>
      </Card>
    )
  }

  if (isLoading) {
    return <TrendChartsCardSkeleton className={className} />
  }

  if (error || !data) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center h-[400px] text-destructive">
          Khong the tai Trend Metrics
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-lg">
          <TrendingUp className="h-5 w-5" />
          Trend Analysis
          <span className="ml-auto text-primary font-bold">{data.symbol}</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="revenue" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="revenue" className="text-xs">
              <BarChart3 className="h-4 w-4 mr-1" />
              Doanh thu
            </TabsTrigger>
            <TabsTrigger value="margin" className="text-xs">
              <LineChart className="h-4 w-4 mr-1" />
              Bien LN
            </TabsTrigger>
            <TabsTrigger value="roe" className="text-xs">
              <TrendingUp className="h-4 w-4 mr-1" />
              ROE/ROA
            </TabsTrigger>
            <TabsTrigger value="cashflow" className="text-xs">
              <Wallet className="h-4 w-4 mr-1" />
              Dong tien
            </TabsTrigger>
          </TabsList>

          <TabsContent value="revenue" className="mt-4">
            <RevenueProfitChart data={data} />
          </TabsContent>

          <TabsContent value="margin" className="mt-4">
            <MarginTrendChart data={data} />
          </TabsContent>

          <TabsContent value="roe" className="mt-4">
            <RoeRoaChart data={data} />
          </TabsContent>

          <TabsContent value="cashflow" className="mt-4">
            <CashFlowChart data={data} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

function TrendChartsCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={className}>
      <CardHeader>
        <Skeleton className="h-6 w-48" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-10 w-full mb-4" />
        <Skeleton className="h-[300px] w-full" />
      </CardContent>
    </Card>
  )
}
```

### Step 8: Export Components

**File: `/apps/web/src/components/dashboard/index.ts`**

```typescript
// Add exports
export * from "./financial-trends/trend-charts-card"
export * from "./financial-trends/revenue-profit-chart"
export * from "./financial-trends/margin-trend-chart"
export * from "./financial-trends/roe-roa-chart"
export * from "./financial-trends/cash-flow-chart"
```

## Todo

- [x] Add API types and `fetchTrendMetrics()` to api.ts
- [x] Create `useTrendMetrics` hook
- [x] Create `RevenueProfitChart` component
- [x] Create `MarginTrendChart` component
- [x] Create `RoeRoaChart` component
- [x] Create `CashFlowChart` component
- [x] Create `TrendChartsCard` container with tabs
- [x] Add skeleton loading states
- [x] Export from index.ts

## Success Criteria

- [x] All 4 chart types render correctly
- [x] 8 quarters of data displayed
- [x] Y-axis formatted with M/B suffixes
- [x] Tooltips show formatted values
- [x] Charts responsive on mobile
- [x] Smooth tab switching

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Missing data points | Medium | Low | Handle null values gracefully |
| Chart performance | Low | Medium | Limit to 8 periods, disable animations |
| SSR issues | Low | Medium | "use client" directive |
