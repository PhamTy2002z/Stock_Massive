# Phase 02: Frontend Chart Component

**Date:** 2025-12-20
**Priority:** High
**Status:** Pending
**Estimated Effort:** 3 hours

## Context

Build reusable volume anomaly chart component using Recharts library with shadcn/ui styling. Display 72 bars with color-coded anomaly highlighting and baseline average line.

**Design Requirements:**
- Bar chart with 5-min intervals on X-axis
- Volume on Y-axis (formatted with K/M suffixes)
- Color coding: normal (muted), elevated (yellow), high (orange), very high (red)
- Baseline average as dashed line overlay
- Responsive layout (mobile/desktop)
- Hover tooltips with volume, ratio, time

## Related Files

- `D:\Stock_Massive\apps\web\src\lib\api.ts` (add types and fetch function)
- `D:\Stock_Massive\apps\web\src\components\dashboard\` (new chart component)
- `D:\Stock_Massive\apps\web\package.json` (add recharts dependency)

## Implementation Steps

### Step 1: Install Recharts (10 min)

**File:** `D:\Stock_Massive\apps\web\package.json`

```bash
cd D:\Stock_Massive\apps\web
pnpm add recharts
pnpm add -D @types/recharts
```

Verify installation:
```json
{
  "dependencies": {
    "recharts": "^2.10.0"
  },
  "devDependencies": {
    "@types/recharts": "^1.8.29"
  }
}
```

### Step 2: Add API Types and Fetch Function (20 min)

**File:** `D:\Stock_Massive\apps\web\src\lib\api.ts`

Add at end of file:

```typescript
// Volume Anomaly Types
export type VolumeAnomalyLevel = "normal" | "elevated" | "high" | "very_high"

export interface VolumeTimeSlot {
  hour: number
  minute_bucket: number
  time_label: string
  current_volume: number
  avg_volume: number
  volume_ratio: number
  anomaly_level: VolumeAnomalyLevel
  sample_count: number
}

export interface VolumeAnomalyResponse {
  symbol: string
  days_analyzed: number
  trading_session: string
  time_slots: VolumeTimeSlot[]
  generated_at: string
  latest_date: string | null
}

export async function fetchVolumeAnomalies(
  symbol: string,
  days: number = 20
): Promise<VolumeAnomalyResponse> {
  return fetchApi<VolumeAnomalyResponse>(
    `/stocks/${encodeURIComponent(symbol)}/volume-anomalies?days=${days}`
  )
}
```

### Step 3: Create Chart Component (120 min)

**File:** `D:\Stock_Massive\apps\web\src\components\dashboard\volume-anomaly-chart.tsx`

```typescript
"use client"

import { useMemo } from "react"
import {
  BarChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { VolumeTimeSlot, VolumeAnomalyLevel } from "@/lib/api"

interface VolumeAnomalyChartProps {
  data: VolumeTimeSlot[]
  symbol: string
  daysAnalyzed: number
  latestDate: string | null
  className?: string
}

// Color mapping for anomaly levels
const ANOMALY_COLORS: Record<VolumeAnomalyLevel, string> = {
  normal: "hsl(var(--muted-foreground))",
  elevated: "hsl(45 93% 47%)", // Yellow
  high: "hsl(25 95% 53%)", // Orange
  very_high: "hsl(0 84% 60%)", // Red
}

// Format volume with K/M suffixes
function formatVolume(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`
  }
  return value.toString()
}

// Custom tooltip component
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload || !payload.length) return null

  const data = payload[0].payload as VolumeTimeSlot
  const anomalyLabel = {
    normal: "Normal",
    elevated: "Elevated (1.5x-2x)",
    high: "High (2x-3x)",
    very_high: "Very High (>3x)",
  }[data.anomaly_level]

  return (
    <Card className="shadow-lg border-border/50">
      <CardContent className="p-3 space-y-1.5">
        <p className="font-semibold text-sm">{data.time_label}</p>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Volume:</span>
            <span className="font-medium">{formatVolume(data.current_volume)}</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Avg (20d):</span>
            <span className="font-medium">{formatVolume(data.avg_volume)}</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Ratio:</span>
            <span className="font-medium">{data.volume_ratio}x</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Status:</span>
            <span
              className={cn(
                "font-medium",
                data.anomaly_level === "very_high" && "text-red-500",
                data.anomaly_level === "high" && "text-orange-500",
                data.anomaly_level === "elevated" && "text-yellow-500"
              )}
            >
              {anomalyLabel}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function VolumeAnomalyChart({
  data,
  symbol,
  daysAnalyzed,
  latestDate,
  className,
}: VolumeAnomalyChartProps) {
  // Prepare chart data with colors
  const chartData = useMemo(() => {
    return data.map((slot) => ({
      ...slot,
      fill: ANOMALY_COLORS[slot.anomaly_level],
    }))
  }, [data])

  // Calculate statistics
  const stats = useMemo(() => {
    const anomalies = data.filter((s) => s.anomaly_level !== "normal")
    const maxVolume = Math.max(...data.map((s) => s.current_volume))
    const totalVolume = data.reduce((sum, s) => sum + s.current_volume, 0)

    return {
      anomalyCount: anomalies.length,
      maxVolume,
      totalVolume,
      avgVolume: totalVolume / data.length,
    }
  }, [data])

  // X-axis tick formatter (show every 12th label = hourly)
  const xAxisTicks = useMemo(() => {
    return data.filter((_, i) => i % 12 === 0).map((s) => s.time_label)
  }, [data])

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Volume Anomaly Detection</span>
          <span className="text-sm font-normal text-muted-foreground">
            {symbol} • {latestDate || "N/A"}
          </span>
        </CardTitle>
        <CardDescription>
          5-minute intervals • {daysAnalyzed}-day baseline • {stats.anomalyCount} anomalies detected
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="time_label"
              ticks={xAxisTicks}
              tick={{ fontSize: 12 }}
              className="text-muted-foreground"
              angle={-45}
              textAnchor="end"
              height={60}
            />
            <YAxis
              tickFormatter={formatVolume}
              tick={{ fontSize: 12 }}
              className="text-muted-foreground"
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "hsl(var(--muted))" }} />
            <Legend
              wrapperStyle={{ paddingTop: "20px" }}
              iconType="circle"
              formatter={(value) => (
                <span className="text-sm text-muted-foreground">{value}</span>
              )}
            />
            <Bar
              dataKey="current_volume"
              name="Volume"
              radius={[4, 4, 0, 0]}
              maxBarSize={20}
            />
            <Line
              type="monotone"
              dataKey="avg_volume"
              name="20-day Average"
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={false}
            />
          </BarChart>
        </ResponsiveContainer>

        {/* Legend for anomaly colors */}
        <div className="flex flex-wrap gap-4 mt-4 pt-4 border-t border-border/50">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-muted-foreground" />
            <span className="text-xs text-muted-foreground">Normal</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: ANOMALY_COLORS.elevated }} />
            <span className="text-xs text-muted-foreground">Elevated (1.5x-2x)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: ANOMALY_COLORS.high }} />
            <span className="text-xs text-muted-foreground">High (2x-3x)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: ANOMALY_COLORS.very_high }} />
            <span className="text-xs text-muted-foreground">Very High (&gt;3x)</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// Loading skeleton
export function VolumeAnomalyChartSkeleton({ className }: { className?: string }) {
  return (
    <Card className={cn("w-full", className)}>
      <CardHeader>
        <div className="h-6 w-48 bg-muted animate-pulse rounded" />
        <div className="h-4 w-64 bg-muted animate-pulse rounded mt-2" />
      </CardHeader>
      <CardContent>
        <div className="h-[400px] bg-muted animate-pulse rounded" />
      </CardContent>
    </Card>
  )
}
```

### Step 4: Export Component (5 min)

**File:** `D:\Stock_Massive\apps\web\src\components\dashboard\index.ts`

Add exports:

```typescript
export { VolumeAnomalyChart, VolumeAnomalyChartSkeleton } from "./volume-anomaly-chart"
```

### Step 5: Test Component in Isolation (25 min)

Create test page to verify chart rendering:

**File:** `D:\Stock_Massive\apps\web\src\app\test-chart\page.tsx`

```typescript
"use client"

import { VolumeAnomalyChart } from "@/components/dashboard"
import type { VolumeTimeSlot } from "@/lib/api"

// Mock data for testing
const mockData: VolumeTimeSlot[] = Array.from({ length: 72 }, (_, i) => {
  const hour = 9 + Math.floor(i / 12)
  const minute = (i % 12) * 5
  const baseVolume = 100000 + Math.random() * 50000
  const ratio = Math.random() * 4

  return {
    hour,
    minute_bucket: minute,
    time_label: `${hour.toString().padStart(2, "0")}:${minute.toString().padStart(2, "0")}`,
    current_volume: Math.floor(baseVolume * ratio),
    avg_volume: baseVolume,
    volume_ratio: parseFloat(ratio.toFixed(2)),
    anomaly_level: ratio >= 3 ? "very_high" : ratio >= 2 ? "high" : ratio >= 1.5 ? "elevated" : "normal",
    sample_count: 20,
  }
})

export default function TestChartPage() {
  return (
    <div className="container mx-auto p-8">
      <VolumeAnomalyChart
        data={mockData}
        symbol="VCB"
        daysAnalyzed={20}
        latestDate="2025-12-20"
      />
    </div>
  )
}
```

Test in browser: `http://localhost:3000/test-chart`

## Todo

- [ ] Install recharts and types
- [ ] Add VolumeAnomalyResponse types to api.ts
- [ ] Add fetchVolumeAnomalies function to api.ts
- [ ] Create volume-anomaly-chart.tsx component
- [ ] Implement CustomTooltip component
- [ ] Add color mapping for anomaly levels
- [ ] Add formatVolume utility
- [ ] Create loading skeleton component
- [ ] Export components from index.ts
- [ ] Test with mock data
- [ ] Verify responsive behavior
- [ ] Verify tooltip interactions
- [ ] Delete test page after verification

## Success Criteria

- Chart renders 72 bars correctly
- Bars colored by anomaly level (normal/elevated/high/very_high)
- Baseline average line displayed as dashed overlay
- Tooltips show volume, ratio, and anomaly status
- X-axis shows hourly labels (09:00, 10:00, etc.)
- Y-axis formats volumes with K/M suffixes
- Responsive on mobile (stacks properly)
- Loading skeleton matches chart dimensions
- Component follows shadcn/ui design patterns
