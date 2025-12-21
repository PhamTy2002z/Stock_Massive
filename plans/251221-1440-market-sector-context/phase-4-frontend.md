# Phase 4: Frontend Components

## Context

- **Plan**: `/plans/251221-1440-market-sector-context/plan.md`
- **Phase 3**: `/plans/251221-1440-market-sector-context/phase-3-backend-api.md`
- **Design**: `/plans/reports/brainstorm-251221-1432-market-sector-context.md` (Section 4)
- **Deep Dive Page**: `/apps/web/src/app/analytics/deep-dive/page.tsx`

## Overview

**Description**: Build "Market Context" tab in Deep Dive page with relative performance chart, correlation metrics cards, sector context, and period selector. Uses Recharts for visualization and TanStack Query for data fetching.

**Priority**: P1

**Status**: ✅ DONE (2025-12-21)

**Effort**: 2-3 days

## Requirements

### Functional
1. New tab "Market Context" in Deep Dive page
2. Period selector (1M, 3M, 6M, 1Y)
3. Relative performance chart (3 lines: stock, VNINDEX, sector)
4. Correlation metrics card (beta, correlation, RS)
5. Sector context card (rank, peers)
6. Performance summary badges
7. Handle "Unclassified" sector (hide sector line, show market-only)
8. Mobile responsive layout

### Non-Functional
1. Chart renders smoothly (< 1s)
2. Loading skeleton during data fetch
3. Error handling with retry
4. Consistent with Modern + Clean design
5. Accessible (keyboard navigation, ARIA labels)

## Architecture Decisions

### Component Structure

```
MarketContextTab (container)
├── PeriodSelector (1M/3M/6M/1Y buttons)
├── RelativePerformanceChart (Recharts LineChart)
├── MetricsGrid
│   ├── CorrelationCard (beta, correlation, RS)
│   └── SectorCard (rank, peers)
└── PerformanceSummary (badges)
```

### State Management
- URL param for period (shareable links)
- TanStack Query for API data
- Local state for chart interactions (hover, tooltip)

### Chart Library
- Use Recharts (already in project)
- LineChart with 3 lines
- Tooltip with custom formatter
- Legend with toggle

## Related Code Files

**Existing**:
- `/apps/web/src/app/analytics/deep-dive/page.tsx` - Deep Dive page
- `/apps/web/src/components/dashboard/stock-detail-tabs.tsx` - Tab structure
- `/apps/web/src/hooks/use-stock-detail.ts` - Data fetching pattern
- `/apps/web/src/lib/query-keys.ts` - Query key factory
- `/apps/web/src/lib/api.ts` - API client

**New**:
- `/apps/web/src/hooks/use-market-context.ts` - Data fetching hook
- `/apps/web/src/components/dashboard/market-context-tab.tsx` - Main tab component
- `/apps/web/src/components/dashboard/relative-performance-chart.tsx` - Chart component
- `/apps/web/src/components/dashboard/correlation-card.tsx` - Metrics card
- `/apps/web/src/components/dashboard/sector-context-card.tsx` - Sector card

## Implementation Steps

### Step 1: Add Query Key and Type Definitions (20 min)

Update `/apps/web/src/lib/query-keys.ts`:

```typescript
export const queryKeys = {
  // ... existing keys
  marketContext: (symbol: string, period: string) =>
    ['market-context', symbol, period] as const,
}
```

Create `/apps/web/src/types/market-context.ts`:

```typescript
export interface ChartDataPoint {
  date: string
  stock: number
  vnindex: number
  sector: number | null
}

export interface MarketMetrics {
  beta_20d: number | null
  beta_60d: number | null
  correlation_20d: number | null
  correlation_60d: number | null
  rs_market_20d: number | null
  rs_sector_20d: number | null
}

export interface TopPeer {
  symbol: string
  change_pct: number
}

export interface SectorContext {
  icb_code: string
  icb_name: string
  rank: number
  total: number
  top_peers: TopPeer[]
}

export interface PerformanceSummary {
  stock_return: number
  vnindex_return: number
  sector_return: number | null
  outperform_market: boolean
  outperform_sector: boolean | null
}

export interface MarketContextResponse {
  symbol: string
  period: '1M' | '3M' | '6M' | '1Y'
  chart_data: ChartDataPoint[]
  metrics: MarketMetrics
  sector: SectorContext | null
  performance: PerformanceSummary
  generated_at: string
}

export type Period = '1M' | '3M' | '6M' | '1Y'
```

### Step 2: Create Data Fetching Hook (30 min)

Create `/apps/web/src/hooks/use-market-context.ts`:

```typescript
import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/lib/query-keys'
import { api } from '@/lib/api'
import type { MarketContextResponse, Period } from '@/types/market-context'

export function useMarketContext(symbol: string | null, period: Period = '3M') {
  return useQuery({
    queryKey: queryKeys.marketContext(symbol || '', period),
    queryFn: async () => {
      if (!symbol) throw new Error('Symbol is required')

      const response = await api.get<MarketContextResponse>(
        `/stocks/${symbol}/market-context`,
        { params: { period } }
      )
      return response.data
    },
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  })
}
```

### Step 3: Create Period Selector Component (30 min)

Create `/apps/web/src/components/dashboard/period-selector.tsx`:

```typescript
"use client"

import { Button } from "@/components/ui/button"
import type { Period } from "@/types/market-context"

interface PeriodSelectorProps {
  value: Period
  onChange: (period: Period) => void
}

const PERIODS: { value: Period; label: string }[] = [
  { value: '1M', label: '1M' },
  { value: '3M', label: '3M' },
  { value: '6M', label: '6M' },
  { value: '1Y', label: '1Y' },
]

export function PeriodSelector({ value, onChange }: PeriodSelectorProps) {
  return (
    <div className="flex gap-2">
      {PERIODS.map((period) => (
        <Button
          key={period.value}
          variant={value === period.value ? 'default' : 'outline'}
          size="sm"
          onClick={() => onChange(period.value)}
          className="min-w-[60px]"
        >
          {period.label}
        </Button>
      ))}
    </div>
  )
}
```

### Step 4: Create Relative Performance Chart (1.5 hours)

Create `/apps/web/src/components/dashboard/relative-performance-chart.tsx`:

```typescript
"use client"

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { ChartDataPoint } from '@/types/market-context'

interface RelativePerformanceChartProps {
  data: ChartDataPoint[]
  symbol: string
  hasSector: boolean
}

export function RelativePerformanceChart({ data, symbol, hasSector }: RelativePerformanceChartProps) {
  // Format data for Recharts
  const chartData = data.map(point => ({
    date: new Date(point.date).toLocaleDateString('vi-VN', { month: 'short', day: 'numeric' }),
    [symbol]: point.stock,
    'VNINDEX': point.vnindex,
    ...(hasSector && point.sector !== null ? { 'Sector': point.sector } : {})
  }))

  return (
    <Card>
      <CardHeader>
        <CardTitle>Relative Performance</CardTitle>
        <CardDescription>
          Normalized to 100 at start of period
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="date"
              className="text-xs"
              tick={{ fill: 'hsl(var(--muted-foreground))' }}
            />
            <YAxis
              className="text-xs"
              tick={{ fill: 'hsl(var(--muted-foreground))' }}
              label={{ value: 'Index (Base 100)', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--background))',
                border: '1px solid hsl(var(--border))',
                borderRadius: '8px'
              }}
              formatter={(value: number) => value.toFixed(2)}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey={symbol}
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
            <Line
              type="monotone"
              dataKey="VNINDEX"
              stroke="hsl(var(--muted-foreground))"
              strokeWidth={2}
              dot={false}
              strokeDasharray="5 5"
            />
            {hasSector && (
              <Line
                type="monotone"
                dataKey="Sector"
                stroke="hsl(var(--chart-2))"
                strokeWidth={2}
                dot={false}
                strokeDasharray="3 3"
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
```

### Step 5: Create Correlation Card (45 min)

Create `/apps/web/src/components/dashboard/correlation-card.tsx`:

```typescript
"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { TrendingUp, TrendingDown } from "lucide-react"
import type { MarketMetrics } from '@/types/market-context'

interface CorrelationCardProps {
  metrics: MarketMetrics
}

export function CorrelationCard({ metrics }: CorrelationCardProps) {
  const formatMetric = (value: number | null, decimals = 2) => {
    if (value === null) return 'N/A'
    return value.toFixed(decimals)
  }

  const getBetaColor = (beta: number | null) => {
    if (beta === null) return 'secondary'
    if (beta > 1.2) return 'destructive'
    if (beta < 0.8) return 'default'
    return 'secondary'
  }

  const getCorrelationColor = (corr: number | null) => {
    if (corr === null) return 'secondary'
    if (Math.abs(corr) > 0.7) return 'default'
    return 'secondary'
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Market Correlation</CardTitle>
        <CardDescription>
          Relationship with VNINDEX
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Beta (20D)</span>
            <Badge variant={getBetaColor(metrics.beta_20d)}>
              {formatMetric(metrics.beta_20d)}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            {metrics.beta_20d && metrics.beta_20d > 1
              ? 'More volatile than market'
              : 'Less volatile than market'}
          </p>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Correlation (20D)</span>
            <Badge variant={getCorrelationColor(metrics.correlation_20d)}>
              {formatMetric(metrics.correlation_20d)}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            {metrics.correlation_20d && Math.abs(metrics.correlation_20d) > 0.7
              ? 'Strong correlation'
              : 'Weak correlation'}
          </p>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Relative Strength (20D)</span>
            <div className="flex items-center gap-2">
              {metrics.rs_market_20d && metrics.rs_market_20d > 1 ? (
                <TrendingUp className="h-4 w-4 text-green-500" />
              ) : (
                <TrendingDown className="h-4 w-4 text-red-500" />
              )}
              <Badge variant={metrics.rs_market_20d && metrics.rs_market_20d > 1 ? 'default' : 'secondary'}>
                {formatMetric(metrics.rs_market_20d)}
              </Badge>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            {metrics.rs_market_20d && metrics.rs_market_20d > 1
              ? 'Outperforming market'
              : 'Underperforming market'}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
```

### Step 6: Create Sector Context Card (45 min)

Create `/apps/web/src/components/dashboard/sector-context-card.tsx`:

```typescript
"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { SectorContext } from '@/types/market-context'

interface SectorContextCardProps {
  sector: SectorContext | null
}

export function SectorContextCard({ sector }: SectorContextCardProps) {
  if (!sector) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Sector Context</CardTitle>
          <CardDescription>No sector classification</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            This stock is not classified under any sector.
          </p>
        </CardContent>
      </Card>
    )
  }

  const getRankColor = (rank: number, total: number) => {
    const percentile = rank / total
    if (percentile <= 0.2) return 'default'
    if (percentile <= 0.5) return 'secondary'
    return 'outline'
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sector Context</CardTitle>
        <CardDescription>{sector.icb_name}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Sector Rank</span>
            <Badge variant={getRankColor(sector.rank, sector.total)}>
              #{sector.rank} / {sector.total}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            {sector.rank <= sector.total * 0.2
              ? 'Top 20% in sector'
              : sector.rank <= sector.total * 0.5
              ? 'Above median'
              : 'Below median'}
          </p>
        </div>

        {sector.top_peers.length > 0 && (
          <div className="space-y-2">
            <span className="text-sm font-medium">Top Peers</span>
            <div className="space-y-1">
              {sector.top_peers.map((peer) => (
                <div key={peer.symbol} className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{peer.symbol}</span>
                  <span className={peer.change_pct >= 0 ? 'text-green-500' : 'text-red-500'}>
                    {peer.change_pct >= 0 ? '+' : ''}{peer.change_pct.toFixed(2)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
```

### Step 7: Create Main Tab Component (1 hour)

Create `/apps/web/src/components/dashboard/market-context-tab.tsx`:

```typescript
"use client"

import { useState } from 'react'
import { useMarketContext } from '@/hooks/use-market-context'
import { PeriodSelector } from './period-selector'
import { RelativePerformanceChart } from './relative-performance-chart'
import { CorrelationCard } from './correlation-card'
import { SectorContextCard } from './sector-context-card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AlertCircle, TrendingUp, TrendingDown } from 'lucide-react'
import type { Period } from '@/types/market-context'

interface MarketContextTabProps {
  symbol: string
}

export function MarketContextTab({ symbol }: MarketContextTabProps) {
  const [period, setPeriod] = useState<Period>('3M')
  const { data, isLoading, error, refetch } = useMarketContext(symbol, period)

  if (isLoading) {
    return <MarketContextSkeleton />
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>
          Failed to load market context data.
          <button
            onClick={() => refetch()}
            className="ml-2 underline"
          >
            Try again
          </button>
        </AlertDescription>
      </Alert>
    )
  }

  if (!data) {
    return null
  }

  const hasSector = data.sector !== null

  return (
    <div className="space-y-6">
      {/* Header with Period Selector */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Market Context</h3>
          <p className="text-sm text-muted-foreground">
            Analyze stock movement vs market and sector trends
          </p>
        </div>
        <PeriodSelector value={period} onChange={setPeriod} />
      </div>

      {/* Performance Summary Badges */}
      <div className="flex flex-wrap gap-2">
        <Badge variant={data.performance.outperform_market ? 'default' : 'secondary'}>
          {data.performance.outperform_market ? (
            <TrendingUp className="mr-1 h-3 w-3" />
          ) : (
            <TrendingDown className="mr-1 h-3 w-3" />
          )}
          {data.performance.outperform_market ? 'Outperforming' : 'Underperforming'} Market
        </Badge>

        {data.performance.outperform_sector !== null && (
          <Badge variant={data.performance.outperform_sector ? 'default' : 'secondary'}>
            {data.performance.outperform_sector ? (
              <TrendingUp className="mr-1 h-3 w-3" />
            ) : (
              <TrendingDown className="mr-1 h-3 w-3" />
            )}
            {data.performance.outperform_sector ? 'Outperforming' : 'Underperforming'} Sector
          </Badge>
        )}

        <Badge variant="outline">
          Stock: {data.performance.stock_return >= 0 ? '+' : ''}{data.performance.stock_return.toFixed(2)}%
        </Badge>
        <Badge variant="outline">
          Market: {data.performance.vnindex_return >= 0 ? '+' : ''}{data.performance.vnindex_return.toFixed(2)}%
        </Badge>
        {data.performance.sector_return !== null && (
          <Badge variant="outline">
            Sector: {data.performance.sector_return >= 0 ? '+' : ''}{data.performance.sector_return.toFixed(2)}%
          </Badge>
        )}
      </div>

      {/* Chart */}
      <RelativePerformanceChart
        data={data.chart_data}
        symbol={symbol}
        hasSector={hasSector}
      />

      {/* Metrics Grid */}
      <div className="grid gap-6 md:grid-cols-2">
        <CorrelationCard metrics={data.metrics} />
        <SectorContextCard sector={data.sector} />
      </div>
    </div>
  )
}

function MarketContextSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-60" />
        </div>
        <Skeleton className="h-10 w-60" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-6 w-24" />
      </div>
      <Skeleton className="h-[400px] w-full" />
      <div className="grid gap-6 md:grid-cols-2">
        <Skeleton className="h-[250px] w-full" />
        <Skeleton className="h-[250px] w-full" />
      </div>
    </div>
  )
}
```

### Step 8: Integrate into Deep Dive Page (30 min)

Update `/apps/web/src/app/analytics/deep-dive/page.tsx`:

```typescript
import { MarketContextTab } from '@/components/dashboard/market-context-tab'
import { TrendingUp } from 'lucide-react'

// Add to tabs array
const tabs = [
  // ... existing tabs
  {
    value: "market" as const,
    label: "Market Context",
    icon: TrendingUp,
  },
]

// Add to tab content rendering
{activeTab === "market" && symbol && (
  <MarketContextTab symbol={symbol} />
)}
```

### Step 9: Add Responsive Styles (30 min)

Update chart component for mobile:

```typescript
// In RelativePerformanceChart
<ResponsiveContainer width="100%" height={window.innerWidth < 768 ? 300 : 400}>
  {/* ... */}
</ResponsiveContainer>

// In MarketContextTab, update grid
<div className="grid gap-6 md:grid-cols-2 lg:grid-cols-2">
  {/* Cards */}
</div>
```

### Step 10: Write Component Tests (1 hour)

Create `/apps/web/src/components/dashboard/__tests__/market-context-tab.test.tsx`:

```typescript
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MarketContextTab } from '../market-context-tab'

const mockData = {
  symbol: 'VCB',
  period: '3M',
  chart_data: [
    { date: '2024-09-21', stock: 100, vnindex: 100, sector: 100 },
    { date: '2024-09-22', stock: 102, vnindex: 101, sector: 101.5 },
  ],
  metrics: {
    beta_20d: 1.15,
    correlation_20d: 0.82,
    rs_market_20d: 1.08,
  },
  sector: {
    icb_code: '8355',
    icb_name: 'Ngân hàng',
    rank: 3,
    total: 27,
  },
  performance: {
    stock_return: 12.5,
    vnindex_return: 8.3,
    sector_return: 10.2,
    outperform_market: true,
    outperform_sector: true,
  },
}

describe('MarketContextTab', () => {
  it('renders loading skeleton initially', () => {
    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <MarketContextTab symbol="VCB" />
      </QueryClientProvider>
    )
    expect(screen.getByTestId('skeleton')).toBeInTheDocument()
  })

  it('renders chart and metrics after data loads', async () => {
    // Mock API response
    global.fetch = jest.fn(() =>
      Promise.resolve({
        json: () => Promise.resolve(mockData),
      })
    )

    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <MarketContextTab symbol="VCB" />
      </QueryClientProvider>
    )

    await waitFor(() => {
      expect(screen.getByText('Market Context')).toBeInTheDocument()
      expect(screen.getByText('Outperforming Market')).toBeInTheDocument()
    })
  })

  it('changes period when selector clicked', async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient()

    render(
      <QueryClientProvider client={queryClient}>
        <MarketContextTab symbol="VCB" />
      </QueryClientProvider>
    )

    const button1Y = screen.getByRole('button', { name: '1Y' })
    await user.click(button1Y)

    // Verify API called with new period
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('period=1Y')
    )
  })
})
```

## Success Criteria

- [ ] Tab renders without errors
- [ ] Chart displays 3 lines (stock, VNINDEX, sector)
- [ ] Period selector changes data
- [ ] Metrics cards show correct values
- [ ] Handles "Unclassified" sector (hides sector line)
- [ ] Loading skeleton displays during fetch
- [ ] Error state with retry button
- [ ] Mobile responsive (chart scales, cards stack)
- [ ] Accessible (keyboard navigation, ARIA labels)
- [ ] Performance badges update correctly

## Testing Checklist

- [ ] Test with valid symbol (VCB, FPT)
- [ ] Test with "Unclassified" sector stock
- [ ] Test all periods (1M, 3M, 6M, 1Y)
- [ ] Test loading state
- [ ] Test error state
- [ ] Test retry functionality
- [ ] Test mobile layout (< 768px)
- [ ] Test tablet layout (768px - 1024px)
- [ ] Test desktop layout (> 1024px)
- [ ] Test keyboard navigation
- [ ] Test screen reader compatibility

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Chart performance with large dataset | Medium | Limit data points, use Recharts optimization |
| Mobile chart readability | Medium | Reduce height, simplify tooltip |
| Color contrast (accessibility) | Low | Use HSL variables, test with tools |
| API timeout | Medium | Show loading state, implement retry |

## Performance Targets

- Chart render time: < 1s
- Component mount time: < 500ms
- Re-render on period change: < 300ms
- Mobile scroll performance: 60fps

## Dependencies

- Phase 3 completed (API endpoint available)
- Recharts installed
- TanStack Query configured
- ShadCN/UI components available

## Accessibility Considerations

- ARIA labels for chart elements
- Keyboard navigation for period selector
- Screen reader announcements for data updates
- Color contrast ratio > 4.5:1
- Focus indicators visible

## Next Steps

After Phase 4 completion:
1. User testing and feedback
2. Performance optimization
3. Additional metrics (if requested)
4. Export chart as image feature
