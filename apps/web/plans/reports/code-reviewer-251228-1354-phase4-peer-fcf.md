# Code Review: Phase 4 - Peer Comparison & FCF Analysis

**Date**: 2025-12-28
**Reviewer**: code-reviewer subagent
**Scope**: 8 files (components, hooks, API types)

---

## Summary

| Category | Count |
|----------|-------|
| Critical Issues | 0 |
| Warnings | 2 |
| Suggestions | 4 |

**Overall**: Code quality is good. No security vulnerabilities. Design guidelines followed. Minor improvements suggested.

---

## Files Reviewed

1. `peer-comparison/peer-comparison-card.tsx` (72 lines)
2. `peer-comparison/peer-metrics-table.tsx` (107 lines)
3. `fcf-analysis/fcf-analysis-card.tsx` (95 lines)
4. `fcf-analysis/fcf-waterfall.tsx` (62 lines)
5. `fcf-analysis/ccc-indicator.tsx` (51 lines)
6. `hooks/use-sector-peers.ts` (12 lines)
7. `hooks/use-fcf-analysis.ts` (12 lines)
8. `lib/api.ts` (lines 727-798)

---

## Critical Issues

**None found.**

---

## Warnings (Medium Priority)

### W1: Missing Retry Button on Error States

**Location**: `peer-comparison-card.tsx:44-51`, `fcf-analysis-card.tsx:45-52`

**Issue**: Error states show message but no retry action.

**Design Guidelines require**:
> Error - Clear error message with recovery action

**Current**:
```tsx
<CardContent className="... text-destructive">
  Khong the tai FCF Analysis
</CardContent>
```

**Recommended**: Add refetch button for better UX.

---

### W2: Average Calculations Not Memoized

**Location**: `peer-metrics-table.tsx:38-46`

**Issue**: Average calculations run on every render.

```tsx
const validRoe = peers.filter(p => p.roe !== null)
const avgRoe = validRoe.length > 0 ? validRoe.reduce(...) : 0
// 4 similar calculations
```

**Impact**: Low (dataset small ~5 peers), but violates optimization best practices.

**Fix**: Wrap in `useMemo`.

---

## Suggestions (Low Priority)

### S1: CCCIndicator Missing "use client" Directive

**Location**: `ccc-indicator.tsx:1`

**Issue**: File doesn't have `"use client"` but is used by client component.

**Impact**: Works currently since parent is client component, but explicit is better.

---

### S2: Inconsistent tabular-nums Usage

**Location**: Multiple files

**Current**: Some numbers use `tabular-nums`, others don't.

| File | Has tabular-nums |
|------|-----------------|
| peer-metrics-table.tsx | Yes (lines 82-95) |
| fcf-waterfall.tsx | Yes (line 45) |
| ccc-indicator.tsx | No (lines 30, 37, 41, 45) |
| fcf-analysis-card.tsx | No (lines 72, 78) |

**Fix**: Add `tabular-nums` to all numeric displays for alignment.

---

### S3: Consider Extract Format Functions to Shared Utils

**Issue**: `formatBillions` appears similar to `formatMarketCap` but in different files.

**Location**:
- `fcf-waterfall.tsx:10-17` - formatBillions
- `peer-metrics-table.tsx:21-26` - formatMarketCap

**Fix**: Extract to `@/lib/format-utils.ts` (DRY principle).

---

### S4: Missing Type Export for PeerMetrics

**Location**: `lib/api.ts:729`

**Issue**: PeerMetrics imported in peer-metrics-table but interface at top-level.

**Status**: Works correctly, but consider grouping related types.

---

## Positive Observations

1. **Security**: All inputs properly sanitized with `encodeURIComponent`
2. **Loading States**: Skeleton components properly implemented
3. **Orange Accent**: Correctly used `hsl(var(--accent-orange))` per design guidelines
4. **Green/Red Semantics**: Proper use for financial metrics (heatmap colors)
5. **Query Config**: Proper staleTime (5-10 min) and enabled pattern
6. **File Naming**: Follows kebab-case convention
7. **Hook Pattern**: Clean TanStack Query usage with proper types
8. **Empty State**: Handled when no symbol selected
9. **Dark Mode**: CSS variables support both themes

---

## Verification Checklist

| Check | Status |
|-------|--------|
| TypeScript type-check | PASS |
| ESLint | PASS |
| Build | PASS |
| No XSS vulnerabilities | PASS |
| No injection risks | PASS |
| Design guidelines (orange accent) | PASS |
| Loading states | PASS |
| Error states | PARTIAL (missing retry) |
| YAGNI/KISS | PASS |
| DRY | MINOR VIOLATION (format funcs) |

---

## Recommended Actions

1. **[W1]** Add retry button to error states
2. **[W2]** Memoize average calculations in PeerMetricsTable
3. **[S2]** Add `tabular-nums` to CCCIndicator and FCFAnalysisCard metrics
4. **[S3]** Consider extracting format utils (optional, low priority)

---

## Unresolved Questions

None.
