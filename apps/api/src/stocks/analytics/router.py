"""Analytics domain router.

The volume-spike route that used to live here is gone. It ranked the whole
market out of ``stock_daily_ohlcv`` and grouped the answer by industry, which
ADR-0003 rules out: this system holds a hundred symbols and cannot speak for the
market. Its replacement is ``/api/v1/signals/volume-spikes``, which serves the
bounded scopes and says how much of each it could actually see.
"""

from fastapi import APIRouter, Depends, Query

from src.core.cache import TradingHoursCache
from src.core.ratelimit import standard_rate_limit
from src.core.vnstock_client import VnstockUnavailable
from src.stocks.schemas.financial import SectorPeersResponse
from src.stocks.financial import get_financial_service
from src.stocks.shared import validate_symbol
from src.stocks.analytics.sector_historical_router import router as sector_historical_router

router = APIRouter(prefix="/analytics", tags=["analytics"])

sector_peers_response_cache = TradingHoursCache(
    key_prefix="stock:sector_peers_response:",
    ttl_trading=4 * 3600,
    ttl_off_hours=86400,
    stale_ttl=7 * 86400,
)

# Include sector historical router
router.include_router(sector_historical_router, tags=["sector-historical"])


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
