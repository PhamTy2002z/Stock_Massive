# Phase 3: API Endpoints

**Status:** ✅ Completed
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

- [x] Create apps/api/src/stocks/router.py
- [x] Update apps/api/src/main.py to include router
- [x] Add query parameter validation
- [x] Test endpoints with curl/httpie

## Success Criteria

- [x] All endpoints return valid JSON
- [x] OpenAPI docs show all endpoints
- [x] Error responses follow consistent format

## Completion Notes
- Routers modularized: `apps/api/src/stocks/{price,company,financial,market,analytics}/router.py`
- Main router aggregates sub-routers: `apps/api/src/stocks/router.py`
- Validators in `apps/api/src/stocks/shared/validators.py`

## Next Steps

Proceed to [phase-04-testing.md](phase-04-testing.md)
