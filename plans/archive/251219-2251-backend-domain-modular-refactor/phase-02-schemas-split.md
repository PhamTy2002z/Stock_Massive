# Phase 2: Split Schemas by Domain

**Date:** 2024-12-19
**Priority:** P2
**Status:** done
**Effort:** 1h
**Completed:** 2025-12-19

## Context

- [Plan Overview](plan.md)
- [Schema-Router Mapping](research/researcher-02-schemas-router-mapping.md)
- **Depends on:** Phase 1 (shared utilities)

## Overview

Split monolithic `schemas.py` (426 lines) into domain-specific schema modules. Maintain backward compatibility via re-exports from `stocks/schemas/__init__.py`.

## Related Files

- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/schemas.py` (all 426 lines)
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/router.py` (imports schemas)

## Requirements

1. Create `stocks/schemas/` directory
2. Split schemas into 5 domain files
3. Maintain all Pydantic model configurations
4. Re-export all schemas for backward compatibility
5. No changes to router imports

## Schema Distribution

| Domain | Schemas | Lines | Source Lines |
|--------|---------|-------|--------------|
| price.py | 10 | ~100 | 8-30, 164-204, 213-270 |
| company.py | 9 | ~90 | 32-54, 272-382 |
| financial.py | 9 | ~105 | 56-161 |
| market.py | 4 | ~45 | 384-426 |
| common.py | 1 | ~5 | 206-210 |

## Implementation Steps

### Step 1: Create Directory Structure

```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks
mkdir -p schemas
touch schemas/__init__.py
touch schemas/price.py
touch schemas/company.py
touch schemas/financial.py
touch schemas/market.py
touch schemas/common.py
```

### Step 2: Create Common Schemas

**File:** `stocks/schemas/common.py`

Extract lines 206-210 + 166-171 from original:

```python
"""Common schemas shared across domains."""

from pydantic import BaseModel, Field
from datetime import date
from typing import Optional


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str


class HistoryParams(BaseModel):
    """Query parameters for historical data."""
    start: date = Field(..., description="Start date")
    end: date = Field(..., description="End date")
    interval: str = Field("1D", description="Data interval (1D, 1W, 1M)")
```

### Step 3: Create Price Schemas

**File:** `stocks/schemas/price.py`

Extract lines 8-30, 164-204, 213-270:

```python
"""Price domain schemas."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class StockPrice(BaseModel):
    """Historical OHLCV price data."""
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class IntradayTick(BaseModel):
    """Intraday tick data."""
    time: datetime
    price: float
    volume: int
    # ... (complete from lines 21-29)


class PriceBoardItem(BaseModel):
    """Real-time price board item."""
    # ... (lines 174-193)


class MarketIndexItem(BaseModel):
    """Market index data."""
    # ... (lines 196-203)


class IntradayBarCreate(BaseModel):
    """Intraday bar creation schema."""
    # ... (lines 216-227)


class IntradayBar(IntradayBarCreate):
    """Database intraday bar with ID."""
    # ... (lines 230-237)


class IntradayCollectionResult(BaseModel):
    """Intraday collection result."""
    # ... (lines 240-245)


class VolumeTimePeriod(BaseModel):
    """Volume time period analysis."""
    # ... (lines 251-259)


class VolumeAnalysisResponse(BaseModel):
    """Volume analysis response."""
    # ... (lines 262-269)
```

### Step 4: Create Company Schemas

**File:** `stocks/schemas/company.py`

Extract lines 32-54, 272-382:

```python
"""Company domain schemas."""

from pydantic import BaseModel, Field
from typing import Optional


class CompanyOverview(BaseModel):
    """Company overview information."""
    # ... (lines 34-44)


class StockSymbol(BaseModel):
    """Stock symbol listing."""
    # ... (lines 47-53)


class StockDetail(BaseModel):
    """Comprehensive stock detail (composite)."""
    # ... (lines 272-321)


class ShareholderItem(BaseModel):
    """Shareholder data."""
    # ... (lines 327-334)


class ShareholdersResponse(BaseModel):
    """Shareholders response."""
    # ... (lines 337-342)


class OfficerItem(BaseModel):
    """Officer/management data."""
    # ... (lines 345-355)


class OfficersResponse(BaseModel):
    """Officers response."""
    # ... (lines 358-363)


class InsiderDealItem(BaseModel):
    """Insider trading deal."""
    # ... (lines 366-373)


class InsiderDealsResponse(BaseModel):
    """Insider deals response."""
    # ... (lines 376-381)
```

### Step 5: Create Financial Schemas

**File:** `stocks/schemas/financial.py`

Extract lines 56-161:

```python
"""Financial domain schemas."""

from pydantic import BaseModel, Field
from typing import Optional, List


class FinancialRatio(BaseModel):
    """Financial ratios."""
    # ... (lines 58-78)


class IncomeStatementItem(BaseModel):
    """Simple income statement item."""
    # ... (lines 81-90)


class IncomeStatementRow(BaseModel):
    """Detailed income statement row."""
    # ... (lines 93-101)


class IncomeStatementResponse(BaseModel):
    """Detailed income statement response."""
    # ... (lines 104-110)


class BalanceSheetItem(BaseModel):
    """Simple balance sheet item."""
    # ... (lines 113-121)


class BalanceSheetRow(BaseModel):
    """Detailed balance sheet row."""
    # ... (lines 124-132)


class BalanceSheetResponse(BaseModel):
    """Detailed balance sheet response."""
    # ... (lines 135-141)


class CashFlowRow(BaseModel):
    """Cash flow row."""
    # ... (lines 144-152)


class CashFlowResponse(BaseModel):
    """Cash flow response."""
    # ... (lines 155-161)
```

### Step 6: Create Market Schemas

**File:** `stocks/schemas/market.py`

Extract lines 384-426:

```python
"""Market domain schemas."""

from pydantic import BaseModel, Field
from typing import Optional, List


class SectorPerformanceItem(BaseModel):
    """Sector performance data."""
    # ... (lines 387-396)


class SectorPerformanceResponse(BaseModel):
    """Sector performance response."""
    # ... (lines 399-404)


class FundCertificateItem(BaseModel):
    """Fund certificate data."""
    # ... (lines 410-418)


class FundCertificatesResponse(BaseModel):
    """Fund certificates response."""
    # ... (lines 421-426)
```

### Step 7: Setup Re-exports

**File:** `stocks/schemas/__init__.py`

```python
"""Schemas module with backward compatibility re-exports."""

# Common
from .common import ErrorResponse, HistoryParams

# Price domain
from .price import (
    StockPrice,
    IntradayTick,
    PriceBoardItem,
    MarketIndexItem,
    IntradayBarCreate,
    IntradayBar,
    IntradayCollectionResult,
    VolumeTimePeriod,
    VolumeAnalysisResponse,
)

# Company domain
from .company import (
    CompanyOverview,
    StockSymbol,
    StockDetail,
    ShareholderItem,
    ShareholdersResponse,
    OfficerItem,
    OfficersResponse,
    InsiderDealItem,
    InsiderDealsResponse,
)

# Financial domain
from .financial import (
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

# Market domain
from .market import (
    SectorPerformanceItem,
    SectorPerformanceResponse,
    FundCertificateItem,
    FundCertificatesResponse,
)

__all__ = [
    # Common
    "ErrorResponse",
    "HistoryParams",
    # Price
    "StockPrice",
    "IntradayTick",
    "PriceBoardItem",
    "MarketIndexItem",
    "IntradayBarCreate",
    "IntradayBar",
    "IntradayCollectionResult",
    "VolumeTimePeriod",
    "VolumeAnalysisResponse",
    # Company
    "CompanyOverview",
    "StockSymbol",
    "StockDetail",
    "ShareholderItem",
    "ShareholdersResponse",
    "OfficerItem",
    "OfficersResponse",
    "InsiderDealItem",
    "InsiderDealsResponse",
    # Financial
    "FinancialRatio",
    "IncomeStatementItem",
    "IncomeStatementRow",
    "IncomeStatementResponse",
    "BalanceSheetItem",
    "BalanceSheetRow",
    "BalanceSheetResponse",
    "CashFlowRow",
    "CashFlowResponse",
    # Market
    "SectorPerformanceItem",
    "SectorPerformanceResponse",
    "FundCertificateItem",
    "FundCertificatesResponse",
]
```

### Step 8: Verify Router Imports

Ensure `router.py` continues to import from `stocks.schemas`:

```python
# This should continue to work without changes
from .schemas import (
    StockPrice,
    CompanyOverview,
    # ... all other schemas
)
```

### Step 9: Rename Original File

```bash
mv schemas.py schemas_old.py
```

Keep as backup until Phase 5 verification complete.

## Success Criteria

- [x] `stocks/schemas/` module created with 6 files
- [x] All 33 schemas split correctly by domain
- [x] Re-exports in `__init__.py` complete
- [x] Router imports unchanged and functional
- [x] All tests pass
- [x] No breaking changes

## Testing

```bash
cd /Users/typham/Documents/GitHub/Stock_Massive/apps/api
pytest tests/test_stocks_router.py -v
pytest tests/test_stocks_service.py -v
pytest tests/ -v
```

## Risk Assessment

**Low-Medium Risk:**
- Pure code organization, no logic changes
- Re-export strategy ensures compatibility
- Router imports remain unchanged

**Mitigation:**
- Keep `schemas_old.py` as backup
- Verify all 33 schemas in re-exports
- Test all 27 API endpoints
- Check Pydantic model_config preserved

## Unresolved Questions

- Should `HistoryParams` stay in common or move to price domain?
- Should `StockDetail` (composite) stay in company or separate module?

**Decision:** Keep in common/company respectively for simplicity. Can refactor later if needed.
