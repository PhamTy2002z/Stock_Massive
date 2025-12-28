# Code Review: Phase 3 - Trend Charts Implementation

**Date**: 2025-12-28
**Reviewer**: code-reviewer-9097c995
**Scope**: Phase 3 Trend Charts components

---

## Code Review Summary

### Scope
- Files reviewed: 11 files
- Lines of code analyzed: ~600
- Review focus: Phase 3 Trend Charts implementation
- TypeScript check: PASSED

### Overall Assessment

**GOOD IMPLEMENTATION** - Code follows project standards, design guidelines compliant, no critical issues.

---

## Critical Issues

**NONE**

---

## High Priority Findings

### 1. DRY Violation: Duplicate `formatBillions` Function

**Location**:
- `/apps/web/src/components/dashboard/financial-trends/revenue-profit-chart.tsx` (lines 20-25)
- `/apps/web/src/components/dashboard/financial-trends/cash-flow-chart.tsx` (lines 20-25)

**Issue**: Same function duplicated in 2 files:
```typescript
function formatBillions(value: number): string {
  if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(1)}T`
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(1)}B`
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(1)}M`
  return value.toLocaleString()
}
```

**Recommendation**: Extract to `/lib/format.ts` or `/lib/utils.ts`

---

## Medium Priority Improvements

### 1. Vietnamese Label Consistency

**Location**: All chart components

Labels use mix of accented/unaccented Vietnamese:
- `"LN gop"` should be `"LN gộp"` or just `"Gross Profit"`
- `"Bien LN gop"` should be `"Biên LN gộp"` or standardize

**Recommendation**: Decide on single convention (full Vietnamese with accents OR English)

### 2. Non-null Assertion in Margin Calculations

**Location**: `margin-trend-chart.tsx`, `roe-roa-chart.tsx`

```typescript
gross_margin: data.gross_margin[i] ? data.gross_margin[i]! * 100 : null
```

**Issue**: Uses non-null assertion `!` after truthy check. Safe but verbose.

**Better pattern**:
```typescript
gross_margin: data.gross_margin[i] != null ? data.gross_margin[i] * 100 : null
```

---

## Low Priority Suggestions

### 1. Chart Height Consistency
All charts use `height={300}` - good consistency. Consider making configurable via prop for responsive layouts.

### 2. Legend Label DRY
Label mappings repeated in Tooltip and Legend formatters:
```typescript
const labels: Record<string, string> = {
  revenue: "Doanh thu",
  gross_profit: "LN gop",
  net_profit: "LN rong",
}
```
Could extract to constants at module level.

---

## Security Analysis

| Check | Status | Notes |
|-------|--------|-------|
| XSS | PASS | No dangerouslySetInnerHTML, data rendered via Recharts |
| Injection | PASS | encodeURIComponent used for symbol in API |
| Data exposure | PASS | No sensitive data in components |

---

## Performance Analysis

| Check | Status | Notes |
|-------|--------|-------|
| Memoization | OK | Hooks use proper dependencies |
| Re-renders | OK | Chart data transformation inline but lightweight |
| Query caching | GOOD | 5min staleTime appropriate |
| Bundle size | OK | Recharts tree-shakeable imports |

---

## Architecture Compliance

| Check | Status |
|-------|--------|
| File structure | PASS - follows `components/dashboard/{feature}/` |
| Export pattern | PASS - barrel exports via index.ts |
| Query key pattern | PASS - uses queryKeys.trendMetrics() |
| Hook pattern | PASS - follows project useXxx convention |

---

## Design Guidelines Compliance

| Requirement | Status | Evidence |
|-------------|--------|----------|
| --accent-orange primary | PASS | Bars, Lines use `hsl(var(--accent-orange))` |
| muted-foreground secondary | PASS | Secondary lines use `hsl(var(--muted-foreground))` |
| Skeleton loading | PASS | TrendChartsCardSkeleton provided |
| Empty state | PASS | "Chon mot co phieu..." message |
| Error state | PASS | Error message with retry guidance |
| Card structure | PASS | Uses CardHeader, CardContent |
| Tooltip styling | PASS | Uses --card, --border vars |

---

## Test Coverage

- `test_financial_health.py` includes `TestTrendMetricsEndpoint`
- Tests cover: basic fetch, custom periods, validation (min/max periods)
- Coverage: ADEQUATE for Phase 3 scope

---

## Positive Observations

1. **Clean component separation** - Each chart is self-contained
2. **Proper loading/error states** - UX complete
3. **Design system compliance** - Colors, spacing correct
4. **TypeScript strict** - No type errors
5. **Query caching** - 5min staleTime prevents excessive API calls
6. **Responsive charts** - ResponsiveContainer used

---

## Recommended Actions

1. **[Medium]** Extract `formatBillions` to shared utility
2. **[Low]** Standardize Vietnamese labels
3. **[Low]** Consider label constants extraction

---

## Metrics

- Type Coverage: 100% (no any, proper interfaces)
- Linting Issues: 0
- Security Issues: 0
- Performance Issues: 0

---

## Unresolved Questions

None.
