# Schema-Router Mapping Analysis

**File:** `apps/api/src/stocks/schemas.py` (427 lines)
**File:** `apps/api/src/stocks/router.py` (486 lines)

---

## 1. Schema Groupings by Domain

### Price Domain (Lines 8-30, 164-204, 213-270)
| Schema | Lines | Description |
|--------|-------|-------------|
| `StockPrice` | 10-18 | Historical OHLCV |
| `IntradayTick` | 21-29 | Tick data |
| `HistoryParams` | 166-171 | Query params |
| `PriceBoardItem` | 174-193 | Real-time price board |
| `MarketIndexItem` | 196-203 | Market indices |
| `IntradayBarCreate` | 216-227 | Intraday bar creation |
| `IntradayBar` | 230-237 | DB intraday bar |
| `IntradayCollectionResult` | 240-245 | Collection result |
| `VolumeTimePeriod` | 251-259 | Volume period |
| `VolumeAnalysisResponse` | 262-269 | Volume analysis |

**Total: 10 schemas (~100 lines)**

### Company Domain (Lines 32-54, 272-322, 324-382)
| Schema | Lines | Description |
|--------|-------|-------------|
| `CompanyOverview` | 34-44 | Company info |
| `StockSymbol` | 47-53 | Symbol listing |
| `StockDetail` | 272-321 | Comprehensive detail |
| `ShareholderItem` | 327-334 | Shareholder data |
| `ShareholdersResponse` | 337-342 | Shareholders response |
| `OfficerItem` | 345-355 | Officer data |
| `OfficersResponse` | 358-363 | Officers response |
| `InsiderDealItem` | 366-373 | Insider deal |
| `InsiderDealsResponse` | 376-381 | Insider deals response |

**Total: 9 schemas (~90 lines)**

### Financial Domain (Lines 56-161)
| Schema | Lines | Description |
|--------|-------|-------------|
| `FinancialRatio` | 58-78 | Financial ratios |
| `IncomeStatementItem` | 81-90 | Simple income stmt |
| `IncomeStatementRow` | 93-101 | Detailed row |
| `IncomeStatementResponse` | 104-110 | Detailed response |
| `BalanceSheetItem` | 113-121 | Simple balance sheet |
| `BalanceSheetRow` | 124-132 | Detailed row |
| `BalanceSheetResponse` | 135-141 | Detailed response |
| `CashFlowRow` | 144-152 | Cash flow row |
| `CashFlowResponse` | 155-161 | Cash flow response |

**Total: 9 schemas (~105 lines)**

### Market Domain (Lines 384-426)
| Schema | Lines | Description |
|--------|-------|-------------|
| `SectorPerformanceItem` | 387-396 | Sector data |
| `SectorPerformanceResponse` | 399-404 | Sector response |
| `FundCertificateItem` | 410-418 | Fund cert data |
| `FundCertificatesResponse` | 421-426 | Fund certs response |

**Total: 4 schemas (~45 lines)**

### Common/Shared (Lines 206-210)
| Schema | Lines | Description |
|--------|-------|-------------|
| `ErrorResponse` | 206-210 | Standard error |

**Total: 1 schema (~5 lines)**

---

## 2. Endpoint-to-Schema Mapping

### Symbol Endpoints
| Endpoint | Method | Response Schema |
|----------|--------|-----------------|
| `/symbols` | GET | `list[StockSymbol]` |
| `/symbols/group/{group}` | GET | `list[str]` |
| `/symbols/search` | GET | `list[StockSymbol]` |

### Price Endpoints
| Endpoint | Method | Response Schema |
|----------|--------|-----------------|
| `/{symbol}/history` | GET | `list[StockPrice]` |
| `/{symbol}/intraday` | GET | `list[IntradayTick]` |
| `/market-indices` | GET | `list[MarketIndexItem]` |
| `/price-board` | GET | `list[PriceBoardItem]` |
| `/intraday/collect` | POST | `IntradayCollectionResult` |
| `/{symbol}/volume-analysis` | GET | `VolumeAnalysisResponse` |

### Company Endpoints
| Endpoint | Method | Response Schema |
|----------|--------|-----------------|
| `/{symbol}/company` | GET | `CompanyOverview` |
| `/{symbol}/detail` | GET | `StockDetail` |
| `/{symbol}/shareholders` | GET | `ShareholdersResponse` |
| `/{symbol}/officers` | GET | `OfficersResponse` |
| `/{symbol}/insider-deals` | GET | `InsiderDealsResponse` |

### Financial Endpoints
| Endpoint | Method | Response Schema |
|----------|--------|-----------------|
| `/{symbol}/financials/ratios` | GET | `list[FinancialRatio]` |
| `/{symbol}/financials/income` | GET | `list[IncomeStatementItem]` |
| `/{symbol}/financials/income-statement` | GET | `IncomeStatementResponse` |
| `/{symbol}/financials/balance-sheet` | GET | `list[BalanceSheetItem]` |
| `/{symbol}/financials/balance-sheet-detailed` | GET | `BalanceSheetResponse` |
| `/{symbol}/financials/cash-flow` | GET | `CashFlowResponse` |

### Market Endpoints
| Endpoint | Method | Response Schema |
|----------|--------|-----------------|
| `/sector-performance` | GET | `SectorPerformanceResponse` |
| `/fund-certificates` | GET | `FundCertificatesResponse` |

---

## 3. Schema Dependencies

```
IntradayBar ──extends──> IntradayBarCreate

IncomeStatementResponse ──contains──> IncomeStatementRow[]
BalanceSheetResponse ──contains──> BalanceSheetRow[]
CashFlowResponse ──contains──> CashFlowRow[]
VolumeAnalysisResponse ──contains──> VolumeTimePeriod[]
ShareholdersResponse ──contains──> ShareholderItem[]
OfficersResponse ──contains──> OfficerItem[]
InsiderDealsResponse ──contains──> InsiderDealItem[]
SectorPerformanceResponse ──contains──> SectorPerformanceItem[]
FundCertificatesResponse ──contains──> FundCertificateItem[]

StockDetail (composite) ──uses fields from──> CompanyOverview, PriceBoardItem, FinancialRatio
```

---

## 4. Recommended Split for Backward Compatibility

### Proposed Module Structure
```
src/stocks/
├── schemas/
│   ├── __init__.py          # Re-export all for backward compat
│   ├── price.py             # StockPrice, IntradayTick, PriceBoardItem, MarketIndexItem, Intraday*, Volume*
│   ├── company.py           # CompanyOverview, StockSymbol, StockDetail, Shareholder*, Officer*, InsiderDeal*
│   ├── financial.py         # FinancialRatio, IncomeStatement*, BalanceSheet*, CashFlow*
│   ├── market.py            # SectorPerformance*, FundCertificate*
│   └── common.py            # ErrorResponse, HistoryParams
```

### Backward Compatibility Strategy
1. **`schemas/__init__.py`** re-exports all schemas:
   ```python
   from .price import StockPrice, IntradayTick, ...
   from .company import CompanyOverview, StockSymbol, ...
   from .financial import FinancialRatio, ...
   from .market import SectorPerformanceItem, ...
   from .common import ErrorResponse, HistoryParams
   ```

2. **Keep original `schemas.py`** as alias (deprecation period):
   ```python
   # schemas.py - DEPRECATED, use schemas/ module
   from src.stocks.schemas import *
   ```

3. **Router imports unchanged** - continues importing from `src.stocks.schemas`

### Migration Priority
1. **Phase 1:** Create `schemas/` module with re-exports (zero breaking changes)
2. **Phase 2:** Update router imports to specific modules (optional optimization)
3. **Phase 3:** Deprecate monolithic `schemas.py` after 1 release cycle

---

## Summary Stats

| Domain | Schemas | Lines | Endpoints |
|--------|---------|-------|-----------|
| Price | 10 | ~100 | 6 |
| Company | 9 | ~90 | 5 |
| Financial | 9 | ~105 | 6 |
| Market | 4 | ~45 | 2 |
| Common | 1 | ~5 | 0 |
| **Total** | **33** | **~345** | **19** |

---

## Unresolved Questions
- Should `StockDetail` stay in company or become its own composite module?
- Should `HistoryParams` move to price domain or stay in common?
