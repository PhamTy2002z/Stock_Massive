"""Market domain router for market-wide endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.core.cache import TradingHoursCache
from src.core.ratelimit import standard_rate_limit
from ..service import get_stock_service
from ..schemas.company import StockSymbol
from ..schemas.market import (
    SectorPerformanceResponse,
    FundCertificatesResponse,
)
from ..shared import StockServiceError

router = APIRouter()

# Cache instances for endpoints
symbols_cache = TradingHoursCache(
    key_prefix="stock:symbols:",
    ttl_trading=3600,
    ttl_off_hours=86400,
)
sector_performance_cache = TradingHoursCache(
    key_prefix="stock:sector:",
    ttl_trading=300,
    ttl_off_hours=3600,
)


@router.get("/symbols", response_model=List[StockSymbol], dependencies=[Depends(standard_rate_limit)])
async def list_symbols(
    exchange: Optional[str] = Query(None, description="Filter by exchange: HOSE, HNX, UPCOM"),
) -> List[StockSymbol]:
    """List all available stock symbols."""
    cache_key = exchange or "all"

    # Check cache first
    cached = symbols_cache.get(cache_key)
    if cached is not None:
        return [StockSymbol(**item) for item in cached]

    # Cache miss - fetch from service
    try:
        service = get_stock_service()
        result = service.list_symbols(exchange=exchange)

        # Cache the result
        symbols_cache.set(cache_key, [item.model_dump() for item in result])

        return result
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/symbols/group/{group}", response_model=List[str], dependencies=[Depends(standard_rate_limit)])
async def list_symbols_by_group(group: str) -> List[str]:
    """List symbols by group (e.g., VN30, HNX30, VN100)."""
    try:
        service = get_stock_service()
        return service.list_symbols_by_group(group)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/symbols/search", response_model=List[StockSymbol], dependencies=[Depends(standard_rate_limit)])
async def search_symbols(
    q: str = Query(..., min_length=1, description="Search query (symbol or company name)"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results to return"),
) -> List[StockSymbol]:
    """Search stock symbols by ticker or company name."""
    try:
        service = get_stock_service()
        return service.search_symbols(q, limit)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/sector-performance", response_model=SectorPerformanceResponse, dependencies=[Depends(standard_rate_limit)])
async def get_sector_performance() -> SectorPerformanceResponse:
    """Get market-cap weighted sector performance (ICB Level 2)."""
    cache_key = "performance"

    # Check cache first
    cached = sector_performance_cache.get(cache_key)
    if cached is not None:
        return SectorPerformanceResponse(**cached)

    # Cache miss - fetch from service
    try:
        service = get_stock_service()
        result = service.get_sector_performance()

        # Cache the result
        sector_performance_cache.set(cache_key, result.model_dump())

        return result
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/fund-certificates", response_model=FundCertificatesResponse, dependencies=[Depends(standard_rate_limit)])
async def get_fund_certificates(
    fund_type: Optional[str] = Query(None, description="Filter by type: STOCK, BOND, BALANCED"),
) -> FundCertificatesResponse:
    """Get fund certificates (ETFs and open-end funds)."""
    if fund_type and fund_type.upper() not in ("STOCK", "BOND", "BALANCED"):
        raise HTTPException(status_code=400, detail="Invalid fund_type. Use STOCK, BOND, or BALANCED")

    try:
        service = get_stock_service()
        return service.get_fund_certificates(fund_type)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
