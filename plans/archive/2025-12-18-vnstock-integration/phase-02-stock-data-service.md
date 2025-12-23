# Phase 2: Stock Data Service

**Status:** ✅ Completed
**Priority:** High

## Context

- [plan.md](plan.md) - Main plan
- [phase-01-core-setup.md](phase-01-core-setup.md) - Prerequisites

## Overview

Create service layer wrapping vnstock library with clean interfaces.

## Requirements

1. Stock data service with vnstock wrapper
2. Pydantic schemas for API responses
3. Error handling for invalid symbols/dates

## Architecture

```python
# Service pattern
class StockService:
    def get_history(symbol, start, end, interval) -> list[StockPrice]
    def get_intraday(symbol) -> list[IntradayTick]
    def get_company_overview(symbol) -> CompanyOverview
    def get_financial_ratios(symbol, period) -> list[FinancialRatio]
    def list_symbols(exchange) -> list[StockSymbol]
```

## Implementation Steps

### 2.1 Create stocks/schemas.py
- StockPrice, IntradayTick, CompanyOverview schemas
- FinancialRatio, StockSymbol schemas
- Request/Response models

### 2.2 Create stocks/service.py
- VnstockService class wrapping vnstock
- Methods for each data type
- DataFrame to Pydantic conversion
- Error handling

## Todo List

- [x] Create apps/api/src/stocks/schemas.py
- [x] Create apps/api/src/stocks/service.py
- [x] Add error handling for API failures
- [x] Test service methods independently

## Success Criteria

- [x] Service returns typed Pydantic models
- [x] Handles invalid symbols gracefully
- [x] Clean separation from vnstock internals

## Completion Notes
- Schemas modularized: `apps/api/src/stocks/schemas/{common,price,company,financial,market,analytics}.py`
- Services modularized: `apps/api/src/stocks/{price,company,financial,market,analytics}/service.py`
- Shared utilities: `apps/api/src/stocks/shared/{exceptions,validators,converters}.py`

## Next Steps

Proceed to [phase-03-api-endpoints.md](phase-03-api-endpoints.md)
