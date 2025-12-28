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
    FinancialStatementsCollectionResult,
    FinancialStatementsResponse,
    VolumeSpikeResponse,
    VolumeSpikeMetadata,
)
from src.stocks.schemas.financial import SectorPeersResponse
from src.stocks.financial_statements_collector import FinancialStatementsCollector
from src.stocks.service import get_stock_service
from src.stocks.shared import StockServiceError

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Cache instance with trading-hours-aware TTL
financial_statements_cache = TradingHoursCache(
    key_prefix="stock:financial_statements:",
    ttl_trading=3600,      # 1 hour during trading
    ttl_off_hours=86400,   # 24 hours off-hours
)

# Volume spikes cache: 5min trading, 1hr off-hours
volume_spikes_cache = TradingHoursCache(
    key_prefix="stock:volume_spikes:",
    ttl_trading=300,       # 5 min during trading
    ttl_off_hours=3600,    # 1 hour off-hours
)


@router.get("/financial-statements", response_model=FinancialStatementsResponse)
async def get_financial_statements(
    limit: int = Query(50, ge=1, le=100, description="Number of results"),
    exchange: Optional[str] = Query(None, pattern="^(HOSE|HSX|HNX)$", description="Filter by exchange: HOSE (or HSX) or HNX"),
    year: Optional[int] = Query(None, ge=2020, le=2030, description="Fiscal year"),
    quarter: Optional[int] = Query(None, ge=1, le=4, description="Fiscal quarter"),
    db: AsyncSession = Depends(get_db),
) -> FinancialStatementsResponse:
    """Get top performing companies by net profit.

    Returns ranked list of companies sorted by quarterly net profit.
    Data is updated weekly via scheduled batch job.
    """
    # Build cache key
    cache_key = f"{limit}:{exchange or 'all'}:{year or 'latest'}:{quarter or 'latest'}"

    # Try cache
    cached = financial_statements_cache.get(cache_key)
    if cached:
        return FinancialStatementsResponse(**cached)

    # Query database
    service = AnalyticsService(db)
    result = await service.get_financial_statements(
        limit=limit,
        exchange=exchange,
        year=year,
        quarter=quarter,
    )

    # Cache result
    financial_statements_cache.set(cache_key, result.model_dump(mode='json'))

    return result


@router.post(
    "/financial-statements/collect",
    response_model=FinancialStatementsCollectionResult,
    dependencies=[Depends(heavy_rate_limit)],
)
async def collect_financial_statements(
    db: AsyncSession = Depends(get_db),
) -> FinancialStatementsCollectionResult:
    """Manually trigger financial statements data collection.

    Fetches quarterly financials for all HOSE+HNX symbols and stores
    ranked data. This is a long-running operation (10-30 minutes).

    Note: Data is also collected automatically every Sunday at 02:00 ICT.
    """
    collector = FinancialStatementsCollector(db)
    result = await collector.collect()

    # Clear cache after fresh collection
    financial_statements_cache.clear_prefix()

    return FinancialStatementsCollectionResult(**result)


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
    top_profitable_only: bool = Query(
        False, description="Only show Top 50 profitable companies"
    ),
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
    cache_key = f"{date_str}:{min_ratio}:{exchange or 'all'}:{include_upcom}:{limit}:{top_profitable_only}"

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
        top_profitable_only=top_profitable_only,
    )

    # Cache result
    volume_spikes_cache.set(cache_key, result.model_dump(mode="json"))

    return result


@router.delete("/volume-spikes/cache", dependencies=[Depends(heavy_rate_limit)])
async def clear_volume_spikes_cache() -> dict:
    """Clear volume spikes cache. Use when data seems stale or after updates."""
    deleted = volume_spikes_cache.clear_prefix()
    return {"message": f"Cleared {deleted} cache entries"}


# ==================== Sector Peers Endpoint ====================


@router.get(
    "/sector-peers",
    response_model=SectorPeersResponse,
    dependencies=[Depends(standard_rate_limit)],
)
async def get_sector_peers(
    symbol: str = Query(..., description="Target stock symbol"),
    limit: int = Query(10, ge=5, le=20, description="Number of peers (5-20)"),
) -> SectorPeersResponse:
    """Get peer companies in the same ICB sector with median and premium/discount.

    Returns top N companies in the same ICB Level 3 sector,
    sorted by market capitalization, with key financial metrics
    and premium/discount vs sector median.
    """
    try:
        service = get_stock_service()
        # Service handles caching internally via sector_peers_cache
        return service.get_sector_peers(symbol, limit)
    except StockServiceError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail=str(e))
