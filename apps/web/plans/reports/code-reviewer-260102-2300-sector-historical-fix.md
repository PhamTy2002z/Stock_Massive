# Code Review: Sector Historical Performance Fix

**Reviewer:** code-reviewer | **Date:** 2026-01-02 23:00
**Plan:** phase-01-sector-historical-fix, Step 2
**Files Reviewed:**
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-sector-historical-performance.ts`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/sector-historical-performance.tsx`

**Reference:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-fund-certificates.ts`

---

## Summary

**APPROVED** - Implementation is solid, follows patterns correctly, no critical issues.

---

## Hook Review: `use-sector-historical-performance.ts`

### Pattern Consistency with Reference ✅

| Aspect | Reference (`use-fund-certificates`) | Implementation | Match |
|--------|-------------------------------------|----------------|-------|
| `useQuery` import | ✅ | ✅ | ✅ |
| `keepPreviousData` | ✅ | ✅ | ✅ |
| `placeholderData` option | ✅ | ✅ | ✅ |
| `refetchIntervalInBackground: false` | ✅ | ✅ | ✅ |
| `refetchOnWindowFocus: true` | ✅ | ✅ | ✅ |
| Returns `isPlaceholderData` | ✅ | ✅ | ✅ |
| Returns `isFetching` | ✅ | ✅ | ✅ |

### Minor Differences (Acceptable)

1. **`isPending` vs `isLoading`**: Hook returns `isPending`, reference returns `isLoading`. Both valid - `isPending` is newer TanStack Query v5 naming. Consistent within this hook's usage.

2. **Missing `error` return**: Reference returns `error`, this hook doesn't. Not needed if component doesn't handle errors explicitly. Minor.

3. **Missing `refetchOnMount`**: Reference has it, this doesn't. Default is `true`, so behavior same.

4. **Different stale/refetch times**: 5min/10min vs 1min/1min. Appropriate for historical vs real-time data.

### Security ✅
- No user input directly in query
- Uses typed API function
- No XSS vectors

### TypeScript ✅
- Proper typing with `SectorHistoricalPeriod`
- No `any` types
- Return type inferred correctly

---

## Component Review: `sector-historical-performance.tsx`

### React Hooks Rules ✅
- `useMemo` called before early return (line 118-131)
- Comment explicitly notes this requirement (line 117)
- `isPending` check after hooks (line 134)

### Loading UX Implementation ✅

1. **First load**: Shows skeleton (`isPending` check, line 134-136)
2. **Tab switch**: Previous data shown with opacity fade (`isPlaceholderData && "opacity-60"`, line 143)
3. **Refetch indicator**: Subtle spinner top-right (`isFetching && !isPending`, line 149-153)
4. **Animation disabled during placeholder**: `isAnimationActive={!isPlaceholderData}` (line 97)

### Performance ✅
- `memo` with custom comparator using `isEqual` (line 111)
- `useMemo` for chart data transformation (line 118)
- No unnecessary re-renders

### Architecture ✅
- Clean separation: `PeriodContent` handles data, parent handles state
- Proper prop drilling of `isPlaceholderData` to chart
- Consistent with existing patterns

### Minor Suggestions (Non-blocking)

1. **Line 100-105**: Using index as key in `Cell` map. Acceptable here since data order is stable per render, but could use `entry.name` for extra safety.

2. **Line 121-122, 125-126**: Duplicate truncation logic. Could extract to util, but YAGNI - only used here.

---

## Checklist

| Criteria | Status |
|----------|--------|
| Security (XSS, injection, OWASP) | ✅ Pass |
| Performance (re-renders, memory) | ✅ Pass |
| Architecture (pattern consistency) | ✅ Pass |
| YAGNI/KISS/DRY | ✅ Pass |
| TypeScript (proper typing) | ✅ Pass |
| React hooks rules | ✅ Pass |

---

## Verdict

**APPROVED** - No critical issues. Implementation correctly follows `keepPreviousData` pattern from reference. Loading states handled properly. Code is clean and maintainable.

---

## Unresolved Questions

None.
