"""Company domain router for company-related endpoints.

Frozen: every endpoint here calls vnstock inside the user's request. Nothing in
`providers/contracts.py` carries a company profile, its officers, its
shareholders or its insider deals — `ReferenceSnapshot` holds share counts and
foreign room and nothing else — so serving these from the store would mean a
fifth `Capability` and an `Adapter` behind it. That was weighed in #27 and
declined: the data changes on corporate actions rather than per session, so it
costs little quota, and the pipeline's promise is about the figures a reader
refreshes daily. Reopen the decision if this data ever needs a data age.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.core.ratelimit import standard_rate_limit, heavy_rate_limit
from src.core.cache import TradingHoursCache
from src.core.vnstock_client import VnstockUnavailable
from .service import get_company_service
from ..schemas.company import (
    CompanyOverview,
    StockDetail,
    ShareholdersResponse,
    OfficersResponse,
    InsiderDealsResponse,
    NewsResponse,
    RatioSummaryResponse,
)
from ..shared import validate_symbol

# Response caches prevent interactive requests from multiplying provider calls.
company_overview_cache = TradingHoursCache(
    key_prefix="stock:company_overview:",
    ttl_trading=3600,
    ttl_off_hours=86400,
    stale_ttl=7 * 86400,
)
stock_detail_cache = TradingHoursCache(
    key_prefix="stock:detail:",
    ttl_trading=60,
    ttl_off_hours=3600,
    stale_ttl=86400,
)
shareholders_cache = TradingHoursCache(
    key_prefix="stock:shareholders:",
    ttl_trading=21600,
    ttl_off_hours=86400,
    stale_ttl=7 * 86400,
)
officers_cache = TradingHoursCache(
    key_prefix="stock:officers:",
    ttl_trading=21600,
    ttl_off_hours=86400,
    stale_ttl=7 * 86400,
)
insider_deals_cache = TradingHoursCache(
    key_prefix="stock:insider_deals:",
    ttl_trading=3600,
    ttl_off_hours=21600,
    stale_ttl=7 * 86400,
)
company_news_cache = TradingHoursCache(
    key_prefix="stock:company_news:",
    ttl_trading=900,
    ttl_off_hours=3600,
    stale_ttl=7 * 86400,
)
ratio_summary_cache = TradingHoursCache(
    key_prefix="stock:ratio_summary:",
    ttl_trading=3600,
    ttl_off_hours=86400,
    stale_ttl=7 * 86400,
)
router = APIRouter()


def _cached_model(cache, key: str, model, loader):
    payload = cache.get_or_load(
        key,
        lambda: loader().model_dump(mode="json"),
        suppress_failure=lambda exc: isinstance(exc, VnstockUnavailable),
    )
    return model.model_validate(payload)


@router.get("/{symbol}/company", response_model=CompanyOverview, dependencies=[Depends(standard_rate_limit)])
def get_company_overview(symbol: str) -> CompanyOverview:
    """Get company overview information."""
    symbol = validate_symbol(symbol)
    service = get_company_service()
    return _cached_model(
        company_overview_cache,
        symbol.upper(),
        CompanyOverview,
        lambda: service.get_company_overview(symbol),
    )


@router.get("/{symbol}/detail", response_model=StockDetail, dependencies=[Depends(standard_rate_limit)])
def get_stock_detail(symbol: str) -> StockDetail:
    """Get comprehensive stock detail data (composite endpoint)."""
    symbol = validate_symbol(symbol)
    service = get_company_service()
    return _cached_model(
        stock_detail_cache,
        symbol.upper(),
        StockDetail,
        lambda: service.get_stock_detail(symbol),
    )


@router.get("/{symbol}/shareholders", response_model=ShareholdersResponse, dependencies=[Depends(standard_rate_limit)])
def get_shareholders(symbol: str) -> ShareholdersResponse:
    """Get major shareholders for a stock."""
    symbol = validate_symbol(symbol)
    service = get_company_service()
    return _cached_model(
        shareholders_cache,
        symbol.upper(),
        ShareholdersResponse,
        lambda: service.get_shareholders(symbol),
    )


@router.get("/{symbol}/officers", response_model=OfficersResponse, dependencies=[Depends(standard_rate_limit)])
def get_officers(
    symbol: str,
    filter_by: str = Query("working", description="Filter: working, resigned, all"),
) -> OfficersResponse:
    """Get company officers/management for a stock."""
    if filter_by not in ("working", "resigned", "all"):
        raise HTTPException(status_code=400, detail="Invalid filter_by. Use 'working', 'resigned', or 'all'")

    symbol = validate_symbol(symbol)
    service = get_company_service()
    return _cached_model(
        officers_cache,
        f"{symbol.upper()}:{filter_by}",
        OfficersResponse,
        lambda: service.get_officers(symbol, filter_by),
    )


@router.get("/{symbol}/news", response_model=NewsResponse, dependencies=[Depends(standard_rate_limit)])
def get_company_news(symbol: str) -> NewsResponse:
    """Get company news and announcements."""
    symbol = validate_symbol(symbol)
    service = get_company_service()
    return _cached_model(
        company_news_cache,
        symbol.upper(),
        NewsResponse,
        lambda: service.get_company_news(symbol),
    )


@router.get("/{symbol}/insider-deals", response_model=InsiderDealsResponse, dependencies=[Depends(standard_rate_limit)])
def get_insider_deals(symbol: str) -> InsiderDealsResponse:
    """Get insider trading deals for a stock."""
    symbol = validate_symbol(symbol)
    service = get_company_service()
    return _cached_model(
        insider_deals_cache,
        symbol.upper(),
        InsiderDealsResponse,
        lambda: service.get_insider_deals(symbol),
    )


# === Advanced Deep Dive endpoints ===


@router.get("/{symbol}/ratio-summary", response_model=RatioSummaryResponse, dependencies=[Depends(heavy_rate_limit)])
def get_ratio_summary(symbol: str) -> RatioSummaryResponse:
    """Get financial ratios summary for advanced tab.

    Returns key financial ratios (PE, PB, ROE, ROA, etc.) for a stock.
    """
    symbol = validate_symbol(symbol)
    cache_key = symbol

    service = get_company_service()
    return _cached_model(
        ratio_summary_cache,
        cache_key,
        RatioSummaryResponse,
        lambda: service.get_ratio_summary(symbol),
    )
