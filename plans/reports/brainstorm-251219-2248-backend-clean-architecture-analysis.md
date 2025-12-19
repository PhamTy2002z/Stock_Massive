# Backend Architecture Analysis Report

**Date:** 2024-12-19
**Type:** Brainstorm / Architecture Review
**Status:** Analysis Complete

---

## Problem Statement

Verify backend follows Feature-based Modular Architecture standards. Ensure code is maintainable, scalable, and files are not too long.

---

## Current State Analysis

### Directory Structure

```
apps/api/src/
├── main.py                 (62 lines)  ✅ Good
├── core/                   # Shared infrastructure
│   ├── config.py           (43 lines)  ✅ Good
│   ├── database.py         (46 lines)  ✅ Good
│   ├── scheduler.py        (45 lines)  ✅ Good
│   └── dependencies.py     (8 lines)   ✅ Good
└── stocks/                 # Feature module
    ├── router.py           (485 lines) ⚠️ Borderline
    ├── service.py          (1507 lines) ❌ TOO LARGE
    ├── schemas.py          (426 lines) ⚠️ Borderline
    ├── models.py           (30 lines)  ✅ Good
    ├── jobs.py             (60 lines)  ✅ Good
    └── intraday_collector.py (230 lines) ✅ Good
```

### What's Working Well

| Aspect | Status | Notes |
|--------|--------|-------|
| Feature-based structure | ✅ | `stocks/` module is self-contained |
| Separation of concerns | ✅ | Router/Service/Schema/Model layers exist |
| Core infrastructure | ✅ | Clean shared modules in `core/` |
| Async database | ✅ | SQLAlchemy 2.0 async patterns |
| Dependency injection | ✅ | FastAPI `Depends()` used correctly |
| Test structure | ✅ | Tests mirror source structure |

### Critical Issues

#### 1. `service.py` - 1507 lines (CRITICAL)

**Problem:** Single file contains ALL business logic for:
- Price data (history, intraday)
- Company info (overview, shareholders, officers, insider deals)
- Financial statements (income, balance sheet, cash flow, ratios)
- Market data (price board, indices, sector performance)
- Fund certificates
- 15+ private `_df_to_*` conversion methods

**Violation:** Single Responsibility Principle (SRP)

#### 2. `schemas.py` - 426 lines (MODERATE)

**Problem:** 30+ Pydantic models in one file covering:
- Price schemas
- Company schemas
- Financial schemas (income, balance, cash flow)
- Market schemas
- Response wrappers

#### 3. `router.py` - 485 lines (MODERATE)

**Problem:** All endpoints in single file, though logically grouped with comments.

---

## Recommended Modularization

### Option A: Domain-based Split (Recommended)

Split by business domain within the `stocks/` feature:

```
stocks/
├── __init__.py
├── router.py              # Main router, imports sub-routers
├── models.py              # Keep as-is (small)
├── jobs.py                # Keep as-is (small)
├── intraday_collector.py  # Keep as-is
│
├── price/                 # Price domain
│   ├── __init__.py
│   ├── router.py          # /history, /intraday endpoints
│   ├── service.py         # get_history, get_intraday
│   └── schemas.py         # StockPrice, IntradayTick
│
├── company/               # Company domain
│   ├── __init__.py
│   ├── router.py          # /overview, /shareholders, /officers
│   ├── service.py         # get_company_overview, get_shareholders
│   └── schemas.py         # CompanyOverview, ShareholderItem, etc.
│
├── financial/             # Financial statements domain
│   ├── __init__.py
│   ├── router.py          # /ratios, /income, /balance, /cashflow
│   ├── service.py         # get_financial_ratios, get_income_statement
│   └── schemas.py         # FinancialRatio, IncomeStatementItem, etc.
│
├── market/                # Market-wide data domain
│   ├── __init__.py
│   ├── router.py          # /price-board, /indices, /sectors
│   ├── service.py         # get_price_board, get_market_indices
│   └── schemas.py         # PriceBoardItem, MarketIndexItem, etc.
│
└── shared/                # Shared utilities
    ├── __init__.py
    ├── converters.py      # _df_to_* methods
    ├── validators.py      # validate_symbol, SYMBOL_PATTERN
    └── exceptions.py      # StockServiceError
```

**Pros:**
- Clear domain boundaries
- Each service ~200-300 lines
- Easy to find related code
- Independent scaling per domain

**Cons:**
- More files to navigate
- Need to update imports

### Option B: Layer-based Split (Alternative)

Keep current structure but split large files:

```
stocks/
├── router.py              # Keep as-is (acceptable at 485)
├── schemas/
│   ├── __init__.py        # Re-export all
│   ├── price.py
│   ├── company.py
│   ├── financial.py
│   └── market.py
├── services/
│   ├── __init__.py        # Re-export StockService
│   ├── base.py            # StockService class, shared methods
│   ├── price.py           # PriceServiceMixin
│   ├── company.py         # CompanyServiceMixin
│   ├── financial.py       # FinancialServiceMixin
│   └── market.py          # MarketServiceMixin
└── converters/
    ├── __init__.py
    ├── price.py           # _df_to_stock_prices, _df_to_intraday
    └── financial.py       # _df_to_income_statements, etc.
```

**Pros:**
- Minimal structural change
- Mixins keep single service interface
- Easier migration path

**Cons:**
- Mixins can be confusing
- Less clear domain boundaries

---

## Recommended Action Plan

### Phase 1: Extract Shared Utilities (Low Risk)
1. Create `stocks/shared/exceptions.py` - move `StockServiceError`
2. Create `stocks/shared/validators.py` - move `validate_symbol`, `SYMBOL_PATTERN`
3. Create `stocks/shared/converters.py` - move all `_df_to_*` methods

**Result:** `service.py` drops from 1507 → ~900 lines

### Phase 2: Split Schemas (Low Risk)
1. Creathemas/` directory
2. Split into `price.py`, `company.py`, `financial.py`, `market.py`
3. Create `__init__.py` that re-exports all (backward compatible)

**Result:** Each schema file ~100-150 lines

### Phase 3: Split Services (Medium Risk)
1. Create `stocks/services/` directory
2. Extract domain-specific services
3. Keep facade `StockService` that delegates to domain services

**Result:** Each service file ~200-300 lines

### Phase 4: Split Routers (Optional)
1. Create sub-routers per domain
2. Main router includes sub-routers
3. Only if router grows beyond 500 lines

---

## Metrics Summary

| File | Current | Target | Reduction |
|------|---------|--------|-----------|
| service.py | 1507 | ~250 per domain | -83% |
| schemas.py | 426 | ~100 per domain | -76% |
| router.py | 485 | Keep or split | 0% to -75% |

---

## Verdict

**Current architecture is ~70% compliant** with Feature-based Modular Architecture:

| Criteria | Score | Notes |
|----------|-------|-------|
| Feature isolation | ✅ 9/10 | `stocks/` is self-contained |
| Layer separation | ✅ 8/10 | Router/Service/Schema/Model exists |
| File size limits | ❌ 4/10 | `service.py` is 5x too large |
| Single responsibility | ❌ 5/10 | Service does too much |
| Maintainability | ⚠️ 6/10 | Hard to navigate 1500-line file |
| Scalability | ⚠️ 6/10 | Adding features bloats service.py |

**Recommendation:** Implement Phase 1-2 immediately (low risk, high impact). Phase 3 when adding new features.

---

## Unresolved Questions

1. Should converters be static methods or standalone functions?
2. Keep single `StockService` facade or expose domain services directly?
3. Priority: refactor now or wait until next feature addition?
