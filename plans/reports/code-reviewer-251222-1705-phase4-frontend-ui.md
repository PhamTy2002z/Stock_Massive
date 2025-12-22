# Code Review: Phase 4 Frontend UI - Top Performers

**Date**: 2025-12-22 17:05
**Reviewer**: code-reviewer (a294bd9)
**Scope**: Top Performers frontend implementation

---

## Files Reviewed

| File | LOC | Status |
|------|-----|--------|
| `apps/web/src/lib/query-keys.ts` | 39 | Modified |
| `apps/web/src/lib/api.ts` | 416 | Modified |
| `apps/web/src/hooks/use-top-performers.ts` | 25 | New |
| `apps/web/src/components/dashboard/top-performers-table.tsx` | 373 | New |
| `apps/web/src/app/analytics/top-performers/page.tsx` | 21 | Modified |

---

## Overall Assessment

Implementation follows existing VN30OverviewTable patterns well. Code is clean, readable, and mostly adheres to project standards. No critical security issues. Minor improvements possible.

**Rating**: PASS with minor suggestions

---

## Critical Issues

None found.

---

## High Priority Findings

### 1. Inconsistent limit parameter (api.ts vs hook)

**Location**: `use-top-performers.ts:7` + `top-performers-table.tsx:47`

**Issue**: Hook defaults `limit=50` but table calls with `limit=100`.

```tsx
// use-top-performers.ts
export function useTopPerformers(limit: number = 50, exchange?: string)

// top-performers-table.tsx
const { data } = useTopPerformers(100)  // Overrides default
```

**Impact**: Hook default of 50 is never used. Either align defaults or document why 100 is needed.

---

## Medium Priority Findings

### 1. DRY violation - formatPercent duplicated

**Location**: `top-performers-table.tsx:36` + `vn30-overview-table.tsx:27`

**Issue**: Nearly identical `formatPercent` function in both files.

```tsx
// top-performers-table.tsx
function formatPercent(value: number | null): string {
  if (value === null) return "-"
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

// vn30-overview-table.tsx - same logic, slight formatting difference
```

**Suggestion**: Extract to shared `lib/formatters.ts` utility.

### 2. Minor: formatProfit similar to formatMarketCap

**Location**: `top-performers-table.tsx:30` + `vn30-overview-table.tsx:45`

**Issue**: Both format billions with Vietnamese locale. Could share formatter.

### 3. Accessibility: sortable headers missing role

**Location**: `top-performers-table.tsx:166-211`

**Issue**: Sortable column headers use `<button>` inside `<th>` which is valid, but missing `aria-sort` attribute.

```tsx
// Add to sortable th elements:
aria-sort={sortField === "rank" ? (sortDirection || "none") : undefined}
```

### 4. Language inconsistency

**Location**: Multiple files

**Issue**: VN30OverviewTable uses Vietnamese ("Trang", "Hàng mỗi trang"), TopPerformersTable uses English ("Page", "Rows per page"). Should be consistent.

---

## Low Priority Suggestions

### 1. Magic number for staleTime

**Location**: `use-top-performers.ts:11-12`

```tsx
staleTime: 60 * 1000,        // 1 min
refetchInterval: 5 * 60 * 1000, // 5 min
```

Consider extracting to constants if reused elsewhere.

### 2. SortIcon component inline definition

**Location**: `top-performers-table.tsx:93-99`

Defining component inside render function recreates it each render. Move outside or use `useMemo`.

### 3. Unused TrendingUp/TrendingDown icons

**Location**: N/A (not imported in top-performers-table)

VN30Table uses trending icons for % change; TopPerformers only uses color. Intentional but inconsistent visual.

---

## Positive Observations

1. **Follows patterns**: Correctly mirrors VN30OverviewTable structure for sorting, pagination, skeleton
2. **Type safety**: Proper TypeScript types imported from api.ts
3. **Accessibility**: aria-labels on pagination buttons
4. **Error handling**: Proper loading, error, empty states
5. **Performance**: useMemo for sorting/filtering, pagination prevents large renders
6. **KISS**: No over-engineering, simple client-side sorting for 100 items is appropriate

---

## Security Analysis

| Check | Status |
|-------|--------|
| XSS via user data | SAFE - React escapes by default, no dangerouslySetInnerHTML |
| URL injection | SAFE - URLSearchParams handles encoding |
| API error messages | SAFE - Only displays error.message, no sensitive data |
| CORS | N/A - Handled at API level |

---

## Performance Analysis

| Area | Assessment |
|------|------------|
| Re-renders | Good - useMemo prevents unnecessary sorts |
| Data fetching | Good - staleTime prevents excessive requests |
| Bundle size | Good - lucide-react is tree-shaken |
| Table virtualization | Not needed for 100 rows |

---

## YAGNI/KISS/DRY Compliance

| Principle | Status | Notes |
|-----------|--------|-------|
| YAGNI | PASS | No unused features, exchange filter wired but not exposed (acceptable) |
| KISS | PASS | Simple client-side sort/pagination appropriate for 100 items |
| DRY | MINOR | formatPercent/formatProfit could be shared utilities |

---

## Recommended Actions

1. **Consider**: Extract formatPercent, formatProfit to `lib/formatters.ts`
2. **Optional**: Add `aria-sort` to sortable column headers
3. **Decision needed**: Standardize UI language (EN or VI)

---

## Metrics

- Type Coverage: 100% (all props/returns typed)
- Linting Issues: 0 (assumed - follows patterns)
- Test Coverage: Pending (see tester report)

---

## Verdict

**APPROVED** - Implementation is solid, follows project patterns, no blocking issues. DRY violation is minor and can be addressed in future refactor.
