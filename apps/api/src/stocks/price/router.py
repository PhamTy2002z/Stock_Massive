"""Price domain router for price-related endpoints."""

import logging
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.ratelimit import standard_rate_limit, heavy_rate_limit
from src.stocks.intraday_collector import IntradayCollector
from src.core.cache import TradingHoursCache
from src.stocks.price.cache import volume_anomaly_cache
from ..service import get_stock_service
from .service import MARKET_INDICES

# Cache instances for endpoints
market_indices_cache = TradingHoursCache(
    key_prefix="stock:indices:",
    ttl_trading=30,
    ttl_off_hours=3600,
)
price_board_cache = TradingHoursCache(
    key_prefix="stock:price_board:",
    ttl_trading=15,
    ttl_off_hours=3600,
)
price_depth_cache = TradingHoursCache(
    key_prefix="stock:price_depth:",
    ttl_trading=30,
    ttl_off_hours=300,
)
from ..schemas.price import (
    StockPrice,
    IntradayTick,
    PriceBoardItem,
    MarketIndexItem,
    IntradayCollectionResult,
    VolumeAnalysisResponse,
    VolumeAnomalyResponse,
    PriceDepthResponse,
)
from ..shared import StockServiceError
from src.auth.dependencies import require_admin

router = APIRouter()


@router.get("/{symbol}/history", response_model=List[StockPrice], dependencies=[Depends(standard_rate_limit)])
def get_history(
    symbol: str,
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: date = Query(default_factory=date.today, description="End date (YYYY-MM-DD)"),
    interval: str = Query("1D", description="Interval: 1D, 1W, 1M"),
) -> List[StockPrice]:
    """Get historical OHLCV data for a stock."""
    if interval not in ("1D", "1W", "1M"):
        raise HTTPException(status_code=400, detail="Invalid interval. Use 1D, 1W, or 1M")

    if start > end:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    try:
        service = get_stock_service()
        return service.get_history(symbol, start, end, interval)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/intraday", response_model=List[IntradayTick], dependencies=[Depends(standard_rate_limit)])
def get_intraday(
    symbol: str,
    page_size: int = Query(10000, ge=100, le=50000, description="Number of ticks to fetch"),
) -> List[IntradayTick]:
    """Get intraday tick data for a stock."""
    try:
        service = get_stock_service()
        return service.get_intraday(symbol, page_size)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/market-indices", response_model=List[MarketIndexItem], dependencies=[Depends(standard_rate_limit)])
def get_market_indices() -> List[MarketIndexItem]:
    """Get market indices data (VN-INDEX, VN30, HNX-INDEX, UPCOM-INDEX)."""
    cache_key = "all"

    # Check cache first
    cached = market_indices_cache.get(cache_key)
    if cached is not None:
        return [MarketIndexItem(**item) for item in cached]

    # Cache miss - fetch from service
    try:
        service = get_stock_service()
        result = service.get_market_indices()

        # Only cache a complete board. A partial fetch (one index timing out)
        # would otherwise be pinned for the whole TTL and read as "the market
        # has three indices".
        if len(result) == len(MARKET_INDICES):
            market_indices_cache.set(cache_key, [item.model_dump() for item in result])

        return result
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/price-board", response_model=List[PriceBoardItem], dependencies=[Depends(standard_rate_limit)])
def get_price_board(
    symbols: str = Query(..., description="Comma-separated list of symbols (e.g., VCB,ACB,TCB)"),
) -> List[PriceBoardItem]:
    """Get real-time price board for multiple stocks."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    if not symbol_list:
        raise HTTPException(status_code=400, detail="At least one symbol is required")

    if len(symbol_list) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols allowed")

    # Use sorted symbols as cache key for consistency
    cache_key = ",".join(sorted(symbol_list))

    # Check cache first
    cached = price_board_cache.get(cache_key)
    if cached is not None:
        return [PriceBoardItem(**item) for item in cached]

    # Cache miss - fetch from service
    try:
        service = get_stock_service()
        result = service.get_price_board(symbol_list)

        # Never cache an empty board — an upstream hiccup would otherwise be
        # served as "these symbols have no prices" for the whole TTL.
        if result:
            price_board_cache.set(cache_key, [item.model_dump() for item in result])

        return result
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/intraday/collect", response_model=IntradayCollectionResult, dependencies=[Depends(heavy_rate_limit), Depends(require_admin)])
async def collect_intraday_data(
    symbols: list[str] = Query(
        default=["VCB", "FPT", "VNM"],
        description="List of stock symbols to collect",
    ),
    db: AsyncSession = Depends(get_db),
) -> IntradayCollectionResult:
    """Manually trigger intraday data collection."""
    if len(symbols) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols allowed")

    collector = IntradayCollector(db)
    result = await collector.collect_and_save(symbols)
    return IntradayCollectionResult(**result)


@router.get("/{symbol}/volume-analysis", response_model=VolumeAnalysisResponse, dependencies=[Depends(standard_rate_limit)])
async def get_volume_analysis(
    symbol: str,
    days: int = Query(default=10, ge=1, le=30, description="Number of days to analyze"),
    top_n: int = Query(default=10, ge=1, le=72, description="Number of top periods to return"),
    db: AsyncSession = Depends(get_db),
) -> VolumeAnalysisResponse:
    """Analyze intraday volume patterns for a stock."""
    collector = IntradayCollector(db)
    result = await collector.analyze_volume(symbol, days, top_n)

    if not result["peak_periods"]:
        raise HTTPException(
            status_code=404,
            detail=f"No intraday data found for {symbol.upper()} in last {days} days",
        )

    return VolumeAnalysisResponse(**result)


@router.get("/{symbol}/volume-anomalies", response_model=VolumeAnomalyResponse, dependencies=[Depends(heavy_rate_limit)])
async def get_volume_anomalies(
    symbol: str,
    days: int = Query(default=20, ge=5, le=60, description="Baseline period in days"),
    db: AsyncSession = Depends(get_db),
) -> VolumeAnomalyResponse:
    """Detect volume anomalies for all 5-minute time slots.

    Compares latest day's volume against N-day average baseline.
    Returns 72 time slots (09:00-14:55) with anomaly flags.

    Auto-collects intraday data if stale or missing.
    """
    symbol = symbol.upper()
    cache_key = f"{symbol}:{days}"
    logger = logging.getLogger(__name__)

    # Check cache first
    cached = volume_anomaly_cache.get(cache_key)
    if cached is not None:
        return VolumeAnomalyResponse(**cached)

    # Cache miss - collect fresh data
    collector = IntradayCollector(db)

    try:
        # Fetch from vnstock and save to DB
        bars = await collector.collect_symbol(symbol)
        if bars:
            await collector.save_bars(bars)
            await db.commit()
    except Exception as e:
        # Rollback failed transaction to allow subsequent queries
        await db.rollback()
        logger.warning(f"Failed to collect intraday data for {symbol}: {e}")

    # Compute anomalies from DB (includes any newly collected data)
    result = await collector.detect_volume_anomalies(symbol, days)

    # Cache the result
    volume_anomaly_cache.set(cache_key, result)

    return VolumeAnomalyResponse(**result)


@router.get("/{symbol}/price-depth", response_model=PriceDepthResponse, dependencies=[Depends(heavy_rate_limit)])
def get_price_depth(symbol: str) -> PriceDepthResponse:
    """Get price depth (bid/ask levels) for a stock.

    Returns 3 levels of bid/ask prices and volumes with spread calculation.
    Uses heavy rate limit due to real-time data requirements.
    """
    cache_key = symbol.upper()

    # Check cache first
    cached = price_depth_cache.get(cache_key)
    if cached is not None:
        return PriceDepthResponse(**cached)

    try:
        service = get_stock_service()
        result = service.get_price_depth(symbol)

        # Cache the result
        price_depth_cache.set(cache_key, result.model_dump())

        return result
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
