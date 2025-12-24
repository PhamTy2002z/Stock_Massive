"""Trading domain router for money flow endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.core.ratelimit import standard_rate_limit
from src.core.cache import TradingHoursCache
from ..shared import StockServiceError
from .service import get_trading_service
from .schemas import (
    ForeignTradingResponse,
    PropTradingResponse,
    OrderStatsResponse,
)

router = APIRouter()

# Cache instances for trading data
foreign_cache = TradingHoursCache(
    key_prefix="stock:foreign:",
    ttl_trading=900,  # 15 min during trading
    ttl_off_hours=3600,  # 1 hour off-hours
)

prop_cache = TradingHoursCache(
    key_prefix="stock:prop:",
    ttl_trading=900,
    ttl_off_hours=3600,
)

order_stats_cache = TradingHoursCache(
    key_prefix="stock:orderstats:",
    ttl_trading=900,
    ttl_off_hours=3600,
)


@router.get(
    "/{symbol}/foreign-trading",
    response_model=ForeignTradingResponse,
    dependencies=[Depends(standard_rate_limit)],
)
async def get_foreign_trading(
    symbol: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to fetch"),
) -> ForeignTradingResponse:
    """Get foreign investor trading data for last N days.

    Returns daily net volume, buy/sell data, remaining room, and ownership percentage.
    """
    cache_key = f"{symbol}:{days}"
    cached = foreign_cache.get(cache_key)
    if cached:
        return ForeignTradingResponse(**cached)

    try:
        service = get_trading_service()
        result = service.get_foreign_trading(symbol, days)
        foreign_cache.set(cache_key, result.model_dump())
        return result
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get(
    "/{symbol}/prop-trading",
    response_model=PropTradingResponse,
    dependencies=[Depends(standard_rate_limit)],
)
async def get_prop_trading(
    symbol: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to fetch"),
) -> PropTradingResponse:
    """Get proprietary trading (self-trading by securities firms) data.

    Returns daily net volume and value for proprietary trades.
    """
    cache_key = f"{symbol}:{days}"
    cached = prop_cache.get(cache_key)
    if cached:
        return PropTradingResponse(**cached)

    try:
        service = get_trading_service()
        result = service.get_prop_trading(symbol, days)
        prop_cache.set(cache_key, result.model_dump())
        return result
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get(
    "/{symbol}/order-stats",
    response_model=OrderStatsResponse,
    dependencies=[Depends(standard_rate_limit)],
)
async def get_order_stats(
    symbol: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to fetch"),
) -> OrderStatsResponse:
    """Get order flow statistics for last N days.

    Returns daily buy/sell order counts, volumes, and average order sizes.
    """
    cache_key = f"{symbol}:{days}"
    cached = order_stats_cache.get(cache_key)
    if cached:
        return OrderStatsResponse(**cached)

    try:
        service = get_trading_service()
        result = service.get_order_stats(symbol, days)
        order_stats_cache.set(cache_key, result.model_dump())
        return result
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
