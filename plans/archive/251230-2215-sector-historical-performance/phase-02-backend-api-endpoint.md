# Phase 2: Backend - API Endpoint

## Overview

| Field | Value |
|-------|-------|
| Priority | P1 |
| Effort | 1h |
| Status | DONE |
| Dependencies | Phase 1 complete |

## Files to Modify/Create

| Action | File |
|--------|------|
| CREATE | `apps/api/src/stocks/analytics/sector_historical_router.py` |
| MODIFY | `apps/api/src/stocks/schemas/market.py` |
| MODIFY | `apps/api/src/stocks/analytics/router.py` |

## Implementation Steps

### Step 1: Add Pydantic Schemas

**File**: `apps/api/src/stocks/schemas/market.py` (MODIFY)

```python
from typing import Literal

# Period type for sector historical
SectorHistoricalPeriod = Literal["1W", "2W", "1M"]


class SectorHistoricalItem(BaseModel):
    """Sector historical performance item."""

    icb_code: str = Field(..., description="ICB Level 2 code")
    icb_name: str = Field(..., description="Sector name (Vietnamese)")
    change_pct: float = Field(..., description="Average change percentage")


class SectorHistoricalResponse(BaseModel):
    """Response for sector historical performance endpoint."""

    period: str = Field(..., description="Period: 1W, 2W, or 1M")
    top_gainers: list[SectorHistoricalItem] = Field(default_factory=list)
    top_losers: list[SectorHistoricalItem] = Field(default_factory=list)
    generated_at: Optional[str] = Field(None, description="When data was calculated")
```

### Step 2: Create Router

**File**: `apps/api/src/stocks/analytics/sector_historical_router.py` (CREATE)

```python
"""Sector historical performance endpoint."""
from fastapi import APIRouter, Depends, HTTPException, Query

from src.core.ratelimit import standard_rate_limit
from src.stocks.analytics.sector_historical_service import (
    SectorHistoricalService,
    sector_historical_cache,
)
from src.stocks.schemas.market import (
    SectorHistoricalItem,
    SectorHistoricalResponse,
    SectorHistoricalPeriod,
)

router = APIRouter()


@router.get(
    "/sector-historical",
    response_model=SectorHistoricalResponse,
    dependencies=[Depends(standard_rate_limit)],
)
async def get_sector_historical_performance(
    period: SectorHistoricalPeriod = Query("1W", description="Period: 1W, 2W, or 1M"),
) -> SectorHistoricalResponse:
    """Get sector historical performance for a given period.

    Returns top 5 gaining and top 5 losing sectors based on
    average stock performance over the specified period.

    Data is pre-computed daily at 15:45 ICT and cached for 24h.
    """
    # Try cache first
    cached = sector_historical_cache.get(period)

    if cached is not None:
        return SectorHistoricalResponse(
            period=period,
            top_gainers=[SectorHistoricalItem(**g) for g in cached.get("top_gainers", [])],
            top_losers=[SectorHistoricalItem(**l) for l in cached.get("top_losers", [])],
            generated_at=cached.get("generated_at"),
        )

    # Cache miss - return empty (job hasn't run yet)
    return SectorHistoricalResponse(
        period=period,
        top_gainers=[],
        top_losers=[],
        generated_at=None,
    )


@router.post(
    "/sector-historical/refresh",
    response_model=dict,
    dependencies=[Depends(standard_rate_limit)],
)
async def refresh_sector_historical() -> dict:
    """Manually trigger sector historical calculation.

    For admin/debug use. In production, data is computed via scheduled job.
    """
    import asyncio

    service = SectorHistoricalService()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, service.calculate_all_periods)

    return {"status": "ok", "periods_calculated": list(result.keys())}
```

### Step 3: Register Router

**File**: `apps/api/src/stocks/analytics/router.py` (MODIFY)

```python
from .sector_historical_router import router as sector_historical_router

# Add to existing includes:
router.include_router(sector_historical_router, tags=["sector-historical"])
```

## API Contract

### GET /api/v1/stocks/analytics/sector-historical

**Query Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| period | string | 1W | One of: 1W, 2W, 1M |

**Response (200 OK):**
```json
{
  "period": "1W",
  "top_gainers": [
    {"icb_code": "8300", "icb_name": "Bất động sản", "change_pct": 5.23},
    {"icb_code": "5500", "icb_name": "Tiện ích", "change_pct": 3.15}
  ],
  "top_losers": [
    {"icb_code": "4500", "icb_name": "Y tế", "change_pct": -2.34},
    {"icb_code": "5300", "icb_name": "Bán lẻ", "change_pct": -1.87}
  ],
  "generated_at": "2025-12-30T15:45:00"
}
```

**Response (No Data):**
```json
{
  "period": "1W",
  "top_gainers": [],
  "top_losers": [],
  "generated_at": null
}
```

## Todo List

- [ ] Add `SectorHistoricalItem` and `SectorHistoricalResponse` to schemas
- [ ] Create `sector_historical_router.py` with GET endpoint
- [ ] Add POST `/refresh` endpoint for manual trigger
- [ ] Register router in `analytics/router.py`
- [ ] Test endpoint with curl/httpie

## Success Criteria

- GET returns cached data from Redis
- Empty response (not 500) when cache is empty
- POST `/refresh` triggers job and populates cache
- Response matches API contract above

## Risks

| Risk | Mitigation |
|------|------------|
| Cache empty on first deploy | Return empty arrays, frontend shows "No data" |
| Invalid period param | FastAPI validates enum, returns 422 |
