# Phase 02: Implementation

**Status:** Done
**Completed:** 2025-12-18
**Priority:** High

## Context

Integrate components into dashboard page with API data fetching.

## Requirements

### 1. Market Indices Container
- Fetches data from `/api/v1/stocks/price-board`
- Displays 4 index cards in grid
- File: `apps/web/src/components/dashboard/market-indices.tsx`

### 2. Dashboard Page Update
- Import and render MarketIndices
- File: `apps/web/src/app/page.tsx`

### 3. API Integration
- Create fetch utility for stock data
- Handle loading/error states
- File: `apps/web/src/lib/api.ts`

## Implementation Steps

1. Create API fetch utility
2. Create MarketIndices container component
3. Update dashboard page
4. Test with real API data

## API Endpoints Used

- `GET /api/v1/stocks/price-board` - Real-time price data

## Success Criteria

- [ ] Data loads from API
- [ ] Loading skeleton shown
- [ ] Error handling works
- [ ] Cards update with real data
