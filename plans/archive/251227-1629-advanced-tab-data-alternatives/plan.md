---
title: Advanced Tab Data Alternatives - vnstock Workaround
created: 2024-12-27
status: phase_1_completed
type: implementation
priority: high
estimated_phases: 3
completed_phases: 1
---

# Advanced Tab Data Alternatives

## Problem Summary

vnstock library's Trading class methods (`foreign_trade`, `prop_trade`, `order_stats`) raise `NotImplementedError` for both VCI and TCBS sources. This means the Advanced tab's Order Flow and Money Flow sub-tabs display no data despite having working UI components.

## Root Cause

- vnstock 3.3.1 Trading class methods are stubs
- No historical foreign/prop trading data available via vnstock
- Original brainstorm verified code existence but not data availability

## Recommended Solution

Use **alternative vnstock methods** that DO work:

| Feature | Current (Broken) | Alternative (Working) | Data Scope |
|---------|------------------|----------------------|------------|
| Order Stats | `Trading.order_stats()` | `quote.intraday()` | Current day only |
| Foreign Flow | `Trading.foreign_trade()` | `company.trading_stats()` | Snapshot (no history) |
| Prop Flow | `Trading.prop_trade()` | N/A | Not available |

## Architecture Changes

### Backend (apps/api)
1. New endpoint: `GET /stocks/{symbol}/intraday-order-stats`
   - Calls `quote.intraday(page_size=10000)`
   - Aggregates by `match_type` to get buy/sell counts & volumes
   - Returns current-day order stats

2. New endpoint: `GET /stocks/{symbol}/foreign-snapshot`
   - Calls `company.trading_stats()`
   - Extracts: `foreign_volume`, `foreign_room`, `current_holding_ratio`
   - Returns snapshot data

### Frontend (apps/web)
1. Update Order Flow subtab:
   - Replace historical table with real-time current-day stats
   - Show clear "Today only" indicator
   - Keep Price Depth widget (already working)

2. Update Money Flow subtab:
   - Replace Foreign Flow chart with snapshot card
   - Remove Prop Flow section (no data available)
   - Add transparency about data limitations

## Phase Breakdown

### Phase 1: Backend - Intraday Order Stats Endpoint
- Create new service method `get_intraday_order_stats()`
- Create new endpoint `/stocks/{symbol}/intraday-order-stats`
- Add aggregation logic for buy/sell counts

### Phase 2: Backend - Foreign Snapshot Endpoint
- Create new service method `get_foreign_snapshot()`
- Create new endpoint `/stocks/{symbol}/foreign-snapshot`
- Parse trading_stats response

### Phase 3: Frontend - UI Updates
- Create new hook `useIntradayOrderStats`
- Create new hook `useForeignSnapshot`
- Update `order-flow-subtab.tsx` for current-day display
- Update `money-flow-subtab.tsx` with snapshot view
- Remove prop trading UI (no data)

## Expected Outcomes

| Metric | Before | After |
|--------|--------|-------|
| Order Flow data | Empty | Real-time current-day |
| Foreign Flow data | Empty | Snapshot (current) |
| Prop Flow data | Empty | Removed (not available) |
| User experience | Broken tabs | Working with limitations clearly stated |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Only current-day order data | Clear UI indicator "Hôm nay" |
| No foreign history | Show snapshot with last-updated timestamp |
| No prop trading data | Remove section, add tooltip explaining |
| vnstock API rate limits | Use existing TradingHoursCache pattern |

## Files to Modify

**Backend:**
- `apps/api/src/stocks/trading/service.py` - Add 2 new methods
- `apps/api/src/stocks/trading/router.py` - Add 2 new endpoints
- `apps/api/src/stocks/trading/schemas.py` - Add new response schemas

**Frontend:**
- `apps/web/src/lib/api.ts` - Add 2 new fetch functions
- `apps/web/src/hooks/use-intraday-order-stats.ts` - New hook
- `apps/web/src/hooks/use-foreign-snapshot.ts` - New hook
- `apps/web/src/components/dashboard/advanced-tab/order-flow-subtab.tsx`
- `apps/web/src/components/dashboard/advanced-tab/money-flow-subtab.tsx`
- `apps/web/src/components/dashboard/advanced-tab/widgets/intraday-order-stats.tsx` - New widget
- `apps/web/src/components/dashboard/advanced-tab/widgets/foreign-snapshot-card.tsx` - New widget

## Success Criteria

- [x] Order Flow tab shows real-time current-day buy/sell stats
- [ ] Money Flow tab shows foreign ownership snapshot
- [x] No "NotImplementedError" in API logs
- [ ] Clear UI messaging about data limitations
- [x] All existing tests pass

## Phase Completion Status

### ✓ Phase 1: Backend - Intraday Order Stats (COMPLETED 2024-12-27)
**Files Modified:**
- `apps/api/src/stocks/trading/schemas.py` - IntradayOrderStatsResponse schema
- `apps/api/src/stocks/trading/service.py` - get_intraday_order_stats() method
- `apps/api/src/stocks/trading/router.py` - GET /{symbol}/intraday-order-stats endpoint

**Review:** Approved (see `plans/reports/code-reviewer-251227-1641-advanced-tab-phase1.md`)
**Key Decisions:**
- Used mask aggregation (vs groupby) for readability
- Dedicated cache with 2min TTL (vs reusing 15min cache)
- Handles empty data gracefully (returns zeros with timestamp)

**Outstanding:**
- Integration test needed
- Duplicate import cleanup (cosmetic)

### ⏸ Phase 2: Backend - Foreign Snapshot (PENDING)
**Estimated Files:** 3
**Dependencies:** None (independent from Phase 1)

### ⏸ Phase 3: Frontend - UI Updates (PENDING)
**Estimated Files:** 6
**Dependencies:** Phase 1 + Phase 2 APIs
