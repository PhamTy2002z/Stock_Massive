"""Company domain router for company-related endpoints."""

from fastapi import APIRouter, HTTPException, Query

from ..service import get_stock_service
from ..schemas.company import (
    CompanyOverview,
    StockDetail,
    ShareholdersResponse,
    OfficersResponse,
    InsiderDealsResponse,
)
from ..shared import StockServiceError

router = APIRouter()


@router.get("/{symbol}/company", response_model=CompanyOverview)
async def get_company_overview(symbol: str) -> CompanyOverview:
    """Get company overview information."""
    try:
        service = get_stock_service()
        return service.get_company_overview(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/detail", response_model=StockDetail)
async def get_stock_detail(symbol: str) -> StockDetail:
    """Get comprehensive stock detail data (composite endpoint)."""
    try:
        service = get_stock_service()
        return service.get_stock_detail(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/shareholders", response_model=ShareholdersResponse)
async def get_shareholders(symbol: str) -> ShareholdersResponse:
    """Get major shareholders for a stock."""
    try:
        service = get_stock_service()
        return service.get_shareholders(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/officers", response_model=OfficersResponse)
async def get_officers(
    symbol: str,
    filter_by: str = Query("working", description="Filter: working, resigned, all"),
) -> OfficersResponse:
    """Get company officers/management for a stock."""
    if filter_by not in ("working", "resigned", "all"):
        raise HTTPException(status_code=400, detail="Invalid filter_by. Use 'working', 'resigned', or 'all'")

    try:
        service = get_stock_service()
        return service.get_officers(symbol, filter_by)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/insider-deals", response_model=InsiderDealsResponse)
async def get_insider_deals(symbol: str) -> InsiderDealsResponse:
    """Get insider trading deals for a stock."""
    try:
        service = get_stock_service()
        return service.get_insider_deals(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
