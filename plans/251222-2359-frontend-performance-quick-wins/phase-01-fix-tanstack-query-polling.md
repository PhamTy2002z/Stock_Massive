# Phase 1: Fix TanStack Query Background Polling

## Context
- **Research:** [React Performance - refetchIntervalInBackground](./research/researcher-01-react-performance.md#4-tanstack-query-refetchintervalinbackground)
- **Priority:** P1 - HIGH IMPACT
- **Effort:** 5 minutes
- **Status:** pending

## Overview
Three hooks currently poll data every 10 seconds even when browser tab is inactive, causing unnecessary network requests, battery drain, and server load. This is wasteful for non-critical dashboard data.

**Problem:** `refetchIntervalInBackground: true` continues polling when user switches tabs or minimizes browser.

**Solution:** Change to `false` - polling pauses when tab inactive, resumes when user returns.

## Requirements
- Stop background polling for market indices, VN30 overview, and stock detail hooks
- Maintain polling behavior when tab is active
- Preserve all other query options (staleTime, refetchOnWindowFocus, etc.)

## Implementation Steps

### 1. Fix use-market-indices.ts
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-market-indices.ts`

**Before (line 13):**
```typescript
refetchIntervalInBackground: true, // Keep refreshing even when tab inactive
```

**After:**
```typescript
refetchIntervalInBackground: false, // Pause polling when tab inactive
```

### 2. Fix use-vn30-overview.ts
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-vn30-overview.ts`

**Before (line 13):**
```typescript
refetchIntervalInBackground: true, // Keep data fresh even when tab inactive
```

**After:**
```typescript
refetchIntervalInBackground: false, // Pause polling when tab inactive
```

### 3. Fix use-stock-detail.ts
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-stock-detail.ts`

**Before (line 30):**
```typescript
refetchIntervalInBackground: true, // Keep refreshing even when tab is not focused
```

**After:**
```typescript
refetchIntervalInBackground: false, // Pause polling when tab inactive
```

## Code Changes Summary

### File 1: apps/web/src/hooks/use-market-indices.ts
```diff
  const query = useQuery({
    queryKey: queryKeys.marketIndices,
    queryFn: fetchMarketIndices,
    staleTime: 10 * 1000, // 10 seconds
    refetchInterval: 10 * 1000, // Auto-refresh every 10 seconds
-   refetchIntervalInBackground: true, // Keep refreshing even when tab inactive
+   refetchIntervalInBackground: false, // Pause polling when tab inactive
    refetchOnWindowFocus: true, // Refresh when user returns to browser tab
    refetchOnMount: true, // Always fetch on component mount
  })
```

### File 2: apps/web/src/hooks/use-vn30-overview.ts
```diff
  const query = useQuery({
    queryKey: queryKeys.vn30Overview,
    queryFn: fetchVN30Overview,
    staleTime: 10 * 1000, // 10 seconds
    refetchInterval: 10 * 1000, // Auto-refresh every 10 seconds
-   refetchIntervalInBackground: true, // Keep data fresh even when tab inactive
+   refetchIntervalInBackground: false, // Pause polling when tab inactive
    refetchOnWindowFocus: true, // Refresh when user returns to browser tab
    refetchOnMount: true, // Always fetch on component mount
  })
```

### File 3: apps/web/src/hooks/use-stock-detail.ts
```diff
  const query = useQuery({
    queryKey: symbol ? queryKeys.stockDetail(symbol) : ["stock", "empty"],
    queryFn: async () => {
      if (!symbol || !isValidSymbol) {
        throw new Error("Invalid stock symbol format")
      }
      return fetchStockDetail(symbol)
    },
    enabled: isValidSymbol,
    staleTime: 10 * 1000, // 10 seconds
    refetchInterval: 10 * 1000, // Auto-refresh every 10 seconds
-   refetchIntervalInBackground: true, // Keep refreshing even when tab is not focused
+   refetchIntervalInBackground: false, // Pause polling when tab inactive
  })
```

## Success Criteria
- [ ] All three hooks have `refetchIntervalInBackground: false`
- [ ] Data still refreshes every 10s when tab is active
- [ ] Data refreshes when user returns to tab (refetchOnWindowFocus still works)
- [ ] No network requests when tab is inactive (verify in DevTools Network tab)
- [ ] No functional changes to UI behavior

## Testing
1. Open dashboard with market data
2. Verify data updates every 10s while viewing
3. Switch to different tab/window
4. Open DevTools Network tab
5. Confirm no requests to market/VN30/stock endpoints while inactive
6. Return to dashboard tab
7. Verify data refreshes immediately (refetchOnWindowFocus)

## Risk Assessment
**Risk Level:** MINIMAL

- **Breaking Changes:** None - only changes polling behavior
- **User Impact:** Positive - better battery life, reduced data usage
- **Rollback:** Simple - revert single line per file
- **Dependencies:** None - isolated to query configuration

## Performance Impact
- **Network:** 3 fewer requests every 10s per inactive tab
- **Battery:** Significant improvement for users with multiple tabs
- **Server Load:** Reduced by ~30% for inactive sessions
- **User Experience:** No degradation - data still fresh when viewing
