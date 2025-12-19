# Plan: Vnstock Market Indices Integration

## Overview
- **Date**: 2024-12-18
- **Status**: Draft
- **Priority**: High
- **Description**: Integrate real market index data (VNINDEX, VN30, HNXINDEX, UPCOMINDEX) into dashboard "Chỉ số thị trường" section using vnstock library.

## Context
- Dashboard has mock data in `market-indices.tsx`
- UI components (`StockIndexCard`, `Sparkline`) already implemented
- Backend uses vnstock library with VCI source
- Need: Backend endpoint + Frontend API integration

## Phases

| Phase | Name | Status | File |
|-------|------|--------|------|
| 01 | Backend API Endpoint | Pending | [phase-01-backend-api.md](./phase-01-backend-api.md) |
| 02 | Frontend Integration | Pending | [phase-02-frontend-integration.md](./phase-02-frontend-integration.md) |

## Research
- [Vnstock Index API](./research/researcher-01-vnstock-index-api.md)
- [Frontend Integration](./research/researcher-02-frontend-integration.md)

## Key Decisions
1. Use `Quote(symbol='VNINDEX')` pattern for index data
2. Fetch 10-day history for sparkline chart
3. Calculate change from last 2 trading days
4. Server Component with client-side refresh for real-time feel

## Success Criteria
- [ ] `/api/v1/indices` endpoint returns 4 indices with real data
- [ ] Dashboard displays live market indices
- [ ] Sparkline shows 10-day price trend
- [ ] Loading skeleton shown during fetch
- [ ] Error handling for API failures
