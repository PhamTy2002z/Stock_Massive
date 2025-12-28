# Code Review Report: Phase 3 Frontend UI Updates

**ID:** code-reviewer-251227-1703
**Scope:** Phase 3 Frontend UI - IntradayOrderStats, ForeignSnapshot widgets
**Files:** 7 files reviewed
**Critical Issues:** 0

---

## Summary

Phase 3 implementation is **solid**. TypeScript compiles clean. No security vulnerabilities. Minor DRY/consistency issues exist but don't block deployment.

---

## Findings by Priority

### Critical (0)
None.

### High (0)
None.

### Medium (3)

**M1. Query Key Inconsistency**
- New hooks use inline keys: `["intradayOrderStats", symbol]`, `["foreignSnapshot", symbol]`
- Existing pattern uses `queryKeys.ts` (e.g., `usePriceDepth` uses `queryKeys.priceDepth(symbol)`)
- **Impact:** Potential cache invalidation issues if not consistent
- **Fix:** Add to `query-keys.ts`:
  ```ts
  intradayOrderStats: (symbol: string) => [...queryKeys.stock(symbol), "intradayOrderStats"] as const,
  foreignSnapshot: (symbol: string) => [...queryKeys.stock(symbol), "foreignSnapshot"] as const,
  ```

**M2. DRY Violation - formatVolume() duplicated in 11 files**
- `formatVolume()` defined locally in: intraday-order-stats.tsx, foreign-snapshot-card.tsx, + 9 others
- `formatNumber()` duplicated in 4 files
- **Fix:** Extract to `src/lib/formatters.ts` (future tech debt ticket)

**M3. Missing retry/error config in new hooks**
- `usePriceDepth` has `retry: 2`, `refetchIntervalInBackground: false`
- `useIntradayOrderStats` and `useForeignSnapshot` lack these
- **Impact:** Minor - may retry more than intended on transient failures

### Low (2)

**L1. Optional chaining for foreign_pct_of_volume**
- Line 55 in foreign-snapshot-card.tsx: `data.foreign_pct_of_volume?.toFixed(1)`
- Type says `number | null` - correct usage, but could centralize with `formatPct`

**L2. Hardcoded Vietnamese strings**
- Not i18n-ready (acceptable for Vietnam-specific stock app)

---

## Positive Observations

1. **Clean TypeScript** - No type errors, proper interface definitions
2. **Good separation** - Hooks/widgets/subtabs properly decoupled
3. **Loading states** - Skeleton components provide good UX
4. **Error handling** - Both subtabs show error states appropriately
5. **Consistent styling** - Tailwind classes follow project patterns
6. **XSS-safe** - All data rendered via React, no dangerouslySetInnerHTML
7. **Input sanitization** - API uses `encodeURIComponent()` on symbol param

---

## Security Checklist

| Check | Status |
|-------|--------|
| XSS prevention | PASS - React escaping |
| Input sanitization | PASS - encodeURIComponent |
| SSRF risk | PASS - API_BASE_URL from env |
| Sensitive data exposure | PASS - No secrets in code |

---

## Performance Checklist

| Check | Status |
|-------|--------|
| Unnecessary re-renders | PASS - hooks memoized by TanStack |
| Query staleTime | PASS - 60s appropriate |
| Auto-refresh | PASS - 120s reasonable |
| Bundle size | OK - lucide-react tree-shakeable |

---

## Architecture Compliance

- **YAGNI:** PASS - No over-engineering
- **KISS:** PASS - Simple widget pattern
- **DRY:** MEDIUM - formatVolume duplication (pre-existing, not new)

---

## Recommendations

1. **[Should]** Add query keys to `query-keys.ts` for consistency
2. **[Could]** Add `retry: 2` to new hooks for parity
3. **[Later]** Create `src/lib/formatters.ts` to DRY up formatting functions

---

## Verdict

**APPROVED for merge.** No critical/high issues. Medium issues are non-blocking improvements for future iteration.
