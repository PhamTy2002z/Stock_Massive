# Phase 3: Advanced Chart Visualizations

## Context

- **Research**: `research/researcher-01-chart-types.md`
- **Current**: Bar chart + pie chart (from Phase 1)
- **Goal**: Add treemap and composed chart for deeper insights
- **Priority**: Medium | **Effort**: Medium

## Overview

Add advanced visualizations: treemap for industry hierarchy and composed chart for volume vs price correlation. Implement chart selector/tabs for switching between views.

## Key Insights from Research

1. **Treemap**: Shows hierarchical industry->stock relationships with relative sizing
2. **ComposedChart**: Correlates volume spikes with price movements (dual-axis)
3. **Chart Selector**: Use tabs or dropdown to switch between chart types
4. **Mobile Consideration**: Treemap may not work well on small screens

## Requirements

### Functional
- Create treemap showing industry hierarchy with drill-down to stocks
- Create composed chart showing volume spike ratio vs price change
- Add chart selector (tabs or dropdown) for switching views
- Hide treemap on mobile (< 768px) or show simplified version
- Maintain consistent styling with existing charts

### Non-Functional
- Responsive design (hide/adapt on mobile)
- Performance: useMemo for data transformations
- Accessible (keyboard nav, ARIA labels)
- Consistent with design system

## Architecture

### Component Structure
```
VolumeSpikeDashboard
├── ChartSection (new wrapper)
│   ├── ChartSelector (Tabs)
│   │   ├── Tab: Bar Chart
│   │   ├── Tab: Pie Chart
│   │   ├── Tab: Treemap
│   │   └── Tab: Volume vs Price
│   └── ChartDisplay
│       ├── VolumeSpikeChart (existing)
│       ├── VolumeSpikePieChart (Phase 1)
│       ├── VolumeSpikeTreemap (new)
│       └── VolumeSpikeComposedChart (new)
```

### State Management
```typescript
const [selectedChart, setSelectedChart] = useState<"bar" | "pie" | "treemap" | "composed">("bar")
```

### Data Transformations

**Treemap Data:**
```typescript
const treemapData = useMemo(() => {
  if (!industries?.length) return []
  return industries.map(ind => ({
    name: ind.icb_name,
    size: ind.spike_count,
    value: ind.avg_spike_ratio,
    children: ind.stocks.slice(0, 10).map(s => ({
      name: s.symbol,
      size: s.spike_ratio,
      value: s.price_change_pct || 0,
      anomaly_level: s.anomaly_level,
    }))
  }))
}, [industries])
```

**Composed Chart Data:**
```typescript
const composedData = useMemo(() => {
  if (!industries?.length) return []
  return industries
    .flatMap(g => g.stocks)
    .sort((a, b) => b.spike_ratio - a.spike_ratio)
    .slice(0, 20) // Top 20 for readability
    .map(s => ({
      symbol: s.symbol,
      spike_ratio: s.spike_ratio,
      price_change_pct: s.price_change_pct || 0,
      anomaly_level: s.anomaly_level,
    }))
}, [industries])
```

## Related Code Files

- `/apps/web/src/components/dashboard/volume-spike-chart.tsx` - Reference patterns
- `/apps/web/src/components/dashboard/volume-spike-pie-chart.tsx` - Phase 1 output
- `/apps/web/src/components/ui/tabs.tsx` - ShadCN Tabs
- `/apps/web/src/lib/utils.ts` - cn utility

## Implementation Steps

### Step 1: Create Treemap Component

**File**: `/apps/web/src/components/dashboard/volume-spike-treemap.tsx`

```typescript
"use client"

import { useMemo } from "react"
import { Treemap, ResponsiveContainer, Tooltip } from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { IndustryVolumeSpikeGroup } from "@/lib/api"

interface TreemapProps {
  industries: IndustryVolumeSpikeGroup[]
  className?: string
}

// Custom content renderer
function CustomizedContent({
  x, y, width, height, name, value, depth
}: any) {
  const fontSize = depth === 1 ? 12 : 10
  const fontWeight = depth === 1 ? 600 : 400

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        style={{
          fill: depth === 1 ? "hsl(var(--muted))" : getTreemapColor(value),
          stroke: "hsl(var(--background))",
          strokeWidth: 2,
        }}
      />
      {width > 40 && height > 20 && (
        <text
          x={x + width / 2}
          y={y + height / 2}
          textAnchor="middle"
          fill="hsl(var(--foreground))"
          fontSize={fontSize}
          fontWeight={fontWeight}
        >
          {name}
        </text>
      )}
    </g>
  )
}

function getTreemapColor(anomalyLevel: string): string {
  const colors = {
    very_high: "hsl(0 84% 60%)",
    high: "hsl(25 95% 53%)",
    elevated: "hsl(45 93% 47%)",
    normal: "hsl(var(--muted-foreground))",
  }
  return colors[anomalyLevel as keyof typeof colors] || colors.normal
}

export function VolumeSpikeTreemap({ industries, className }: TreemapProps) {
  const treemapData = useMemo(() => {
    if (!industries?.length) return []
    return industries.map(ind => ({
      name: ind.icb_name.length > 15 ? ind.icb_name.slice(0, 13) + "..." : ind.icb_name,
      children: ind.stocks.slice(0, 10).map(s => ({
        name: s.symbol,
        size: s.spike_ratio,
        value: s.anomaly_level,
      }))
    }))
  }, [industries])

  if (treemapData.length === 0) return null

  return (
    <Card className={cn("w-full hidden md:block", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Phân bố phân cấp theo ngành</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={400}>
          <Treemap
            data={treemapData}
            dataKey="size"
            aspectRatio={4 / 3}
            stroke="hsl(var(--background))"
            content={<CustomizedContent />}
          />
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
```

### Step 2: Create Composed Chart Component

**File**: `/apps/web/src/components/dashboard/volume-spike-composed-chart.tsx`

```typescript
"use client"

import { useMemo } from "react"
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
  Cell,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import type { IndustryVolumeSpikeGroup } from "@/lib/api"

interface ComposedChartProps {
  industries: IndustryVolumeSpikeGroup[]
  className?: string
}

// Custom tooltip
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const data = payload[0].payload

  return (
    <Card className="shadow-lg border-border/50">
      <CardContent className="p-3 space-y-1.5">
        <p className="font-semibold text-sm">{data.symbol}</p>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Tỷ lệ KL:</span>
            <span className="font-medium">{data.spike_ratio.toFixed(1)}x</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Thay đổi giá:</span>
            <span className={data.price_change_pct >= 0 ? "text-green-500" : "text-red-500"}>
              {data.price_change_pct >= 0 ? "+" : ""}{data.price_change_pct.toFixed(2)}%
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function getBarColor(anomalyLevel: string): string {
  const colors = {
    very_high: "hsl(0 84% 60%)",
    high: "hsl(25 95% 53%)",
    elevated: "hsl(45 93% 47%)",
    normal: "hsl(var(--muted-foreground))",
  }
  return colors[anomalyLevel as keyof typeof colors] || colors.normal
}

export function VolumeSpikeComposedChart({ industries, className }: ComposedChartProps) {
  const chartData = useMemo(() => {
    if (!industries?.length) return []
    return industries
      .flatMap(g => g.stocks)
      .sort((a, b) => b.spike_ratio - a.spike_ratio)
      .slice(0, 20)
      .map(s => ({
        symbol: s.symbol,
        spike_ratio: s.spike_ratio,
        price_change_pct: s.price_change_pct || 0,
        anomaly_level: s.anomaly_level,
      }))
  }, [industries])

  if (chartData.length === 0) return null

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Khối lượng vs Giá (Top 20)</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={350}>
          <ComposedChart
            data={chartData}
            margin={{ top: 10, right: 30, left: 0, bottom: 20 }}
          >
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="symbol"
              tick={{ fontSize: 10 }}
              angle={-45}
              textAnchor="end"
              height={60}
            />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 11 }}
              label={{ value: "Tỷ lệ KL", angle: -90, position: "insideLeft", fontSize: 11 }}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 11 }}
              label={{ value: "% Giá", angle: 90, position: "insideRight", fontSize: 11 }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar
              yAxisId="left"
              dataKey="spike_ratio"
              name="Tỷ lệ KL"
              maxBarSize={30}
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getBarColor(entry.anomaly_level)} />
              ))}
            </Bar>
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="price_change_pct"
              name="% Giá"
              stroke="hsl(142 76% 36%)"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
```

### Step 3: Create Chart Selector Component

In `volume-spike-dashboard.tsx`, add:

```typescript
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { VolumeSpikeTreemap } from "./volume-spike-treemap"
import { VolumeSpikeComposedChart } from "./volume-spike-composed-chart"

// In render section, replace single chart with tabs:
{data?.industries && data.industries.length > 0 && (
  <Tabs defaultValue="bar" className="w-full">
    <TabsList className="grid w-full grid-cols-4 lg:w-auto lg:inline-grid">
      <TabsTrigger value="bar" className="text-xs sm:text-sm">Cột ngang</TabsTrigger>
      <TabsTrigger value="pie" className="text-xs sm:text-sm">Tròn</TabsTrigger>
      <TabsTrigger value="treemap" className="text-xs sm:text-sm hidden md:block">Phân cấp</TabsTrigger>
      <TabsTrigger value="composed" className="text-xs sm:text-sm">KL vs Giá</TabsTrigger>
    </TabsList>

    <TabsContent value="bar" className="mt-4">
      <VolumeSpikeChart industries={data.industries} />
    </TabsContent>

    <TabsContent value="pie" className="mt-4">
      <VolumeSpikePieChart industries={data.industries} />
    </TabsContent>

    <TabsContent value="treemap" className="mt-4">
      <VolumeSpikeTreemap industries={data.industries} />
    </TabsContent>

    <TabsContent value="composed" className="mt-4">
      <VolumeSpikeComposedChart industries={data.industries} />
    </TabsContent>
  </Tabs>
)}
```

### Step 4: Mobile Optimization

Add responsive classes:
```typescript
// Hide treemap tab on mobile
<TabsTrigger value="treemap" className="text-xs sm:text-sm hidden md:inline-flex">
  Phân cấp
</TabsTrigger>

// Adjust grid for mobile
<TabsList className="grid w-full grid-cols-3 md:grid-cols-4 lg:w-auto">
```

### Step 5: Testing
- Test all chart types with real data
- Test tab switching (smooth transitions)
- Test mobile layout (treemap hidden)
- Test composed chart dual-axis alignment
- Test treemap drill-down (if implemented)
- Test tooltips on all charts
- Test responsive behavior
- Test accessibility (keyboard tab navigation)

## Todo List

- [ ] Create `volume-spike-treemap.tsx` component
- [ ] Implement treemap data transformation
- [ ] Create custom treemap content renderer
- [ ] Add treemap color coding by anomaly level
- [ ] Create `volume-spike-composed-chart.tsx` component
- [ ] Implement composed chart data transformation
- [ ] Add dual Y-axis (volume left, price right)
- [ ] Create custom tooltip for composed chart
- [ ] Add Tabs component to dashboard
- [ ] Integrate all 4 chart types in tabs
- [ ] Hide treemap tab on mobile
- [ ] Test all chart types
- [ ] Test tab switching
- [ ] Test mobile responsiveness
- [ ] Test accessibility
- [ ] Code review

## Success Criteria

- [ ] Treemap displays industry hierarchy correctly
- [ ] Treemap hidden on mobile (< 768px)
- [ ] Composed chart shows volume and price correlation
- [ ] Dual Y-axis scales appropriately
- [ ] Tab switching works smoothly
- [ ] All charts maintain consistent styling
- [ ] Tooltips work on all charts
- [ ] No performance degradation
- [ ] Keyboard navigation works
- [ ] No console errors/warnings

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Treemap too complex on mobile | High | High | Hide on mobile, show only on desktop |
| Composed chart axis confusion | Medium | Medium | Clear labels, legend, tooltip |
| Too many tabs overwhelm users | Medium | Low | Use clear icons/labels, default to bar |
| Performance with large datasets | Medium | Low | Limit to top 20 stocks, use useMemo |
| Treemap drill-down complexity | High | Medium | Start with flat view, defer drill-down |

## Security Considerations

- No user input in these components
- Data comes from trusted API
- No XSS risks (React escapes by default)

## Next Steps

1. Implement treemap component
2. Implement composed chart component
3. Add tabs integration
4. Test thoroughly on all devices
5. Gather user feedback
6. Consider adding:
   - Chart export functionality
   - Chart customization options
   - Drill-down interactions for treemap
   - Animation on chart load
