# Test Report: Volume Anomaly On-Demand Integration

**Date**: 2025-12-20 17:11
**Scope**: Volume anomaly endpoint with on-demand data collection
**Files tested**:
- `src/stocks/price/router.py` (endpoint + cache integration)
- `src/stocks/price/cache.py` (TradingHoursCache)
- `src/stocks/intraday_collector.py` (detect_volume_anomalies)

---

## Results Summary

**Total**: 44 tests
**Passed**: 41/44 (93.2%)
**Failed**: 3/44 (6.8%)
**Import Status**: ✓ All modules import successfully

---

## Test Breakdown

### ✓ Cache Module (`test_trading_hours_cache.py`)
**Status**: 21/21 PASSED

- Trading hours detection (7 tests) - boundaries, weekends, market hours
- TTL selection (2 tests) - 60s trading, 3600s off-hours
- Graceful degradation (6 tests) - Redis unavailable, exceptions
- Cache operations (6 tests) - get/set/delete, key prefix

### ✓ Schemas (`TestVolumeAnomalySchemas`)
**Status**: 4/4 PASSED

- Enum values validation
- Schema structure (VolumeTimeSlot, VolumeAnomalyResponse)
- 72 time slots capacity

### ✓ Detection Logic (`TestDetectVolumeAnomaliesMethod`)
**Status**: 12/12 PASSED

- Returns 72 slots (09:00-14:55 at 5min intervals)
- Anomaly thresholds: normal (<1.5x), elevated (1.5-2x), high (2-3x), very_high (≥3x)
- Edge cases: zero avg_volume, sparse data, symbol normalization
- Time label formatting (HH:MM)

### ✗ Endpoint Tests (`TestVolumeAnomalyEndpoint`)
**Status**: 3/4 PASSED, 1 FAILED

**FAILED**: `test_endpoint_no_data_returns_404`
- Expected: HTTPException(404) when no data
- Actual: No exception raised
- Root cause: On-demand collector (line 156-159) runs before validation
- Impact: Endpoint doesn't return 404 for invalid symbols during fresh collection attempts

**Passed**:
- Happy path returns 200 + 72 slots
- Default days=20 parameter
- Custom days parameter

### ✗ Integration Tests (`TestVolumeAnomalyIntegration`)
**Status**: 0/2 PASSED, 2 FAILED

**FAILED**: `test_full_flow_with_mock_data`, `test_edge_case_boundary_ratios`
- Error: `StopAsyncIteration` - mock side_effect exhausted
- Root cause: On-demand collector executes 2 DB queries (collect + detect), tests only mocked 3 queries (latest + baseline + current)
- Missing mocks for:
  1. Symbol existence check (line 156)
  2. Additional bar insertion queries (line 158)

---

## Critical Issues

### Issue #1: 404 Behavior Changed
**Severity**: Medium
**File**: `src/stocks/price/router.py:156-162`

On-demand collection added between cache check and anomaly detection, masks invalid symbols:
```python
# Cache miss - collect fresh data
try:
    bars = await collector.collect_symbol(symbol)  # ← Runs for invalid symbols
    if bars:
        await collector.save_bars(bars)
```

**Expected**: Return 404 immediately if symbol invalid
**Actual**: Attempts collection, logs warning, then computes anomalies (may return empty data without 404)

### Issue #2: Integration Test Mocks Incomplete
**Severity**: Low (tests only)
**File**: `tests/test_volume_anomaly_detection.py:642`

Tests assume 3 DB queries but on-demand flow executes 4-5:
1. Latest date query
2. **Symbol validation (new)**
3. Baseline query
4. Current query
5. **Bar insertion (new, conditional)**

---

## Performance Metrics

- Cache tests: 0.05s (21 tests)
- Schema tests: 0.04s (4 tests)
- Detection tests: 0.06s (12 tests)
- Endpoint/Integration: 1.06s (7 tests, 3 failed)

**Total execution**: ~1.2s

---

## Warnings

1. **Pydantic V2 deprecation** (`src/stocks/schemas/price.py:90`): Class-based config deprecated, use ConfigDict
2. **Jupyter platformdirs migration**: Non-blocking

---

## Coverage Analysis

**Not tested**:
- Cache hit path (line 147-149) - needs integration test with actual cache populated
- On-demand collection failure recovery (line 160-162) - warning logged but continues
- Concurrent cache access (race conditions during trading hours)
- Cache invalidation on stale data

**Well covered**:
- Core detection algorithm (12 tests)
- Trading hours logic (7 tests)
- Cache operations (6 tests)
- Schema validation (4 tests)

---

## Recommendations

### Priority 1 - Fix Failing Tests
1. Update `test_endpoint_no_data_returns_404` to account for on-demand collection
2. Add DB query mocks for symbol validation + bar insertion in integration tests

### Priority 2 - Add Missing Tests
1. Cache hit scenario (endpoint returns cached result)
2. On-demand collection when vnstock API fails
3. Symbol validation before attempting collection
4. Race condition handling (multiple requests for same symbol)

### Priority 3 - Code Quality
1. Migrate Pydantic schema to ConfigDict (line 90)
2. Add validation for invalid symbols before collection (line 142-143)
3. Consider cache warming strategy for popular symbols

---

## Unresolved Questions

1. Should endpoint return 404 for invalid symbols or attempt collection first?
2. What's the expected behavior when vnstock returns empty bars for valid symbol?
3. Should cache be pre-warmed during market hours for top symbols?
4. How to handle partial data (only some time slots have baseline)?

---

**Next Steps**: Fix test mocks OR update endpoint behavior to validate symbols before collection.
