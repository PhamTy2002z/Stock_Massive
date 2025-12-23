# Phase 4: Split Routers by Domain

**Date:** 2024-12-19
**Priority:** P2
**Status:** done
**Effort:** 1h

## Context

- [Plan Overview](plan.md)
- [Schema-Router Mapping](research/researcher-02-schemas-router-mapping.md)
- **Depends on:** Phase 1-3 (shared utilities, schemas, services split)

## Overview

Split monolithic `router.py` (485 lines) into domain-specific routers. Main router becomes aggregator that includes sub-routers. All 27 endpoints remain accessible at same paths.

## Related Files

- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/router.py` (all 485 lines)
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/api/v1/router.py` (includes stocks router)

## Requirements

1. Create domain router files
2. Split endpoints by domain (19 endpoints total)
3. Maintain all URL paths unchanged
4. Aggregate sub-routers in main router
5. Preserve OpenAPI tags and documentation

## Endpoint Distribution

| Domain | Endpoints | Lines | Tags |
|--------|-----------|-------|------|
| Symbol/Market | 3 | ~80 | ["stocks"] |
| Price | 6 | ~150 | ["stocks"] |
| Company | 5 | ~120 | ["stocks"] |
| Financial | 6 | ~130 | ["stocks"] |
| Market | 2 | ~60 | ["stocks"] |

## Implementation Steps

### Step 1: Create Router Files

```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks
touch price/router.py
touch company/router.py
touch financial/router.py
touch market/router.py
```

### Step 2: Create Price Router

**File:** `stocks/price/router.py`

Extract price-related endpoints:

```python
"""Price domain router."""

from fastapi import APIRouter, HTTPException, Query
from datetime import date
from typing import List

from ..service import get_stock_service
from ..schemas.price import (
    StockPrice,
    IntradayTick,
    PriceBoardItem,
    MarketIndexItem,
    IntradayCollectionResult,
    VolumeAnalysisResponse,
)
from ..schemas.common import HistoryParams
from ..shared import StockServiceError


router = APIRouter()


@router.get("/{symbol}/history", response_model=List[StockPrice])
async def get_stock_history(
    symbol: str,
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: date = Query(..., description="End date (YYYY-MM-DD)"),
    interval: str = Query("1D", description="Interval: 1D, 1W, 1M"),
) -> List[StockPrice]:
    """Get historical OHLCV data for a stock.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    - **start**: Start date
    - **end**: End date
    - **interval**: Data interval (1D=daily, 1W=weekly, 1M=monthly)
    """
    try:
        service = get_stock_service()
        return service.get_history(symbol, start, end, interval)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/intraday", response_model=List[IntradayTick])
async def get_intraday_data(symbol: str) -> List[IntradayTick]:
    """Get intraday tick data for a stock.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_stock_service()
        return service.get_intraday(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/market-indices", response_model=List[MarketIndexItem])
async def get_market_indices() -> List[MarketIndexItem]:
    """Get market indices (VN-INDEX, VN30, HNX, UPCOM)."""
    try:
        service = get_stock_service()
        return service.get_market_indices()
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/price-board", response_model=List[PriceBoardItem])
async def get_price_board(
    symbols_list: str = Query("VN30", description="Symbol list (VN30, HNX30, etc)")
) -> List[PriceBoardItem]:
    """Get real-time price board for a list of symbols.

    - **symbols_list**: VN30, HNX30, UPCOM, or custom list
    """
    try:
        service = get_stock_service()
        return service.get_price_board(symbols_list)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/intraday/collect", response_model=IntradayCollectionResult)
async def collect_intraday_data() -> IntradayCollectionResult:
    """Trigger intraday data collection for all VN30 stocks."""
    # ... (existing implementation from original router)


@router.get("/{symbol}/volume-analysis", response_model=VolumeAnalysisResponse)
async def get_volume_analysis(symbol: str) -> VolumeAnalysisResponse:
    """Get volume pattern analysis for a stock.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    # ... (existing implementation from original router)
```

### Step 3: Create Company Router

**File:** `stocks/company/router.py`

Extract company-related endpoints:

```python
"""Company domain router."""

from fastapi import APIRouter, HTTPException
from typing import List

from ..service import get_stock_service
from ..schemas.company import (
    CompanyOverview,
    StockDetail,
    ShareholdersResponse,
    OfficersResponse,
    InsiderDealsResponse,
)
from ..shared import StockServiceError


router = APIRouter()


@router.get("/{symbol}/company", response_model=CompanyOverview)
async def get_company_overview(symbol: str) -> CompanyOverview:
    """Get company overview information.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_stock_service()
        return service.get_company_overview(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/detail", response_model=StockDetail)
async def get_stock_detail(symbol: str) -> StockDetail:
    """Get comprehensive stock detail data (composite endpoint).

    Combines price, company, and financial data.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_stock_service()
        return service.get_stock_detail(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/shareholders", response_model=ShareholdersResponse)
async def get_shareholders(symbol: str) -> ShareholdersResponse:
    """Get major shareholders for a stock.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_stock_service()
        return service.get_shareholders(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/officers", response_model=OfficersResponse)
async def get_officers(symbol: str) -> OfficersResponse:
    """Get company officers/management.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_stock_service()
        return service.get_officers(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/insider-deals", response_model=InsiderDealsResponse)
async def get_insider_deals(symbol: str) -> InsiderDealsResponse:
    """Get insider trading deals.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_stock_service()
        return service.get_insider_deals(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

### Step 4: Create Financial Router

**File:** `stocks/financial/router.py`

Extract financial-related endpoints:

```python
"""Financial domain router."""

from fastapi import APIRouter, HTTPException
from typing import List

from ..service import get_stock_service
from ..schemas.financial import (
    FinancialRatio,
    IncomeStatementItem,
    IncomeStatementResponse,
    BalanceSheetItem,
    BalanceSheetResponse,
    CashFlowResponse,
)
from ..shared import StockServiceError


router = APIRouter()


@router.get("/{symbol}/financials/ratios", response_model=List[FinancialRatio])
async def get_financial_ratios(symbol: str) -> List[FinancialRatio]:
    """Get financial ratios for a stock.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_stock_service()
        return service.get_financial_ratios(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/income", response_model=List[IncomeStatementItem])
async def get_income_statement(symbol: str) -> List[IncomeStatementItem]:
    """Get income statement (simple format).

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_stock_service()
        return service.get_income_statement(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/income-statement", response_model=IncomeStatementResponse)
async def get_income_statement_detailed(symbol: str) -> IncomeStatementResponse:
    """Get income statement (detailed format with quarters).

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_stock_service()
        return service.get_income_statement_detailed(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/balance-sheet", response_model=List[BalanceSheetItem])
async def get_balance_sheet(symbol: str) -> List[BalanceSheetItem]:
    """Get balance sheet (simple format).

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_stock_service()
        return service.get_balance_sheet(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/balance-sheet-detailed", response_model=BalanceSheetResponse)
async def get_balance_sheet_detailed(symbol: str) -> BalanceSheetResponse:
    """Get balance sheet (detailed format with quarters).

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_stock_service()
        return service.get_balance_sheet_detailed(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/cash-flow", response_model=CashFlowResponse)
async def get_cash_flow_detailed(symbol: str) -> CashFlowResponse:
    """Get cash flow statement (detailed format with quarters).

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_stock_service()
        return service.get_cash_flow_detailed(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

### Step 5: Create Market Router

**File:** `stocks/market/router.py`

Extract market-related endpoints:

```python
"""Market domain router."""

from fastapi import APIRouter, HTTPException, Query
from typing import List

from ..service import get_stock_service
from ..schemas.company import StockSymbol
from ..schemas.market import (
    SectorPerformanceResponse,
    FundCertificatesResponse,
)
from ..shared import StockServiceError


router = APIRouter()


@router.get("/symbols", response_model=List[StockSymbol])
async def list_symbols() -> List[StockSymbol]:
    """List all available stock symbols."""
    try:
        service = get_stock_service()
        return service.list_symbols()
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/symbols/group/{group}", response_model=List[str])
async def list_symbols_by_group(group: str) -> List[str]:
    """List symbols by group (VN30, HNX30, etc).

    - **group**: Group name (VN30, HNX30, UPCOM, etc)
    """
    try:
        service = get_stock_service()
        return service.list_symbols_by_group(group)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/symbols/search", response_model=List[StockSymbol])
async def search_symbols(
    q: str = Query(..., min_length=1, description="Search query")
) -> List[StockSymbol]:
    """Search symbols by ticker or company name.

    - **q**: Search query (ticker or company name)
    """
    try:
        service = get_stock_service()
        return service.search_symbols(q)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/sector-performance", response_model=SectorPerformanceResponse)
async def get_sector_performance() -> SectorPerformanceResponse:
    """Get sector performance data (ICB Level 2)."""
    try:
        service = get_stock_service()
        return service.get_sector_performance()
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/fund-certificates", response_model=FundCertificatesResponse)
async def get_fund_certificates() -> FundCertificatesResponse:
    """Get fund certificates data."""
    try:
        service = get_stock_service()
        return service.get_fund_certificates()
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

### Step 6: Update Main Router

**File:** `stocks/router.py` (replace existing)

```python
"""Main stocks router aggregating domain routers."""

from fastapi import APIRouter

from .price import router as price_router
from .company import router as company_router
from .financial import router as financial_router
from .market import router as market_router


# Main router with prefix and tags
router = APIRouter(prefix="/stocks", tags=["stocks"])

# Include domain routers
router.include_router(market_router)    # Symbol endpoints (no prefix)
router.include_router(price_router)     # Price endpoints
router.include_router(company_router)   # Company endpoints
router.include_router(financial_router) # Financial endpoints

# Note: Order matters for path matching
# - /symbols/* must come before /{symbol}/*
# - Market router first to match /symbols, /sector-performance, /fund-certificates
# - Then domain routers for /{symbol}/* paths
```

### Step 7: Update Domain __init__.py Files

**File:** `stocks/price/__init__.py`

```python
"""Price domain module."""

from .service import PriceService
from .router import router

__all__ = ["PriceService", "router"]
```

Repeat for company, financial, market modules.

### Step 8: Verify API Registration

Ensure `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/api/v1/router.py` includes stocks router:

```python
from src.stocks.router import router as stocks_router

api_router.include_router(stocks_router, prefix="/api/v1")
```

This should continue to work without changes.

### Step 9: Rename Original File

```bash
mv router.py router_old.py
```

Keep as backup until Phase 5 verification.

## Success Criteria

- [x] 4 domain routers created
- [x] Main router aggregates sub-routers
- [x] All 27 endpoints accessible at same paths
- [x] OpenAPI docs show all endpoints under "stocks" tag
- [x] All tests pass
- [x] No breaking changes to API paths

## Testing

```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/api
pytest tests/test_stocks_router.py -v
pytest tests/test_sector_performance.py -v
pytest tests/ -v

# Manual API testing
curl http://localhost:8000/api/v1/stocks/symbols
curl http://localhost:8000/api/v1/stocks/VCB/detail
curl http://localhost:8000/api/v1/stocks/market-indices
curl http://localhost:8000/api/v1/stocks/sector-performance

# Check OpenAPI docs
open http://localhost:8000/docs
```

## Risk Assessment

**Low-Medium Risk:**
- Router splitting is straightforward
- Path matching order is critical
- OpenAPI documentation must remain consistent

**Mitigation:**
- Keep `router_old.py` as backup
- Test all 27 endpoints manually
- Verify OpenAPI docs completeness
- Check path matching order (symbols before {symbol})
- Run integration tests

## Path Matching Order

**Critical:** Market router must be included first to match:
- `/symbols`
- `/symbols/group/{group}`
- `/symbols/search`
- `/sector-performance`
- `/fund-certificates`

Before other routers match `/{symbol}/*` paths.

## OpenAPI Documentation

All endpoints should remain under single "stocks" tag for consistency. Domain separation is internal implementation detail.
