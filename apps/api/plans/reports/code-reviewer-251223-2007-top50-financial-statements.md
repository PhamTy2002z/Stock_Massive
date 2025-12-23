# Code Review: Top 50 Financial Statements Feature

**Date**: 2025-12-23
**Reviewer**: code-reviewer
**ID**: ab168cf

## Scope

- Files reviewed: 8 files (backend + frontend)
- Lines analyzed: ~900
- Focus: Endpoint rename, exchange alias, UI filter

## Overall Assessment

**PASS** - Clean implementation following existing patterns. No critical security issues. Minor improvements possible.

## Critical Issues

**None found.**

## High Priority Findings

### 1. Inconsistent Exchange Pattern in Router (Medium-High)

**File**: `apps/api/src/stocks/analytics/router.py`

```python
# Line 41: financial-statements accepts HOSE|HSX|HNX
exchange: Optional[str] = Query(None, pattern="^(HOSE|HSX|HNX)$", ...)

# Line 111: volume-spikes only accepts HOSE|HNX (no HSX)
exchange: Optional[str] = Query(None, pattern="^(HOSE|HNX)$", ...)
```

**Impact**: API inconsistency - users may expect same pattern for both endpoints.

**Recommendation**: Apply HOSE alias consistently to volume-spikes endpoint too, OR document the difference.

## Medium Priority Improvements

### 1. Unused EXCHANGE_ALIASES Entry

**File**: `apps/api/src/stocks/analytics/service.py` (line 31)

```python
EXCHANGE_ALIASES = {
    "HOSE": "HSX",
    "HSX": "HSX",  # Redundant - HSX maps to itself
    "HNX": "HNX",  # Missing - would be needed for consistency
}
```

**Recommendation**: Keep for robustness, but add comment explaining purpose.

### 2. Volume Spikes Not Using normalize_exchange()

**File**: `apps/api/src/stocks/analytics/service.py` (line 231)

```python
# get_volume_spikes() uses raw exchange comparison:
if exchange and symbol_exchange != exchange.upper():
```

But `get_top_performers()` uses `normalize_exchange()`. Consider consistency.

### 3. Frontend Type Coercion

**File**: `apps/web/src/components/dashboard/top-performers-table.tsx` (line 294-296)

```tsx
{item.exchange === "HSX" ? "HOSE" : item.exchange}
```

**Recommendation**: Consider extracting to utility function for reuse across components.

## Low Priority Suggestions

1. **Test Coverage**: Tests use `exchange="HOSE"` but don't test `exchange="HSX"` alias - add alias test case
2. **Scheduler Job ID**: Changed to `collect-financial-statements` - good semantic naming
3. **Query Key Rename**: `topPerformers` -> `financialStatements` - consistent with endpoint

## Positive Observations

1. **Input Validation**: Proper regex patterns on exchange parameter
2. **XSS Prevention**: `SYMBOL_PATTERN` regex in ICB mapping (line 49, 298-299)
3. **String Sanitization**: Length limits on company_name (255), icb_name (100), icb_code (4)
4. **Error Handling**: Proper try-catch with specific HTTP exceptions
5. **Cache Strategy**: Trading-hours-aware TTL - smart approach
6. **Rate Limiting**: Applied via dependencies
7. **All Tests Pass**: 26/26 tests passing

## Security Audit

| Check | Status |
|-------|--------|
| SQL Injection | SAFE - Uses SQLAlchemy ORM |
| XSS | SAFE - Symbol pattern validation |
| Input Validation | SAFE - FastAPI Query with pattern/ge/le |
| Auth | N/A - Public read endpoint |
| Secrets Exposure | SAFE - No secrets in code |

## Build Status

- Python syntax: PASS
- TypeScript: PASS
- Tests: 26/26 PASS

## Recommended Actions

1. **[High]** Consider adding HOSE alias to volume-spikes endpoint pattern for API consistency
2. **[Medium]** Extract `HSX->HOSE` display logic to shared utility
3. **[Low]** Add test case for HSX alias resolution

## Metrics

| Metric | Value |
|--------|-------|
| Type Coverage | N/A (Python) |
| Test Coverage | Good (26 tests for analytics) |
| Linting Issues | 0 |

---

**Verdict**: Approve with minor suggestions. No blocking issues.
