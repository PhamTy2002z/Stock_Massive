# Phase 2: Stock Data Service

**Status:** Pending
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

- [ ] Create apps/api/src/stocks/schemas.py
- [ ] Create apps/api/src/stocks/service.py
- [ ] Add error handling for API failures
- [ ] Test service methods independently

## Success Criteria

- Service returns typed Pydantic models
- Handles invalid symbols gracefully
- Clean separation from vnstock internals

## Next Steps

Proceed to [phase-03-api-endpoints.md](phase-03-api-endpoints.md)
