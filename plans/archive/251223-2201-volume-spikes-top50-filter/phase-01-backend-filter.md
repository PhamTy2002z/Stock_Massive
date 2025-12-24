# Phase 01: Backend Filter Implementation

## Context

- **Parent Plan:** [plan.md](./plan.md)
- **Dependencies:** None
- **Docs:** `docs/code-standards.md`, `docs/system-architecture.md`

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-23 |
| Priority | P2 |
| Effort | 1h |
| Implementation Status | pending |
| Review Status | pending |

## Description

Add `top_profitable_only: bool` parameter to `/analytics/volume-spikes` endpoint. When enabled, filter spikes to only include symbols from Top 50 FinancialStatement records.

## Key Insights

1. `FinancialStatement` table already has `rank` column (1-50)
2. Query latest period's top 50 symbols, create Set for O(1) lookup
3. Skip non-top-50 symbols during spike calculation loop
4. Add param to cache key for proper cache separation

## Requirements

- [x] Add `top_profitable_only: bool = Query(False)` to router
- [x] Query top 50 symbols from FinancialStatement in service
- [x] Filter spikes during calculation
- [x] Update cache key pattern

## Related Files

| File | Changes |
|------|---------|
| `apps/api/src/stocks/analytics/router.py` | Add parameter, update cache key |
| `apps/api/src/stocks/analytics/service.py` | Add filter logic |

## Implementation Steps

### Step 1: Update Router (router.py)

```python
# Add parameter to endpoint
@router.get("/volume-spikes", response_model=VolumeSpikeResponse)
async def get_volume_spikes(
    target_date: Optional[date] = Query(None, ...),
    min_ratio: float = Query(1.5, ...),
    exchange: Optional[str] = Query(None, ...),
    include_upcom: bool = Query(False, ...),
    limit: int = Query(50, ...),
    top_profitable_only: bool = Query(  # NEW
        False,
        description="Only show Top 50 profitable companies"
    ),
    db: AsyncSession = Depends(get_db),
) -> VolumeSpikeResponse:
    # Update cache key
    cache_key = f"{date_str}:{min_ratio}:{exchange or 'all'}:{include_upcom}:{limit}:{top_profitable_only}"

    # Pass to service
    result = await service.get_volume_spikes(
        target_date=target_date,
        min_ratio=min_ratio,
        exchange=exchange,
        include_upcom=include_upcom,
        limit=limit,
        top_profitable_only=top_profitable_only,  # NEW
    )
```

### Step 2: Update Service (service.py)

```python
async def get_volume_spikes(
    self,
    target_date: Optional[date] = None,
    min_ratio: float = 1.5,
    exchange: Optional[str] = None,
    include_upcom: bool = False,
    limit: int = 50,
    top_profitable_only: bool = False,  # NEW
) -> VolumeSpikeResponse:
    start_time = time.time()

    # NEW: Get top 50 symbols if filter enabled
    top_symbols: Optional[set[str]] = None
    if top_profitable_only:
        top_symbols = await self._get_top_profitable_symbols()

    # ... existing code ...

    # In spike calculation loop, add filter:
    for symbol, data_list in symbol_data.items():
        # NEW: Skip if not in top 50
        if top_symbols is not None and symbol not in top_symbols:
            continue

        # ... rest of existing logic ...

async def _get_top_profitable_symbols(self) -> set[str]:
    """Get symbols of top 50 profitable companies from latest period."""
    # Get latest period
    latest = await self.db.execute(
        select(FinancialStatement.year, FinancialStatement.quarter)
        .order_by(desc(FinancialStatement.year), desc(FinancialStatement.quarter))
        .limit(1)
    )
    row = latest.first()
    if not row:
        return set()

    year, quarter = row.year, row.quarter

    # Get top 50 symbols for this period
    result = await self.db.execute(
        select(FinancialStatement.symbol)
        .where(
            FinancialStatement.year == year,
            FinancialStatement.quarter == quarter,
            FinancialStatement.rank <= 50
        )
    )
    return {r.symbol for r in result.all()}
```

### Step 3: Add Import (service.py)

```python
# At top of file, ensure FinancialStatement is imported
from src.stocks.models import FinancialStatement, StockDailyOHLCV
```

## Todo List

- [ ] Add `top_profitable_only` parameter to router endpoint
- [ ] Update cache key to include new parameter
- [ ] Add `_get_top_profitable_symbols()` helper method
- [ ] Add filter logic in `get_volume_spikes()` method
- [ ] Test endpoint with `top_profitable_only=true`

## Success Criteria

1. `GET /analytics/volume-spikes?top_profitable_only=true` returns filtered results
2. Only symbols from Top 50 FinancialStatement appear in response
3. Cache key properly separates cached results
4. No performance regression (set lookup is O(1))

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Empty FinancialStatement table | Low | Medium | Return empty response, log warning |
| Period mismatch | Low | Low | Always use latest available period |

## Security Considerations

- Input validation via FastAPI Query (bool type)
- No SQL injection risk (parameterized queries)

## Next Steps

After this phase: [Phase 02 - Frontend Tabs](./phase-02-frontend-tabs.md)
