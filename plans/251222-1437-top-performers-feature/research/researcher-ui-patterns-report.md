# UI/UX Patterns Research Report
**Date:** 2025-12-22
**Focus:** Data tables, dashboard components, TanStack Query, loading patterns

---

## Table Component Structure

### Base Pattern (VN30OverviewTable)
**File:** `apps/web/src/components/dashboard/vn30-overview-table.tsx`

**Architecture:**
- Native HTML `<table>` wrapped in responsive container
- Client component (`"use client"`)
- State management: `useState` for pagination, sorting
- Data transformation: `useMemo` for computed data
- Conditional rendering for loading/error/empty states

**Key Features:**
```tsx
// Responsive wrapper
<div className="rounded-lg border border-border/50 bg-card/50 overflow-hidden">
  <div className="overflow-x-auto scrollbar-thin">
    <table className="w-full min-w-[800px] border-collapse">
```

**Styling:**
- Border: `border-border/50`
- Background: `bg-card/50`, `bg-muted/30` (header), `bg-muted/20` (hover)
- Text colors: `text-foreground`, `text-muted-foreground`
- Dark mode: Automatic via Tailwind CSS classes

---

## Data Fetching Pattern (TanStack Query)

### Hook Structure
**File:** `apps/web/src/hooks/use-vn30-overview.ts`

**Pattern:**
```tsx
export function useVN30Overview() {
  const query = useQuery({
    queryKey: queryKeys.vn30Overview,
    queryFn: fetchVN30Overview,
    staleTime: 10 * 1000,              // 10s
    refetchInterval: 10 * 1000,        // Auto-refresh every 10s
    refetchIntervalInBackground: true, // Keep fresh when tab inactive
    refetchOnWindowFocus: true,        // Refresh on tab focus
    refetchOnMount: true,              // Always fetch on mount
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    refetch: query.refetch,
  }
}
```

**Key Observations:**
- 10s auto-refresh interval is standard
- Expose `isFetching` for refresh UI states
- Centralized `queryKeys` from `@/lib/query-keys`
- API functions from `@/lib/api`

---

## Loading/Skeleton Patterns

### Loading States Hierarchy
1. **Initial load:** Show skeleton (`isLoading && !data`)
2. **Background refresh:** Show spinner on refresh button (`isFetching`)
3. **Error:** Error card with retry button
4. **Empty:** Empty state card

### Skeleton Implementation
**Pattern:** `VN30OverviewTableSkeleton`

```tsx
// Skeleton row structure
<div className="flex gap-4">
  <div className="h-4 w-12 rounded bg-muted animate-pulse" />
  <div className="h-4 w-40 rounded bg-muted animate-pulse" />
  // ... more columns
</div>
```

**Design:**
- Match table structure (header + 10 rows)
- `bg-muted animate-pulse` for skeleton blocks
- Same spacing/layout as real table
- Footer pagination skeleton

### Refresh UI Pattern
```tsx
<RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
```

---

## Sorting/Filtering Patterns

### Client-Side Sorting
```tsx
const [sortDirection, setSortDirection] = useState<SortDirection>(null)

// Three-state toggle: null → desc → asc → null
const toggleSort = () => {
  setSortDirection((prev) => {
    if (prev === null) return "desc"
    if (prev === "desc") return "asc"
    return null
  })
  setCurrentPage(1) // Reset to page 1 when sorting
}

// Sort with useMemo
const stocks = useMemo(() => {
  const rawStocks = data?.stocks ?? []
  if (sortDirection === null) return rawStocks
  return [...rawStocks].sort((a, b) => {
    const aVal = a.change_pct ?? -Infinity
    const bVal = b.change_pct ?? -Infinity
    return sortDirection === "asc" ? aVal - bVal : bVal - aVal
  })
}, [data?.stocks, sortDirection])
```

**UI:**
- Clickable header button with icons: `ArrowUpDown`, `ArrowDown`, `ArrowUp`
- Visual feedback for sort state

---

## Pagination Pattern

### State Management
```tsx
const [currentPage, setCurrentPage] = useState(1)
const [rowsPerPage, setRowsPerPage] = useState(10)

const totalItems = stocks.length
const totalPages = Math.max(1, Math.ceil(totalItems / rowsPerPage))
const startIndex = (currentPage - 1) * rowsPerPage
const endIndex = Math.min(startIndex + rowsPerPage, totalItems)

const currentData = useMemo(() => {
  return stocks.slice(startIndex, endIndex)
}, [stocks, startIndex, endIndex])
```

### Pagination UI
**Components:**
- Row selector: `Select` component (10/20/30 options)
- Navigation: `ChevronLeft`, `ChevronRight` buttons
- Info text: `{startIndex + 1}-{endIndex} trên {totalItems} cổ phiếu`

---

## Responsive Design Approach

**Strategy:**
1. Horizontal scroll for mobile: `overflow-x-auto scrollbar-thin`
2. Min-width constraint: `min-w-[800px]` on table
3. Responsive footer: flex layout adapts to screen size
4. Whitespace control: `whitespace-nowrap` for critical text

---

## Utility Functions

### Formatters
```tsx
formatPrice(value: number | null): string     // Vietnamese locale, no decimals
formatPercent(value: number | null): string   // ±X.XX%
formatVolume(value: number | null): string    // X.XXM (millions)
formatMarketCap(value: number | null): string // X,XXX tỷ
```

### Null Handling
All formatters return `"-"` for null values

---

## Color System

**Change Indicators:**
- Positive: `text-green-500 dark:text-green-400`
- Negative: `text-red-500 dark:text-red-400`
- Icons: `TrendingUp`, `TrendingDown`

**States:**
- Error: `border-destructive/50 bg-destructive/10 text-destructive`
- Empty: `border-border/50 bg-card/50 text-muted-foreground`

---

## Recommended Patterns for Top Performers

1. **Reuse table structure** with responsive wrapper
2. **TanStack Query hook** with 10s auto-refresh
3. **Export skeleton component** for consistency
4. **Client-side sorting** on multiple columns
5. **Pagination** with same UI components
6. **RefreshCw button** with spin animation
7. **Three-state error hierarchy** (loading/error/empty)
8. **Vietnamese locale** formatting
9. **Color-coded** change indicators

---

## Unresolved Questions
None - all patterns clear and consistent across codebase.
