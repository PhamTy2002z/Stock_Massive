# Phase 3: Split Services by Domain

**Date:** 2024-12-19
**Priority:** P2
**Status:** done
**Effort:** 2h

## Context

- [Plan Overview](plan.md)
- [Service Domain Analysis](research/researcher-01-service-domain-analysis.md)
- **Depends on:** Phase 1 (shared utilities), Phase 2 (schemas split)

## Overview

Split monolithic `service.py` (1,507 lines) into 4 domain services + 1 facade. Each domain service handles specific business logic with converters. Main `StockService` becomes facade aggregating domain services.

## Related Files

- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/service.py` (all 1,507 lines)
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/router.py` (uses StockService)

## Requirements

1. Create domain service classes
2. Move converters to `shared/converters.py`
3. Maintain singleton pattern via facade
4. Preserve all method signatures
5. Handle cross-domain dependencies (StockDetail)

## Service Distribution

| Domain | Methods | Converters | Total Lines |
|--------|---------|------------|-------------|
| PriceService | 4 | 3 | ~200 |
| CompanyService | 5 | 1 | ~230 |
| FinancialService | 6 | 6 | ~450 |
| MarketService | 4 | 1 | ~140 |
| StockService (facade) | 1 composite | - | ~50 |

## Implementation Steps

### Step 1: Move Converters to Shared

**File:** `stocks/shared/converters.py`

Add all converter methods from service.py (lines 1009-1495):

```python
"""Data conversion utilities for DataFrame to Pydantic models."""

from typing import Any, Optional, List
import pandas as pd
from ..schemas.price import StockPrice, IntradayTick, PriceBoardItem
from ..schemas.company import CompanyOverview, StockSymbol
from ..schemas.financial import (
    FinancialRatio,
    IncomeStatementItem,
    IncomeStatementRow,
    IncomeStatementResponse,
    BalanceSheetItem,
    BalanceSheetRow,
    BalanceSheetResponse,
    CashFlowRow,
    CashFlowResponse,
)


def _safe_float(value: Any) -> Optional[float]:
    """Safely convert value to float."""
    # ... (existing implementation)


def df_to_stock_symbols(df: pd.DataFrame) -> List[StockSymbol]:
    """Convert DataFrame to StockSymbol list."""
    # ... (lines 1009-1025)


def df_to_stock_prices(df: pd.DataFrame) -> List[StockPrice]:
    """Convert DataFrame to StockPrice list."""
    # ... (lines 1027-1055)


def df_to_intraday_ticks(df: pd.DataFrame) -> List[IntradayTick]:
    """Convert DataFrame to IntradayTick list."""
    # ... (lines 1057-1082)


def to_company_overview(data: dict) -> CompanyOverview:
    """Convert dict to CompanyOverview."""
    # ... (lines 1084-1117)


def df_to_financial_ratios(df: pd.DataFrame) -> List[FinancialRatio]:
    """Convert DataFrame to FinancialRatio list."""
    # ... (lines 1119-1159)


def df_to_income_statements(df: pd.DataFrame) -> List[IncomeStatementItem]:
    """Convert DataFrame to IncomeStatementItem list."""
    # ... (lines 1161-1193)


def df_to_income_statement_response(df: pd.DataFrame) -> IncomeStatementResponse:
    """Convert DataFrame to IncomeStatementResponse."""
    # ... (lines 1195-1268)


def df_to_balance_sheets(df: pd.DataFrame) -> List[BalanceSheetItem]:
    """Convert DataFrame to BalanceSheetItem list."""
    # ... (lines 1270-1302)


def df_to_balance_sheet_response(df: pd.DataFrame) -> BalanceSheetResponse:
    """Convert DataFrame to BalanceSheetResponse."""
    # ... (lines 1304-1370)


def df_to_cash_flow_response(df: pd.DataFrame) -> CashFlowResponse:
    """Convert DataFrame to CashFlowResponse."""
    # ... (lines 1372-1453)


def df_to_price_board(df: pd.DataFrame) -> List[PriceBoardItem]:
    """Convert DataFrame to PriceBoardItem list."""
    # ... (lines 1466-1495)
```

Update `shared/__init__.py` to export converters.

### Step 2: Create Price Service

**File:** `stocks/price/service.py`

Extract lines 81-114, 116-137, 423-501:

```python
"""Price domain service."""

from datetime import date
from typing import List
from vnstock3 import Vnstock

from ..schemas.price import (
    StockPrice,
    IntradayTick,
    PriceBoardItem,
    MarketIndexItem,
)
from ..shared import validate_symbol, StockServiceError
from ..shared.converters import (
    df_to_stock_prices,
    df_to_intraday_ticks,
    df_to_price_board,
)


class PriceService:
    """Price domain service for historical and real-time price data."""

    def __init__(self):
        """Initialize price service with vnstock."""
        self.stock = Vnstock().stock(symbol="VN30", source="VCI")

    def get_history(
        self, symbol: str, start: date, end: date, interval: str = "1D"
    ) -> List[StockPrice]:
        """Get historical OHLCV data."""
        # ... (lines 81-114)

    def get_intraday(self, symbol: str) -> List[IntradayTick]:
        """Get intraday tick data."""
        # ... (lines 116-137)

    def get_price_board(self, symbols_list: str = "VN30") -> List[PriceBoardItem]:
        """Get real-time price board."""
        # ... (lines 423-446)

    def get_market_indices(self) -> List[MarketIndexItem]:
        """Get market indices (VN-INDEX, VN30, HNX, UPCOM)."""
        # ... (lines 448-501)
```

**File:** `stocks/price/__init__.py`

```python
"""Price domain module."""

from .service import PriceService

__all__ = ["PriceService"]
```

### Step 3: Create Company Service

**File:** `stocks/company/service.py`

Extract lines 139-159, 629-795:

```python
"""Company domain service."""

from typing import List
from vnstock3 import Vnstock

from ..schemas.company import (
    CompanyOverview,
    ShareholdersResponse,
    ShareholderItem,
    OfficersResponse,
    OfficerItem,
    InsiderDealsResponse,
    InsiderDealItem,
)
from ..shared import validate_symbol, StockServiceError
from ..shared.converters import to_company_overview


class CompanyService:
    """Company domain service for company information."""

    def __init__(self):
        """Initialize company service with vnstock."""
        self.stock = Vnstock().stock(symbol="VN30", source="VCI")

    def get_company_overview(self, symbol: str) -> CompanyOverview:
        """Get company overview information."""
        # ... (lines 139-159)

    def get_shareholders(self, symbol: str) -> ShareholdersResponse:
        """Get major shareholders."""
        # ... (lines 629-677)

    def get_officers(self, symbol: str) -> OfficersResponse:
        """Get company officers/management."""
        # ... (lines 679-735)

    def get_insider_deals(self, symbol: str) -> InsiderDealsResponse:
        """Get insider trading deals."""
        # ... (lines 737-795)
```

**File:** `stocks/company/__init__.py`

```python
"""Company domain module."""

from .service import CompanyService

__all__ = ["CompanyService"]
```

### Step 4: Create Financial Service

**File:** `stocks/financial/service.py`

Extract lines 161-333:

```python
"""Financial domain service."""

from typing import List
from vnstock3 import Vnstock

from ..schemas.financial import (
    FinancialRatio,
    IncomeStatementItem,
    IncomeStatementResponse,
    BalanceSheetItem,
    BalanceSheetResponse,
    CashFlowResponse,
)
from ..shared import validate_symbol, StockServiceError
from ..shared.converters import (
    df_to_financial_ratios,
    df_to_income_statements,
    df_to_income_statement_response,
    df_to_balance_sheets,
    df_to_balance_sheet_response,
    df_to_cash_flow_response,
)


class FinancialService:
    """Financial domain service for financial statements and ratios."""

    def __init__(self):
        """Initialize financial service with vnstock."""
        self.stock = Vnstock().stock(symbol="VN30", source="VCI")

    def get_financial_ratios(self, symbol: str) -> List[FinancialRatio]:
        """Get financial ratios."""
        # ... (lines 161-188)

    def get_income_statement(self, symbol: str) -> List[IncomeStatementItem]:
        """Get income statement (simple)."""
        # ... (lines 190-217)

    def get_income_statement_detailed(self, symbol: str) -> IncomeStatementResponse:
        """Get income statement (detailed)."""
        # ... (lines 219-246)

    def get_balance_sheet(self, symbol: str) -> List[BalanceSheetItem]:
        """Get balance sheet (simple)."""
        # ... (lines 248-275)

    def get_balance_sheet_detailed(self, symbol: str) -> BalanceSheetResponse:
        """Get balance sheet (detailed)."""
        # ... (lines 277-304)

    def get_cash_flow_detailed(self, symbol: str) -> CashFlowResponse:
        """Get cash flow statement (detailed)."""
        # ... (lines 306-333)
```

**File:** `stocks/financial/__init__.py`

```python
"""Financial domain module."""

from .service import FinancialService

__all__ = ["FinancialService"]
```

### Step 5: Create Market Service

**File:** `stocks/market/service.py`

Extract lines 335-421, 797-920:

```python
"""Market domain service."""

from typing import List
from vnstock3 import Vnstock

from ..schemas.company import StockSymbol
from ..schemas.market import (
    SectorPerformanceResponse,
    SectorPerformanceItem,
    FundCertificatesResponse,
    FundCertificateItem,
)
from ..shared import StockServiceError
from ..shared.converters import df_to_stock_symbols


class MarketService:
    """Market domain service for listings and market-wide data."""

    def __init__(self):
        """Initialize market service with vnstock."""
        self.stock = Vnstock().stock(symbol="VN30", source="VCI")

    def list_symbols(self) -> List[StockSymbol]:
        """List all stock symbols."""
        # ... (lines 335-366)

    def list_symbols_by_group(self, group: str) -> List[str]:
        """List symbols by group (VN30, HNX30, etc)."""
        # ... (lines 368-387)

    def search_symbols(self, query: str) -> List[StockSymbol]:
        """Search symbols by ticker or name."""
        # ... (lines 389-421)

    def get_sector_performance(self) -> SectorPerformanceResponse:
        """Get sector performance (ICB Level 2)."""
        # ... (lines 797-870)

    def get_fund_certificates(self) -> FundCertificatesResponse:
        """Get fund certificates data."""
        # ... (lines 872-920)
```

**File:** `stocks/market/__init__.py`

```python
"""Market domain module."""

from .service import MarketService

__all__ = ["MarketService"]
```

### Step 6: Create Facade Service

**File:** `stocks/service.py` (replace existing)

```python
"""Stock service facade aggregating domain services."""

from typing import Optional
from datetime import date

from .price import PriceService
from .company import CompanyService
from .financial import FinancialService
from .market import MarketService
from .schemas.company import StockDetail
from .shared import validate_symbol, StockServiceError


class StockService:
    """Facade service aggregating all domain services."""

    def __init__(self):
        """Initialize facade with domain services."""
        self.price = PriceService()
        self.company = CompanyService()
        self.financial = FinancialService()
        self.market = MarketService()

    def get_stock_detail(self, symbol: str) -> StockDetail:
        """Get comprehensive stock detail (composite method).

        Combines data from price, company, and financial domains.
        """
        # ... (lines 503-627 from original service.py)
        # This method orchestrates calls to:
        # - self.price.get_price_board()
        # - self.company.get_company_overview()
        # - self.financial.get_financial_ratios()

    # Delegate methods for backward compatibility
    def get_history(self, symbol: str, start: date, end: date, interval: str = "1D"):
        """Delegate to price service."""
        return self.price.get_history(symbol, start, end, interval)

    def get_intraday(self, symbol: str):
        """Delegate to price service."""
        return self.price.get_intraday(symbol)

    def get_price_board(self, symbols_list: str = "VN30"):
        """Delegate to price service."""
        return self.price.get_price_board(symbols_list)

    def get_market_indices(self):
        """Delegate to price service."""
        return self.price.get_market_indices()

    def get_company_overview(self, symbol: str):
        """Delegate to company service."""
        return self.company.get_company_overview(symbol)

    def get_shareholders(self, symbol: str):
        """Delegate to company service."""
        return self.company.get_shareholders(symbol)

    def get_officers(self, symbol: str):
        """Delegate to company service."""
        return self.company.get_officers(symbol)

    def get_insider_deals(self, symbol: str):
        """Delegate to company service."""
        return self.company.get_insider_deals(symbol)

    def get_financial_ratios(self, symbol: str):
        """Delegate to financial service."""
        return self.financial.get_financial_ratios(symbol)

    def get_income_statement(self, symbol: str):
        """Delegate to financial service."""
        return self.financial.get_income_statement(symbol)

    def get_income_statement_detailed(self, symbol: str):
        """Delegate to financial service."""
        return self.financial.get_income_statement_detailed(symbol)

    def get_balance_sheet(self, symbol: str):
        """Delegate to financial service."""
        return self.financial.get_balance_sheet(symbol)

    def get_balance_sheet_detailed(self, symbol: str):
        """Delegate to financial service."""
        return self.financial.get_balance_sheet_detailed(symbol)

    def get_cash_flow_detailed(self, symbol: str):
        """Delegate to financial service."""
        return self.financial.get_cash_flow_detailed(symbol)

    def list_symbols(self):
        """Delegate to market service."""
        return self.market.list_symbols()

    def list_symbols_by_group(self, group: str):
        """Delegate to market service."""
        return self.market.list_symbols_by_group(group)

    def search_symbols(self, query: str):
        """Delegate to market service."""
        return self.market.search_symbols(query)

    def get_sector_performance(self):
        """Delegate to market service."""
        return self.market.get_sector_performance()

    def get_fund_certificates(self):
        """Delegate to market service."""
        return self.market.get_fund_certificates()


# Singleton pattern
_stock_service: Optional[StockService] = None


def get_stock_service() -> StockService:
    """Get singleton StockService instance."""
    global _stock_service
    if _stock_service is None:
        _stock_service = StockService()
    return _stock_service
```

### Step 7: Update stocks/__init__.py

```python
"""Stocks module with domain-based architecture."""

from .service import StockService, get_stock_service
from .shared import StockServiceError

__all__ = [
    "StockService",
    "get_stock_service",
    "StockServiceError",
]
```

### Step 8: Rename Original File

```bash
mv service.py service_old.py
```

Keep as backup until Phase 5 verification.

## Success Criteria

- [x] 4 domain services created (price, company, financial, market)
- [x] Facade service delegates to domain services
- [x] All converters moved to `shared/converters.py`
- [x] Singleton pattern preserved
- [x] All method signatures unchanged
- [x] Router continues to work without changes
- [x] All tests pass

## Testing

```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/api
pytest tests/test_stocks_service.py -v
pytest tests/test_volume_analysis.py -v
pytest tests/test_intraday_collector.py -v
pytest tests/ -v
```

## Risk Assessment

**Medium Risk:**
- Large refactor with cross-domain dependencies
- Composite method `get_stock_detail` requires careful orchestration
- Singleton pattern must work with multiple services

**Mitigation:**
- Keep `service_old.py` as backup
- Test each domain service independently
- Verify facade delegation works correctly
- Run full test suite multiple times
- Check `get_stock_detail` composite logic carefully

## Unresolved Questions

1. Should converters stay in `shared/converters.py` or move to domain services?
   - **Decision:** Keep in shared for reusability and consistency

2. Should domain services be singletons or instantiated by facade?
   - **Decision:** Instantiated by facade, facade is singleton

3. How to handle vnstock instance sharing?
   - **Decision:** Each domain service has own vnstock instance for isolation
