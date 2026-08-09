"""Router for the supported intraday order-flow endpoint."""

from fastapi import APIRouter, Depends

from src.core.cache import TradingHoursCache
from src.core.ratelimit import standard_rate_limit

from .schemas import IntradayOrderStatsResponse
from .service import get_trading_service

router = APIRouter()

intraday_order_stats_cache = TradingHoursCache(
    key_prefix="stock:intraday_orderstats:",
    ttl_trading=120,
    ttl_off_hours=1800,
)


@router.get(
    "/{symbol}/intraday-order-stats",
    response_model=IntradayOrderStatsResponse,
    dependencies=[Depends(standard_rate_limit)],
)
def get_intraday_order_stats(symbol: str) -> IntradayOrderStatsResponse:
    """Return latest-session buy and sell statistics."""
    cached = intraday_order_stats_cache.get(symbol)
    if cached:
        return IntradayOrderStatsResponse(**cached)

    result = get_trading_service().get_intraday_order_stats(symbol)
    intraday_order_stats_cache.set(symbol, result.model_dump())
    return result
