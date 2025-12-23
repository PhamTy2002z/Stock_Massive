# Phase 1: Backend - HSX/HOSE Normalization

## Context Links

- [Main Plan](./plan.md)
- [Brainstorm Report](../reports/brainstorm-251223-1951-top50-financial-statements-readiness.md)
- API Router: `apps/api/src/stocks/analytics/router.py`
- Service: `apps/api/src/stocks/analytics/service.py`

## Overview

- **Priority**: P0
- **Status**: Complete
- **Description**: Normalize exchange names so API accepts both `HOSE` and `HSX` as valid inputs

## Key Insights

- Database stores `HSX` (from vnstock library)
- Frontend/users expect `HOSE` (common name)
- API description says "HOSE or HNX" but data is "HSX or HNX"
- Need mapping layer, NOT data migration

## Requirements

### Functional
- API accepts `HOSE` as alias for `HSX`
- API accepts `HNX` unchanged
- API rejects invalid exchange values

### Non-Functional
- No database migration needed
- Backward compatible (HSX still works)

## Architecture

```
Frontend sends: exchange=HOSE
     ↓
API Router normalizes: HOSE → HSX
     ↓
Service queries: WHERE exchange = 'HSX'
     ↓
Response: data with exchange='HSX' displayed as 'HOSE' (optional)
```

## Related Code Files

| Action | File |
|--------|------|
| MODIFY | `apps/api/src/stocks/analytics/router.py` |
| MODIFY | `apps/api/src/stocks/analytics/service.py` |

## Implementation Steps

### Step 1: Add Exchange Normalization Helper

In `apps/api/src/stocks/analytics/service.py`, add at top:

```python
# Exchange name mapping (UI name → DB name)
EXCHANGE_ALIASES = {
    "HOSE": "HSX",
    "HSX": "HSX",
    "HNX": "HNX",
}

def normalize_exchange(exchange: str | None) -> str | None:
    """Normalize exchange name for database query."""
    if not exchange:
        return None
    return EXCHANGE_ALIASES.get(exchange.upper(), exchange.upper())
```

### Step 2: Update Service Method

In `get_financial_statements` method, normalize exchange before query:

```python
async def get_financial_statements(
    self,
    limit: int = 50,
    exchange: Optional[str] = None,
    year: Optional[int] = None,
    quarter: Optional[int] = None,
) -> FinancialStatementsResponse:
    # Normalize exchange alias
    normalized_exchange = normalize_exchange(exchange)

    # ... rest of method uses normalized_exchange ...
```

### Step 3: Update Router Description

In `apps/api/src/stocks/analytics/router.py`:

```python
exchange: Optional[str] = Query(
    None,
    pattern="^(HOSE|HSX|HNX)$",
    description="Filter by exchange: HOSE (or HSX) or HNX"
)
```

## Todo List

- [x] Add `EXCHANGE_ALIASES` constant to service.py
- [x] Add `normalize_exchange()` helper function
- [x] Update `get_financial_statements()` to use normalized exchange
- [x] Update router Query description
- [x] Test with curl: `/analytics/financial-statements?exchange=HOSE`

## Success Criteria

- `GET /analytics/financial-statements?exchange=HOSE` returns HSX records
- `GET /analytics/financial-statements?exchange=HSX` still works
- `GET /analytics/financial-statements?exchange=INVALID` returns 422

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Cache key mismatch | Normalize before cache key generation |
| Breaking existing clients using HSX | Both HSX and HOSE map to same result |

## Security Considerations

- Input validation via regex pattern in Query
- No SQL injection risk (uses SQLAlchemy ORM)

## Next Steps

After this phase, proceed to Phase 2: Frontend Exchange Filter UI
