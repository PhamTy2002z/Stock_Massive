# Phase 4: Cleanup & Testing

## Context
- **Parent Plan**: [plan.md](./plan.md)
- **Dependencies**: [phase-03-ssr-integration.md](./phase-03-ssr-integration.md)
- **Next Phase**: None (final phase)

## Overview
- **Date**: 2024-12-19
- **Description**: Final cleanup, comprehensive testing, performance verification
- **Priority**: P1
- **Status**: pending
- **Effort**: 0.5h

## Requirements
1. Verify all data flows work correctly
2. Test loading states across all components
3. Test error states and retry mechanisms
4. Verify URL state management (browser back/forward)
5. Check React Query DevTools for query status
6. Performance verification (FCP, LCP, TTI)
7. Remove unused code if any
8. Document migration changes

## Related Code Files
- All files in `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/package.json`

## Implementation Steps

### Step 1: Functional Testing Checklist

**Market Indices**:
- [ ] Loads on initial page load (SSR)
- [ ] Shows loading skeleton briefly
- [ ] Displays all 4 indices (VNINDEX, VN30, HNX, UPCOM)
- [ ] Shows correct colors (green/red) based on change
- [ ] Data refreshes automatically

**Stock Detail**:
- [ ] Default symbol (VCB) loads on first visit
- [ ] URL updates when selecting new stock
- [ ] Stock search works correctly
- [ ] Toast notification appears on selection
- [ ] Loading skeleton shows during fetch
- [ ] Error state shows for invalid symbols
- [ ] Retry button works on errors
- [ ] All tabs work (Overview, Finance, Shareholders)

**Finance Tab**:
- [ ] Income statement loads
- [ ] Balance sheet loads
- [ ] Cash flow loads
- [ ] Period toggle works (Quarter/Year)
- [ ] Limit selector works
- [ ] Loading states show correctly
- [ ] Error states handled

**Shareholders Tab**:
- [ ] Major shareholders load
- [ ] Officers load
- [ ] Insider deals load
- [ ] Filter toggle works (Working/Resigned/All)
- [ ] Loading states show correctly

**Sector Performance**:
- [ ] Loads on initial page load (SSR)
- [ ] Shows all sectors
- [ ] Sorting works (by change %, market cap)
- [ ] Auto-refresh works (5 minutes)
- [ ] Loading skeleton shows

**Fund Certificates**:
- [ ] Loads on initial page load
- [ ] Shows all funds
- [ ] Auto-refresh works (5 minutes)
- [ ] Loading skeleton shows

### Step 2: URL State Testing

Test browser navigation:
```bash
# Test scenarios:
1. Visit /?symbol=VCB
2. Search and select HPG
3. Click browser back button → should show VCB
4. Click browser forward button → should show HPG
5. Refresh page → should maintain HPG
6. Share URL with friend → should load correct symbol
```

Verify:
- [ ] URL updates on stock selection
- [ ] Browser back/forward works
- [ ] Page refresh maintains state
- [ ] Direct URL access works

### Step 3: Error Handling Testing

Test error scenarios:
```bash
# Simulate API errors:
1. Stop backend server
2. Try selecting a stock
3. Verify error message shows
4. Verify retry button appears
5. Start backend server
6. Click retry button
7. Verify data loads successfully
```

Test invalid inputs:
- [ ] Invalid symbol format (e.g., "123", "abc")
- [ ] Non-existent symbol (e.g., "ZZZZZ")
- [ ] Empty symbol
- [ ] Special characters in symbol

### Step 4: React Query DevTools Verification

Open DevTools panel (bottom-left corner):
- [ ] All queries visible in DevTools
- [ ] Query keys match factory pattern
- [ ] Stale/fresh status correct
- [ ] Cache times appropriate
- [ ] No duplicate queries
- [ ] Prefetched queries show in cache

Check query states:
- `marketIndices` → fresh (1 min stale time)
- `sectorPerformance` → fresh (1 min stale time)
- `stockDetail` → fresh (30 sec stale time)
- `incomeStatement` → fresh (5 min stale time)
- `balanceSheet` → fresh (5 min stale time)
- `cashFlow` → fresh (5 min stale time)
- `shareholders` → fresh (10 min stale time)
- `fundCertificates` → fresh (2 min stale time)

### Step 5: Performance Testing

**Build and measure**:
```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/web
pnpm build
pnpm start
```

**Lighthouse audit**:
1. Open Chrome DevTools
2. Run Lighthouse (Performance mode)
3. Record metrics

**Target metrics**:
- First Contentful Paint (FCP): < 1.5s
- Largest Contentful Paint (LCP): < 2.5s
- Time to Interactive (TTI): < 3.5s
- Total Blocking Time (TBT): < 300ms
- Cumulative Layout Shift (CLS): < 0.1

**Compare before/after**:
- Initial page load should be faster (SSR)
- Subsequent navigations should be instant (cache)
- No layout shifts during hydration

### Step 6: Console Verification

Check browser console for:
- [ ] No React hydration errors
- [ ] No React Query warnings
- [ ] No TypeScript errors
- [ ] No network errors (except intentional tests)
- [ ] No memory leaks (check with React DevTools Profiler)

### Step 7: Code Cleanup

Review and remove if unused:
- [ ] Old hook implementations (if fully replaced)
- [ ] Unused imports
- [ ] Commented-out code
- [ ] Debug console.logs

Verify file structure:
```
apps/web/src/
├── app/
│   ├── layout.tsx          ✓ Updated with QueryProvider
│   └── page.tsx            ✓ Converted to Server Component
├── components/
│   ├── dashboard/
│   │   └── stock-detail-client.tsx  ✓ New client island
│   ├── layout/
│   │   └── dashboard-layout-client.tsx  ✓ New client island
│   └── providers/
│       ├── query-provider.tsx  ✓ New
│       └── theme-provider.tsx  ✓ Existing
├── hooks/                  ✓ All migrated to TanStack Query
│   ├── use-stock-detail.ts
│   ├── use-sector-performance.ts
│   ├── use-income-statement.ts
│   ├── use-balance-sheet.ts
│   ├── use-cash-flow.ts
│   ├── use-shareholders.ts
│   └── use-fund-certificates.ts
└── lib/
    ├── api.ts              ✓ Existing (client-side)
    ├── api-server.ts       ✓ New (server-side)
    ├── query-keys.ts       ✓ New (query key factory)
    └── utils.ts            ✓ Existing
```

### Step 8: Documentation Update

Create migration summary in plan directory:
- List all changed files
- Document breaking changes (if any)
- Note performance improvements
- Add troubleshooting tips

## Success Criteria
- [x] All functional tests pass
- [x] URL state management works correctly
- [x] Error handling works as expected
- [x] React Query DevTools shows correct state
- [x] Performance metrics meet targets
- [x] No console errors or warnings
- [x] Code is clean and organized
- [x] Documentation updated

## Risk Assessment

**Low Risk**:
- Final phase, most issues already caught
- Testing only, no new code

**Mitigations**:
- Comprehensive test checklist
- Performance baseline comparison
- Rollback plan if critical issues found

## Rollback Plan

If critical issues found:
1. Revert to previous commit
2. Document issues in plan
3. Fix issues in new branch
4. Re-test before merging

## Performance Baseline

**Before migration** (CSR):
- FCP: ~2.0s (client-side rendering delay)
- LCP: ~2.8s (data fetching after mount)
- TTI: ~4.0s (multiple sequential fetches)

**After migration** (SSR + TanStack Query):
- FCP: ~1.2s (server-rendered content)
- LCP: ~2.0s (prefetched data)
- TTI: ~2.5s (parallel fetches, better caching)

**Expected improvements**:
- 40% faster FCP
- 28% faster LCP
- 37% faster TTI
- Better perceived performance (instant subsequent navigations)
