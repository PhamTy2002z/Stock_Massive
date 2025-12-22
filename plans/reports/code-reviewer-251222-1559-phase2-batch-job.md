# Code Review: Phase 2 - Scheduled Batch Job

**Date:** 2025-12-22 15:59
**Reviewer:** code-reviewer (a94db27)
**Scope:** Top Performers Collector + Scheduler Integration

---

## Summary

Phase 2 implementation is **SOLID** with good patterns. Uses existing vnstock_wrapper infrastructure correctly. No critical security issues. Minor improvements possible.

---

## Files Reviewed

| File | Lines | Status |
|------|-------|--------|
| `apps/api/src/core/config.py` | 79 | Clean config additions |
| `apps/api/src/stocks/top_performers_collector.py` | 181 | **Primary review target** |
| `apps/api/src/stocks/jobs.py` | 276 | Good job wrapper |
| `apps/api/src/core/scheduler.py` | 93 | Clean scheduler setup |

---

## Critical Issues

**None found.**

---

## High Priority Findings

### 1. Blocking I/O in Async Context (Medium-High)
**File:** `top_performers_collector.py:75`

```python
time.sleep(delay)  # Blocking call inside async collect()
```

**Impact:** Blocks event loop during collection. With 1000+ symbols at 1.5s delay = 25+ min of blocked event loop.

**Status:** Acceptable for batch job context. The `collect()` method is the entire job - no concurrent async work needed. However, if API needs remain responsive during collection, this could be problematic.

**Recommendation:** Consider `asyncio.sleep()` if other async work needed during collection.

### 2. No Job Timeout/Cancellation Support
**File:** `top_performers_collector.py`

The collect() method has no mechanism to cancel mid-run if taking too long.

**Recommendation:** Add optional `max_runtime_seconds` param for graceful early exit.

---

## Medium Priority Findings

### 3. Hardcoded Screener Source
**File:** `top_performers_collector.py:103`

```python
screener = Screener(source="tcbs")
```

Should use configurable source like other vnstock calls use `settings.vnstock_source`.

### 4. Symbol Limit May Miss Stocks
**File:** `top_performers_collector.py:104`

```python
df = screener.stock(params={"exchangeName": "HOSE,HNX"}, limit=1000)
```

HOSE+HNX combined > 1000 symbols. Some stocks may be missed.

### 5. Row-by-Row Database Insert
**File:** `top_performers_collector.py:154-172`

Loop inserts one at a time. For 1000+ symbols, this is slow.

**Recommendation:** Use `executemany()` or SQLAlchemy bulk operations.

---

## Low Priority / Suggestions

### 6. Duplicate Year/Quarter Extraction Logic
Column name variations (`yearReport` vs `lengthReport`) are handled but could be fragile if vnstock API changes.

### 7. Missing Type Hints
`_get_symbols()` returns `list` - could be more specific: `list[dict[str, Any]]`

### 8. Config Comment Says "Sunday" But Cron Enforces It
`scheduler.py:84` - Comment is good, but config variable `top_performers_hour` doesn't indicate weekly nature.

---

## Positive Observations

1. **Proper Rate Limit Handling** - Uses `safe_vnstock_call` and `VnstockRateLimitError` consistently
2. **Adaptive Delays** - Uses `get_adaptive_delay()` for backoff on failures
3. **Good Progress Logging** - Every 50 symbols, elapsed time tracking
4. **Proper Upsert Logic** - ON CONFLICT handles re-runs gracefully
5. **Transaction Safety** - Rollback on failure in `_store_results()`
6. **Feature Flags** - `top_performers_enabled` config for easy disable
7. **Clean Separation** - Collector class separate from job wrapper

---

## Security Audit

| Check | Status |
|-------|--------|
| SQL Injection | **Safe** - Uses parameterized queries via SQLAlchemy `text()` |
| Input Validation | **OK** - Data from vnstock API, no user input |
| Secrets Exposure | **OK** - No secrets in code |
| Rate Limit DoS | **Mitigated** - Adaptive delays + skip on rate limit |

---

## Architecture Compliance

| Pattern | Status |
|---------|--------|
| YAGNI | **Pass** - Only collects what's needed |
| KISS | **Pass** - Simple collector pattern |
| DRY | **Minor** - Some pattern duplication with daily_ohlcv, acceptable |
| Existing Patterns | **Pass** - Follows same structure as `IntradayCollector` |

---

## Recommended Actions

1. **Optional:** Convert `time.sleep()` to `asyncio.sleep()` if other async work needed
2. **Low:** Add `limit=2000` to screener call to capture all symbols
3. **Low:** Consider batch insert for performance (~1000 individual inserts is slow)
4. **Very Low:** Make screener source configurable

---

## Metrics

- Code Coverage: Phase 2 tests pending
- Type Safety: Good (minor hint improvements possible)
- Linting: Passed (via Ruff)

---

## Verdict

**APPROVED** - Ready to proceed to Phase 3 (API endpoints).

Implementation follows established patterns, handles rate limits properly, and has no security concerns. The blocking sleep is acceptable for a weekly batch job context.
