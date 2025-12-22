# Frontend Patterns Research Report: Stock Analytics Dashboard
**Date:** 2025-12-22
**Focus:** Volume Spike Dashboard Implementation
**Tech Stack:** Next.js 15.5.9, React 18, TanStack Query v5, Recharts 3.6, ShadCN UI, TailwindCSS 3.4

---

## 1. ACCORDION/COLLAPSIBLE PATTERNS

### Current Implementation
- **Component:** `/apps/web/src/components/ui/collapsible.tsx`
- **Library:** `@radix-ui/react-collapsible` v1.1.12
- **Pattern:** Radix UI primitives (Root, Trigger, Content)
- **Status:** Available but NOT actively used in dashboard components

### Recommended Pattern for Volume Spike Dashboard
```tsx
// Group stocks by anomaly level (very_high, high, elevated)
<Collapsible defaultOpen={true}>
  <CollapsibleTrigger className="flex items-center gap-2">
    <ChevronDown className="h-4 w-4 transition-transform" />
    <Badge variant="destructive">Very High (>3x)</Badge>
    <span className="text-muted-foreground">12 stocks</span>
  </CollapsibleTrigger>
  <CollapsibleContent>
    {/* Stock list table */}
  </CollapsibleContent>
</Collapsible>
```

### Best Practices from Codebase
- Use `defaultOpen={true}` for critical sections
- Animate chevron icon with `transition-transform`
- Include count badges for quick scanning
- Maintain consistent spacing with `space-y-4`

---

## 2. TANSTACK QUERY PATTERNS

### Current Hook Pattern (from `/apps/web/src/hooks/use-top-performers.ts`)
```tsx
export function useTopPerformers(limit: number = 50, exchange?: string) {
  return useQuery({
    queryKey: queryKeys.topPerformers(limit, exchange),
    queryFn: () => fetchTopPerformers(limit, exchange),
    staleTime: 60 * 1000,           // 1 min
    refetchInterval: 5 * 60 * 1000, // 5 min auto-refresh
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })
}
```

### Key Patterns Observed
1. **Centralized Query Keys:** Use `queryKeys` object for consistency
2. **Smart Caching:** `staleTime: 60s` for financial data (balance freshness vs API load)
3. **Auto-Refresh:** `refetchInterval: 5min` for near-real-time updates
4. **Loading States:** Destructure `isLoading`, `isFetching`, `error`, `refetch`
5. **Optimistic UI:** Show stale data while fetching (`isLoading && !data` check)

### Recommended for Volume Spike Hook
```tsx
export function useVolumeSpikes(date?: string, minRatio: number = 1.5) {
  return useQuery({
    queryKey: ['volume-spikes', date, minRatio],
    queryFn: () => fetchVolumeSpikes(date, minRatio),
    staleTime: 2 * 60 * 1000,       // 2 min (more frequent for anomalies)
    refetchInterval: 3 * 60 * 1000, // 3 min auto-refresh
    refetchOnWindowFocus: true,
  })
}
```

---

## 3. RECHARTS VOLUME VISUALIZATION

### Current Implementation (from `/apps/web/src/components/dashboard/volume-anomaly-chart.tsx`)

**Chart Type:** `ComposedChart` (Bar + Line combination)

**Key Features:**
- **Bar Chart:** Current volume with color-coded anomaly levels
- **Line Chart:** Average baseline (dashed line)
- **Custom Tooltip:** Rich context (volume, avg, ratio, status)
- **Color Mapping:** HSL variables for theme consistency
- **Responsive:** `ResponsiveContainer` with fixed height (400px)

### Color Scheme (Anomaly Levels)
```tsx
const ANOMALY_COLORS = {
  normal: "hsl(var(--muted-foreground))",
  elevated: "hsl(45 93% 47%)",  // Yellow
  high: "hsl(25 95% 53%)",      // Orange
  very_high: "hsl(0 84% 60%)",  // Red
}
```

### Volume Formatting Pattern
```tsx
function formatVolume(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`
  return value.toString()
}
```

### Best Practices
1. **Cell-based Coloring:** Use `<Cell>` inside `<Bar>` for per-bar colors
2. **Dashed Baseline:** `strokeDasharray="5 5"` for reference lines
3. **Compact Ticks:** `tick={{ fontSize: 11 }}` for readability
4. **Legend Below Chart:** Manual legend with color dots + labels
5. **Tooltip Card:** Use ShadCN `Card` component for consistent styling

---

## 4. SHADCN UI COMPONENTS FOR FINANCIAL DASHBOARDS

### Components Used in Existing Dashboard

#### Table Pattern (from `top-performers-table.tsx`, `vn30-overview-table.tsx`)
- **Structure:** `<table>` with custom styling (no ShadCN Table component)
- **Styling:** `border-border/50`, `bg-card/50`, `hover:bg-muted/20`
- **Pagination:** Custom with `ChevronLeft/Right` icons
- **Sorting:** Custom with `ArrowUpDown/Up/Down` icons
- **Rows Per Page:** ShadCN `Select` component

#### Card Pattern (from `volume-anomaly-chart.tsx`)
```tsx
<Card>
  <CardHeader>
    <CardTitle>Title with metadata</CardTitle>
    <CardDescription>Subtitle with stats</CardDescription>
  </CardHeader>
  <CardContent>{/* Chart or table */}</CardContent>
</Card>
```

#### Select Component (Pagination)
```tsx
<Select value={String(rowsPerPage)} onValueChange={handleRowsPerPageChange}>
  <SelectTrigger className="w-[70px] h-8 text-sm">
    <SelectValue />
  </SelectTrigger>
  <SelectContent>
    <SelectItem value="10">10</SelectItem>
    <SelectItem value="20">20</SelectItem>
    <SelectItem value="50">50</SelectItem>
  </SelectContent>
</Select>
```

#### Skeleton Loading Pattern
```tsx
export function TableSkeleton() {
  return (
    <div className="space-y-4">
      {[...Array(10)].map((_, i) => (
        <div key={i} className="flex gap-4">
          <Skeleton className="h-4 w-16 rounded" />
          <Skeleton className="h-4 w-40 rounded" />
        </div>
      ))}
    </div>
  )
}
```

### Recommended Components for Volume Spike Dashboard
1. **Badge:** For anomaly level indicators (`variant="destructive"` for very_high)
2. **Collapsible:** Group stocks by severity
3. **Card:** Wrap each section (chart, table, filters)
4. **Select:** Date picker, exchange filter, min ratio selector
5. **Button:** Refresh, export, trigger collection
6. **Skeleton:** Loading states for table rows
7. **Tooltip:** Hover details on stock symbols

---

## 5. EXISTING DASHBOARD PATTERNS SUMMARY

### Layout Structure
- **Grid System:** `grid grid-cols-1 md:grid-cols-2 gap-4`
- **Spacing:** `space-y-4` for vertical stacking
- **Responsive:** Mobile-first with `md:` breakpoints

### Header Pattern (Consistent Across Components)
```tsx
<div className="flex items-center justify-between mb-4">
  <h2 className="text-lg font-semibold">Section Title</h2>
  <button onClick={refetch} disabled={isFetching}>
    <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
  </button>
</div>
```

### Color Conventions
- **Positive:** `text-green-500 dark:text-green-400`
- **Negative:** `text-red-500 dark:text-red-400`
- **Neutral:** `text-muted-foreground`
- **Primary:** `text-primary` for stock symbols
- **Borders:** `border-border/50` for subtle separation

### Number Formatting (Vietnamese Locale)
```tsx
// Billions: 1,234.5 tỷ
formatProfit(value / 1_000_000_000) + " tỷ"

// Millions: 12.34M
formatVolume(value / 1_000_000) + "M"

// Percent: +2.45%
`${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
```

---

## 6. RECOMMENDATIONS FOR VOLUME SPIKE DASHBOARD

### Component Structure
```
volume-spike-dashboard.tsx
├── Header (Title + Date Selector + Refresh)
├── Summary Cards (Total Spikes, Avg Ratio, Top Exchange)
├── Chart Section (ComposedChart with volume bars)
└── Collapsible Groups
    ├── Very High (>3x) - defaultOpen
    ├── High (2x-3x)
    └── Elevated (1.5x-2x)
```

### Data Flow
1. **Hook:** `useVolumeSpikes(date, minRatio)` with TanStack Query
2. **Grouping:** `useMemo` to group by anomaly level
3. **Sorting:** Default by volume ratio (desc)
4. **Pagination:** Per-group with shared state

### Performance Optimizations
- **Virtualization:** Consider `react-window` if >100 stocks per group
- **Memoization:** `useMemo` for expensive calculations (grouping, sorting)
- **Debounced Filters:** Use `useDebouncedValue` for search/filter inputs
- **Lazy Loading:** Load chart data only when section is expanded

---

**End of Report**
