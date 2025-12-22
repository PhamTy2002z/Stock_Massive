# Phase 1: Pie Chart for Top 10 Stocks

## Context

- **Research**: `research/researcher-01-chart-types.md`
- **Current**: Only horizontal bar chart for industries
- **Goal**: Add pie chart showing top 10 stocks by spike_ratio across all industries
- **Priority**: High | **Effort**: Low

## Overview

Create new component `volume-spike-pie-chart.tsx` displaying top 10 stocks with highest spike ratios. Uses Recharts PieChart with custom colors, tooltips, and responsive design.

## Key Insights from Research

1. **Chart Type**: PieChart ideal for showing proportional distribution of top performers
2. **Data Source**: Flatten all stocks from `industries[]`, sort by `spike_ratio`, take top 10
3. **Existing Patterns**:
   - Dynamic Cell coloring based on anomaly levels
   - Custom tooltip with ShadCN Card
   - ResponsiveContainer for adaptive sizing
4. **Color Scheme**: Use existing anomaly colors (red/orange/yellow) or introduce new palette

## Requirements

### Functional
- Display top 10 stocks by spike_ratio across all industries
- Show stock symbol, spike_ratio, price_change_pct in tooltip
- Click on slice navigates to stock deep-dive page
- Auto-hide if no data available

### Non-Functional
- Responsive (300px height minimum)
- Accessible (ARIA labels, keyboard nav)
- Performance: useMemo for data transformation
- Consistent with existing design system

## Architecture

### Component Structure
```
VolumeSpikePieChart
├── Props: { industries: IndustryVolumeSpikeGroup[], className?: string }
├── Data Transform: useMemo(() => flatten + sort + slice(10))
├── ResponsiveContainer
│   └── PieChart
│       ├── Pie (dataKey="spike_ratio", nameKey="symbol")
│       │   └── Cell[] (dynamic colors)
│       ├── Tooltip (CustomTooltip)
│       └── Legend
└── Skeleton variant
```

### Data Transformation
```typescript
const topStocks = useMemo(() => {
  return industries
    .flatMap(g => g.stocks)
    .sort((a, b) => b.spike_ratio - a.spike_ratio)
    .slice(0, 10)
    .map(s => ({
      symbol: s.symbol,
      spike_ratio: s.spike_ratio,
      price_change_pct: s.price_change_pct,
      anomaly_level: s.anomaly_level,
      company_name: s.company_name,
    }))
}, [industries])
```

### Color Strategy
Option A: Use anomaly level colors (consistent with bar chart)
Option B: Use distinct palette for better visual separation

**Recommendation**: Option A for consistency

## Related Code Files

- `/apps/web/src/components/dashboard/volume-spike-chart.tsx` - Reference patterns
- `/apps/web/src/components/dashboard/volume-spike-dashboard.tsx` - Integration point
- `/apps/web/src/lib/api.ts` - Type definitions
- `/apps/web/src/components/ui/card.tsx` - ShadCN Card for tooltip

## Implementation Steps

### Step 1: Create Component File
```bash
touch /apps/web/src/components/dashboard/volume-spike-pie-chart.tsx
```

### Step 2: Implement Base Component
- Import Recharts: `PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend`
- Import types: `IndustryVolumeSpikeGroup`
- Import UI: `Card, CardContent, CardHeader, CardTitle`
- Define props interface

### Step 3: Data Transformation
- Flatten stocks from all industries
- Sort by spike_ratio descending
- Take top 10
- Memoize with useMemo

### Step 4: Color Function
```typescript
function getPieColor(anomalyLevel: VolumeSpikeAnomalyLevel): string {
  const colors = {
    very_high: "hsl(0 84% 60%)",    // Red
    high: "hsl(25 95% 53%)",         // Orange
    elevated: "hsl(45 93% 47%)",     // Yellow
    normal: "hsl(var(--muted-foreground))",
  }
  return colors[anomalyLevel]
}
```

### Step 5: Custom Tooltip
```typescript
function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const data = payload[0].payload
  return (
    <Card className="shadow-lg border-border/50">
      <CardContent className="p-3 space-y-1.5">
        <p className="font-semibold text-sm">{data.symbol}</p>
        <p className="text-xs text-muted-foreground truncate max-w-[200px]">
          {data.company_name}
        </p>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Tỷ lệ:</span>
            <span className="font-medium">{data.spike_ratio.toFixed(1)}x</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Giá:</span>
            <span className={data.price_change_pct >= 0 ? "text-green-500" : "text-red-500"}>
              {formatPercent(data.price_change_pct)}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
```

### Step 6: Render PieChart
```typescript
<Card className={cn("w-full", className)}>
  <CardHeader className="pb-2">
    <CardTitle className="text-base">Top 10 CP đột biến mạnh nhất</CardTitle>
  </CardHeader>
  <CardContent>
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={topStocks}
          dataKey="spike_ratio"
          nameKey="symbol"
          cx="50%"
          cy="50%"
          outerRadius={100}
          label={({ symbol }) => symbol}
          labelLine={false}
        >
          {topStocks.map((stock, index) => (
            <Cell
              key={`cell-${index}`}
              fill={getPieColor(stock.anomaly_level)}
              onClick={() => router.push(`/analytics/deep-dive?symbol=${stock.symbol}`)}
              className="cursor-pointer hover:opacity-80 transition-opacity"
            />
          ))}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
        <Legend
          verticalAlign="bottom"
          height={36}
          formatter={(value) => value}
        />
      </PieChart>
    </ResponsiveContainer>
  </CardContent>
</Card>
```

### Step 7: Add Skeleton
```typescript
export function VolumeSpikePieChartSkeleton({ className }: { className?: string }) {
  return (
    <Card className={cn("w-full", className)}>
      <CardHeader className="pb-2">
        <div className="h-5 w-48 bg-muted animate-pulse rounded" />
      </CardHeader>
      <CardContent>
        <div className="h-[300px] bg-muted animate-pulse rounded" />
      </CardContent>
    </Card>
  )
}
```

### Step 8: Integrate into Dashboard
In `volume-spike-dashboard.tsx`:
```typescript
import { VolumeSpikePieChart } from "./volume-spike-pie-chart"

// After VolumeSpikeChart
{data?.industries && data.industries.length > 0 && (
  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
    <VolumeSpikeChart industries={data.industries} />
    <VolumeSpikePieChart industries={data.industries} />
  </div>
)}
```

### Step 9: Testing
- Test with real data (various spike counts)
- Test empty state
- Test click navigation
- Test responsive behavior (mobile/tablet/desktop)
- Test tooltip interactions
- Test accessibility (keyboard, screen reader)

## Todo List

- [ ] Create `volume-spike-pie-chart.tsx` file
- [ ] Implement data transformation with useMemo
- [ ] Implement color function based on anomaly levels
- [ ] Create custom tooltip component
- [ ] Implement PieChart with Cell coloring
- [ ] Add click handler for navigation
- [ ] Create skeleton component
- [ ] Integrate into dashboard (2-column grid)
- [ ] Test with real data
- [ ] Test responsive behavior
- [ ] Test accessibility
- [ ] Code review

## Success Criteria

- [ ] Pie chart displays top 10 stocks correctly
- [ ] Colors match anomaly levels
- [ ] Tooltip shows all required info
- [ ] Click navigates to deep-dive page
- [ ] Responsive on all screen sizes
- [ ] No console errors/warnings
- [ ] Passes accessibility audit
- [ ] Performance: <100ms render time

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Too many slices hard to read | Medium | Low | Limit to 10, use clear labels |
| Color confusion with bar chart | Low | Low | Use same color scheme |
| Mobile label overlap | Medium | Medium | Use labelLine={false}, smaller outerRadius |
| Click target too small | Medium | Low | Ensure min 44x44px touch target |

## Security Considerations

- Sanitize symbol before navigation (already handled by encodeURIComponent)
- No user input in this component
- Data comes from trusted API

## Next Steps

1. Implement component following steps above
2. Test thoroughly
3. Move to Phase 2 (ICB UI improvements)
4. Consider adding chart selector/tabs if multiple charts added
