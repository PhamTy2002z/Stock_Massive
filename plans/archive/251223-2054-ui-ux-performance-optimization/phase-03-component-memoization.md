# Phase 3: Component Memoization

**Parent Plan:** [plan.md](./plan.md)
**Dependencies:** None (can run in parallel with Phase 1-2)

---

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-23 |
| Priority | P2 |
| Effort | 1.5h |
| Status | completed |

**Goal:** Prevent unnecessary re-renders by memoizing table rows and chart components.

---

## Requirements

1. Wrap table row components with `React.memo`
2. Extract inline handlers with `useCallback`
3. Wrap chart components with `React.memo`
4. Use custom comparison for complex props where needed

---

## Related Files

| File | Action | Priority |
|------|--------|----------|
| `apps/web/src/components/dashboard/vn30-overview-table.tsx` | Extract row, add memo | High |
| `apps/web/src/components/dashboard/financial-statements-table.tsx` | Extract row, add memo | High |
| `apps/web/src/components/dashboard/volume-spike-chart.tsx` | Add memo | Medium |
| `apps/web/src/components/dashboard/volume-spike-treemap.tsx` | Add memo | Medium |
| `apps/web/src/components/dashboard/stock-index-card.tsx` | Add memo | Medium |

---

## Implementation Steps

### Step 1: Extract and Memoize VN30 Table Row

In `vn30-overview-table.tsx`, extract the table row to a separate memoized component:

```tsx
// Add at top of file
import { memo, useCallback } from "react"

// Extract row component BEFORE the main component
interface VN30RowProps {
  stock: {
    symbol: string
    company_name: string
    price: number | null
    change_pct: number | null
    volume: number | null
    market_cap: number | null
  }
}

const VN30Row = memo(function VN30Row({ stock }: VN30RowProps) {
  const isPositive = (stock.change_pct ?? 0) >= 0
  const changeColor = isPositive
    ? "text-green-500 dark:text-green-400"
    : "text-red-500 dark:text-red-400"

  return (
    <tr className="border-b border-border/30 transition-colors hover:bg-muted/20">
      <td className="py-3 px-4 text-sm font-semibold text-foreground">
        {stock.symbol}
      </td>
      <td className="py-3 px-4 text-sm text-foreground/90">
        {stock.company_name}
      </td>
      <td className="py-3 px-4 text-sm text-right tabular-nums font-medium text-foreground">
        {formatPrice(stock.price)}
      </td>
      <td className="py-3 px-4 text-sm text-right tabular-nums">
        <div className="flex items-center justify-end gap-1">
          {stock.change_pct !== null && (
            isPositive ? (
              <TrendingUp className={cn("h-3.5 w-3.5", changeColor)} />
            ) : (
              <TrendingDown className={cn("h-3.5 w-3.5", changeColor)} />
            )
          )}
          <span className={cn("font-medium", changeColor)}>
            {formatPercent(stock.change_pct)}
          </span>
        </div>
      </td>
      <td className="py-3 px-4 text-sm text-right tabular-nums text-foreground/90">
        {formatVolume(stock.volume)}
      </td>
      <td className="py-3 px-4 text-sm text-right tabular-nums text-foreground/90">
        {formatMarketCap(stock.market_cap)}
      </td>
    </tr>
  )
})

// In the main component, update the tbody:
<tbody>
  {currentData.map((stock) => (
    <VN30Row key={stock.symbol} stock={stock} />
  ))}
</tbody>
```

### Step 2: Memoize VN30 Table Handlers

```tsx
// In VN30OverviewTable component, memoize handlers:
const toggleSort = useCallback(() => {
  setSortDirection((prev) => {
    if (prev === null) return "desc"
    if (prev === "desc") return "asc"
    return null
  })
  setCurrentPage(1)
}, [])

const goToPage = useCallback((page: number) => {
  setCurrentPage((curr) => {
    if (page >= 1 && page <= totalPages) return page
    return curr
  })
}, [totalPages])

const handleRowsPerPageChange = useCallback((value: string) => {
  setRowsPerPage(Number(value))
  setCurrentPage(1)
}, [])

const handleRefetch = useCallback(() => {
  refetch()
}, [refetch])
```

### Step 3: Extract and Memoize Financial Statements Row

Similar pattern for `financial-statements-table.tsx`:

```tsx
import { memo, useCallback } from "react"

interface FinancialRowProps {
  statement: FinancialStatementItem
  onClick?: () => void
}

const FinancialRow = memo(function FinancialRow({ statement, onClick }: FinancialRowProps) {
  // ... row render logic
})
```

### Step 4: Memoize Chart Components

For `volume-spike-chart.tsx`:

```tsx
import { memo } from "react"

interface VolumeSpikeChartProps {
  data: VolumeSpikeData[]
  className?: string
}

export const VolumeSpikeChart = memo(function VolumeSpikeChart({
  data,
  className
}: VolumeSpikeChartProps) {
  // ... existing component logic
})
```

For `volume-spike-treemap.tsx`:

```tsx
import { memo } from "react"

export const VolumeSpikeTreemap = memo(function VolumeSpikeTreemap({
  data,
  className
}: VolumeSpikeTreemapProps) {
  // ... existing component logic
})
```

### Step 5: Memoize Stock Index Card

For `stock-index-card.tsx`:

```tsx
import { memo } from "react"

interface StockIndexCardProps {
  index: MarketIndex
  className?: string
}

export const StockIndexCard = memo(function StockIndexCard({
  index,
  className
}: StockIndexCardProps) {
  // ... existing component logic
})
```

---

## Success Criteria

- [x] VN30 table rows wrapped in `React.memo`
- [x] Financial statements rows wrapped in `React.memo`
- [x] All chart components wrapped in `React.memo`
- [x] Stock index cards wrapped in `React.memo`
- [x] Inline handlers extracted to `useCallback`
- [ ] React DevTools Profiler shows reduced re-renders (manual verification)
- [x] No TypeScript errors

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Over-memoization | Low | Only memo expensive components |
| Props changing frequently | Low | Check props are primitives or stable refs |
| Memory overhead | Very Low | React.memo is cheap |

---

## Testing Checklist

1. Install React DevTools Profiler
2. Record render cycles during data refresh
3. Verify row components maintain identity (no flash in Profiler)
4. Check chart components don't re-render on unrelated state changes
