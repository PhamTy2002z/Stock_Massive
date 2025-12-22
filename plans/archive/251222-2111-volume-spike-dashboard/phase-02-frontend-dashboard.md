# Phase 2: Frontend Dashboard - Volume Spike Visualization

## Context
- **Plan:** [Main Plan](./plan.md)
- **Phase 1:** [Backend API](./phase-01-backend-api.md)
- **Research:** [Frontend Patterns Report](./research/researcher-frontend-patterns-report.md)
- **Existing Patterns:**
  - `/apps/web/src/components/dashboard/top-performers-table.tsx`
  - `/apps/web/src/components/dashboard/volume-anomaly-chart.tsx`
  - `/apps/web/src/hooks/use-top-performers.ts`

## Overview
Build interactive dashboard in "Deep Dive" tab showing volume spikes grouped by ICB industry. Features collapsible sections, Recharts visualization, configurable filters, and click-to-navigate functionality.

## Requirements

### Functional
- **Location:** New tab in Deep Dive section (sidebar navigation)
- **Display:** Collapsible groups by anomaly level (Very High >3x, High 2-3x, Elevated 1.5-2x)
- **Filters:** Date picker, threshold selector (1.5x/2x/2.5x/3x), exchange filter, UPCOM toggle
- **Interaction:** Click symbol → navigate to `/deep-dive?symbol=XXX`
- **Visualization:** ComposedChart with volume bars + 20d avg baseline
- **Auto-refresh:** 3min during trading hours

### Non-Functional
- Responsive design (mobile-first)
- Loading skeletons for perceived performance
- Error states with retry button
- Optimistic UI (show stale data while fetching)
- Accessibility (keyboard navigation, ARIA labels)

## Architecture

### Component Structure
```
volume-spike-dashboard.tsx (main container)
├── Header (title + filters + refresh button)
├── SummaryCards (total spikes, avg ratio, top industry)
├── VolumeSpikesChart (Recharts ComposedChart)
└── IndustryGroups (collapsible sections)
    ├── IndustryGroup (Very High >3x) - defaultOpen
    │   └── StockTable (symbol, volume, ratio, price change)
    ├── IndustryGroup (High 2-3x)
    └── IndustryGroup (Elevated 1.5-2x)
```

### Data Flow
```
Component Mount → useVolumeSpikes() → TanStack Query →
API Call → Cache Check → Response → useMemo Grouping →
Render Collapsibles → User Click → Navigate
```

## Related Code Files
- `/apps/web/src/app/analytics/volume-spikes/page.tsx` - New page
- `/apps/web/src/components/dashboard/volume-spike-dashboard.tsx` - Main component
- `/apps/web/src/components/dashboard/volume-spike-chart.tsx` - Chart component
- `/apps/web/src/components/dashboard/industry-spike-group.tsx` - Collapsible group
- `/apps/web/src/hooks/use-volume-spikes.ts` - TanStack Query hook
- `/apps/web/src/lib/api.ts` - Add `fetchVolumeSpikes()`
- `/apps/web/src/lib/query-keys.ts` - Add query key factory
- `/apps/web/src/components/layout/app-sidebar.tsx` - Add nav link

## Implementation Steps

### Step 1: API Integration (1 hour)
- [ ] Add `fetchVolumeSpikes()` to `/lib/api.ts`
- [ ] Add query key factory to `/lib/query-keys.ts`
- [ ] Create `useVolumeSpikes()` hook in `/hooks/`
- [ ] Configure staleTime (2min), refetchInterval (3min)
- [ ] Add error handling and retry logic

### Step 2: Core Components (3-4 hours)
- [ ] Create `volume-spike-dashboard.tsx` main container
- [ ] Add header with title, date picker, refresh button
- [ ] Create filter controls (threshold, exchange, UPCOM toggle)
- [ ] Implement `useMemo` for grouping by anomaly level
- [ ] Add loading skeleton (reuse pattern from top-performers)
- [ ] Add error state with retry button

### Step 3: Chart Visualization (2 hours)
- [ ] Create `volume-spike-chart.tsx` with Recharts
- [ ] Use `ComposedChart` (Bar + Line)
- [ ] Color-code bars by anomaly level (red/orange/yellow)
- [ ] Add dashed baseline for 20d average
- [ ] Custom tooltip with volume, ratio, price change
- [ ] Responsive container (400px height)

### Step 4: Collapsible Groups (2 hours)
- [ ] Create `industry-spike-group.tsx` component
- [ ] Use ShadCN `Collapsible` with Radix UI
- [ ] Add chevron icon with rotate animation
- [ ] Display count badge (e.g., "12 stocks")
- [ ] Implement stock table with sorting
- [ ] Add click handler → `router.push('/deep-dive?symbol=XXX')`

### Step 5: Summary Cards (1 hour)
- [ ] Create 3 summary cards (total spikes, avg ratio, top industry)
- [ ] Use ShadCN `Card` component
- [ ] Add icons (TrendingUp, Activity, Building2)
- [ ] Format numbers (1.2M volume, +2.5x ratio)
- [ ] Responsive grid layout

### Step 6: Navigation & Routing (30 min)
- [ ] Create `/app/analytics/volume-spikes/page.tsx`
- [ ] Add "Volume Spikes" link to sidebar
- [ ] Add icon (Activity or TrendingUp)
- [ ] Update sidebar active state logic

### Step 7: Polish & Optimization (2 hours)
- [ ] Add keyboard navigation (Tab, Enter)
- [ ] Add ARIA labels for accessibility
- [ ] Optimize re-renders with `React.memo`
- [ ] Add debounced filter inputs
- [ ] Test mobile responsiveness
- [ ] Add empty state (no spikes found)

## Todo List
- [ ] Add fetchVolumeSpikes to API client
- [ ] Create useVolumeSpikes TanStack Query hook
- [ ] Build main dashboard container component
- [ ] Implement filter controls (date, threshold, exchange)
- [ ] Create Recharts volume spike chart
- [ ] Build collapsible industry group component
- [ ] Create stock table with click-to-navigate
- [ ] Add summary cards (total, avg, top industry)
- [ ] Create new page route in app directory
- [ ] Add sidebar navigation link
- [ ] Implement loading skeletons
- [ ] Add error states with retry
- [ ] Test responsive design (mobile/tablet/desktop)
- [ ] Add keyboard navigation support
- [ ] Optimize performance (memoization, virtualization)

## Success Criteria
- [ ] Dashboard loads in <2s with cached data
- [ ] Collapsible groups expand/collapse smoothly
- [ ] Click symbol navigates to Deep Dive page
- [ ] Filters update results without full reload
- [ ] Chart displays correctly on mobile (responsive)
- [ ] Auto-refresh works during trading hours
- [ ] Loading states provide clear feedback
- [ ] Error states allow retry without page refresh

## Component Specifications

### 1. Main Dashboard (`volume-spike-dashboard.tsx`)
```tsx
export function VolumeSpikeDashboard() {
  const [date, setDate] = useState<string>()
  const [minRatio, setMinRatio] = useState(1.5)
  const [exchange, setExchange] = useState<string>()
  const [includeUpcom, setIncludeUpcom] = useState(false)

  const { data, isLoading, isFetching, error, refetch } = useVolumeSpikes({
    date, minRatio, exchange, includeUpcom
  })

  const groupedByLevel = useMemo(() => {
    // Group stocks by anomaly level (very_high, high, elevated)
  }, [data])

  return (
    <div className="space-y-6">
      <Header filters={...} onRefresh={refetch} />
      <SummaryCards data={data} />
      <VolumeSpikesChart data={data} />
      <IndustryGroups groups={groupedByLevel} />
    </div>
  )
}
```

### 2. TanStack Query Hook (`use-volume-spikes.ts`)
```tsx
export function useVolumeSpikes(params: VolumeSpikeParams) {
  return useQuery({
    queryKey: queryKeys.volumeSpikes(params),
    queryFn: () => fetchVolumeSpikes(params),
    staleTime: 2 * 60 * 1000,       // 2 min
    refetchInterval: 3 * 60 * 1000, // 3 min auto-refresh
    refetchOnWindowFocus: true,
    retry: 2,
  })
}
```

### 3. Chart Component (`volume-spike-chart.tsx`)
```tsx
export function VolumeSpikesChart({ data }: Props) {
  const chartData = useMemo(() => {
    // Transform API data for Recharts
  }, [data])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Volume Spike Distribution</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={chartData}>
            <Bar dataKey="volume" fill="hsl(var(--primary))">
              {chartData.map((entry, index) => (
                <Cell key={index} fill={getAnomalyColor(entry.ratio)} />
              ))}
            </Bar>
            <Line
              dataKey="avgVolume"
              stroke="hsl(var(--muted-foreground))"
              strokeDasharray="5 5"
            />
            <Tooltip content={<CustomTooltip />} />
          </ComposedChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
```

### 4. Industry Group (`industry-spike-group.tsx`)
```tsx
export function IndustrySpikeGroup({ industry, stocks }: Props) {
  const router = useRouter()

  const handleStockClick = (symbol: string) => {
    router.push(`/deep-dive?symbol=${symbol}`)
  }

  return (
    <Collapsible defaultOpen={industry.level === 'very_high'}>
      <CollapsibleTrigger className="flex items-center gap-2">
        <ChevronDown className="h-4 w-4 transition-transform" />
        <Badge variant={getBadgeVariant(industry.level)}>
          {industry.name}
        </Badge>
        <span className="text-muted-foreground">{stocks.length} stocks</span>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <StockTable stocks={stocks} onRowClick={handleStockClick} />
      </CollapsibleContent>
    </Collapsible>
  )
}
```

## Design Specifications (Follow Existing Patterns)

**Reference Components:**
- `vn30-overview-table.tsx` - Table styling, sorting, pagination
- `top-performers-table.tsx` - Table structure, number formatting
- `volume-anomaly-chart.tsx` - Chart styling, tooltip, legend
- `sector-performance.tsx` - Card layout, color scheme

### Table Styling (Match vn30-overview-table)
```tsx
// Container
<div className="rounded-lg border border-border/50 bg-card/50 overflow-hidden">
  {/* Header */}
  <div className="border-b border-border/50 bg-muted/30">
    <div className="py-3 px-4 text-sm font-medium text-muted-foreground">
  {/* Rows */}
  <div className="border-b border-border/30 hover:bg-muted/20 transition-colors">
    <div className="py-3 px-4 text-sm tabular-nums">
```

### Section Header (Match existing pattern)
```tsx
<div className="flex items-center justify-between mb-4">
  <h2 className="text-lg font-semibold text-foreground">Khối lượng đột biến</h2>
  <button className="p-1.5 rounded-md hover:bg-muted transition-colors disabled:opacity-50">
    <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
  </button>
</div>
```

### Color Scheme (Match volume-anomaly-chart)
```tsx
const ANOMALY_COLORS = {
  very_high: "hsl(0 84% 60%)",   // Red (>3x)
  high: "hsl(25 95% 53%)",       // Orange (2-3x)
  elevated: "hsl(45 93% 47%)",   // Yellow (1.5-2x)
  normal: "hsl(var(--muted-foreground))",
}

// Positive/Negative values (match existing)
const VALUE_COLORS = {
  positive: "text-green-500 dark:text-green-400",
  negative: "text-red-500 dark:text-red-400",
}
```

### Pagination Footer (Match top-performers-table)
```tsx
<div className="px-4 py-3 border-t border-border/50 bg-muted/20 flex items-center justify-between">
  <Select value={pageSize} onValueChange={setPageSize}>
    {/* 10/20/50 options */}
  </Select>
  <div className="flex items-center gap-2">
    <span className="text-sm text-muted-foreground">{start}-{end} / {total}</span>
    <ChevronLeft/ChevronRight buttons />
  </div>
</div>
```

### Loading Skeleton (Match existing pattern)
```tsx
// Table skeleton
{[...Array(10)].map((_, i) => (
  <div key={i} className="flex items-center gap-4 py-3 px-4 border-b border-border/30">
    <div className="h-4 w-16 rounded bg-muted animate-pulse" />
    <div className="h-4 w-24 rounded bg-muted animate-pulse" />
    <div className="h-4 w-20 rounded bg-muted animate-pulse" />
  </div>
))}

// Chart skeleton
<div className="h-[400px] bg-muted animate-pulse rounded" />
```

### Error State (Match existing pattern)
```tsx
<div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
  <p className="text-sm text-destructive">{error.message}</p>
  <button className="text-sm underline" onClick={refetch}>Thử lại</button>
</div>
```

### Chart Tooltip (Match volume-anomaly-chart)
```tsx
<Card className="shadow-lg border-border/50">
  <CardContent className="p-3 space-y-1.5">
    <p className="font-semibold text-sm">{industry.name}</p>
    <div className="space-y-1 text-xs">
      <div className="flex justify-between gap-4">
        <span className="text-muted-foreground">Số CP:</span>
        <span className="font-medium">{count}</span>
      </div>
    </div>
  </CardContent>
</Card>
```

### Number Formatting (Vietnamese locale)
```tsx
// Volume: 1,234,567 → "1.234.567" or "1,2M"
value.toLocaleString("vi-VN")

// Percentage with sign
`${change >= 0 ? "+" : ""}${change.toFixed(2)}%`

// Use tabular-nums for numeric alignment
<span className="tabular-nums">{value}</span>
```

### Icons (lucide-react - match existing)
- Refresh: `RefreshCw` with `animate-spin` when fetching
- Sort: `ArrowUpDown`, `ArrowUp`, `ArrowDown`
- Navigation: `ChevronLeft`, `ChevronRight`, `ChevronDown`
- Trends: `TrendingUp`, `TrendingDown`
- Industry: `Building2`

## Risk Assessment

### High Risk
- **Large Data Rendering:** 200+ stocks may cause lag
  - *Mitigation:* Virtualization with `react-window`, pagination per group
- **Chart Performance:** Recharts with 100+ bars
  - *Mitigation:* Limit chart to top 50 spikes, add "View All" button

### Medium Risk
- **Filter State Management:** Complex filter combinations
  - *Mitigation:* Use URL search params for shareable links
- **Mobile UX:** Tables hard to read on small screens
  - *Mitigation:* Card layout for mobile, table for desktop

### Low Risk
- **Auto-refresh Conflicts:** User editing filters during refresh
  - *Mitigation:* Disable auto-refresh when filters are dirty

## Unresolved Questions
1. Should we add export to CSV functionality?
2. Do we need historical comparison (today vs yesterday spikes)?
3. Should chart show all industries or just top 10?
4. Add watchlist integration (star favorite industries)?
5. Include intraday volume spike detection (5-min bars)?
