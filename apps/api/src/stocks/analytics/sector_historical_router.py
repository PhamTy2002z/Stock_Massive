"""Sector historical performance endpoint.

Returns top 5 gaining and top 5 losing sectors over 1W/2W/1M periods.
Data is pre-computed daily at 15:45 ICT and cached for 24h.
"""
import asyncio

from fastapi import APIRouter, Depends, Query

from src.core.ratelimit import heavy_rate_limit, standard_rate_limit
from src.stocks.analytics.sector_historical_service import (
    SectorHistoricalService,
    sector_historical_cache,
)
from src.auth.dependencies import require_admin
from src.stocks.schemas.market import (
    SectorHistoricalItem,
    SectorHistoricalPeriod,
    SectorHistoricalResponse,
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
    dependencies=[Depends(heavy_rate_limit), Depends(require_admin)],
)
async def refresh_sector_historical() -> dict:
    """Manually trigger sector historical calculation.

    For admin/debug use. In production, data is computed via scheduled job.
    """
    service = SectorHistoricalService()
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, service.calculate_all_periods)

    return {"status": "ok", "periods_calculated": list(result.keys())}
