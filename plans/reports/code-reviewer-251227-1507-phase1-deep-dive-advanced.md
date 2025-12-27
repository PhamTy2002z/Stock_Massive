# Code Review: Phase 1 - Deep Dive Advanced Tab

## Summary

| Metric | Value |
|--------|-------|
| Files reviewed | 8 |
| Lines analyzed | ~800 |
| Critical issues | 2 |
| Warnings | 3 |
| Suggestions | 4 |

## Critical Issues (Must Fix)

### 1. Schema Mismatch - InsiderDealItem

**File**: `company/service.py:161-170` vs `schemas/company.py:127-134`

Schema defines:
```python
class InsiderDealItem(BaseModel):
    announce_date: str
    action: str
    quantity: float
    price: Optional[float] = None
    ratio: Optional[float] = None
```

But service creates:
```python
InsiderDealItem(
    id=str(row.get("id", "")),  # NOT IN SCHEMA
    name=str(row.get("deal_owner_name", "")),  # NOT IN SCHEMA
    position=row.get("deal_position"),  # NOT IN SCHEMA
    deal_type=row.get("deal_action"),  # NOT IN SCHEMA
    shares=safe_float(row.get("deal_quantity")),  # SHOULD BE `quantity`
    announce_date=announce_date,
    relation=row.get("deal_relation"),  # NOT IN SCHEMA
)
```

**Impact**: Runtime validation error - Pydantic will reject extra fields.

**Fix**: Update schema to match service fields OR update service to use schema fields.

### 2. Schema Mismatch - CompanyOverview

**File**: `company/service.py:193-205` vs `schemas/company.py:8-18`

Schema defines 8 fields, but service passes additional fields:
- `short_name` - NOT IN SCHEMA
- `issue_share` - NOT IN SCHEMA
- `outstanding_share` - NOT IN SCHEMA

**Impact**: Extra fields silently ignored (with `model_config = ConfigDict(extra='ignore')`) or error.

**Fix**: Add missing fields to `CompanyOverview` schema.

---

## Warnings (Should Fix)

### 1. Division by Zero Risk - Price Depth

**File**: `price/service.py:273`

```python
spread_pct = (spread / bid_1.price * 100) if bid_1.price > 0 else 0
```

Current check is OK, but `bid_1.price` can be `0` from default fallback at line 239:
```python
price=safe_float(...) or 0  # Fallback to 0
```

**Recommendation**: Handle zero price case more explicitly.

### 2. Integer Overflow Potential - Volume Fields

**File**: `price/service.py:240, 245, 250, 256, 261, 266`

```python
volume=int(row.get("bid_volume_1") or row.get("bidVolume1") or row.get("bidVol1") or 0)
```

If vnstock returns unexpected type (str), `int()` may raise ValueError.

**Recommendation**: Use `safe_int()` helper similar to `safe_float()`.

### 3. Cache Key Injection

**File**: `price/router.py:228`, `company/router.py:99,124`

```python
cache_key = symbol.upper()
```

Symbol from path param - validated upstream but cache key injection possible if validation bypassed.

**Recommendation**: Already mitigated by `validate_symbol()` regex check. Low risk.

---

## Suggestions (Optional)

### 1. DRY Violation - Vnstock Instance Creation

**Files**: `company/service.py` - Multiple `Vnstock().stock(symbol=symbol, source=self.source)` calls.

Consider caching stock instance per symbol to reduce API overhead.

### 2. Inconsistent Error Handling

Some methods return empty response on error, others raise StockServiceError.

- `get_company_overview`: Returns empty on None/empty
- `get_ratio_summary`: Returns empty on None/empty
- `get_price_depth`: Raises StockServiceError on None/empty

**Recommendation**: Standardize error handling pattern.

### 3. Missing Type Hints - Service Delegates

**File**: `service.py:36-77`

Delegate methods lack return type hints:
```python
def get_history(self, symbol: str, start: date, end: date, interval: str = "1D"):
    # No return type
```

### 4. Test Coverage - Missing Edge Cases

**File**: `tests/test_advanced_endpoints.py`

Missing tests:
- Cache hit/miss scenarios
- Rate limit exhaustion
- Malformed symbol validation

---

## Positive Observations

1. **Good separation of concerns** - Price/Company/Financial/Market domains properly isolated
2. **Trading-hours-aware caching** - Smart TTL strategy
3. **Consistent error logging** - Logger used throughout
4. **Symbol validation** - Regex-based validation prevents injection
5. **Graceful degradation** - Many methods handle None/empty data gracefully

---

## Task Completion Status

Based on Phase 1 plan (`phase-01-backend-new-endpoints.md`):

| Task | Status |
|------|--------|
| Add PriceLevel, PriceDepthResponse schemas | DONE |
| Add RatioSummaryResponse, TradingStatsResponse schemas | DONE |
| Implement get_price_depth service method | DONE |
| Implement get_ratio_summary service method | DONE |
| Implement get_trading_stats service method | DONE |
| Add price-depth router endpoint | DONE |
| Add ratio-summary router endpoint | DONE |
| Add trading-stats router endpoint | DONE |
| Configure Redis caching | DONE |
| Write tests for new endpoints | DONE |
| Test with VCI data source | NEEDS VALIDATION |

---

## Recommended Actions (Priority Order)

1. **[CRITICAL]** Fix `InsiderDealItem` schema mismatch
2. **[CRITICAL]** Fix `CompanyOverview` schema mismatch
3. **[WARN]** Add `safe_int()` helper for volume parsing
4. **[SUGG]** Add return type hints to service delegates
5. **[SUGG]** Add cache hit/miss tests

---

## Unresolved Questions

1. Is `InsiderDealItem` used by frontend? If so, which fields are expected?
2. Should `CompanyOverview` include financial fields or stay minimal?
3. Cache TTL for ratio-summary shows 5min trading / 1h off-hours in router, but plan says 1h/6h - which is correct?
