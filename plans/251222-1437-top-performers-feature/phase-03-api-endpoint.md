# Phase 3: API Endpoint

## Context

- **Parent Plan:** [plan.md](./plan.md)
- **Dependencies:** Phase 1 (Database), Phase 2 (Batch Job)
- **Docs:** [code-standards.md](../../docs/code-standards.md)

## Overview

- **Priority:** P1
- **Effort:** 1.5h
- **Status:** Pending
- **Description:** Create REST API endpoint to serve top performers data with Redis caching

## Key Insights

- Follow existing router/service/schema pattern
- Use trading-hours-aware cache (1hr during trading, 24hr off-hours)
- Support filtering by exchange, limit, and period
- Include metadata (updated_at, total count)

## Requirements

### Functional
- `GET /api/v1/stocks/top-performers` endpoint
- Query params: limit (default 50), exchange (optional), year, quarter
- Return ranked list with all financial metrics
- Include last update timestamp

### Non-Functional
- Response time <100ms (cached)
- Redis cache with trading-hours-aware TTL

## Architecture

```
GET /api/v1/stocks/top-performers
         │
         ├── Check Redis cache
         │       ↓ (miss)
         ├── Query PostgreSQL top_performers table
         │       ↓
         ├── Transform to response schema
         │       ↓
         └── Cache & return
```

## Related Code Files

### Create
- `apps/api/src/stocks/analytics/router.py` (new router for analytics domain)
- `apps/api/src/stocks/analytics/service.py` (new service)
- `apps/api/src/stocks/schemas/analytics.py` (new schemas)

### Modify
- `apps/api/src/stocks/router.py` (include analytics router)

## Implementation Steps

### Step 1: Create Pydantic Schemas

Create `apps/api/src/stocks/schemas/analytics.py`:

```python
"""Analytics domain schemas."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class TopPerformerItem(BaseModel):
    """Single top performer entry."""
    rank: int = Field(..., description="Ranking position")
    symbol: str = Field(..., description="Stock ticker")
    company_name: Optional[str] = Field(None, description="Company name")
    exchange: Optional[str] = Field(None, description="Exchange (HOSE/HNX)")
    net_profit: Optional[int] = Field(None, description="Net profit in VND")
    revenue: Optional[int] = Field(None, description="Revenue in VND")
    profit_margin: Optional[float] = Field(None, description="Profit margin %")
    eps: Optional[float] = Field(None, description="Earnings per share")
    year: int = Field(..., description="Fiscal year")
    quarter: int = Field(..., description="Fiscal quarter (1-4)")

    model_config = {"from_attributes": True}


class TopPerformersResponse(BaseModel):
    """Top performers list response."""
    period: str = Field(..., description="Period label e.g. 'Q4-2024'")
    updated_at: Optional[datetime] = Field(None, description="Last data update")
    total: int = Field(..., description="Total records available")
    data: List[TopPerformerItem] = Field(..., description="Top performers list")
```

### Step 2: Create Analytics Service

Create `apps/api/src/stocks/analytics/service.py`:

```python
"""Analytics domain service."""

import logging
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.stocks.models import TopPerformer
from src.stocks.schemas.analytics import TopPerformerItem, TopPerformersResponse

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for analytics endpoints."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_top_performers(
        self,
        limit: int = 50,
        exchange: Optional[str] = None,
        year: Optional[int] = None,
        quarter: Optional[int] = None,
    ) -> TopPerformersResponse:
        """Get top performers ranked by net profit."""

        # Build query
        query = select(TopPerformer)

        # If no period specified, get latest available
        if year is None or quarter is None:
            latest = await self.db.execute(
                select(TopPerformer.year, TopPerformer.quarter)
                .order_by(desc(TopPerformer.year), desc(TopPerformer.quarter))
                .limit(1)
            )
            row = latest.first()
            if row:
                year, quarter = row.year, row.quarter
            else:
                # No data yet
                return TopPerformersResponse(
                    period="N/A",
                    updated_at=None,
                    total=0,
                    data=[]
                )

        query = query.where(TopPerformer.year == year, TopPerformer.quarter == quarter)

        if exchange:
            query = query.where(TopPerformer.exchange == exchange.upper())

        query = query.order_by(TopPerformer.rank.asc()).limit(limit)

        result = await self.db.execute(query)
        rows = result.scalars().all()

        # Get total count
        count_query = select(func.count()).select_from(TopPerformer).where(
            TopPerformer.year == year,
            TopPerformer.quarter == quarter
        )
        if exchange:
            count_query = count_query.where(TopPerformer.exchange == exchange.upper())
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # Get latest update time
        updated_at = None
        if rows:
            updated_at = max(r.updated_at for r in rows if r.updated_at)

        return TopPerformersResponse(
            period=f"Q{quarter}-{year}",
            updated_at=updated_at,
            total=total,
            data=[TopPerformerItem.model_validate(r) for r in rows]
        )
```

### Step 3: Create Analytics Router

Create `apps/api/src/stocks/analytics/router.py`:

```python
"""Analytics domain router."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.core.cache import TradingHoursCache
from src.core.dependencies import get_async_db
from src.stocks.analytics.service import AnalyticsService
from src.stocks.schemas.analytics import TopPerformersResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Cache instance
top_performers_cache = TradingHoursCache(
    prefix="top_performers",
    trading_ttl=3600,      # 1 hour during trading
    off_hours_ttl=86400,   # 24 hours off-hours
)


@router.get("/top-performers", response_model=TopPerformersResponse)
async def get_top_performers(
    limit: int = Query(50, ge=1, le=100, description="Number of results"),
    exchange: Optional[str] = Query(None, description="Filter by exchange: HOSE or HNX"),
    year: Optional[int] = Query(None, ge=2020, le=2030, description="Fiscal year"),
    quarter: Optional[int] = Query(None, ge=1, le=4, description="Fiscal quarter"),
    db=Depends(get_async_db),
) -> TopPerformersResponse:
    """Get top performing companies by net profit.

    Returns ranked list of companies sorted by quarterly net profit.
    Data is updated weekly via scheduled batch job.
    """
    # Build cache key
    cache_key = f"{limit}:{exchange or 'all'}:{year or 'latest'}:{quarter or 'latest'}"

    # Try cache
    cached = await top_performers_cache.get(cache_key)
    if cached:
        return TopPerformersResponse(**cached)

    # Query database
    service = AnalyticsService(db)
    result = await service.get_top_performers(
        limit=limit,
        exchange=exchange,
        year=year,
        quarter=quarter,
    )

    # Cache result
    await top_performers_cache.set(cache_key, result.model_dump(mode='json'))

    return result
```

### Step 4: Create __init__.py

Create `apps/api/src/stocks/analytics/__init__.py`:

```python
"""Analytics domain module."""
from .router import router as analytics_router
from .service import AnalyticsService

__all__ = ["analytics_router", "AnalyticsService"]
```

### Step 5: Include Router

In `apps/api/src/stocks/router.py`, add:

```python
from src.stocks.analytics import analytics_router

# In router setup:
router.include_router(analytics_router)
```

## Todo List

- [ ] Create schemas/analytics.py with Pydantic models
- [ ] Create analytics/ directory
- [ ] Create analytics/service.py
- [ ] Create analytics/router.py
- [ ] Create analytics/__init__.py
- [ ] Include analytics router in main stocks router
- [ ] Test endpoint with curl/httpie
- [ ] Verify Redis caching works

## Success Criteria

- [ ] GET /api/v1/stocks/analytics/top-performers returns data
- [ ] Query params filter correctly (exchange, limit, period)
- [ ] Response includes period, updated_at, total, data[]
- [ ] Second request hits cache (faster response)
- [ ] OpenAPI docs show endpoint

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| No data in DB | Low | Return empty response with clear message |
| Cache invalidation issues | Low | Short TTL, manual cache clear endpoint if needed |

## Security Considerations

- Input validation via Query() constraints
- No raw SQL - use SQLAlchemy ORM
- Rate limiting via existing middleware

## Next Steps

- Proceed to Phase 4: Frontend UI
