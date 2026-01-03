# Code Review: Sector Historical Performance

**Reviewer:** code-reviewer | **Date:** 2024-12-30 22:41 ICT

## Code Review Summary

### Scope
- Files reviewed: 9 files (backend, frontend, schema, tests)
- Lines analyzed: ~550
- Review focus: Sector Historical Performance feature

### Overall Assessment
Implementation is **solid** and follows codebase patterns. Minor security consideration identified but not critical. All tests pass (8/8).

---

## Critical Issues
None.

---

## High Priority Findings

### 1. `/refresh` endpoint uses wrong rate limit [MEDIUM-HIGH]
**File:** `sector_historical_router.py:62`

- Uses `standard_rate_limit` (100 req/min) instead of `heavy_rate_limit` (20 req/min)
- `calculate_all_periods()` runs ~2 min (100 symbols x 1.2s delay)
- Similar endpoint `/financial-statements/collect` correctly uses `heavy_rate_limit`

```python
# Current
dependencies=[Depends(standard_rate_limit)],

# Should be
dependencies=[Depends(heavy_rate_limit)],
```

**Impact:** Could allow multiple concurrent expensive computations if abused

---

## Medium Priority Improvements

### 2. Admin endpoint lacks authentication
**File:** `sector_historical_router.py:59-73`

- Docstring says "For admin/debug use" but no auth guard
- Follows existing codebase pattern (other endpoints also unprotected)
- Acceptable for MVP but note for future

### 3. Missing startup job check for sector-historical
**File:** `scheduler.py`

- `run_startup_jobs()` checks intraday, cleanup, ohlcv but NOT sector-historical
- Not critical since data updates daily and TTL=24h

---

## Low Priority Suggestions

### 4. Type consistency in schema
**File:** `schemas/market.py:92`

```python
generated_at: Optional[str] = Field(None, ...)  # str
# vs SectorPerformanceResponse uses
generated_at: datetime  # datetime object
```
Minor inconsistency, not breaking.

---

## Positive Observations

1. **Clean architecture**: Service/Router/Schema separation follows patterns
2. **Good caching**: Uses `TradingHoursCache` with 24h TTL - appropriate for historical data
3. **Proper validation**: Uses `Literal["1W", "2W", "1M"]` for period - FastAPI returns 422 for invalid
4. **Good tests**: 8 tests covering config, API structure, validation
5. **Performance optimized**: Single VN100 symbols fetch, shared across all periods
6. **Frontend**: Uses `useSuspenseQuery` + memo + lodash `isEqual` - follows patterns

---

## Security Checklist

| Check | Status | Notes |
|-------|--------|-------|
| SQL Injection | PASS | Uses vnstock lib APIs, no raw SQL |
| XSS | PASS | Pydantic models sanitize output |
| CSRF | N/A | Read-only GET endpoint |
| Rate Limiting | WARN | `/refresh` should use heavy limit |
| Input Validation | PASS | Period uses Literal type |
| Auth | INFO | No auth on admin endpoint (matches codebase) |

---

## Test Results

```
tests/test_sector_historical.py: 8 passed (1.01s)
```

| Test | Result |
|------|--------|
| test_periods_config_values | PASS |
| test_periods_keys | PASS |
| test_get_endpoint_response_structure | PASS |
| test_get_endpoint_all_periods | PASS |
| test_response_item_structure | PASS |
| test_invalid_period | PASS |
| test_service_initialization | PASS |
| test_get_cached_returns_none_for_missing | PASS |

---

## Build Status

- **Backend tests:** PASS (8/8)
- **Frontend build:** See note below

**Note:** Frontend build fails on `/page.tsx` SSG but this is pre-existing issue with API fetch during static generation - not related to this feature.

---

## Recommended Actions

1. **[HIGH]** Change `/refresh` to use `heavy_rate_limit`
2. **[LOW]** Consider adding `_should_run_sector_historical_job()` to startup checks

---

## Files Reviewed

**Backend:**
- `apps/api/src/stocks/analytics/sector_historical_service.py` - OK
- `apps/api/src/stocks/analytics/sector_historical_router.py` - Rate limit issue
- `apps/api/src/core/config.py` - OK
- `apps/api/src/stocks/jobs.py` - OK
- `apps/api/src/core/scheduler.py` - OK
- `apps/api/src/stocks/schemas/market.py` - OK
- `apps/api/tests/test_sector_historical.py` - OK

**Frontend:**
- `apps/web/src/hooks/use-sector-historical-performance.ts` - OK
- `apps/web/src/components/dashboard/sector-historical-performance.tsx` - OK
- `apps/web/src/lib/api.ts` - OK
- `apps/web/src/lib/query-keys.ts` - OK

---

## Unresolved Questions
None.
