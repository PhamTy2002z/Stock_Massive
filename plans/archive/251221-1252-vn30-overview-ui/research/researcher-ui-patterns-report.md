# UI/UX Patterns Research Report - Stock Data Tables

**Date:** 2025-12-21
**Researcher:** UI Patterns Analysis
**Scope:** Existing table components, design patterns, stock data display, color coding

---

## 1. EXISTING TABLE COMPONENTS

### 1.1 StockStatsTable Component
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/stock-stats-table.tsx`

**Pattern:** Grid-based stats display (not traditional table)
- Uses 3-column grid layout with dividers
- Responsive: `grid-cols-1 sm:grid-cols-3`
- Card wrapper: `rounded-lg border bg-card`
- Stats rows: label-value pairs with `justify-between`

```tsx
<div className="rounded-lg border bg-card overflow-hidden">
  <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x">
    <StatsRow label="Mở cửa" value={formatNumber(openPrice)} />
  </div>
</div>
```

### 1.2 ShareholdersTabContent - Full Data Table
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/shareholders-tab-content.tsx`

**Pattern:** Traditional HTML table with pagination
- Wrapper: `rounded-lg border border-border/50 bg-card/50`
- Horizontal scroll: `overflow-x-auto scrollbar-thin`
- Min-width enforcement: `min-w-[600px]`
- Sticky header styling
- Pagination controls with Select dropdown

```tsx
<table className="w-full min-w-[600px] border-collapse">
  <thead>
    <tr className="border-b border-border/50 bg-muted/30">
      <th className="py-3 px-4 text-left text-sm font-medium text-muted-foreground">
  </thead>
  <tbody>
    <tr className="border-b border-border/30 transition-colors hover:bg-muted/20">
```

### 1.3 FinanceTabContent - Financial Tables
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/finance-tab-content.tsx`

**Pattern:** Sticky column table with hierarchical rows
- Sticky left column: `sticky left-0 z-10 bg-background`
- Hierarchical indentation via `paddingLeft: ${16 + level * 16}px`
- Bold headers/summaries: `font-semibold text-foreground`
- Tabular numbers: `tabular-nums`

```tsx
<td className="sticky left-0 z-10 bg-background py-2.5 px-4 text-sm"
    style={{ paddingLeft: level ? `${16 + level * 16}px` : "16px" }}>
```

---

## 2. DESIGN SYSTEM (SHADCN + TAILWIND)

### 2.1 Card Component
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/ui/card.tsx`

**Base Pattern:**
```tsx
className="rounded-xl border bg-card text-card-foreground shadow-sm"
```

### 2.2 Utility Function
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/utils.ts`

```tsx
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

### 2.3 CSS Variables
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/globals.css`

**Chart Colors:**
- `--chart-1: 142 76% 36%` (Green for positive)
- `--chart-2: 0 84% 60%` (Red for negative)

**Dark Mode:**
- `--chart-1: 142 70% 45%` (Green adjusted)
- `--chart-2: 0 84% 60%` (Red same)

---

## 3. COLOR CODING PATTERNS

### 3.1 Price Change Colors (Green/Red)

**Pattern 1: Emerald/Red (Stock Ticker)**
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/stock-ticker-header.tsx`

```tsx
const isPositive = change >= 0
className={cn(
  "text-2xl font-semibold tabular-nums",
  isPositive ? "text-emerald-500 dark:text-emerald-400"
             : "text-red-500 dark:text-red-400"
)}
```

**Pattern 2: Green/Red (Index Cards)**
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/stock-index-card.tsx`

```tsx
const isPositive = change >= 0
// Icons
<TrendingUp className="h-3.5 w-3.5 text-green-500 dark:text-green-400" />
<TrendingDown className="h-3.5 w-3.5 text-red-500 dark:text-red-400" />

// Text
className={cn(
  "text-sm font-medium tabular-nums",
  isPositive ? "text-green-500 dark:text-green-400"
             : "text-red-500 dark:text-red-400"
)}
```

**Pattern 3: Sector Performance with Background**
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/sector-performance.tsx`

```tsx
// Text color based on actual value
const colorClass = isPositive
  ? "text-green-600 dark:text-green-400"
  : "text-red-600 dark:text-red-400"

// Badge background based on list type
const bgClass = isGainerList
  ? "bg-green-500/10 dark:bg-green-400/10"
  : "bg-red-500/10 dark:bg-red-400/10"
```

### 3.2 Sparkline Component
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/ui/sparkline.tsx`

```tsx
const strokeColor = positive
  ? "hsl(var(--chart-1))"
  : "hsl(var(--chart-2))"
```

---

## 4. STOCK DATA DISPLAY PATTERNS

### 4.1 StockIndexCard - Market Indices
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/stock-index-card.tsx`

**Layout:**
- Card with hover effect: `hover:shadow-md transition-shadow`
- Flex layout: info left, sparkline right
- Value formatting: Vietnamese locale `toLocaleString("vi-VN")`
- Tabular numbers: `tabular-nums` class

```tsx
<Card className="p-5 hover:shadow-md transition-shadow cursor-pointer">
  <div className="flex items-start justify-between gap-4">
    <div className="flex-1 min-w-0">
      <p className="text-2xl font-semibold tabular-nums">{formattedValue}</p>
      <div className="flex items-center gap-1.5">
        <TrendingUp className="h-3.5 w-3.5 text-green-500" />
        <span className="text-sm font-medium tabular-nums">+1.23%</span>
      </div>
    </div>
    <Sparkline data={chartData} width={80} height={40} />
  </div>
</Card>
```

### 4.2 Market Indices Grid
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/market-indices.tsx`

**Grid Pattern:**
```tsx
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
  {indices.map((index) => <StockIndexCard key={index.symbol} {...index} />)}
</div>
```

### 4.3 Sector Performance - Ranked Lists
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/sector-performance.tsx`

**Pattern:** Two-column grid with ranked items
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
  {/* Top 5 Gainers */}
  <div className="rounded-xl border bg-card">
    <div className="divide-y">
      {topGainers.map((sector, index) => (
        <div className="flex items-center gap-3 p-3 hover:bg-muted/30">
          <div className="w-7 h-7 rounded-full bg-green-500/10">
            {rank}
          </div>
          <div className="flex-1">{sector.icb_name}</div>
          <div className="text-green-600">+2.45%</div>
        </div>
      ))}
    </div>
  </div>
</div>
```

---

## 5. API INTEGRATION PATTERNS

### 5.1 API Client
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/api.ts`

**Key Interfaces:**
```tsx
export interface MarketIndex {
  symbol: string
  name: string
  value: number
  change: number
  changePercent: number
}

export interface StockDetail {
  symbol: string
  price: number | null
  change: number | null
  change_pct: number | null
  vn30_rank: number | null  // VN30 ranking field exists!
}
```

### 5.2 React Query Hook Pattern
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-sector-performance.ts`

```tsx
export function useSectorPerformance() {
  const query = useQuery({
    queryKey: queryKeys.sectorPerformance,
    queryFn: fetchSectorPerformance,
    staleTime: 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  })

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  }
}
```

---

## 6. KEY RECOMMENDATIONS FOR VN30 TABLE

### 6.1 Component Structure
- Use traditional HTML `<table>` like ShareholdersTabContent
- Wrapper: `rounded-lg border border-border/50 bg-card/50`
- Enable horizontal scroll: `overflow-x-auto scrollbar-thin`
- Min-width: `min-w-[800px]` for VN30 columns

### 6.2 Color Coding
- Positive: `text-green-500 dark:text-green-400`
- Negative: `text-red-500 dark:text-red-400`
- Icons: `<TrendingUp />` and `<TrendingDown />` from lucide-react

### 6.3 Formatting
- Numbers: `tabular-nums` class
- Vietnamese locale: `toLocaleString("vi-VN")`
- Hover states: `hover:bg-muted/20 transition-colors`

### 6.4 Data Fetching
- Create hook: `use-vn30-overview.ts`
- Use React Query with auto-refresh (5 min interval)
- Filter stocks where `vn30_rank !== null`

---

## UNRESOLVED QUESTIONS

1. Does backend have dedicated VN30 endpoint or filter by vn30_rank?
2. Should VN30 table support sorting/filtering client-side?
3. Pagination needed or show all 30 stocks at once?
4. Real-time updates via WebSocket or polling only?
