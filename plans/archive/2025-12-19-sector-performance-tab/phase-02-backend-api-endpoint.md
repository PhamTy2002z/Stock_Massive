# Phase 2: Backend API Endpoint

## Context

Second phase of Sector Performance Tab feature. Add FastAPI endpoint to expose sector performance data.

## Overview

Create REST endpoint `GET /stocks/sector-performance` following existing router patterns.

## Requirements

1. Add endpoint to `router.py`
2. Follow existing endpoint patterns (error handling, docstrings)
3. Return `SectorPerformanceResponse` schema
4. Handle service errors with HTTP 502

## Architecture

```
GET /api/v1/stocks/sector-performance
    ↓
router.py → get_sector_performance()
    ↓
service.py → StockService.get_sector_performance()
    ↓
SectorPerformanceResponse (JSON)
```

## Related Files

| File | Action |
|------|--------|
| `apps/api/src/stocks/router.py` | Add endpoint |
| `apps/api/src/stocks/schemas.py` | Import (from Phase 1) |

## Implementation Steps

### Step 1: Add Import to `router.py`

```python
from src.stocks.schemas import (
    # ... existing imports ...
    SectorPerformanceResponse,
)
```

### Step 2: Add Endpoint to `router.py`

Add after market-indices endpoint (around line 141):

```python
@router.get("/sector-performance", response_model=SectorPerformanceResponse)
async def get_sector_performance() -> SectorPerformanceResponse:
    """Get market-cap weighted sector performance.

    Returns ICB Level 2 sector performance data with:
    - Market-cap weighted average change percentage
    - Total market cap per sector
    - Stock count per sector
    - Top gainers and losers

    Data is aggregated from real-time price board.
    """
    try:
        service = get_service()
        return service.get_sector_performance()
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

### Step 3: Verify Endpoint Registration

Endpoint will be auto-registered via existing router setup:
- `router.py` uses `APIRouter(prefix="/stocks", tags=["stocks"])`
- Included in `api/v1/router.py`

## Todo List

- [ ] Add `SectorPerformanceResponse` to router.py imports
- [ ] Add `get_sector_performance` endpoint
- [ ] Test endpoint via Swagger UI (`/docs`)
- [ ] Verify response format matches schema

## Success Criteria

- [ ] Endpoint accessible at `GET /api/v1/stocks/sector-performance`
- [ ] Returns valid JSON matching `SectorPerformanceResponse`
- [ ] Swagger documentation shows endpoint with description
- [ ] Error handling returns 502 for service errors
- [ ] Response time < 2s (acceptable for aggregated data)

## Risks

| Risk | Mitigation |
|------|------------|
| Slow response | Consider caching in future |
| Service errors | Proper HTTP 502 with message |

## Testing

```bash
# Test endpoint
curl http://localhost:8000/api/v1/stocks/sector-performance

# Expected response structure
{
  "sectors": [
    {
      "icb_code": "8000",
      "icb_name": "Tài chính",
      "change_pct": 1.25,
      "total_market_cap": 1234.56,
      "stock_count": 45,
      "top_gainers": ["VCB", "TCB", "MBB"],
      "top_losers": ["STB", "EIB", "SHB"]
    }
  ],
  "generated_at": "2025-12-19T10:30:00",
  "total_sectors": 10
}
```

## Notes

- Endpoint follows existing patterns in router.py
- No query parameters needed for MVP
- Future: Add optional `icb_level` param for Level 1/2/3
