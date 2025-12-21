# Market Context API Test Results

**Report ID:** tester-251221-1635-market-context-test-results
**Test Suite:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/tests/test_market_context_api.py`
**Date:** 2025-12-21
**Test Runner:** pytest 9.0.2

---

## Executive Summary

**Total Tests:** 11
**Passed:** 9 (81.8%)
**Failed:** 2 (18.2%)
**Skipped:** 0
**Warnings:** 1 (Pydantic config deprecation)
**Execution Time:** 18.61s
**Overall Status:** ❌ FAILING

---

## Test Results Overview

### Passed Tests (9)
1. ✓ `test_get_market_context_all_periods` - All period validations working
2. ✓ `test_get_market_context_invalid_period` - 422 validation error returned correctly
3. ✓ `test_get_market_context_invalid_symbol` - 400 error for invalid symbols
4. ✓ `test_response_schema_structure` - Response schema matches specification
5. ✓ `test_chart_data_normalization` - Chart data normalization at base 100
6. ✓ `test_performance_logic` - Outperform flags logically correct
7. ✓ `test_sector_context_nullable` - Sector nullable handling works
8. ✓ `test_symbol_case_insensitive` - Case-insensitive symbol handling
9. ✓ `test_cache_hit_same_request` - Caching behavior functional

### Failed Tests (2)

#### 1. `test_get_market_context_success`
**Location:** `tests/test_market_context_api.py:32`
**Expected:** Status code 400 (acceptable for missing EOD data)
**Actual:** Status code 500 (Internal Server Error)
**Root Cause:** Database table `stock_daily_returns` does not exist

#### 2. `test_get_market_context_default_period`
**Location:** `tests/test_market_context_api.py:43`
**Expected:** Status code 400 (acceptable for missing EOD data)
**Actual:** Status code 500 (Internal Server Error)
**Root Cause:** Same - missing `stock_daily_returns` table

---

## Root Cause Analysis

### Primary Issue: Missing Database Schema

**Error:**
```
psycopg2.errors.UndefinedTable: relation "stock_daily_returns" does not exist
```

**Stack Trace Origin:**
```
src/stocks/market_context_repository.py:74
→ self.db.execute(stmt).scalars().all()
```

**Investigation Findings:**

1. **Migration Exists But Not Applied**
   - Migration file: `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/alembic/versions/20251221150022_add_market_context_tables.py`
   - Creates 3 tables: `stock_daily_returns`, `stock_market_metrics`, `sector_daily_benchmark`
   - Migration NOT applied to database

2. **Database State:**
   - Current tables: `alembic_version`, `stock_intraday_bars`, `users`
   - Missing tables: `stock_daily_returns`, `stock_market_metrics`, `sector_daily_benchmark`

3. **Alembic Version Mismatch:**
   - Database version: `d48f54a7103a`
   - Available migrations: `60811b8fd9e3`, `20251221150022`
   - **Problem:** Database points to non-existent migration `d48f54a7103a`
   - This blocks `alembic upgrade head` from running

### Secondary Issue: Pydantic Deprecation Warning

**Warning:**
```
src/stocks/schemas/price.py:90
Support for class-based `config` is deprecated, use ConfigDict instead.
```

**Impact:** Low - cosmetic warning, no functional impact

---

## Suggested Fixes

### Fix 1: Reset Alembic Version (REQUIRED)

**Problem:** Database references deleted/missing migration `d48f54a7103a`

**Solution A - Manual Reset (Recommended for dev):**
```sql
-- Reset to base
UPDATE alembic_version SET version_num = '60811b8fd9e3';
```

Then run:
```bash
alembic upgrade head
```

**Solution B - Stamp with latest:**
```bash
# Force set version (bypasses migration execution)
alembic stamp 60811b8fd9e3
alembic upgrade head
```

**Solution C - Fresh migration (if test DB):**
```bash
# Drop and recreate alembic_version table
alembic stamp head
```

### Fix 2: Apply Market Context Tables Migration

After fixing alembic version issue:
```bash
source .venv/bin/activate
alembic upgrade head
```

This will create:
- `stock_daily_returns` (symbol, date, close_price, return_1d, return_1d_log)
- `stock_market_metrics` (correlation, beta, RS metrics)
- `sector_daily_benchmark` (sector-level returns)

### Fix 3: Update Pydantic Config (Optional)

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/schemas/price.py:90`

Replace:
```python
class Config:
    # ... config options
```

With:
```python
model_config = ConfigDict(
    # ... same options
)
```

---

## Test Expectations vs Reality

### Expected Behavior (Per Test Design)
Tests designed to accept either:
- **200 OK** - If EOD data exists
- **400 Bad Request** - If EOD pipeline hasn't run yet (acceptable state)

### Actual Behavior
- **500 Internal Server Error** - Database schema missing (blocker)

**Test Design is Correct:**
Tests gracefully handle both success and "no data yet" scenarios.
500 error is unexpected and indicates infrastructure issue, not application logic problem.

---

## Impact Assessment

### Blocking Issues
1. **2 test failures** prevent test suite from passing
2. **API endpoint non-functional** - returns 500 for all market context requests
3. **Cannot validate market context feature** until database schema exists

### Non-Blocking Issues
1. Pydantic deprecation warning (cosmetic)

### Downstream Impact
- Market context API unusable in current state
- Phase 2 EOD pipeline likely blocked (needs these tables)
- Integration tests for market context will fail
- Production deployment would fail if attempted

---

## Validation Steps After Fix

1. **Verify migration applied:**
   ```bash
   alembic current
   # Should show: 20251221150022 (head), add market context tables
   ```

2. **Verify tables exist:**
   ```sql
   SELECT tablename FROM pg_tables WHERE schemaname='public'
   ORDER BY tablename;
   ```
   Should include: `stock_daily_returns`, `stock_market_metrics`, `sector_daily_benchmark`

3. **Re-run test suite:**
   ```bash
   pytest tests/test_market_context_api.py -v
   ```
   Expected: All 11 tests pass OR return 400 (if no EOD data seeded)

4. **Seed test data (if needed for 200 responses):**
   - Run Phase 1 EOD pipeline OR
   - Create fixture data for VCB, FPT symbols

---

## Performance Notes

- **Test execution time:** 18.61s (reasonable for 11 integration tests)
- No slow tests identified
- Caching tests passing suggests Redis integration working

---

## Recommendations

### Immediate (Priority 1)
1. Fix alembic version mismatch using Solution A or B
2. Run `alembic upgrade head` to create missing tables
3. Re-run test suite to verify fix

### Short-term (Priority 2)
4. Update Pydantic config to resolve deprecation warning
5. Consider adding database setup documentation to prevent recurrence
6. Add migration validation to CI/CD pipeline

### Long-term (Priority 3)
7. Create test fixtures for market context data to enable full test validation
8. Add database schema verification to test setup
9. Document EOD pipeline prerequisites

---

## Unresolved Questions

1. Why does database reference deleted migration `d48f54a7103a`? Was this migration manually removed or git rebased?
2. Should test suite include automatic migration check/application in setup?
3. Is there a separate test database configuration, or using dev database?
4. Are test fixtures needed for EOD data, or acceptable for tests to return 400 until pipeline runs?

---

**Next Step:** Apply Fix 1 (reset alembic version) then Fix 2 (upgrade migrations).
