"""Price domain router for price-related endpoints.

Frozen, and still needed: everything here calls a provider inside the request.
`/{symbol}/history` keeps that path for the two things the store cannot answer —
granularity finer than a session, and symbols outside the Universe. Sessions for
a watched symbol are served by `/{symbol}/series/market`, which reads the store
and carries a data age; a caller wanting the pipeline's promise asks that one.

`/intraday`, `/volume-analysis` and `/volume-anomalies` describe flow within a
session, which `docs/adr/0001` and #6 put outside the pipeline. The market-wide
endpoints are frozen by #6 itself.
"""

import logging
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.ratelimit import standard_rate_limit, heavy_rate_limit
from src.stocks.intraday_collector import IntradayCollector
from src.core.cache import TradingHoursCache
from src.core.vnstock_client import VnstockUnavailable
from src.stocks.price.cache import volume_anomaly_cache
from .service import get_price_service, HISTORY_INTERVALS, MARKET_INDICES
from ..schemas.price import (
    StockPrice,
    IntradayTick,
    PriceBoardItem,
    MarketIndexItem,
    IntradayCollectionResult,
    VolumeAnalysisResponse,
    VolumeAnomalyResponse,
)
from ..shared import StockServiceError
from src.auth.dependencies import require_admin

# Cache instances for endpoints
#
# **`stale_ttl` is what keeps these two endpoints from eating the account.**
# They are the only ones the browser polls — the board every 15 seconds, the
# indices every 30 — and a cache that is only written on success has nothing to
# serve the moment upstream refuses. Every poll then goes to the provider, one
# market-indices request costs four `Quote.history` calls, and ~30 requests a
# minute is ~120 calls against an allowance of 60. The refusal that started it
# is then held open by the traffic reacting to it, and the cache never refills.
# Measured on 2026-08-17: 157 `/market-indices` requests in five minutes, every
# one of them a miss, and a `/price-board` that answered 503 for seven minutes
# straight.
#
# Fifteen minutes rather than the days the slow-moving endpoints allow
# themselves (`company/router.py`): a company profile from last Tuesday is
# still true, and an index level from last Tuesday is a lie on a trading
# screen. Long enough to ride out a provider blip and a spent minute of
# allowance, short enough that what it serves is still about today.
STALE_TTL_SECONDS = 15 * 60

market_indices_cache = TradingHoursCache(
    key_prefix="stock:indices:",
    ttl_trading=30,
    ttl_off_hours=3600,
    stale_ttl=STALE_TTL_SECONDS,
)
price_board_cache = TradingHoursCache(
    key_prefix="stock:price_board:",
    ttl_trading=15,
    ttl_off_hours=3600,
    stale_ttl=STALE_TTL_SECONDS,
)


class PartialIndexBoard(Exception):
    """The provider answered for some indices and not others.

    Raised so the loader never writes a short board into the cache, where it
    would be pinned for the whole TTL and read as "the market has three
    indices". It carries the partial board because a caller with nothing better
    still shows it — which is what this endpoint did before there was anything
    better.
    """

    def __init__(self, board: List[MarketIndexItem]) -> None:
        super().__init__(f"{len(board)} of {len(MARKET_INDICES)} indices answered")
        self.board = board


class EmptyPriceBoard(Exception):
    """The provider answered with no rows at all.

    Kept out of the cache for the same reason as a short index board: pinned
    for a TTL it reads as "these symbols have no prices", which is a different
    statement from "the provider did not answer".
    """
router = APIRouter()


@router.get("/{symbol}/history", response_model=List[StockPrice], dependencies=[Depends(standard_rate_limit)])
def get_history(
    symbol: str,
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: date = Query(default_factory=date.today, description="End date (YYYY-MM-DD)"),
    interval: str = Query("1D", description="Interval: 1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M"),
) -> List[StockPrice]:
    """Get historical OHLCV data for a stock."""
    if interval not in HISTORY_INTERVALS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interval. Use one of: {', '.join(HISTORY_INTERVALS)}",
        )

    if start > end:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    service = get_price_service()
    return service.get_history(symbol, start, end, interval)


@router.get("/{symbol}/intraday", response_model=List[IntradayTick], dependencies=[Depends(standard_rate_limit)])
def get_intraday(
    symbol: str,
    page_size: int = Query(10000, ge=100, le=50000, description="Number of ticks to fetch"),
) -> List[IntradayTick]:
    """Get intraday tick data for a stock."""
    service = get_price_service()
    return service.get_intraday(symbol, page_size)


@router.get("/market-indices", response_model=List[MarketIndexItem], dependencies=[Depends(standard_rate_limit)])
def get_market_indices() -> List[MarketIndexItem]:
    """Get market indices data (VN-INDEX, VN30, HNX-INDEX, UPCOM-INDEX)."""
    cache_key = "all"

    def load() -> List[dict]:
        board = get_price_service().get_market_indices()
        # Only a complete board is cacheable, for the reason PartialIndexBoard
        # gives. Raising rather than returning is what keeps it out of the
        # cache while still letting a stale complete board answer instead —
        # four indices from a minute ago beat three from now.
        if len(board) != len(MARKET_INDICES):
            raise PartialIndexBoard(board)
        return [item.model_dump() for item in board]

    try:
        payload = market_indices_cache.get_or_load(
            cache_key,
            load,
            # The provider refusing is worth remembering for a few seconds. It
            # is the whole failure mode here: without it every poll re-asks an
            # allowance that is already spent, and keeps it spent.
            suppress_failure=lambda exc: isinstance(exc, VnstockUnavailable),
        )
    except PartialIndexBoard as partial:
        # No complete board anywhere, fresh or stale. Show what there is, as
        # this endpoint always has.
        return partial.board

    return [MarketIndexItem(**item) for item in payload]


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

    def load() -> List[dict]:
        board = get_price_service().get_price_board(symbol_list)
        # Never cache an empty board — an upstream hiccup would otherwise be
        # served as "these symbols have no prices" for the whole TTL. Raising
        # keeps it uncached and lets a stale board answer in its place.
        if not board:
            raise EmptyPriceBoard()
        return [item.model_dump() for item in board]

    try:
        payload = price_board_cache.get_or_load(
            cache_key,
            load,
            suppress_failure=lambda exc: isinstance(exc, VnstockUnavailable),
        )
    except EmptyPriceBoard:
        # Nothing fresh and nothing stale. An empty board is the honest answer.
        return []

    return [PriceBoardItem(**item) for item in payload]


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
