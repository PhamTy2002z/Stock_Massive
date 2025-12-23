# Phase 2: Frontend - Exchange Filter UI

## Context Links

- [Main Plan](./plan.md)
- [Phase 1 - Backend](./phase-01-backend-exchange-normalization.md)
- Table Component: `apps/web/src/components/dashboard/financial-statements-table.tsx`
- Hook: `apps/web/src/hooks/use-financial-statements.ts`
- Page: `apps/web/src/app/analytics/financial-statements/page.tsx`

## Overview

- **Priority**: P0
- **Status**: Complete
- **Description**: Add exchange filter dropdown and period selector to FinancialStatementsTable

## Key Insights

- Hook already supports `exchange` param but UI doesn't pass it
- Current fetch: `useFinancialStatements(100)` - no filter
- Target: `useFinancialStatements(50, selectedExchange)` with HOSE+HNX default
- ShadCN Select component available

## Requirements

### Functional
- Exchange filter dropdown: All | HOSE | HNX
- Default: Show HOSE + HNX combined (exclude UPCOM)
- Limit: 50 records (not 100)
- Filter persists during pagination

### Non-Functional
- Responsive design
- Consistent with existing UI patterns

## Architecture

```
FinancialStatementsTable
├── Filter Bar (NEW)
│   ├── Exchange Select: All | HOSE | HNX
│   └── Period Info (existing)
├── Data Table (existing)
└── Pagination (existing)
```

## Related Code Files

| Action | File |
|--------|------|
| MODIFY | `apps/web/src/components/dashboard/financial-statements-table.tsx` |
| NO CHANGE | `apps/web/src/hooks/use-financial-statements.ts` |
| NO CHANGE | `apps/web/src/lib/api.ts` |

## Implementation Steps

### Step 1: Add Exchange State

At top of `FinancialStatementsTable` component:

```tsx
// Exchange filter options
type ExchangeFilter = "all" | "HOSE" | "HNX"

export function FinancialStatementsTable({ className }: FinancialStatementsTableProps) {
  const [exchangeFilter, setExchangeFilter] = useState<ExchangeFilter>("all")

  // Map "all" to undefined for API, pass HOSE/HNX directly
  const exchangeParam = exchangeFilter === "all" ? undefined : exchangeFilter

  const { data, isLoading, isFetching, error, refetch } = useFinancialStatements(50, exchangeParam)
  // ... rest of component
```

### Step 2: Add Filter Bar UI

After the header div (line ~192), add filter controls:

```tsx
{/* Header with period info and refresh button */}
<div className="flex items-center justify-between">
  <div className="flex items-center gap-4">
    {/* Exchange Filter */}
    <Select value={exchangeFilter} onValueChange={(v) => {
      setExchangeFilter(v as ExchangeFilter)
      setCurrentPage(1) // Reset pagination
    }}>
      <SelectTrigger className="w-[140px] h-8 text-sm bg-background border-border/50">
        <SelectValue placeholder="Sàn" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">Tất cả sàn</SelectItem>
        <SelectItem value="HOSE">HOSE</SelectItem>
        <SelectItem value="HNX">HNX</SelectItem>
      </SelectContent>
    </Select>

    {/* Period info */}
    <div className="text-sm text-muted-foreground">
      {data?.period} • {data?.total} công ty
    </div>
  </div>

  {/* Refresh button - existing */}
  <button ...>
    <RefreshCw ... />
  </button>
</div>
```

### Step 3: Update Exchange Badge Display

In table row, normalize display from HSX → HOSE:

```tsx
<span className="ml-2 text-xs text-muted-foreground">
  {item.exchange === "HSX" ? "HOSE" : item.exchange}
</span>
```

### Step 4: Reset Pagination on Filter Change

Already handled in Step 2 via `setCurrentPage(1)` in onValueChange.

## Todo List

- [x] Add `exchangeFilter` state with type `ExchangeFilter`
- [x] Update `useFinancialStatements` call: `(50, exchangeParam)`
- [x] Add Select dropdown for exchange filter
- [x] Map HSX → HOSE in display
- [x] Reset pagination on filter change
- [ ] Test: Filter HOSE shows correct data
- [ ] Test: Filter HNX shows correct data
- [ ] Test: All shows combined data

## Success Criteria

- [x] Dropdown renders with All | HOSE | HNX options
- [x] Selecting HOSE shows only HOSE stocks
- [x] Selecting HNX shows only HNX stocks
- [x] All shows combined (but excludes UPCOM if API filters)
- [x] Exchange badge shows "HOSE" not "HSX"
- [x] Table shows 50 records max
- [x] Pagination resets on filter change

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Flash of wrong data on filter change | TanStack Query handles loading state |
| Mobile layout breaks | Use responsive width on Select |

## Security Considerations

- No user input goes directly to database
- Exchange values are hardcoded options

## Next Steps

After this phase, proceed to Phase 3: Testing & Verification
