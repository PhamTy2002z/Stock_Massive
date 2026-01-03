# Tester Report: Phase 02 Smooth Section Loading

**Date:** 2026-01-02 23:03
**Agent:** tester-260102-2303
**Status:** FAIL

## Summary

Phase 02 migration introduced React Hooks rule violations in `vn30-overview-table.tsx`.

## Tests Found

**No** - No existing unit tests for hooks/components in `apps/web/src/`

- Searched: `**/*.test.{ts,tsx}`, `**/*.spec.{ts,tsx}`, `**/__tests__/**`
- Result: Only node_modules tests found
- No test framework configured in package.json (no jest, vitest, etc.)

## Build Results

**FAILED** - `pnpm build` exit code 1

### Errors (6 total in vn30-overview-table.tsx)

| Line | Hook | Error |
|------|------|-------|
| 120 | `useMemo` | Called conditionally (after early return on line 116-118) |
| 131 | `useCallback` | Called conditionally |
| 144 | `useMemo` | Called conditionally |
| 148 | `useCallback` | Called conditionally |
| 155 | `useCallback` | Called conditionally |
| 160 | `useCallback` | Called conditionally |

### Root Cause

Early return on lines 116-118 causes hooks to be called conditionally:

```tsx
// Line 116-118 - Early return BEFORE hooks
if (isPending) {
  return <VN30OverviewTableSkeleton className={className} />
}

// Line 120+ - Hooks called AFTER early return (violation)
const stocks = useMemo(() => { ... }, [data?.stocks, sortDirection])
const toggleSort = useCallback(() => { ... }, [])
```

### Warning (non-blocking)

- `shareholders-tab-content.tsx:44` - unused `isFetching` variable

## Files Affected

- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/vn30-overview-table.tsx`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/shareholders-tab-content.tsx`

## Required Fix

Move all hooks BEFORE the early return, or restructure component to avoid conditional hook calls.

## Unresolved Questions

None.
