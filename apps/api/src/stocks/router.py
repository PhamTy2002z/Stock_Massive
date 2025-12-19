"""FastAPI router for stock data endpoints."""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.stocks.intraday_collector import IntradayCollector
from src.stocks.schemas import (
    StockPrice,
    IntradayTick,
    CompanyOverview,
    StockSymbol,
    FinancialRatio,
    IncomeStatementItem,
    IncomeStatementResponse,
    BalanceSheetItem,
    BalanceSheetResponse,
    CashFlowResponse,
    PriceBoardItem,
    MarketIndexItem,
    StockDetail,
    IntradayCollectionResult,
    VolumeAnalysisResponse,
    ShareholdersResponse,
    OfficersResponse,
    InsiderDealsResponse,
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


@router.get("/{symbol}/detail", response_model=StockDetail)
async def get_stock_detail(symbol: str) -> StockDetail:
    """Get comprehensive stock detail data.

    Returns combined data from price board, company overview, and financial ratios.
    Single endpoint for all stock detail page requirements.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_service()
        return service.get_stock_detail(symbol)
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
    """Get income statement data for a stock (simplified).

    Returns revenue, profit, and earnings data.
    """
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    try:
        service = get_service()
        return service.get_income_statement(symbol, period, lang)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/income-statement", response_model=IncomeStatementResponse)
async def get_income_statement_detailed(
    symbol: str,
    period: str = Query("quarter", description="Period: year or quarter"),
    limit: int = Query(4, ge=1, le=12, description="Number of periods to return"),
) -> IncomeStatementResponse:
    """Get detailed income statement data for financial table display.

    Returns structured rows with Vietnamese labels for the Finance tab.
    Values are in millions VND.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    - **period**: 'quarter' for quarterly data, 'year' for annual data
    - **limit**: Number of periods to return (default 4, max 12)
    """
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    try:
        service = get_service()
        return service.get_income_statement_detailed(symbol, period, limit)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/balance-sheet", response_model=list[BalanceSheetItem])
async def get_balance_sheet(
    symbol: str,
    period: str = Query("year", description="Period: year or quarter"),
    lang: str = Query("en", description="Language: en or vi"),
) -> list[BalanceSheetItem]:
    """Get balance sheet data for a stock (simplified).

    Returns assets, liabilities, and equity data.
    """
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    try:
        service = get_service()
        return service.get_balance_sheet(symbol, period, lang)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/balance-sheet-detailed", response_model=BalanceSheetResponse)
async def get_balance_sheet_detailed(
    symbol: str,
    period: str = Query("quarter", description="Period: year or quarter"),
    limit: int = Query(4, ge=1, le=12, description="Number of periods to return"),
) -> BalanceSheetResponse:
    """Get detailed balance sheet data for financial table display.

    Returns structured rows with Vietnamese labels for the Finance tab.
    Values are in millions VND.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    - **period**: 'quarter' for quarterly data, 'year' for annual data
    - **limit**: Number of periods to return (default 4, max 12)
    """
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    try:
        service = get_service()
        return service.get_balance_sheet_detailed(symbol, period, limit)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/cash-flow", response_model=CashFlowResponse)
async def get_cash_flow_detailed(
    symbol: str,
    period: str = Query("quarter", description="Period: year or quarter"),
    limit: int = Query(4, ge=1, le=12, description="Number of periods to return"),
) -> CashFlowResponse:
    """Get detailed cash flow data for financial table display.

    Returns structured rows with Vietnamese labels for the Finance tab.
    Values are in millions VND.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    - **period**: 'quarter' for quarterly data, 'year' for annual data
    - **limit**: Number of periods to return (default 4, max 12)
    """
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    try:
        service = get_service()
        return service.get_cash_flow_detailed(symbol, period, limit)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


# === Intraday Data Collection Endpoints ===


@router.post("/intraday/collect", response_model=IntradayCollectionResult)
async def collect_intraday_data(
    symbols: list[str] = Query(
        default=["VCB", "FPT", "VNM"],
        description="List of stock symbols to collect",
    ),
    db: AsyncSession = Depends(get_db),
) -> IntradayCollectionResult:
    """Manually trigger intraday data collection.

    Collects tick data from vnstock, aggregates to 5-minute OHLCV bars,
    and stores in database. Uses upsert for idempotent operations.

    - **symbols**: List of stock symbols (default: VCB, FPT, VNM)
    """
    if len(symbols) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols allowed")

    collector = IntradayCollector(db)
    result = await collector.collect_and_save(symbols)
    return IntradayCollectionResult(**result)


# === Shareholders & Officers Endpoints ===


@router.get("/{symbol}/shareholders", response_model=ShareholdersResponse)
async def get_shareholders(symbol: str) -> ShareholdersResponse:
    """Get major shareholders for a stock.

    Returns list of major shareholders with ownership percentages.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_service()
        return service.get_shareholders(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/officers", response_model=OfficersResponse)
async def get_officers(
    symbol: str,
    filter_by: str = Query("working", description="Filter: working, resigned, all"),
) -> OfficersResponse:
    """Get company officers/management for a stock.

    Returns list of officers with positions and ownership.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    - **filter_by**: Filter by status (working, resigned, all)
    """
    if filter_by not in ("working", "resigned", "all"):
        raise HTTPException(status_code=400, detail="Invalid filter_by. Use 'working', 'resigned', or 'all'")

    try:
        service = get_service()
        return service.get_officers(symbol, filter_by)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/insider-deals", response_model=InsiderDealsResponse)
async def get_insider_deals(symbol: str) -> InsiderDealsResponse:
    """Get insider trading deals for a stock.

    Returns list of insider buy/sell transactions.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_service()
        return service.get_insider_deals(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/volume-analysis", response_model=VolumeAnalysisResponse)
async def get_volume_analysis(
    symbol: str,
    days: int = Query(default=10, ge=1, le=30, description="Number of days to analyze"),
    top_n: int = Query(default=10, ge=1, le=72, description="Number of top periods to return"),
    db: AsyncSession = Depends(get_db),
) -> VolumeAnalysisResponse:
    """Analyze intraday volume patterns for a stock.

    Returns peak volume periods within trading session (09:00-15:00).
    Groups historical 5-minute bars by time-of-day to identify when
    trading activity is typically highest.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    - **days**: Number of days to analyze (default 10, max 30)
    - **top_n**: Number of top periods to return (default 10, max 72)
    """
    collector = IntradayCollector(db)
    result = await collector.analyze_volume(symbol, days, top_n)

    if not result["peak_periods"]:
        raise HTTPException(
            status_code=404,
            detail=f"No intraday data found for {symbol.upper()} in last {days} days",
        )

    return VolumeAnalysisResponse(**result)
