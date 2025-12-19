"""Market domain router for market-wide endpoints."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..service import get_stock_service
from ..schemas.company import StockSymbol
from ..schemas.market import (
    SectorPerformanceResponse,
    FundCertificatesResponse,
)
from ..shared import StockServiceError

router = APIRouter()


@router.get("/symbols", response_model=List[StockSymbol])
async def list_symbols(
    exchange: Optional[str] = Query(None, description="Filter by exchange: HOSE, HNX, UPCOM"),
) -> List[StockSymbol]:
    """List all available stock symbols."""
    try:
        service = get_stock_service()
        return service.list_symbols(exchange=exchange)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/symbols/group/{group}", response_model=List[str])
async def list_symbols_by_group(group: str) -> List[str]:
    """List symbols by group (e.g., VN30, HNX30, VN100)."""
    try:
        service = get_stock_service()
        return service.list_symbols_by_group(group)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/symbols/search", response_model=List[StockSymbol])
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


@router.get("/sector-performance", response_model=SectorPerformanceResponse)
async def get_sector_performance() -> SectorPerformanceResponse:
    """Get market-cap weighted sector performance (ICB Level 2)."""
    try:
        service = get_stock_service()
        return service.get_sector_performance()
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/fund-certificates", response_model=FundCertificatesResponse)
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
