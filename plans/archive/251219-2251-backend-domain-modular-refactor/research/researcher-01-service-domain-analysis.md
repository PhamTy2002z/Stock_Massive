# Service Domain Analysis Report

**File:** `/apps/api/src/stocks/service.py`
**Total Lines:** 1508
**Date:** 2024-12-19

## 1. Method Groupings by Domain

### A. Price Domain (Lines: ~220)
| Method | Lines | Description |
|--------|-------|-------------|
| `get_history` | 81-114 | Historical OHLCV data |
| `get_intraday` | 116-137 | Intraday tick data |
| `get_price_board` | 423-446 | Real-time price board |
| `get_market_indices` | 448-501 | Market indices (VN-INDEX, VN30, etc.) |

**Private Converters:**
- `_df_to_stock_prices` (1027-1055) - 28 lines
- `_df_to_intraday_ticks` (1057-1082) - 25 lines
- `_df_to_price_board` (1466-1495) - 29 lines

### B. Company Domain (Lines: ~200)
| Method | Lines | Description |
|--------|-------|-------------|
| `get_company_overview` | 139-159 | Company overview info |
| `get_stock_detail` | 503-627 | Comprehensive stock detail (composite) |
| `get_shareholders` | 629-677 | Major shareholders |
| `get_officers` | 679-735 | Company officers/management |
| `get_insider_deals` | 737-795 | Insider trading deals |

**Private Converters:**
- `_to_company_overview` (1084-1117) - 33 lines

### C. Financial Domain (Lines: ~450)
| Method | Lines | Description |
|--------|-------|-------------|
| `get_financial_ratios` | 161-188 | Financial ratios |
| `get_income_statement` | 190-217 | Income statement (simple) |
| `get_income_statement_detailed` | 219-246 | Income statement (detailed) |
| `get_balance_sheet` | 248-275 | Balance sheet (simple) |
| `get_balance_sheet_detailed` | 277-304 | Balance sheet (detailed) |
| `get_cash_flow_detailed` | 306-333 | Cash flow (detailed) |

**Private Converters:**
- `_df_to_financial_ratios` (1119-1159) - 40 lines
- `_df_to_income_statements` (1161-1193) - 32 lines
- `_df_to_income_statement_response` (1195-1268) - 73 lines
- `_df_to_balance_sheets` (1270-1302) - 32 lines
- `_df_to_balance_sheet_response` (1304-1370) - 66 lines
- `_df_to_cash_flow_response` (1372-1453) - 81 lines

### D. Market/Listing Domain (Lines: ~120)
| Method | Lines | Description |
|--------|-------|-------------|
| `list_symbols` | 335-366 | List all symbols |
| `list_symbols_by_group` | 368-387 | Symbols by group (VN30, etc.) |
| `search_symbols` | 389-421 | Search symbols |
| `get_sector_performance` | 797-870 | Sector performance |
| `get_fund_certificates` | 872-920 | Fund certificates |

**Private Converters:**
- `_df_to_stock_symbols` (1009-1025) - 16 lines

## 2. Shared Utilities (Extract to `utils.py`)

| Utility | Lines | Used By |
|---------|-------|---------|
| `validate_symbol()` | 52-67 | All domains except market/listing |
| `_safe_float()` | 1455-1464 | All converters |
| `StockServiceError` | 42-45 | All domains |
| `SYMBOL_PATTERN` | 49 | validate_symbol |

## 3. Dependencies Between Domains

```
┌─────────────────┐
│  Price Domain   │◄──────┐
└────────┬────────┘       │
         │                │
         ▼                │
┌─────────────────┐       │ uses price_board
│ Company Domain  │───────┘
│ (get_stock_detail)      │
└────────┬────────┘       │
         │                │
         ▼                │
┌─────────────────┐       │ uses ratio_summary
│Financial Domain │───────┘
└─────────────────┘

┌─────────────────┐
│ Market Domain   │ (independent)
└─────────────────┘
```

**Cross-Domain Dependencies:**
1. `get_stock_detail` calls: `Trading.price_board`, `company.overview`, `company.ratio_summary`, `Finance.ratio`
2. All domains share: `validate_symbol`, `_safe_float`, `StockServiceError`

## 4. External Library Dependencies

| Domain | vnstock Classes |
|--------|-----------------|
| Price | `Quote`, `Trading` |
| Company | `Vnstock().stock().company` |
| Financial | `Finance`, `Vnstock().stock().company.ratio_summary` |
| Market | `Listing`, `Quote` (for indices) |

## 5. Line Count Summary

| Domain | Public Methods | Private Converters | Total |
|--------|----------------|-------------------|-------|
| Price | ~120 | ~82 | ~202 |
| Company | ~195 | ~33 | ~228 |
| Financial | ~130 | ~324 | ~454 |
| Market | ~125 | ~16 | ~141 |
| Shared Utils | ~30 | - | ~30 |
| **Total** | ~600 | ~455 | ~1055 |

## 6. Recommended Split Strategy

### Phase 1: Extract Shared Utilities
```
src/stocks/
├── utils.py          # validate_symbol, _safe_float, StockServiceError
└── service.py        # (existing, imports from utils)
```

### Phase 2: Domain Services
```
src/stocks/
├── utils.py
├── services/
│   ├── __init__.py
│   ├── price_service.py      # get_history, get_intraday, get_price_board, get_market_indices
│   ├── company_service.py    # get_company_overview, get_shareholders, get_officers, get_insider_deals
│   ├── financial_service.py  # get_financial_ratios, get_income_*, get_balance_*, get_cash_flow_*
│   └── market_service.py     # list_symbols, search_symbols, get_sector_performance, get_fund_certificates
└── service.py                # Facade: StockService aggregating all domain services
```

### Phase 3: Handle `get_stock_detail`
- Option A: Keep in facade (StockService) as composite method
- Option B: Create `StockDetailService` that composes Price + Company + Financial

### Migration Priority
1. **Financial Domain** (largest, most isolated) - 454 lines
2. **Company Domain** - 228 lines
3. **Price Domain** - 202 lines
4. **Market Domain** - 141 lines

## 7. Unresolved Questions

1. Should `get_stock_detail` remain in facade or become separate composite service?
2. Should converters stay with their domain services or centralize in `converters.py`?
3. How to handle singleton pattern (`get_stock_service`) with multiple domain services?
