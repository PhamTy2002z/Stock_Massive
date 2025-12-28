"""Router for market overview endpoint."""

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from src.core.cache import TradingHoursCache
from src.core.ratelimit import standard_rate_limit
from .schemas import MarketOverviewResponse
from .service import MarketOverviewService

router = APIRouter(prefix="/market-overview", tags=["overview"])

# Cache: 10s during trading hours, 5min off-hours
overview_cache = TradingHoursCache(
    key_prefix="market_overview:",
    ttl_trading=10,
    ttl_off_hours=300,
)


@router.get("", response_model=MarketOverviewResponse)
async def get_market_overview(
    response: Response,
    _: None = Depends(standard_rate_limit),
) -> MarketOverviewResponse:
    """Get aggregated market overview data.

    Returns market breadth, top gainers/losers, foreign flow, and top volume.
    Data is cached for 10s during trading hours, 5min otherwise.
    """
    cache_key = "aggregate"

    # Try cache first
    cached = overview_cache.get(cache_key)
    if cached:
        return MarketOverviewResponse(**cached)

    # Fetch fresh data
    service = MarketOverviewService()
    data = await service.get_market_overview()

    # Cache result
    overview_cache.set(cache_key, data.model_dump(mode="json"))

    return data
