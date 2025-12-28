# Code Review: Phase 1 Backend APIs

**Date:** 2024-12-28
**Reviewer:** code-reviewer
**Plan:** `/plans/251228-1211-financial-statements-enhancement/phases/phase-1-backend-apis.md`

---

## Code Review Summary

### Scope
- **Files reviewed:** 6 files
  - `/apps/api/src/stocks/schemas/financial.py` (new schemas)
  - `/apps/api/src/stocks/financial/health_scoring.py` (new module)
  - `/apps/api/src/stocks/financial/service.py` (extended)
  - `/apps/api/src/stocks/financial/router.py` (new endpoints)
  - `/apps/api/src/stocks/analytics/router.py` (sector-peers)
  - `/apps/api/src/stocks/service.py` (delegates)
- **Lines added:** ~700+
- **Review focus:** Security, performance, architecture, error handling

### Overall Assessment

**Rating: 7.5/10** - Solid implementation following existing patterns. Good error handling and caching. Some performance concerns with N+1 API calls in `get_sector_peers`.

---

## Critical Issues

None found.

---

## High Priority Findings

### 1. N+1 API Pattern in `get_sector_peers` (Performance)

**Location:** `/apps/api/src/stocks/financial/service.py:847-870`

**Problem:** Loop calls `get_ratio_history()` for each peer (up to 6 times), causing N+1 external API calls to vnstock VCI.

```python
for peer_symbol in top_symbols[:limit + 1]:
    ratio_history = self.get_ratio_history(peer_symbol, periods=1)  # API call per peer!
```

**Impact:**
- 6 sequential vnstock API calls per request
- ~900ms+ latency (150ms x 6 calls)
- VCI rate limit risk

**Recommendation:**
- Cache is already in place (24h off-hours) which mitigates production impact
- Consider future batch API if vnstock supports it
- Current implementation acceptable for MVP with caching

### 2. Missing Unit Tests for Scoring Algorithms

**Location:** `/apps/api/src/stocks/financial/health_scoring.py`

**Problem:** Plan specifies unit tests but none implemented yet.

**Impact:** Risk of scoring logic bugs going undetected.

**Recommendation:** Add tests in Phase 5 or before merge:
- Test `normalize_score()` with edge cases (None, 0, negative)
- Test `calculate_f_score()` with various scenarios
- Test `calculate_health_score()` weight calculations

---

## Medium Priority Improvements

### 3. Import Statement at Module End (Code Style)

**Location:** `/apps/api/src/stocks/analytics/router.py:167-170`

```python
# ==================== Sector Peers Endpoint ====================
from src.stocks.schemas.financial import SectorPeersResponse
from src.stocks.service import get_stock_service
from src.stocks.shared import StockServiceError
```

**Issue:** Imports should be at file top per PEP-8.

**Impact:** Minor - works but inconsistent style.

### 4. HTTPException Import Inside Function

**Location:** `/apps/api/src/stocks/analytics/router.py:207`

```python
except StockServiceError as e:
    from fastapi import HTTPException  # Should be at top
    raise HTTPException(status_code=502, detail=str(e))
```

**Issue:** Import inside except block.

### 5. Redundant `gross_profit` in TrendMetricsResponse

**Location:** `/apps/api/src/stocks/schemas/financial.py:156`

Schema has `gross_profit` but plan spec only mentions `gross_margin`. Both are returned which is fine but verify frontend needs both.

---

## Low Priority Suggestions

### 6. F-Score Max Should Be 6 Not 9

**Location:** `/apps/api/src/stocks/schemas/financial.py:141`

```python
f_score: int = Field(..., ge=0, le=9)  # Implementation uses 6 criteria
```

Plan specifies "simplified Piotroski (6 criteria)" but schema allows 0-9. Consider:
- Change to `le=6` for accuracy
- Or document as "extended F-Score" if 9 intended

### 7. Magic Column Name Strings

**Location:** `/apps/api/src/stocks/financial/service.py:686-697`

Many vnstock column names hardcoded as strings:
```python
safe_float(i.get("Net Sales") or i.get("Revenue (Bn. VND)"))
```

Consider extracting to constants for maintainability if vnstock column names change.

---

## Positive Observations

1. **Consistent Pattern Usage**
   - Follows existing service/router architecture
   - Uses `validate_symbol()` in all methods
   - Proper `StockServiceError` exception propagation

2. **Comprehensive Error Handling**
   - All new methods have try-except blocks
   - Errors logged before re-raising
   - Graceful None handling in scoring

3. **Smart Caching Strategy**
   - TradingHoursCache with 1h trading / 24h off-hours TTL
   - Cache keys include parameters (periods, limit)
   - Reduces VCI API load significantly

4. **Type Safety**
   - Pydantic schemas with Field constraints (`ge=0, le=100`)
   - Optional types used appropriately
   - `safe_float()` prevents type errors from vnstock data

5. **Well-Structured Scoring Module**
   - Clean separation of concerns (health_scoring.py)
   - Configurable benchmarks and weights
   - Handles Vietnam market specifics

---

## Recommended Actions

1. **[Low]** Move imports to file top in `analytics/router.py`
2. **[Medium]** Add unit tests for `health_scoring.py` before Phase 5
3. **[Low]** Consider changing F-Score max from 9 to 6 in schema
4. **[Future]** Monitor `get_sector_peers` latency in production, optimize if needed

---

## Metrics

| Metric | Value |
|--------|-------|
| Syntax Check | Pass |
| Schema Imports | Pass |
| Router Registration | 4/4 endpoints verified |
| validate_symbol() | 7/7 methods |
| Error Handling | 4/4 methods |
| Caching | 4/4 endpoints |
| Unit Tests | 0 (pending) |

---

## Updated Plans

- `/plans/251228-1211-financial-statements-enhancement/phases/phase-1-backend-apis.md`
  - Updated TODO: 8/9 tasks completed
  - Updated Success Criteria: 5/6 verified
  - Pending: Unit tests, E2E latency testing

---

## Unresolved Questions

1. Is `gross_profit` required in TrendMetrics or should it be removed?
2. Should F-Score schema max be 6 or 9?
3. What's the threshold for acceptable `get_sector_peers` latency?
