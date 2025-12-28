# Design Guidelines - Stock Massive

## Design Philosophy: Modern + Clean

**This is the STANDARD design style for all future development.**

Stock Massive follows a Modern + Clean design philosophy characterized by:
- Clean visual hierarchy with ample whitespace
- HSL-based color system with CSS variables
- Consistent component patterns via ShadCN/UI
- Smooth, purposeful animations
- Full dark/light theme support
- Mobile-first responsive design

---

## Color Palette (MANDATORY)

### Primary Colors

**4 Main Colors**: Black, Grey, White, Orange

```css
:root {
  /* Primary Accent - Orange */
  --accent-orange: 25 95% 53%;         /* #FF6B00 - CTAs, highlights, important indicators */

  /* Base Colors */
  --background: 210 20% 98%;           /* Off-white background */
  --foreground: 222 47% 11%;           /* Dark blue-gray text */

  /* Cards & Surfaces */
  --card: 0 0% 100%;                   /* Pure white cards */
  --card-foreground: 222 47% 11%;

  /* Greys - UI Elements */
  --muted: 210 40% 96%;
  --muted-foreground: 215 16% 47%;
  --border: 214 32% 91%;
  --input: 214 32% 91%;
}

.dark {
  --accent-orange: 25 95% 53%;         /* Same orange in dark mode */

  --background: 222 47% 6%;            /* Deep blue-black */
  --foreground: 210 40% 98%;           /* Off-white text */

  --card: 222 47% 8%;                  /* Slightly lighter cards */
  --card-foreground: 210 40% 98%;

  --muted: 217 33% 17%;
  --muted-foreground: 215 20% 65%;
  --border: 217 33% 17%;
  --input: 217 33% 17%;
}
```

### Semantic Colors

**Keep Green/Red for Stock Up/Down**

```css
:root {
  /* Stock-specific colors */
  --stock-up: 142 76% 36%;             /* Green - price increase */
  --stock-down: 0 84% 60%;             /* Red - price decrease */

  /* Destructive actions */
  --destructive: 0 84% 60%;
  --destructive-foreground: 0 0% 98%;
}

.dark {
  --stock-up: 142 70% 45%;
  --stock-down: 0 84% 60%;

  --destructive: 0 63% 31%;
  --destructive-foreground: 210 40% 98%;
}
```

### Usage Guidelines

```tsx
// Primary CTAs and highlights - Use Orange
<Button className="bg-[hsl(var(--accent-orange))] hover:bg-[hsl(var(--accent-orange))]/90">
  Add to Watchlist
</Button>

// Stock price indicators - Use Green/Red
<span className="text-green-600 dark:text-green-400">↑ 2.5%</span>
<span className="text-red-600 dark:text-red-400">↓ 1.2%</span>

// Background/UI - Use Black/Grey/White
<Card className="bg-card border-border">
  <p className="text-muted-foreground">Secondary text</p>
</Card>
```

---

## UX Information Architecture

**Pattern: Overview → Details → Drill-down**

Every dashboard and data view MUST follow this hierarchy:

### Level 1: Overview (Top Priority)
- Summary KPIs displayed prominently
- High-level metrics at a glance
- Quick insights without scrolling

```tsx
// Example: Dashboard overview
<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
  <KPICard title="Market Cap" value="150.5 ty" delta="+2.3%" />
  <KPICard title="Volume" value="1.2M" delta="-5.1%" />
  <KPICard title="P/E Ratio" value="12.5" benchmark="Industry: 15.2" />
  <KPICard title="ROE" value="18.3%" trend="up" />
</div>
```

### Level 2: Details (Click to Expand)
- Detailed breakdown of each KPI
- Comparison data and context
- Additional metrics not shown in overview

```tsx
// Example: Click KPI to show modal with details
<Dialog>
  <DialogTrigger asChild>
    <button>View Details</button>
  </DialogTrigger>
  <DialogContent>
    <DetailedBreakdown />
  </DialogContent>
</Dialog>
```

### Level 3: Drill-down (Deep Analysis)
- Full data tables with filters
- Historical trends
- Export and analysis tools

```tsx
// Example: Deep analysis page
<Tabs defaultValue="history">
  <TabsList>
    <TabsTrigger value="history">Historical Data</TabsTrigger>
    <TabsTrigger value="analysis">Analysis</TabsTrigger>
  </TabsList>
  <TabsContent value="history">
    <DataTable data={data} exportable sortable filterable />
  </TabsContent>
</Tabs>
```

---

## KPI Requirements (Contextual Data)

**Every KPI MUST answer these questions:**

1. **Is it good or bad?** - Visual indicator (color, icon)
2. **Compared to what/when?** - Delta, benchmark, comparison
3. **What's the impact?** - Context, interpretation, actionable insight

### Mandatory Elements

```tsx
interface KPICardProps {
  label: string           // KPI name
  value: string | number  // Main metric
  unit: string           // %, VND, ms, etc (REQUIRED)
  delta?: {              // vs previous period (REQUIRED if applicable)
    value: number
    period: string       // "vs yesterday", "vs last month"
    direction: "up" | "down" | "neutral"
  }
  benchmark?: {          // Comparison context
    value: number
    label: string        // "Industry avg", "VN30 avg"
  }
  timeRange: string      // "Last 7 days", "YTD", "Q4 2024" (REQUIRED)
  status?: "good" | "bad" | "neutral"  // Visual indicator
}
```

### Example Implementation

```tsx
<Card>
  <CardHeader>
    <CardTitle className="text-sm text-muted-foreground">
      Net Profit Margin
    </CardTitle>
  </CardHeader>
  <CardContent>
    <div className="flex items-baseline justify-between">
      <span className="text-3xl font-bold tabular-nums">18.3%</span>
      <Badge variant={delta > 0 ? "success" : "destructive"}>
        {delta > 0 ? "↑" : "↓"} {Math.abs(delta)}%
      </Badge>
    </div>
    <p className="mt-2 text-xs text-muted-foreground">
      vs Q3 2024: +2.1% | Industry avg: 15.2%
    </p>
    <p className="mt-1 text-xs text-muted-foreground">
      Time range: Q4 2024
    </p>
  </CardContent>
</Card>
```

---

## Data Visualization Guidelines

**DO NOT use charts just for aesthetics!** Choose chart types based on data purpose:

| Purpose | Recommended Chart | Use Case |
|---------|-------------------|----------|
| Trend over time | Line / Area | Stock price history, volume trends |
| Comparison | Bar (horizontal/vertical) | Compare stocks, sectors, quarters |
| Distribution | Stacked bar | Market share, portfolio allocation |
| Anomaly detection | Heatmap | Identify volume spikes, unusual patterns |
| Percentage/Composition | Donut (sparingly) | Portfolio composition (max 5-7 segments) |
| Ranking | Table + inline bar | Top gainers/losers, financial statements |
| Correlation | Scatter plot | P/E vs ROE, risk vs return |

### Chart Implementation Standards

```tsx
// Line chart - Trend over time
<LineChart data={data}>
  <XAxis dataKey="date" />
  <YAxis />
  <Line dataKey="price" stroke="hsl(var(--accent-orange))" />
  <Tooltip />
</LineChart>

// Bar chart - Comparison
<BarChart data={data}>
  <XAxis dataKey="symbol" />
  <YAxis />
  <Bar dataKey="volume" fill="hsl(var(--accent-orange))" />
  <Tooltip />
</BarChart>

// Table with inline bars - Ranking (PREFERRED for rankings)
<Table>
  <TableBody>
    {data.map(row => (
      <TableRow key={row.symbol}>
        <TableCell>{row.symbol}</TableCell>
        <TableCell className="tabular-nums">{row.value}</TableCell>
        <TableCell className="w-[200px]">
          <div className="h-2 rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-[hsl(var(--accent-orange))]"
              style={{ width: `${(row.value / maxValue) * 100}%` }}
            />
          </div>
        </TableCell>
      </TableRow>
    ))}
  </TableBody>
</Table>
```

---

## Filter & Control Patterns (Interactive Dashboard)

### Required Filters

**Global Filters** (affect entire dashboard):
- Date range picker (default: Last 30 days)
- Exchange selector (HOSE, HNX, UPCOM)

**Local Filters** (affect single widget):
- Symbol search
- Sector/Industry
- Sort by (price, volume, change%)

### Implementation Pattern

```tsx
// Global filter - affects entire page
<div className="mb-6 flex items-center gap-4">
  <DateRangePicker
    value={dateRange}
    onChange={setDateRange}
  />
  <Select value={exchange} onChange={setExchange}>
    <SelectItem value="all">All Exchanges</SelectItem>
    <SelectItem value="HOSE">HOSE</SelectItem>
    <SelectItem value="HNX">HNX</SelectItem>
  </Select>
</div>

// Local filter - inside specific card
<Card>
  <CardHeader>
    <div className="flex items-center justify-between">
      <CardTitle>Top Gainers</CardTitle>
      <Select value={sortBy} onChange={setSortBy}>
        <SelectItem value="price">Price</SelectItem>
        <SelectItem value="volume">Volume</SelectItem>
      </Select>
    </div>
  </CardHeader>
</Card>
```

### Sensible Defaults

- Date range: Last 30 days (trading days only)
- Exchange: All
- Sort: Descending by relevance
- Limit: Top 20 items
- Pagination: 25 items per page

---

## Drill-down & Detail on Demand

**Every data point MUST be clickable for more details**

### Interaction Patterns

```tsx
// KPI card - click to view details
<Card
  className="cursor-pointer hover:border-[hsl(var(--accent-orange))] transition-colors"
  onClick={() => setShowDetails(true)}
>
  <KPICard {...props} />
</Card>

// Chart - click data point for breakdown
<LineChart>
  <Line
    dataKey="value"
    onClick={(data) => setSelectedDate(data.date)}
  />
</LineChart>

// Table - click row for detail page
<TableRow
  className="cursor-pointer hover:bg-muted"
  onClick={() => router.push(`/stocks/${row.symbol}`)}
>
  <TableCell>{row.symbol}</TableCell>
  <TableCell>{row.price}</TableCell>
</TableRow>
```

### Table Requirements

**Every table MUST support:**
- Sort (ascending/descending)
- Search/filter
- Pagination (for >25 rows)
- Click row → navigate to detail page

```tsx
<DataTable
  data={data}
  columns={columns}
  enableSorting
  enableFiltering
  enablePagination
  pageSize={25}
  onRowClick={(row) => router.push(`/detail/${row.id}`)}
/>
```

---

## Visual Hierarchy (Dashboard = Scan, Not Read)

**Users should understand the dashboard in 3 seconds without reading**

### Size Hierarchy

1. **KPIs** - Largest (3xl text)
2. **Secondary metrics** - Medium (xl text)
3. **Charts** - Fill remaining space
4. **Labels/captions** - Smallest (xs text)

### Spacing Grid

Use consistent spacing based on 8px grid:
- `gap-2` (8px) - Tight grouping
- `gap-4` (16px) - Standard spacing
- `gap-6` (24px) - Section separation
- `gap-8` (32px) - Major sections

### Example Layout

```tsx
<div className="space-y-8">
  {/* KPIs - Most prominent */}
  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
    <KPICard /> {/* Large text-3xl font-bold */}
  </div>

  {/* Charts - Secondary */}
  <div className="grid gap-6 lg:grid-cols-2">
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Volume Trend</CardTitle>
      </CardHeader>
      <CardContent>
        <LineChart />
      </CardContent>
    </Card>
  </div>

  {/* Tables - Tertiary */}
  <Card>
    <CardHeader>
      <CardTitle className="text-lg">Detailed Data</CardTitle>
    </CardHeader>
    <CardContent>
      <DataTable />
    </CardContent>
  </Card>
</div>
```

---

## Performance UX (Heavy Data = Poor UX)

**Loading states are MANDATORY, not optional**

### Required Loading States

1. **Skeleton Loading** (preferred for charts/cards)
2. **Progressive Loading** (load critical data first)
3. **Empty State** (with guidance)

```tsx
// Skeleton loading
{isLoading ? (
  <Card>
    <CardHeader>
      <Skeleton className="h-6 w-[200px]" />
    </CardHeader>
    <CardContent>
      <Skeleton className="h-[200px] w-full" />
    </CardContent>
  </Card>
) : (
  <ChartCard data={data} />
)}

// Progressive loading
<div>
  <KPICards data={criticalData} /> {/* Load first */}
  <Suspense fallback={<ChartSkeleton />}>
    <Charts data={secondaryData} /> {/* Load after */}
  </Suspense>
</div>

// Empty state with guidance
{data.length === 0 && !isLoading && (
  <Card>
    <CardContent className="py-12 text-center">
      <p className="text-muted-foreground">No data available</p>
      <p className="mt-2 text-sm text-muted-foreground">
        Try adjusting your filters or date range
      </p>
    </CardContent>
  </Card>
)}
```

---

## Feedback & System State

**Users should always know what's happening**

### Required States

1. **Loading** - Skeleton or spinner
2. **Refresh** - Visual indicator during background refresh
3. **Error** - Clear error message with recovery action
4. **Last Updated** - Timestamp for data freshness

```tsx
// Last updated timestamp
<div className="flex items-center gap-2 text-xs text-muted-foreground">
  <Clock className="h-3 w-3" />
  <span>Last updated: {formatDistanceToNow(lastUpdated)} ago</span>
  <Button
    variant="ghost"
    size="icon"
    onClick={refetch}
    disabled={isRefetching}
  >
    <RefreshCw className={cn("h-3 w-3", isRefetching && "animate-spin")} />
  </Button>
</div>

// Error state with retry
{error && (
  <Alert variant="destructive">
    <AlertCircle className="h-4 w-4" />
    <AlertTitle>Failed to load data</AlertTitle>
    <AlertDescription>
      {error.message}
      <Button
        variant="outline"
        size="sm"
        className="ml-4"
        onClick={retry}
      >
        Try Again
      </Button>
    </AlertDescription>
  </Alert>
)}

// Toast on filter changes
const handleFilterChange = (newFilter) => {
  setFilter(newFilter)
  toast.success("Filter applied", {
    description: `Showing ${filteredData.length} results`
  })
}
```

---

## Table UX Standards

**Every production table MUST have these features:**

### Standard Table Requirements

```tsx
interface StandardTableProps {
  // Required features
  data: any[]
  columns: ColumnDef[]
  stickyHeader?: boolean      // Default: true
  enableSorting?: boolean     // Default: true
  enableFiltering?: boolean   // Default: true
  freezeColumns?: string[]    // Column IDs to freeze
  enableExport?: boolean      // Default: true
  exportFormats?: ("csv" | "xlsx")[]  // Default: ["csv"]

  // Optional
  pagination?: {
    pageSize: number          // Default: 25
    pageSizeOptions: number[] // Default: [10, 25, 50, 100]
  }
  onRowClick?: (row: any) => void
}
```

### Implementation Example

```tsx
<DataTable
  data={stocks}
  columns={[
    { header: "Symbol", accessorKey: "symbol", frozen: true },
    { header: "Price", accessorKey: "price", sortable: true },
    { header: "Change%", accessorKey: "change", sortable: true },
  ]}
  stickyHeader
  enableSorting
  enableFiltering
  freezeColumns={["symbol"]}
  enableExport
  exportFormats={["csv", "xlsx"]}
  pagination={{
    pageSize: 25,
    pageSizeOptions: [10, 25, 50, 100]
  }}
  onRowClick={(row) => router.push(`/stocks/${row.symbol}`)}
/>
```

---

## Typography (Unchanged)

### Font Stack
- **Primary**: System fonts (Inter recommended for web)
- **Monospace**: For numbers and code

### Scale

```tsx
// Headings
<h1 className="text-3xl font-semibold">Page Title</h1>
<h2 className="text-2xl font-semibold">Section Title</h2>
<h3 className="text-xl font-semibold">Subsection</h3>
<h4 className="text-lg font-medium">Card Title</h4>

// Body
<p className="text-base">Regular text</p>
<p className="text-sm text-muted-foreground">Secondary text</p>
<p className="text-xs text-muted-foreground">Caption/label</p>

// Numbers (tabular for alignment)
<span className="tabular-nums font-semibold">1,234,567</span>
```

---

## Component Patterns (Unchanged)

### Cards (Primary Container)

```tsx
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"

// Standard card
<Card>
  <CardHeader>
    <CardTitle>Stock Overview</CardTitle>
  </CardHeader>
  <CardContent>
    {/* Content */}
  </CardContent>
</Card>

// Stat card (compact)
<div className="rounded-lg border bg-card p-3">
  <p className="text-xs text-muted-foreground">Label</p>
  <p className="mt-1 text-sm font-semibold tabular-nums">Value</p>
</div>
```

### Buttons

```tsx
import { Button } from "@/components/ui/button"

<Button>Primary Action</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="destructive">Delete</Button>
<Button variant="ghost">Subtle</Button>
<Button variant="outline">Outlined</Button>

// With icon
<Button>
  <PlusIcon className="mr-2 h-4 w-4" />
  Add Stock
</Button>

// CTA with orange accent
<Button className="bg-[hsl(var(--accent-orange))] hover:bg-[hsl(var(--accent-orange))]/90">
  Add to Watchlist
</Button>
```

### Skeleton Loading

```tsx
import { Skeleton } from "@/components/ui/skeleton"

// Text skeleton
<Skeleton className="h-4 w-[200px]" />

// Card skeleton
<div className="space-y-3">
  <Skeleton className="h-8 w-full" />
  <Skeleton className="h-4 w-3/4" />
  <Skeleton className="h-4 w-1/2" />
</div>

// Stock card skeleton
<Card>
  <CardContent className="p-4">
    <Skeleton className="h-6 w-20 mb-2" />
    <Skeleton className="h-8 w-32" />
  </CardContent>
</Card>
```

---

## Animation Patterns (Unchanged)

### Sidebar Transition

```css
.sidebar-transition {
  transition-property: width, left, right, margin;
  transition-duration: 300ms;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  will-change: width, left, right, margin;
}

/* GPU acceleration */
[data-sidebar="sidebar"] {
  transform: translateZ(0);
  backface-visibility: hidden;
}
```

### Stock Detail Enter Animation

```css
.stock-detail-enter {
  animation: stockDetailFadeIn 0.3s ease-out;
}

@keyframes stockDetailFadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

---

## Best Practices Summary

1. **Use Orange for CTAs**: All primary actions use orange accent
2. **Green/Red for Stock Data**: Semantic colors for price movements
3. **Black/Grey/White for UI**: Base colors for structure
4. **Overview → Details → Drill-down**: Information architecture pattern
5. **KPIs need context**: Unit, delta, benchmark, time range
6. **Charts serve purpose**: Choose based on data type, not aesthetics
7. **Global vs Local filters**: Clear separation
8. **Every data point clickable**: Enable drill-down
9. **Loading states mandatory**: Skeleton, progressive, empty states
10. **Tables are fully-featured**: Sort, filter, freeze, export
11. **Dashboard = Scan**: Visual hierarchy, not reading
12. **Feedback always visible**: Loading, refresh, error, last updated

---

## File Organization (Unchanged)

```
components/
├── ui/                    # ShadCN base components
│   ├── button.tsx
│   ├── card.tsx
│   ├── skeleton.tsx
│   └── ...
├── dashboard/             # Feature-specific components
│   ├── market-indices.tsx
│   ├── stock-detail-panel.tsx
│   ├── stock-ticker-header.tsx
│   └── ...
├── layout/                # Layout components
│   ├── app-sidebar.tsx
│   ├── dashboard-header.tsx
│   └── dashboard-layout.tsx
└── providers/             # Context providers
    └── theme-provider.tsx
```
