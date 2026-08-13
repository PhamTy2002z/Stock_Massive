"""Analytics domain router."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.cache import TradingHoursCache
from src.core.database import get_db
from src.core.ratelimit import heavy_rate_limit, standard_rate_limit
from src.core.vnstock_client import VnstockUnavailable
from src.stocks.analytics.service import (
    AnalyticsService,
    build_volume_spikes_cache_key,
    volume_spikes_cache,
)
from src.stocks.schemas.analytics import (
    VolumeSpikeResponse,
    VolumeSpikeMetadata,
)
from src.stocks.schemas.common import MessageResponse
from src.stocks.schemas.financial import SectorPeersResponse
from src.stocks.financial import get_financial_service
from src.stocks.shared import validate_symbol
from src.stocks.analytics.sector_historical_router import router as sector_historical_router
from src.auth.dependencies import require_admin

router = APIRouter(prefix="/analytics", tags=["analytics"])

sector_peers_response_cache = TradingHoursCache(
    key_prefix="stock:sector_peers_response:",
    ttl_trading=4 * 3600,
    ttl_off_hours=86400,
    stale_ttl=7 * 86400,
)

# Include sector historical router
router.include_router(sector_historical_router, tags=["sector-historical"])


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
    cache_key = build_volume_spikes_cache_key(
        target_date, min_ratio, exchange, include_upcom, limit, top_profitable_only
    )

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


@router.delete(
    "/volume-spikes/cache",
    response_model=MessageResponse,
    response_model_exclude_none=True,
    dependencies=[Depends(heavy_rate_limit), Depends(require_admin)],
)
async def clear_volume_spikes_cache() -> MessageResponse:
    """Clear volume spikes cache. Use when data seems stale or after updates."""
    deleted = volume_spikes_cache.clear_prefix()
    return MessageResponse(message=f"Cleared {deleted} cache entries")


# ==================== Sector Peers Endpoint ====================


@router.get(
    "/sector-peers",
    response_model=SectorPeersResponse,
    dependencies=[Depends(standard_rate_limit)],
)
def get_sector_peers(
    symbol: str = Query(..., description="Target stock symbol"),
    limit: int = Query(10, ge=5, le=20, description="Number of peers (5-20)"),
) -> SectorPeersResponse:
    """Get peer companies in the same ICB sector with median and premium/discount.

    Returns top N companies in the same ICB Level 3 sector,
    sorted by market capitalization, with key financial metrics
    and premium/discount vs sector median.
    """
    symbol = validate_symbol(symbol)
    service = get_financial_service()
    cache_key = f"{symbol}:{limit}"
    payload = sector_peers_response_cache.get_or_load(
        cache_key,
        lambda: service.get_sector_peers(symbol, limit).model_dump(mode="json"),
        suppress_failure=lambda exc: isinstance(exc, VnstockUnavailable),
    )
    return SectorPeersResponse.model_validate(payload)
