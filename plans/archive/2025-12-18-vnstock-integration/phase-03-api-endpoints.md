# Phase 3: API Endpoints

**Status:** Pending
**Priority:** High

## Context

- [plan.md](plan.md) - Main plan
- [phase-02-stock-data-service.md](phase-02-stock-data-service.md) - Service layer

## Overview

Create FastAPI router with RESTful endpoints for stock data.

## API Design

```
GET /api/v1/stocks/symbols              # List all symbols
GET /api/v1/stocks/symbols/{group}      # Symbols by group (VN30, etc.)
GET /api/v1/stocks/{symbol}/history     # Historical OHLCV
GET /api/v1/stocks/{symbol}/intraday    # Intraday ticks
GET /api/v1/stocks/{symbol}/company     # Company overview
GET /api/v1/stocks/{symbol}/financials  # Financial statements
GET /api/v1/stocks/{symbol}/ratios      # Financial ratios
GET /api/v1/stocks/price-board          # Real-time price board
```

## Implementation Steps

### 3.1 Create stocks/router.py
- FastAPI APIRouter with prefix "/stocks"
- Dependency injection for service
- Query params for filtering

### 3.2 Register router in main.py
- Include router with v1 prefix
- Add OpenAPI tags

### 3.3 Add request validation
- Date format validation
- Symbol format validation
- Pagination support

## Todo List

- [ ] Create apps/api/src/stocks/router.py
- [ ] Update apps/api/src/main.py to include router
- [ ] Add query parameter validation
- [ ] Test endpoints with curl/httpie

## Success Criteria

- All endpoints return valid JSON
- OpenAPI docs show all endpoints
- Error responses follow consistent format

## Next Steps

Proceed to [phase-04-testing.md](phase-04-testing.md)
