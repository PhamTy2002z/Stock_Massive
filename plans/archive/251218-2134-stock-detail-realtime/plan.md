# Real-Time Stock Detail Data Fetching - Implementation Plan

**Feature:** Real-time stock detail data fetching and display
**Date:** 2025-12-18
**Status:** Planning
**Priority:** High

---

## Overview

Implement end-to-end real-time stock detail data fetching when user selects a stock from search bar. Replace hardcoded data in dashboard with live data from vnstock API.

**Goal:** Single stock selection → Fetch all required data → Update all dashboard components

---

## Current State

**Frontend:**
- Components exist: `StockTickerHeader`, `StockDetailPanel`, `StockStatsTable`, `StockCompanyInfo`
- All use hardcoded props in `/apps/web/src/app/page.tsx`
- Search bar implemented, returns `StockSymbol` (symbol, organ_name)
- No state management for selected stock

**Backend:**
- Endpoints: `/stocks/price-board`, `/stocks/{symbol}/company`, `/stocks/{symbol}/financials/ratios`
- Requires 3 separate API calls to get all data
- Missing fields: `match_price`, `highest`, `lowest` in price board schema

---

## Architecture

```
User selects stock from search
    ↓
DashboardHeader.handleStockSelect(symbol)
    ↓
Update page state: selectedSymbol
    ↓
useStockDetail hook fetches data
    ↓
Single API call: GET /stocks/{symbol}/detail
    ↓
Backend combines: price_board + company_overview + ratio_summary
    ↓
Frontend updates all 4 components with real data
```

---

## Implementation Phases

### Phase 1: Backend - Unified Stock Detail Endpoint
**File:** `phase-01-backend-stock-detail-endpoint.md`
**Status:** DONE
**Completed:** 2025-12-18 21:53:48
**Effort:** 4-6 hours

- Create `GET /stocks/{symbol}/detail` endpoint
- New `StockDetail` schema with all required fields
- Combine vnstock calls: `price_board()`, `company.overview()`, `company.ratio_summary()`
- Update `PriceBoardItem` schema with missing fields

### Phase 2: Frontend - State Management & Data Fetching
**File:** `phase-02-frontend-state-management.md`
**Status:** Pending
**Effort:** 3-4 hours

- Create `useStockDetail` custom hook
- State: `selectedSymbol`, `stockDetail`, `isLoading`, `error`
- Auto-fetch when symbol changes
- Add loading/error UI states

### Phase 3: Frontend - Search Integration & Component Updates
**File:** `phase-03-search-integration.md`
**Status:** Pending
**Effort:** 2-3 hours

- Update `DashboardHeader.handleStockSelect` to lift state
- Pass `selectedSymbol` to page component
- Update all 4 components with real data props
- Add default stock (e.g., VCB) on initial load

---

## Data Mapping

### vnstock → StockDetail Schema

**Price Board:**
- `match_price` → `price`
- `ceiling`, `floor`, `ref_price`
- `highest` → `highPrice`
- `lowest` → `lowPrice`
- `accumulated_volume` → `volume`
- `accumulated_value` → `tradingValue`

**Company Overview:**
- `organ_name` / `short_name` → `companyName`
- `industry` → `industry`
- `issue_share` → `outstandingShares`
- `exchange` → `exchange`

**Financial Ratios (ratio_summary):**
- `eps` → `eps`
- `pe` → `pe`
- `beta` (from lang='vi') → `beta`
- Dividend yield → `dividendYield`

---

## Success Criteria

- [ ] User selects stock from search → All components update with real data
- [ ] Single API call fetches all required data (< 2s response time)
- [ ] Loading states display during data fetch
- [ ] Error handling for invalid symbols or API failures
- [ ] Default stock (VCB) loads on page mount
- [ ] All 4 components render with correct data formatting

---

## Dependencies

- vnstock library (already installed)
- Existing backend service layer
- Existing frontend components (no changes needed)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| vnstock API rate limits | High | Add caching layer, throttle requests |
| Missing data fields (Beta, Dividend) | Medium | Handle null values gracefully, show "N/A" |
| Slow API response (> 3s) | Medium | Add timeout, show loading skeleton |
| Invalid symbol selection | Low | Validate symbol before API call |

---

## Related Files

**Backend:**
- `/apps/api/src/stocks/router.py`
- `/apps/api/src/stocks/service.py`
- `/apps/api/src/stocks/schemas.py`

**Frontend:**
- `/apps/web/src/app/page.tsx`
- `/apps/web/src/components/layout/dashboard-header.tsx`
- `/apps/web/src/lib/api.ts`
- `/apps/web/src/components/dashboard/*`

**Research:**
- `/plans/251218-2134-stock-detail-realtime/research/researcher-01-vnstock-price-data.md`
- `/plans/251218-2134-stock-detail-realtime/research/researcher-02-frontend-components.md`

---

## Next Steps

1. Review and approve plan
2. Implement Phase 1 (backend endpoint)
3. Test endpoint with Postman/curl
4. Implement Phase 2 (frontend state)
5. Implement Phase 3 (integration)
6. End-to-end testing
