# Test Failures Investigation Report

**Date:** 2025-12-22 | **Total Failures:** 5 | **Status:** Root Causes Identified

---

## Executive Summary

5 pre-existing test failures analyzed. Root causes:
1. **StockIntradayBar tests (3):** Event loop lifecycle issue - tests share state across async boundaries
2. **Scheduler mock (1):** Incomplete mock - missing `daily_ohlcv_*` attributes
3. **Sector performance (1):** Test expectation mismatch - mock data lacks `listed_share` column

---

## Failure Analysis

### 1. StockIntradayBar Query Tests (3 failures)

**Files:** `tests/test_database_phase01.py`
- `test_select_intraday_bar`
- `test_delete_intraday_bar`
- `test_unique_constraint_different_time`

**Error:** `RuntimeError: Event loop is closed`

**Root Cause:**
- Tests use `cleanup_test_data()` helper after assertions
- Cleanup runs after test's event loop context may be closing
- `asyncpg` connection teardown attempts to use closed loop

**Fix:**
```python
# Option A: Use pytest-asyncio session-scoped loop
@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# Option B: Move cleanup before assertions or use fixture teardown
@pytest.fixture(autouse=True)
async def cleanup_after_test():
    yield
    await cleanup_test_data()
```

---

### 2. Scheduler Setup Mock (1 failure)

**File:** `tests/test_scheduler.py::test_setup_scheduler_enabled`

**Error:**
```
ValueError: Unrecognized expression "<MagicMock name='settings.daily_ohlcv_hour'...>" for field 'hour'
```

**Root Cause:**
- `setup_scheduler()` added daily OHLCV schedule (lines 56-70)
- Test mocks only `intraday_*` settings, not `daily_ohlcv_*`
- Missing: `daily_ohlcv_enabled`, `daily_ohlcv_hour`, `daily_ohlcv_minute`

**Fix:**
```python
# test_scheduler.py line 140-143, add:
with patch("src.core.scheduler.settings") as mock_settings:
    mock_settings.scheduler_enabled = True
    mock_settings.intraday_collect_hour = 15
    mock_settings.intraday_collect_minute = 30
    # ADD THESE:
    mock_settings.daily_ohlcv_enabled = True
    mock_settings.daily_ohlcv_hour = 20
    mock_settings.daily_ohlcv_minute = 0

    await setup_scheduler(mock_scheduler)
    # Update assertion: now 3 schedules (intraday, cleanup, daily_ohlcv)
    assert mock_scheduler.add_schedule.call_count == 3
```

---

### 3. Sector Performance Unit Conversion (1 failure)

**File:** `tests/test_sector_performance.py::test_total_market_cap_in_billions`

**Error:**
```
AssertionError: assert 150000000.0 == 150.0
```

**Root Cause:**
Test mock provides `accumulated_value` (150 billion) but not `listed_share`:
```python
mock_trading.price_board.return_value = pd.DataFrame({
    'symbol': ['A'],
    'match_price': [101.0],
    'ref_price': [100.0],
    'accumulated_value': [150_000_000_000],  # 150 billion
})
```

Service code (line 202-207):
- If `listed_share` exists: `market_cap = price * listed_share / 1e9`
- Else fallback: `market_cap = accumulated_value / 1000`

**Calculation:** `150_000_000_000 / 1000 = 150_000_000` (not billions!)

**Fix Options:**

**Option A** - Add `listed_share` to mock (recommended):
```python
mock_trading.price_board.return_value = pd.DataFrame({
    'symbol': ['A'],
    'match_price': [101.0],
    'ref_price': [100.0],
    'listed_share': [1_485_148_514],  # ~150B / 101 price
    'accumulated_value': [150_000_000_000],
})
# Expected: 101.0 * 1_485_148_514 / 1e9 = 150.0 billion
```

**Option B** - Fix fallback formula in service:
```python
# line 207: Change /1000 to /1e9
sector_market_cap = valid_rows["accumulated_value"].sum() / 1e9
```

---

## Summary Table

| # | Test | Root Cause | Fix Complexity |
|---|------|------------|----------------|
| 1-3 | StockIntradayBar | Event loop lifecycle | Medium |
| 4 | Scheduler | Missing mock attrs | Low |
| 5 | Sector perf | Mock data mismatch | Low |

---

## Recommendations

1. **Priority 1 (Quick wins):**
   - Fix scheduler test mock (add 3 lines)
   - Fix sector test mock (add `listed_share` column)

2. **Priority 2:**
   - Add `event_loop` fixture to conftest.py for proper async test isolation
   - Refactor cleanup to use fixtures instead of inline calls

3. **Long-term:**
   - Consider using `pytest-asyncio` with `loop_scope="session"` in pytest.ini
   - Add database transaction rollback fixture instead of manual cleanup
