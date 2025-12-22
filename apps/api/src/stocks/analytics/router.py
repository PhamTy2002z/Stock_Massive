"""Analytics domain router."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.cache import TradingHoursCache
from src.core.database import get_db
from src.core.ratelimit import heavy_rate_limit, standard_rate_limit
from src.stocks.analytics.service import AnalyticsService
from src.stocks.schemas.analytics import (
    TopPerformersCollectionResult,
    TopPerformersResponse,
    VolumeSpikeResponse,
    VolumeSpikeMetadata,
)
from src.stocks.top_performers_collector import TopPerformersCollector

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Cache instance with trading-hours-aware TTL
top_performers_cache = TradingHoursCache(
    key_prefix="stock:top_performers:",
    ttl_trading=3600,      # 1 hour during trading
    ttl_off_hours=86400,   # 24 hours off-hours
)

# Volume spikes cache: 5min trading, 1hr off-hours
volume_spikes_cache = TradingHoursCache(
    key_prefix="stock:volume_spikes:",
    ttl_trading=300,       # 5 min during trading
    ttl_off_hours=3600,    # 1 hour off-hours
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


@router.post(
    "/top-performers/collect",
    response_model=TopPerformersCollectionResult,
    dependencies=[Depends(heavy_rate_limit)],
)
async def collect_top_performers(
    db: AsyncSession = Depends(get_db),
) -> TopPerformersCollectionResult:
    """Manually trigger top performers data collection.

    Fetches quarterly financials for all HOSE+HNX symbols and stores
    ranked data. This is a long-running operation (10-30 minutes).

    Note: Data is also collected automatically every Sunday at 02:00 ICT.
    """
    collector = TopPerformersCollector(db)
    result = await collector.collect()

    # Clear cache after fresh collection
    top_performers_cache.clear_prefix()

    return TopPerformersCollectionResult(**result)


@router.get(
    "/volume-spikes",
    response_model=VolumeSpikeResponse,
    dependencies=[Depends(standard_rate_limit)],
)
async def get_volume_spikes(
    target_date: Optional[date] = Query(
        None, description="Target date (default: latest available)"
    ),
    min_ratio: float = Query(
        1.5, ge=1.0, le=5.0, description="Minimum spike ratio threshold"
    ),
    exchange: Optional[str] = Query(
        None, pattern="^(HOSE|HNX)$", description="Filter by exchange: HOSE or HNX"
    ),
    include_upcom: bool = Query(False, description="Include UPCOM stocks"),
    limit: int = Query(50, ge=10, le=200, description="Max results per industry"),
    db: AsyncSession = Depends(get_db),
) -> VolumeSpikeResponse:
    """Detect volume spikes grouped by ICB industry.

    Returns stocks with volume exceeding N-day average by specified ratio,
    grouped by ICB Level 2 industry classification.

    - **target_date**: Trading date to analyze (default: latest)
    - **min_ratio**: Minimum volume spike ratio (1.5 = 150% of average)
    - **exchange**: Filter HOSE or HNX only
    - **include_upcom**: Include UPCOM exchange (default: excluded)
    - **limit**: Maximum stocks per industry group
    """
    # Build cache key
    date_str = target_date.isoformat() if target_date else "latest"
    cache_key = f"{date_str}:{min_ratio}:{exchange or 'all'}:{include_upcom}:{limit}"

    # Try cache
    cached = volume_spikes_cache.get(cache_key)
    if cached:
        # Update metadata to indicate cache hit
        cached["metadata"]["cache_hit"] = True
        return VolumeSpikeResponse(**cached)

    # Query database
    service = AnalyticsService(db)
    result = await service.get_volume_spikes(
        target_date=target_date,
        min_ratio=min_ratio,
        exchange=exchange,
        include_upcom=include_upcom,
        limit=limit,
    )

    # Cache result
    volume_spikes_cache.set(cache_key, result.model_dump(mode="json"))

    return result
