"""Price domain router for price-related endpoints."""

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.stocks.intraday_collector import IntradayCollector
from ..service import get_stock_service
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

router = APIRouter()


@router.get("/{symbol}/history", response_model=List[StockPrice])
async def get_history(
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


@router.get("/{symbol}/intraday", response_model=List[IntradayTick])
async def get_intraday(
    symbol: str,
    page_size: int = Query(10000, ge=100, le=50000, description="Number of ticks to fetch"),
) -> List[IntradayTick]:
    """Get intraday tick data for a stock."""
    try:
        service = get_stock_service()
        return service.get_intraday(symbol, page_size)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/market-indices", response_model=List[MarketIndexItem])
async def get_market_indices() -> List[MarketIndexItem]:
    """Get market indices data (VN-INDEX, VN30, HNX-INDEX, UPCOM-INDEX)."""
    try:
        service = get_stock_service()
        return service.get_market_indices()
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/price-board", response_model=List[PriceBoardItem])
async def get_price_board(
    symbols: str = Query(..., description="Comma-separated list of symbols (e.g., VCB,ACB,TCB)"),
) -> List[PriceBoardItem]:
    """Get real-time price board for multiple stocks."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    if not symbol_list:
        raise HTTPException(status_code=400, detail="At least one symbol is required")

    if len(symbol_list) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols allowed")

    try:
        service = get_stock_service()
        return service.get_price_board(symbol_list)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/intraday/collect", response_model=IntradayCollectionResult)
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


@router.get("/{symbol}/volume-analysis", response_model=VolumeAnalysisResponse)
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


@router.get("/{symbol}/volume-anomalies", response_model=VolumeAnomalyResponse)
async def get_volume_anomalies(
    symbol: str,
    days: int = Query(default=20, ge=5, le=60, description="Baseline period in days"),
    db: AsyncSession = Depends(get_db),
) -> VolumeAnomalyResponse:
    """Detect volume anomalies for all 5-minute time slots.

    Compares latest day's volume against N-day average baseline.
    Returns 72 time slots (09:00-14:55) with anomaly flags.
    """
    collector = IntradayCollector(db)
    result = await collector.detect_volume_anomalies(symbol, days)

    if not result["time_slots"]:
        raise HTTPException(
            status_code=404,
            detail=f"No intraday data found for {symbol.upper()}",
        )

    return VolumeAnomalyResponse(**result)
