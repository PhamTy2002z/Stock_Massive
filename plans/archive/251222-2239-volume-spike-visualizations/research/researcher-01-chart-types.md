# Volume Spike Visualization Research Report

**Date:** 2025-12-22
**Agent:** researcher-251222-2240

---

## 1. Current Implementation

### Existing Components
- `volume-spike-dashboard.tsx` - Main dashboard with filters, summary cards, industry groups table
- `volume-spike-chart.tsx` - Horizontal bar chart showing top 10 industries by spike count

### Current Chart Implementation
```tsx
// volume-spike-chart.tsx uses:
import { Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Cell } from "recharts"
```

**Features:**
- Horizontal BarChart with vertical layout
- Dynamic Cell coloring based on spike intensity (red/orange/yellow)
- Custom tooltip with Card component
- ResponsiveContainer for adaptive sizing
- Top 10 industries sliced from data

### Data Structure
```ts
interface IndustryVolumeSpikeGroup {
  icb_code: string
  icb_name: string
  spike_count: number
  avg_spike_ratio: number
  stocks: VolumeSpikeStock[]
}
```

---

## 2. Available Recharts Chart Types

### Suitable for Volume Spike Data

| Chart Type | Use Case | Recharts Import |
|------------|----------|-----------------|
| **PieChart** | Top 10 stocks by volume ratio | `PieChart, Pie, Cell` |
| **Treemap** | Hierarchical industry->stock view | `Treemap` |
| **BarChart** | Already implemented (horizontal) | `BarChart, Bar` |
| **ComposedChart** | Mix bar + line (volume + price change) | `ComposedChart, Area, Line, Bar` |
| **RadarChart** | Multi-variable comparison | `RadarChart, Radar, PolarGrid` |

### Not Recommended
- LineChart - time series, not snapshot data
- AreaChart - continuous data, not categorical
- ScatterChart - needs x/y correlation data

---

## 3. Recommended Visualizations

### A. Pie Chart - Top 10 Stocks by Spike Ratio
**Purpose:** Quick visual of which stocks dominate volume spikes

```tsx
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'

const COLORS = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9']

<PieChart>
  <Pie
    data={topStocks}
    dataKey="spike_ratio"
    nameKey="symbol"
    cx="50%"
    cy="50%"
    outerRadius={80}
    label={({ symbol }) => symbol}
  >
    {topStocks.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
  </Pie>
  <Tooltip />
  <Legend />
</PieChart>
```

### B. Treemap - Industry Hierarchy
**Purpose:** Show relative size of industries + drill into stocks

```tsx
import { Treemap, ResponsiveContainer, Tooltip } from 'recharts'

// Transform data to hierarchical format
const treemapData = [{
  name: 'Industries',
  children: industries.map(ind => ({
    name: ind.icb_name,
    size: ind.spike_count,
    children: ind.stocks.map(s => ({ name: s.symbol, size: s.spike_ratio }))
  }))
}]

<Treemap
  data={treemapData}
  dataKey="size"
  ratio={4/3}
  stroke="#fff"
  content={<CustomizedContent />}
/>
```

### C. ComposedChart - Volume vs Price Change
**Purpose:** Correlate volume spikes with price movement

```tsx
import { ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, Legend } from 'recharts'

<ComposedChart data={stockData}>
  <XAxis dataKey="symbol" />
  <YAxis yAxisId="left" /> {/* spike_ratio */}
  <YAxis yAxisId="right" orientation="right" /> {/* price_change */}
  <Bar yAxisId="left" dataKey="spike_ratio" fill="#8884d8" />
  <Line yAxisId="right" dataKey="price_change_pct" stroke="#ff7300" />
</ComposedChart>
```

---

## 4. Code Patterns from Codebase

### Pattern 1: Dynamic Cell Coloring
```tsx
// From volume-spike-chart.tsx
function getBarColor(spikeCount: number, maxCount: number): string {
  const ratio = spikeCount / maxCount
  if (ratio > 0.7) return "hsl(0 84% 60%)"   // Red
  if (ratio > 0.4) return "hsl(25 95% 53%)"  // Orange
  return "hsl(45 93% 47%)"                    // Yellow
}

<Bar dataKey="count">
  {chartData.map((entry, index) => (
    <Cell key={`cell-${index}`} fill={getBarColor(entry.count, maxCount)} />
  ))}
</Bar>
```

### Pattern 2: Custom Tooltip with ShadCN Card
```tsx
function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const data = payload[0].payload
  return (
    <Card className="shadow-lg border-border/50">
      <CardContent className="p-3 space-y-1.5">
        <p className="font-semibold text-sm">{data.name}</p>
        {/* ... */}
      </CardContent>
    </Card>
  )
}
```

### Pattern 3: ResponsiveContainer Wrapper
```tsx
<ResponsiveContainer width="100%" height={300}>
  <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
    {/* ... */}
  </BarChart>
</ResponsiveContainer>
```

---

## 5. Implementation Priority

| Priority | Chart | Effort | Value |
|----------|-------|--------|-------|
| 1 | PieChart (Top 10 stocks) | Low | High |
| 2 | ComposedChart (Volume vs Price) | Medium | High |
| 3 | Treemap (Industry hierarchy) | Medium | Medium |

---

## 6. Unresolved Questions

1. **Data granularity:** Should pie chart show top 10 across all industries or per-industry?
2. **Interactivity:** Click-through from chart to stock detail page needed?
3. **Real-time updates:** Should charts animate on data refresh?
4. **Mobile responsiveness:** Treemap may not work well on small screens - alternative needed?
5. **Color scheme:** Use existing anomaly colors or introduce new palette for new charts?
