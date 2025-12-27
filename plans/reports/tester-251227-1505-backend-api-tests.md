# Backend API Test Results Report

**Generated**: 2025-12-27 15:05
**Agent**: tester (ea368907)
**Scope**: Backend API test suite @ /Users/typham/Documents/GitHub/Stock_Massive/apps/api

---

## Executive Summary

**test_advanced_endpoints.py**: ✅ **9/9 PASSED** (1.91s)
**Full Test Suite**: ⚠️ **249 PASSED, 9 FAILED, 3 SKIPPED, 1 ERROR** (23.83s)

---

## Test Results Overview

### Specific Test File: test_advanced_endpoints.py
- **Status**: ✅ ALL PASSED
- **Tests**: 9/9 passed
- **Duration**: 1.91s
- **Coverage**:
  - Router tests (6): price_depth, ratio_summary, trading_stats (success + invalid symbol scenarios)
  - Service tests (3): price_depth, ratio_summary, trading_stats

### Full Test Suite
- **Total**: 262 tests
- **Passed**: 249 (95.0%)
- **Failed**: 9 (3.4%)
- **Skipped**: 3 (1.1%)
- **Errors**: 1 (0.4%)
- **Duration**: 23.83s

---

## Critical Issues

### Failed Tests (9)

#### 1. Database Phase01 - StockIntradayBarModel (7 failures)
**Module**: `tests/test_database_phase01.py`

**Failed Tests**:
- `test_insert_intraday_bar`
- `test_select_intraday_bar`
- `test_update_intraday_bar`
- `test_delete_intraday_bar`
- `test_unique_constraint_violation`
- `test_unique_constraint_different_time`
- `test_unique_constraint_different_symbol`

**Error Pattern**: `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: stock_intraday_bars`

**Root Cause**: Missing table `stock_intraday_bars` in test database. Table creation logic not executed in test setup.

**Impact**: CRUD operations for intraday bars cannot be tested. Database integrity constraints unvalidated.

---

#### 2. Scheduler Integration (1 failure)
**Module**: `tests/test_financial_statements_collector.py`

**Failed Test**: `TestSchedulerIntegration::test_scheduler_registers_financial_statements_job`

**Error**: `AssertionError: assert 3 == 4` (expected 4 scheduled jobs, found 3)

**Root Cause**: Financial statements collection job not registered by scheduler. Expected jobs: intraday collection, cleanup, daily OHLCV, financial statements.

**Impact**: Scheduled financial data collection may not execute in production.

---

#### 3. Sector Performance Calculation (1 failure)
**Module**: `tests/test_sector_performance.py`

**Failed Test**: `TestMarketCapWeightedCalculation::test_total_market_cap_in_billions`

**Error**: `AssertionError: assert 150000000.0 == 150.0`

**Root Cause**: Market cap returned in raw value (150M) instead of billions (150.0). Unit conversion missing.

**Impact**: API returns incorrect market cap units, causing frontend display errors.

---

### Errors (1)

**Module**: `tests/test_volume_anomaly_api.py`

**Test**: `test_endpoint`

**Status**: ERROR (no details in truncated output)

**Needs Investigation**: Full error trace required.

---

## Warnings Summary

### Deprecation Warnings (2 types)
1. **Jupyter Platform Dirs** (non-blocking)
   - Library: `jupyter_client`
   - Action: Set `JUPYTER_PLATFORM_DIRS=1` env var

2. **Pydantic Config** (low priority)
   - File: `src/stocks/schemas/price.py:114`
   - Action: Replace `class Config` with `ConfigDict`
   - Migration: https://errors.pydantic.dev/2.12/migration/

### Runtime Warnings (3 types)
- **Pandas Datetime Deprecation** (10 warnings in `test_intraday_collector.py`)
- **DataFrame.applymap Deprecation** (2 warnings) → Use `.map()` instead
- **DataFrame.fillna Downcasting** (3 warnings) → Add `.infer_objects(copy=False)`

---

## Recommendations

### Priority 1 - Critical Fixes
1. **Fix database table creation** for `stock_intraday_bars` in test setup
   - Add Alembic migration or explicit table creation in conftest.py
   - Impact: Unblocks 7 failed tests

2. **Fix scheduler job registration** for financial statements
   - Verify `setup_jobs()` includes financial statements job
   - Check conditional logic preventing job registration
   - Impact: Ensures data collection runs in production

3. **Fix market cap unit conversion** in sector performance service
   - Divide market cap by 1B before returning
   - Add unit tests for edge cases (small cap < 1B)
   - Impact: Correct API data display

### Priority 2 - Investigate
4. **Debug volume anomaly endpoint error**
   - Run isolated test with full traceback: `pytest tests/test_volume_anomaly_api.py::test_endpoint -vv`
   - Check endpoint implementation and test setup

### Priority 3 - Code Quality
5. **Resolve deprecation warnings**
   - Update Pydantic schema config (1 file)
   - Replace `.applymap()` with `.map()` (2 locations)
   - Add `.infer_objects()` after `.fillna()` (3 locations)
   - Update DatetimeProperties usage (10 locations)

---

## Next Steps

1. Fix database table creation → Run tests again
2. Fix scheduler registration → Verify 4 jobs registered
3. Fix market cap conversion → Verify output in billions
4. Debug volume anomaly error → Get full trace
5. Clean up deprecation warnings → Improve codebase health

---

## Unresolved Questions

1. Should market cap always return in billions or add configurable unit parameter?
2. Are skipped tests (3) intentionally disabled or require implementation?
3. Volume anomaly endpoint - is this a new feature or regression?
4. Should test database use SQLite or match production PostgreSQL?
