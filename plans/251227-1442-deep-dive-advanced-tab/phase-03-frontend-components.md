# Phase 3: Frontend Components

## Context
Create Advanced tab container với 3 nested sub-tabs và 8 widget components.

## Overview
Build Advanced tab UI with Order Flow, Technical, Money Flow sub-tabs. Lazy load each sub-tab.

## Requirements
- R1: Advanced tab container với nested tabs
- R2: 3 sub-tab components (lazy loaded)
- R3: 8 widget components (tables, charts, cards)
- R4: Skeleton loading states
- R5: Error handling with retry
- R6: Responsive design (mobile-first)

## Architecture
```
components/dashboard/advanced-tab/
├── index.tsx                    # Main container
├── order-flow-subtab.tsx        # Sub-tab 1
├── technical-subtab.tsx         # Sub-tab 2
├── money-flow-subtab.tsx        # Sub-tab 3
├── widgets/
│   ├── order-stats-table.tsx    # Order stats 30D
│   ├── price-depth-widget.tsx   # Bid/ask levels
│   ├── ratio-summary-card.tsx   # P/E, P/B, ROE
│   ├── trading-stats-card.tsx   # Volume metrics
│   ├── foreign-flow-chart.tsx   # Foreign net flow
│   └── prop-flow-chart.tsx      # Prop trading chart
└── skeletons/
    ├── order-stats-skeleton.tsx
    └── chart-skeleton.tsx
```

## Related Files
| File | Action | Description |
|------|--------|-------------|
| `apps/web/src/components/dashboard/advanced-tab/index.tsx` | CREATE | Main container |
| `apps/web/src/components/dashboard/advanced-tab/order-flow-subtab.tsx` | CREATE | Order Flow tab |
| `apps/web/src/components/dashboard/advanced-tab/technical-subtab.tsx` | CREATE | Technical tab |
| `apps/web/src/components/dashboard/advanced-tab/money-flow-subtab.tsx` | CREATE | Money Flow tab |
| `apps/web/src/components/dashboard/advanced-tab/widgets/order-stats-table.tsx` | CREATE | Stats table |
| `apps/web/src/components/dashboard/advanced-tab/widgets/price-depth-widget.tsx` | CREATE | Depth widget |
| `apps/web/src/components/dashboard/advanced-tab/widgets/ratio-summary-card.tsx` | CREATE | Ratio card |
| `apps/web/src/components/dashboard/advanced-tab/widgets/trading-stats-card.tsx` | CREATE | Stats card |
| `apps/web/src/components/dashboard/advanced-tab/widgets/foreign-flow-chart.tsx` | CREATE | Foreign chart |
| `apps/web/src/components/dashboard/advanced-tab/widgets/prop-flow-chart.tsx` | CREATE | Prop chart |
| `apps/web/src/components/dashboard/stock-detail-tabs.tsx` | EDIT | Add Advanced tab |

## Implementation Steps

### Step 3.1: Create Main Container
```tsx
// advanced-tab/index.tsx
"use client"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { lazy, Suspense } from "react"
import { Skeleton } from "@/components/ui/skeleton"

const OrderFlowSubtab = lazy(() => import("./order-flow-subtab"))
const TechnicalSubtab = lazy(() => import("./technical-subtab"))
const MoneyFlowSubtab = lazy(() => import("./money-flow-subtab"))

interface Props {
  symbol: string
}

export function AdvancedTab({ symbol }: Props) {
  return (
    <Tabs defaultValue="order-flow" className="w-full">
      <TabsList className="grid w-full grid-cols-3">
        <TabsTrigger value="order-flow">Order Flow</TabsTrigger>
        <TabsTrigger value="technical">Technical</TabsTrigger>
        <TabsTrigger value="money-flow">Money Flow</TabsTrigger>
      </TabsList>
      <TabsContent value="order-flow">
        <Suspense fallback={<SubtabSkeleton />}>
          <OrderFlowSubtab symbol={symbol} />
        </Suspense>
      </TabsContent>
      <TabsContent value="technical">
        <Suspense fallback={<SubtabSkeleton />}>
          <TechnicalSubtab symbol={symbol} />
        </Suspense>
      </TabsContent>
      <TabsContent value="money-flow">
        <Suspense fallback={<SubtabSkeleton />}>
          <MoneyFlowSubtab symbol={symbol} />
        </Suspense>
      </TabsContent>
    </Tabs>
  )
}
```

### Step 3.2: Order Flow Sub-tab
```tsx
// order-flow-subtab.tsx
"use client"

import { useOrderStats } from "@/hooks/use-order-stats"
import { usePriceDepth } from "@/hooks/use-price-depth"
import { OrderStatsTable } from "./widgets/order-stats-table"
import { PriceDepthWidget } from "./widgets/price-depth-widget"

export default function OrderFlowSubtab({ symbol }: { symbol: string }) {
  const orderStats = useOrderStats(symbol)
  const priceDepth = usePriceDepth(symbol)

  return (
    <div className="space-y-6">
      <section>
        <h3 className="text-lg font-semibold mb-4">Order Stats (30D)</h3>
        <OrderStatsTable data={orderStats.data} isLoading={orderStats.isLoading} />
      </section>
      <section>
        <h3 className="text-lg font-semibold mb-4">Price Depth</h3>
        <PriceDepthWidget data={priceDepth.data} isLoading={priceDepth.isLoading} />
      </section>
    </div>
  )
}
```

### Step 3.3: Technical Sub-tab
```tsx
// technical-subtab.tsx
"use client"

import { useRatioSummary } from "@/hooks/use-ratio-summary"
import { useTradingStats } from "@/hooks/use-trading-stats"
import { RatioSummaryCard } from "./widgets/ratio-summary-card"
import { TradingStatsCard } from "./widgets/trading-stats-card"

export default function TechnicalSubtab({ symbol }: { symbol: string }) {
  const ratios = useRatioSummary(symbol)
  const stats = useTradingStats(symbol)

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <RatioSummaryCard data={ratios.data} isLoading={ratios.isLoading} />
      <TradingStatsCard data={stats.data} isLoading={stats.isLoading} />
    </div>
  )
}
```

### Step 3.4: Money Flow Sub-tab
```tsx
// money-flow-subtab.tsx
"use client"

import { useForeignTrading } from "@/hooks/use-foreign-trading"
import { usePropTrading } from "@/hooks/use-prop-trading"
import { ForeignFlowChart } from "./widgets/foreign-flow-chart"
import { PropFlowChart } from "./widgets/prop-flow-chart"

export default function MoneyFlowSubtab({ symbol }: { symbol: string }) {
  const foreign = useForeignTrading(symbol)
  const prop = usePropTrading(symbol)

  return (
    <div className="space-y-6">
      <section>
        <h3 className="text-lg font-semibold mb-4">Foreign Trading (30D)</h3>
        <ForeignFlowChart data={foreign.data} isLoading={foreign.isLoading} />
      </section>
      <section>
        <h3 className="text-lg font-semibold mb-4">Prop Trading (30D)</h3>
        <PropFlowChart data={prop.data} isLoading={prop.isLoading} />
      </section>
    </div>
  )
}
```

### Step 3.5: Widget Components

```tsx
// widgets/order-stats-table.tsx
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

export function OrderStatsTable({ data, isLoading }) {
  if (isLoading) return <TableSkeleton rows={10} />
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Date</TableHead>
          <TableHead className="text-right">Buy Orders</TableHead>
          <TableHead className="text-right">Sell Orders</TableHead>
          <TableHead className="text-right">Buy Vol</TableHead>
          <TableHead className="text-right">Sell Vol</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data?.map((row) => (
          <TableRow key={row.date}>
            <TableCell>{row.date}</TableCell>
            <TableCell className="text-right text-green-600">{row.buy_order_count}</TableCell>
            <TableCell className="text-right text-red-600">{row.sell_order_count}</TableCell>
            <TableCell className="text-right">{row.buy_order_volume}</TableCell>
            <TableCell className="text-right">{row.sell_order_volume}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
```

```tsx
// widgets/price-depth-widget.tsx
import { Card, CardContent } from "@/components/ui/card"

export function PriceDepthWidget({ data, isLoading }) {
  if (isLoading) return <Skeleton className="h-40" />
  if (!data) return <p className="text-muted-foreground">No data</p>

  return (
    <div className="grid grid-cols-2 gap-4">
      {/* Bid Side */}
      <Card className="border-green-200">
        <CardContent className="p-4">
          <h4 className="text-sm font-medium text-green-600 mb-2">BID</h4>
          {[data.bid_1, data.bid_2, data.bid_3].map((level, i) => level && (
            <div key={i} className="flex justify-between text-sm">
              <span>{level.price.toLocaleString()}</span>
              <span className="text-muted-foreground">{level.volume.toLocaleString()}</span>
            </div>
          ))}
          <div className="mt-2 pt-2 border-t text-sm font-medium">
            Total: {data.total_bid_volume.toLocaleString()}
          </div>
        </CardContent>
      </Card>
      {/* Ask Side */}
      <Card className="border-red-200">
        <CardContent className="p-4">
          <h4 className="text-sm font-medium text-red-600 mb-2">ASK</h4>
          {[data.ask_1, data.ask_2, data.ask_3].map((level, i) => level && (
            <div key={i} className="flex justify-between text-sm">
              <span>{level.price.toLocaleString()}</span>
              <span className="text-muted-foreground">{level.volume.toLocaleString()}</span>
            </div>
          ))}
          <div className="mt-2 pt-2 border-t text-sm font-medium">
            Total: {data.total_ask_volume.toLocaleString()}
          </div>
        </CardContent>
      </Card>
      <div className="col-span-2 text-center text-sm text-muted-foreground">
        Spread: {data.spread.toLocaleString()} ({data.spread_percent.toFixed(2)}%)
      </div>
    </div>
  )
}
```

```tsx
// widgets/ratio-summary-card.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function RatioSummaryCard({ data, isLoading }) {
  if (isLoading) return <Skeleton className="h-48" />

  const ratios = [
    { label: "P/E", value: data?.pe },
    { label: "P/B", value: data?.pb },
    { label: "ROE", value: data?.roe, suffix: "%" },
    { label: "ROA", value: data?.roa, suffix: "%" },
    { label: "D/E", value: data?.debt_to_equity },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Valuation Ratios</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {ratios.map(({ label, value, suffix = "" }) => (
            <div key={label} className="flex justify-between">
              <span className="text-muted-foreground">{label}</span>
              <span className="font-medium">
                {value != null ? `${value.toFixed(2)}${suffix}` : "N/A"}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
```

```tsx
// widgets/foreign-flow-chart.tsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"

export function ForeignFlowChart({ data, isLoading }) {
  if (isLoading) return <Skeleton className="h-64" />
  if (!data?.length) return <p className="text-muted-foreground">No data</p>

  return (
    <ResponsiveContainer width="100%" height={256}>
      <BarChart data={data}>
        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip />
        <Bar dataKey="net_volume" fill="hsl(var(--primary))" />
      </BarChart>
    </ResponsiveContainer>
  )
}
```

### Step 3.6: Update Stock Detail Tabs
```tsx
// stock-detail-tabs.tsx - ADD Advanced tab
import { AdvancedTab } from "./advanced-tab"

// In tabs list
<TabsTrigger value="advanced">Advanced</TabsTrigger>

// In tabs content
<TabsContent value="advanced">
  <AdvancedTab symbol={symbol} />
</TabsContent>
```

## Todo List
- [ ] Create advanced-tab/index.tsx container
- [ ] Create order-flow-subtab.tsx
- [ ] Create technical-subtab.tsx
- [ ] Create money-flow-subtab.tsx
- [ ] Create order-stats-table.tsx widget
- [ ] Create price-depth-widget.tsx widget
- [ ] Create ratio-summary-card.tsx widget
- [ ] Create trading-stats-card.tsx widget
- [ ] Create foreign-flow-chart.tsx widget
- [ ] Create prop-flow-chart.tsx widget
- [ ] Create skeleton components
- [ ] Update stock-detail-tabs.tsx to include Advanced

## Success Criteria
- [ ] Advanced tab renders in Deep Dive page
- [ ] 3 sub-tabs switch correctly
- [ ] Lazy loading works (components load on demand)
- [ ] Skeleton states show during loading
- [ ] Responsive on mobile/desktop
- [ ] Charts render with Recharts
- [ ] Error states display with retry option
