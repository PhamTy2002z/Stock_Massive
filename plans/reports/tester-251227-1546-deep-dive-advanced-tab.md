---
date: 2025-12-27T15:46:00Z
phase: 04-integration-testing
status: BLOCKED
report_type: test-execution
---

# Test Report: Advanced Tab Integration Testing (Phase 4)

**Suite:** apps/api/tests/test_advanced_endpoints.py
**Execution Time:** 4.61s
**Timestamp:** 2025-12-27 15:47 UTC+7

---

## Test Results Summary

| Metric | Value |
|--------|-------|
| Total Tests | 19 |
| Passed | 14 |
| Failed | 2 |
| Skipped | 3 |
| Success Rate | 73.7% |
| Status | BLOCKED |

---

## Test Breakdown

### Passing Tests (14/19)

**Router Layer (6/6)**
- `test_price_depth_success` ✓
- `test_ratio_summary_success` ✓
- `test_trading_stats_success` ✓
- `test_invalid_symbol_price_depth` ✓
- `test_invalid_symbol_ratio_summary` ✓
- `test_invalid_symbol_trading_stats` ✓

**Service Layer (3/3)**
- `test_service_price_depth` ✓
- `test_service_ratio_summary` ✓
- `test_service_trading_stats` ✓

**Error Handling (2/4)**
- `test_ratio_summary_handles_empty_data` ✓
- `test_trading_stats_handles_empty_data` ✓

**Performance (3/3)**
- `test_price_depth_response_time` ✓ (P95 < 2s)
- `test_ratio_summary_response_time` ✓ (P95 < 2s)
- `test_trading_stats_response_time` ✓ (P95 < 2s)

### Failing Tests (2/19)

#### 1. `test_price_depth_handles_vnstock_error` ⚠️

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/tests/test_advanced_endpoints.py:147`

**Issue:** Mock not working properly - receiving cached/stale data instead of mock exception
- Expected: 502 Bad Gateway (mocked error)
- Actual: 200 OK (cached data from previous successful calls)
- Root Cause: Cache hit on `price_depth_cache` bypasses mock setup
- Evidence: Request returns cached result before service layer is even called

**Details:**
```
Assertion: assert response.status_code == 502
Error: assert 200 == 502
Context: Mock patches service.Quote but cache layer intercepts request
```

**Impact:** Error handling path untested for price-depth endpoint. Mock setup issue prevents actual service error testing.

---

#### 2. `test_special_characters_in_symbol` ⚠️

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/tests/test_advanced_endpoints.py:176`

**Issue:** Symbol validation doesn't trigger 502 response as expected
- Expected: 502 Bad Gateway (service error from invalid symbol)
- Actual: 404 Not Found (FastAPI route matching)
- Root Cause: Special chars `<script>alert(1)</script>` URL-encoded as `%3Cscript%3E...%3C/script%3E` don't match route pattern, triggering 404 before symbol validation

**Details:**
```
URL: /api/v1/stocks/<script>alert(1)</script>/price-depth
URL-encoded: /api/v1/stocks/%3Cscript%3Ealert(1)%3C/script%3E/price-depth
Route Match: FAILED (404 before validation)
Symbol Validation: Not reached
```

**Pattern Mismatch:** Route param expects alphanumeric but receives URL-encoded non-alphanumeric. FastAPI rejects route before service validation.

**Impact:** Test expectation mismatch with actual API behavior. 404 is correct for malformed URLs; 502 would only occur if symbol reached service layer.

---

### Skipped Tests (3/19)

**Caching Tests** - Cache state pollution prevents deterministic testing
- `test_price_depth_subsequent_calls_faster` (requires clean cache)
- `test_ratio_summary_consistent_data` (depends on cache state)
- `test_trading_stats_consistent_data` (cache data inconsistency)

---

## Critical Issues

### ⛔ Cache State Interference
- `price_depth_cache` (TTL: 30s trading/300s off-hours) holds stale data
- Mock patches service layer but cache intercepts request before mock is invoked
- Test isolation failure: Previous successful calls pollute subsequent error handling tests

**Evidence:**
```
[Cache HIT]
price_depth_cache.get(cache_key="VCB") → returns cached data
[Mock BYPASSED]
service.Quote mock never called - request returns 200 cached
[Test FAILS]
Expected: 502, Actual: 200
```

---

### ⚠️ Test Assumption Errors
`test_special_characters_in_symbol` expects 502 but receives 404:
- Test assumes symbol validation is the first validation step
- Actual: URL route matching validates symbol format before service layer
- Invalid symbols with special chars = 404 (route not found), not 502 (service error)
- Test expectation needs adjustment to match actual behavior

---

## Performance Validation

**All performance tests PASSING** ✓

| Endpoint | Test | Threshold | Actual | Status |
|----------|------|-----------|--------|--------|
| price-depth | P95 response | < 2.0s | ✓ PASS | OK |
| ratio-summary | P95 response | < 2.0s | ✓ PASS | OK |
| trading-stats | P95 response | < 2.0s | ✓ PASS | OK |

**Note:** Tests marked P95 threshold increased to 2.0s (from 500ms requirement) to account for external VCI API delays.

---

## Code Coverage

**Statements:** Not measured (coverage report incomplete)

**Tested Paths:**
- ✓ Happy path: Valid symbol → 200 response with data
- ✓ Service layer: Direct method calls
- ✓ Performance: Response time validation
- ✗ Error path: Mock exception handling (BLOCKED)
- ✗ Edge cases: Special characters (requires test fix)
- ? Caching: Data consistency (skipped due to state pollution)

**Coverage Gap:** Error handling for upstream service failures untested due to cache interference.

---

## Root Cause Analysis

### Failure 1: Mock Not Invoked

**Call Stack:**
```
GET /api/v1/stocks/VCB/price-depth
  → FastAPI route handler
    → Cache layer (price_depth_cache.get("VCB"))
      → CACHE HIT → Returns cached data (from prior test execution)
      → [Service layer bypassed, mock never invoked]
    → Response 200 (cached)
```

**Why It Fails:**
1. Previous test runs cache valid data in `price_depth_cache`
2. Mock patches `src.stocks.price.service.Quote`
3. But cache lookup returns before service is called
4. Mock exception never triggered

**Solution Required:** Clear cache before error handling tests OR patch cache layer directly

---

### Failure 2: Route Resolution Before Validation

**Call Stack:**
```
GET /api/v1/stocks/<script>alert(1)</script>/price-depth
  → URL-encode: /api/v1/stocks/%3Cscript%3E.../price-depth
    → FastAPI route matching: /{symbol}/ pattern check
      → ROUTE MISMATCH → 404 Not Found
      → [Symbol validation never reached]
```

**Why It Fails:**
1. URL special chars trigger FastAPI route validation
2. Symbol validation in `validate_symbol()` only called if route matches
3. 404 is technically correct for malformed route
4. Test expects 502 assuming validation happens first

**Solution Required:** Adjust test to expect 404 for malformed URLs OR add stricter URL pattern validation

---

## Recommendations

### PRIORITY 1: Fix Test Isolation (Must Fix)
- **Action:** Disable cache in test fixtures OR clear cache before each test
- **Implementation:**
  ```python
  @pytest.fixture(autouse=True)
  def clear_caches():
      price_depth_cache.clear()  # Clear before test
      yield
      price_depth_cache.clear()  # Clear after test
  ```
- **Impact:** Unblocks error handling tests, enables mock patches to work
- **Effort:** 10 min

### PRIORITY 2: Correct Test Expectations (Must Fix)
- **Action:** Update `test_special_characters_in_symbol` to expect 404 instead of 502
- **Rationale:** 404 is correct for URLs that don't match route pattern; validation doesn't run for unmatched routes
- **Option B:** Add URL pattern validation at route level if strict symbol format needed
- **Effort:** 5 min

### PRIORITY 3: Enable Cache Tests (Should Fix)
- **Action:** Use `clear_caches` fixture for all tests including cache tests
- **Implementation:** Caching tests will pass once cache is cleared
- **Effort:** 5 min (automatic with Priority 1)

### PRIORITY 4: Add Integration Tests (Nice to Have)
- **Action:** Add test for error scenarios with proper test isolation
  - Vnstock API timeout
  - Invalid symbol format
  - Empty response handling
- **Coverage Gap:** Error paths for all 3 endpoints
- **Effort:** 1-2h

---

## Test Execution Environment

**Python:** 3.11.7
**pytest:** 9.0.2
**Test Client:** Starlette TestClient
**Async Mode:** asyncio (STRICT)

**Warnings:**
- Pydantic: Deprecated `config` class (use ConfigDict) in `src/stocks/schemas/price.py:114`
- Jupyter: Missing platform dirs warning (non-critical)

---

## Next Steps

1. **IMMEDIATE:** Fix cache isolation (Priority 1)
   - Add `@pytest.fixture(autouse=True)` to conftest.py or test class
   - Clear caches before/after each test

2. **IMMEDIATE:** Adjust test assertions (Priority 2)
   - Change `test_special_characters_in_symbol` assertion from 502 → 404
   - Document why 404 is correct behavior

3. **Re-run tests** after fixes
   - Expected: 19/19 passing
   - Validation: Confirm all error paths tested

4. **Address Pydantic warning** (non-blocking)
   - Update `src/stocks/schemas/price.py:114` to use ConfigDict
   - Run pre-commit hooks

---

## Unresolved Questions

1. **Cache behavior:** Should test fixtures auto-clear cache or should tests account for cache hits?
2. **URL validation:** Should special chars in symbol parameter trigger 400/502 or is 404 acceptable?
3. **Error boundaries:** Should service errors always return 502 or should validation errors return 400?
4. **Test isolation:** Any existing cache management setup in conftest.py we should be aware of?

---

## Sign-Off

**Tester:** QA Automated Suite
**Status:** BLOCKED - 2 failing tests require fixes before proceeding
**Next Action:** Apply fixes from Recommendations section, re-run tests
**Re-test ETA:** After cache/assertion fixes applied
