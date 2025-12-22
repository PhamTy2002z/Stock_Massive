"""Analytics domain router."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.cache import TradingHoursCache
from src.core.database import get_db
from src.stocks.analytics.service import AnalyticsService
from src.stocks.schemas.analytics import TopPerformersResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Cache instance with trading-hours-aware TTL
top_performers_cache = TradingHoursCache(
    key_prefix="stock:top_performers:",
    ttl_trading=3600,      # 1 hour during trading
    ttl_off_hours=86400,   # 24 hours off-hours
)


@router.get("/top-performers", response_model=TopPerformersResponse)
async def get_top_performers(
    limit: int = Query(50, ge=1, le=100, description="Number of results"),
    exchange: Optional[str] = Query(None, description="Filter by exchange: HOSE or HNX"),
    year: Optional[int] = Query(None, ge=2020, le=2030, description="Fiscal year"),
    quarter: Optional[int] = Query(None, ge=1, le=4, description="Fiscal quarter"),
    db: AsyncSession = Depends(get_db),
) -> TopPerformersResponse:
    """Get top performing companies by net profit.

    Returns ranked list of companies sorted by quarterly net profit.
    Data is updated weekly via scheduled batch job.
    """
    # Build cache key
    cache_key = f"{limit}:{exchange or 'all'}:{year or 'latest'}:{quarter or 'latest'}"

    # Try cache
    cached = top_performers_cache.get(cache_key)
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
    top_performers_cache.set(cache_key, result.model_dump(mode='json'))

    return result
