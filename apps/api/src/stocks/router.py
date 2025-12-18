"""FastAPI router for stock data endpoints."""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.stocks.schemas import (
    StockPrice,
    IntradayTick,
    CompanyOverview,
    StockSymbol,
    FinancialRatio,
    IncomeStatementItem,
    BalanceSheetItem,
    PriceBoardItem,
    MarketIndexItem,
)
from src.stocks.service import StockService, StockServiceError, get_stock_service

router = APIRouter(prefix="/stocks", tags=["stocks"])


def get_service() -> StockService:
    """Get stock service instance."""
    return get_stock_service()


# === Symbol Listing Endpoints ===


@router.get("/symbols", response_model=list[StockSymbol])
async def list_symbols(
    exchange: Optional[str] = Query(None, description="Filter by exchange: HOSE, HNX, UPCOM"),
) -> list[StockSymbol]:
    """List all available stock symbols."""
    try:
        service = get_service()
        return service.list_symbols(exchange=exchange)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/symbols/group/{group}", response_model=list[str])
async def list_symbols_by_group(group: str) -> list[str]:
    """List symbols by group (e.g., VN30, HNX30, VN100)."""
    try:
        service = get_service()
        return service.list_symbols_by_group(group)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/symbols/search", response_model=list[StockSymbol])
async def search_symbols(
    q: str = Query(..., min_length=1, description="Search query (symbol or company name)"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results to return"),
) -> list[StockSymbol]:
    """Search stock symbols by ticker or company name.

    - **q**: Search query (matches symbol or company name, case-insensitive)
    - **limit**: Maximum number of results (default 20, max 50)
    """
    try:
        service = get_service()
        return service.search_symbols(q, limit)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


# === Price Data Endpoints ===


@router.get("/{symbol}/history", response_model=list[StockPrice])
async def get_history(
    symbol: str,
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: date = Query(default_factory=date.today, description="End date (YYYY-MM-DD)"),
    interval: str = Query("1D", description="Interval: 1D, 1W, 1M"),
) -> list[StockPrice]:
    """Get historical OHLCV data for a stock.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    - **start**: Start date for historical data
    - **end**: End date (defaults to today)
    - **interval**: Time interval - 1D (daily), 1W (weekly), 1M (monthly)
    """
    if interval not in ("1D", "1W", "1M"):
        raise HTTPException(status_code=400, detail="Invalid interval. Use 1D, 1W, or 1M")

    if start > end:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    try:
        service = get_service()
        return service.get_history(symbol, start, end, interval)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/intraday", response_model=list[IntradayTick])
async def get_intraday(
    symbol: str,
    page_size: int = Query(10000, ge=100, le=50000, description="Number of ticks to fetch"),
) -> list[IntradayTick]:
    """Get intraday tick data for a stock.

    Returns tick-by-tick trading data for the current trading day.
    """
    try:
        service = get_service()
        return service.get_intraday(symbol, page_size)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/market-indices", response_model=list[MarketIndexItem])
async def get_market_indices() -> list[MarketIndexItem]:
    """Get market indices data (VN-INDEX, VN30, HNX-INDEX, UPCOM-INDEX).

    Returns current values and daily changes for major Vietnamese market indices.
    """
    try:
        service = get_service()
        return service.get_market_indices()
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/price-board", response_model=list[PriceBoardItem])
async def get_price_board(
    symbols: str = Query(..., description="Comma-separated list of symbols (e.g., VCB,ACB,TCB)"),
) -> list[PriceBoardItem]:
    """Get real-time price board for multiple stocks.

    Returns current trading data including bid/ask prices, volume, and changes.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    if not symbol_list:
        raise HTTPException(status_code=400, detail="At least one symbol is required")

    if len(symbol_list) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols allowed")

    try:
        service = get_service()
        return service.get_price_board(symbol_list)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


# === Company Information Endpoints ===


@router.get("/{symbol}/company", response_model=CompanyOverview)
async def get_company_overview(symbol: str) -> CompanyOverview:
    """Get company overview information.

    Returns basic company information including name, industry, and description.
    """
    try:
        service = get_service()
        return service.get_company_overview(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


# === Financial Data Endpoints ===


@router.get("/{symbol}/financials/ratios", response_model=list[FinancialRatio])
async def get_financial_ratios(
    symbol: str,
    period: str = Query("year", description="Period: year or quarter"),
    lang: str = Query("en", description="Language: en or vi"),
) -> list[FinancialRatio]:
    """Get financial ratios for a stock.

    Returns key financial metrics including ROE, ROA, P/E, P/B, and more.
    """
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    if lang not in ("en", "vi"):
        raise HTTPException(status_code=400, detail="Invalid language. Use 'en' or 'vi'")

    try:
        service = get_service()
        return service.get_financial_ratios(symbol, period, lang)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/income", response_model=list[IncomeStatementItem])
async def get_income_statement(
    symbol: str,
    period: str = Query("year", description="Period: year or quarter"),
    lang: str = Query("en", description="Language: en or vi"),
) -> list[IncomeStatementItem]:
    """Get income statement data for a stock.

    Returns revenue, profit, and earnings data.
    """
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    try:
        service = get_service()
        return service.get_income_statement(symbol, period, lang)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/balance-sheet", response_model=list[BalanceSheetItem])
async def get_balance_sheet(
    symbol: str,
    period: str = Query("year", description="Period: year or quarter"),
    lang: str = Query("en", description="Language: en or vi"),
) -> list[BalanceSheetItem]:
    """Get balance sheet data for a stock.

    Returns assets, liabilities, and equity data.
    """
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    try:
        service = get_service()
        return service.get_balance_sheet(symbol, period, lang)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
