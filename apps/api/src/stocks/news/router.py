"""News feed router.

One rebuild of this response costs up to `FEED_SYMBOL_LIMIT` provider calls —
the feed has no upstream equivalent and is assembled symbol by symbol. So the
route is metered by `heavy_rate_limit`, cached far longer than the per-symbol
news it is built from, and keeps a day of stale fallback: serving yesterday's
headlines beats spending twelve calls to answer a refresh, and beats a 503 when
the allowance is already gone.
"""

from fastapi import APIRouter, Depends

from src.core.cache import TradingHoursCache
from src.core.ratelimit import heavy_rate_limit
from src.core.vnstock_client import VnstockUnavailable

from ..schemas.company import NewsFeedResponse
from .service import get_news_feed_service

news_feed_cache = TradingHoursCache(
    key_prefix="stock:news_feed:",
    ttl_trading=900,
    ttl_off_hours=3600,
    stale_ttl=86400,
)

router = APIRouter()


@router.get(
    "/news/feed",
    response_model=NewsFeedResponse,
    dependencies=[Depends(heavy_rate_limit)],
)
def get_news_feed() -> NewsFeedResponse:
    """Get the market-wide news feed aggregated across the VN30 constituents."""
    service = get_news_feed_service()
    payload = news_feed_cache.get_or_load(
        "vn30",
        lambda: service.get_feed().model_dump(mode="json"),
        suppress_failure=lambda exc: isinstance(exc, VnstockUnavailable),
    )
    return NewsFeedResponse.model_validate(payload)
