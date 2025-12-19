"""Financial domain router for financial-related endpoints."""

from typing import List

from fastapi import APIRouter, HTTPException, Query

from ..service import get_stock_service
from ..schemas.financial import (
    FinancialRatio,
    IncomeStatementItem,
    IncomeStatementResponse,
    BalanceSheetItem,
    BalanceSheetResponse,
    CashFlowResponse,
)
from ..shared import StockServiceError

router = APIRouter()


@router.get("/{symbol}/financials/ratios", response_model=List[FinancialRatio])
async def get_financial_ratios(
    symbol: str,
    period: str = Query("year", description="Period: year or quarter"),
    lang: str = Query("en", description="Language: en or vi"),
) -> List[FinancialRatio]:
    """Get financial ratios for a stock."""
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    if lang not in ("en", "vi"):
        raise HTTPException(status_code=400, detail="Invalid language. Use 'en' or 'vi'")

    try:
        service = get_stock_service()
        return service.get_financial_ratios(symbol, period, lang)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/income", response_model=List[IncomeStatementItem])
async def get_income_statement(
    symbol: str,
    period: str = Query("year", description="Period: year or quarter"),
    lang: str = Query("en", description="Language: en or vi"),
) -> List[IncomeStatementItem]:
    """Get income statement data for a stock (simplified)."""
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    try:
        service = get_stock_service()
        return service.get_income_statement(symbol, period, lang)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/income-statement", response_model=IncomeStatementResponse)
async def get_income_statement_detailed(
    symbol: str,
    period: str = Query("quarter", description="Period: year or quarter"),
    limit: int = Query(4, ge=1, le=12, description="Number of periods to return"),
) -> IncomeStatementResponse:
    """Get detailed income statement data for financial table display."""
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    try:
        service = get_stock_service()
        return service.get_income_statement_detailed(symbol, period, limit)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/balance-sheet", response_model=List[BalanceSheetItem])
async def get_balance_sheet(
    symbol: str,
    period: str = Query("year", description="Period: year or quarter"),
    lang: str = Query("en", description="Language: en or vi"),
) -> List[BalanceSheetItem]:
    """Get balance sheet data for a stock (simplified)."""
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    try:
        service = get_stock_service()
        return service.get_balance_sheet(symbol, period, lang)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/balance-sheet-detailed", response_model=BalanceSheetResponse)
async def get_balance_sheet_detailed(
    symbol: str,
    period: str = Query("quarter", description="Period: year or quarter"),
    limit: int = Query(4, ge=1, le=12, description="Number of periods to return"),
) -> BalanceSheetResponse:
    """Get detailed balance sheet data for financial table display."""
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    try:
        service = get_stock_service()
        return service.get_balance_sheet_detailed(symbol, period, limit)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{symbol}/financials/cash-flow", response_model=CashFlowResponse)
async def get_cash_flow_detailed(
    symbol: str,
    period: str = Query("quarter", description="Period: year or quarter"),
    limit: int = Query(4, ge=1, le=12, description="Number of periods to return"),
) -> CashFlowResponse:
    """Get detailed cash flow data for financial table display."""
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    try:
        service = get_stock_service()
        return service.get_cash_flow_detailed(symbol, period, limit)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
