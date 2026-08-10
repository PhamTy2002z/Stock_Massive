"""Financial domain router for financial-related endpoints.

Frozen: these call vnstock inside the user's request. `FundamentalSnapshot`
holds a period end, trailing twelve-month net income and parent equity — the
inputs a health score needs — while these endpoints return whole statements.
Serving them from the store would mean widening the ingestion contract to the
shape of six statement endpoints and migrating what is already stored. Declined
in #27 for now: statements move quarterly, so the quota they cost is small, and
`/{symbol}/snapshot` already carries the figures that are collected.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query

from src.core.cache import TradingHoursCache
from src.core.ratelimit import heavy_rate_limit, standard_rate_limit
from src.core.vnstock_client import VnstockUnavailable
from .service import get_financial_service
from ..schemas.financial import (
    FinancialRatio,
    IncomeStatementItem,
    IncomeStatementResponse,
    BalanceSheetItem,
    BalanceSheetResponse,
    CashFlowResponse,
    HealthScoreResponse,
    TrendMetricsResponse,
    FCFAnalysisResponse,
)
from ..shared import validate_symbol

router = APIRouter()

# Provider-backed statements change slowly and should never fan out on UI load.
financial_response_cache = TradingHoursCache(
    key_prefix="stock:financial_response:",
    ttl_trading=3600,
    ttl_off_hours=86400,
    stale_ttl=7 * 86400,
)

# Cache instances for derived endpoints
health_score_cache = TradingHoursCache(
    key_prefix="stock:health_score:",
    ttl_trading=3600,      # 1 hour during trading
    ttl_off_hours=86400,   # 24 hours off-hours
)

trend_metrics_cache = TradingHoursCache(
    key_prefix="stock:trend_metrics:",
    ttl_trading=3600,
    ttl_off_hours=86400,
)

fcf_analysis_cache = TradingHoursCache(
    key_prefix="stock:fcf_analysis:",
    ttl_trading=3600,
    ttl_off_hours=86400,
)


def _cached_model(key: str, model, loader):
    payload = financial_response_cache.get_or_load(
        key,
        lambda: loader().model_dump(mode="json"),
        suppress_failure=lambda exc: isinstance(exc, VnstockUnavailable),
    )
    return model.model_validate(payload)


def _cached_list(key: str, model, loader):
    payload = financial_response_cache.get_or_load(
        key,
        lambda: [item.model_dump(mode="json") for item in loader()],
        suppress_failure=lambda exc: isinstance(exc, VnstockUnavailable),
    )
    return [model.model_validate(item) for item in payload]


@router.get("/{symbol}/financials/ratios", response_model=List[FinancialRatio], dependencies=[Depends(heavy_rate_limit)])
def get_financial_ratios(
    symbol: str,
    period: str = Query("year", description="Period: year or quarter"),
    lang: str = Query("en", description="Language: en or vi"),
) -> List[FinancialRatio]:
    """Get financial ratios for a stock."""
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    if lang not in ("en", "vi"):
        raise HTTPException(status_code=400, detail="Invalid language. Use 'en' or 'vi'")

    symbol = validate_symbol(symbol)
    service = get_financial_service()
    return _cached_list(
        f"ratios:{symbol.upper()}:{period}:{lang}",
        FinancialRatio,
        lambda: service.get_financial_ratios(symbol, period, lang),
    )


@router.get("/{symbol}/financials/income", response_model=List[IncomeStatementItem], dependencies=[Depends(heavy_rate_limit)])
def get_income_statement(
    symbol: str,
    period: str = Query("year", description="Period: year or quarter"),
    lang: str = Query("en", description="Language: en or vi"),
) -> List[IncomeStatementItem]:
    """Get income statement data for a stock (simplified)."""
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    symbol = validate_symbol(symbol)
    service = get_financial_service()
    return _cached_list(
        f"income:{symbol.upper()}:{period}:{lang}",
        IncomeStatementItem,
        lambda: service.get_income_statement(symbol, period, lang),
    )


@router.get("/{symbol}/financials/income-statement", response_model=IncomeStatementResponse, dependencies=[Depends(heavy_rate_limit)])
def get_income_statement_detailed(
    symbol: str,
    period: str = Query("quarter", description="Period: year or quarter"),
    limit: int = Query(4, ge=1, le=12, description="Number of periods to return"),
) -> IncomeStatementResponse:
    """Get detailed income statement data for financial table display."""
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    symbol = validate_symbol(symbol)
    service = get_financial_service()
    return _cached_model(
        f"income-statement:{symbol.upper()}:{period}:{limit}",
        IncomeStatementResponse,
        lambda: service.get_income_statement_detailed(symbol, period, limit),
    )


@router.get("/{symbol}/financials/balance-sheet", response_model=List[BalanceSheetItem], dependencies=[Depends(heavy_rate_limit)])
def get_balance_sheet(
    symbol: str,
    period: str = Query("year", description="Period: year or quarter"),
    lang: str = Query("en", description="Language: en or vi"),
) -> List[BalanceSheetItem]:
    """Get balance sheet data for a stock (simplified)."""
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    symbol = validate_symbol(symbol)
    service = get_financial_service()
    return _cached_list(
        f"balance-sheet:{symbol.upper()}:{period}:{lang}",
        BalanceSheetItem,
        lambda: service.get_balance_sheet(symbol, period, lang),
    )


@router.get("/{symbol}/financials/balance-sheet-detailed", response_model=BalanceSheetResponse, dependencies=[Depends(heavy_rate_limit)])
def get_balance_sheet_detailed(
    symbol: str,
    period: str = Query("quarter", description="Period: year or quarter"),
    limit: int = Query(4, ge=1, le=12, description="Number of periods to return"),
) -> BalanceSheetResponse:
    """Get detailed balance sheet data for financial table display."""
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    symbol = validate_symbol(symbol)
    service = get_financial_service()
    return _cached_model(
        f"balance-sheet-detailed:{symbol.upper()}:{period}:{limit}",
        BalanceSheetResponse,
        lambda: service.get_balance_sheet_detailed(symbol, period, limit),
    )


@router.get("/{symbol}/financials/cash-flow", response_model=CashFlowResponse, dependencies=[Depends(heavy_rate_limit)])
def get_cash_flow_detailed(
    symbol: str,
    period: str = Query("quarter", description="Period: year or quarter"),
    limit: int = Query(4, ge=1, le=12, description="Number of periods to return"),
) -> CashFlowResponse:
    """Get detailed cash flow data for financial table display."""
    if period not in ("year", "quarter"):
        raise HTTPException(status_code=400, detail="Invalid period. Use 'year' or 'quarter'")

    symbol = validate_symbol(symbol)
    service = get_financial_service()
    return _cached_model(
        f"cash-flow:{symbol.upper()}:{period}:{limit}",
        CashFlowResponse,
        lambda: service.get_cash_flow_detailed(symbol, period, limit),
    )


# ==================== New Endpoints for Health Score & Trends ====================


@router.get(
    "/{symbol}/health-score",
    response_model=HealthScoreResponse,
    dependencies=[Depends(standard_rate_limit)],
)
def get_health_score(symbol: str) -> HealthScoreResponse:
    """Get financial health scorecard for a stock.

    Calculates a 0-100 health score based on 5 dimensions:
    - Profitability (ROE, ROA, Net Margin)
    - Liquidity (Current Ratio, Quick Ratio)
    - Leverage (D/E)
    - Efficiency (Asset Turnover)
    - Valuation (P/E, P/B)

    Also includes Piotroski F-Score (0-9) for fundamental strength.
    """
    # Try cache first
    cached = health_score_cache.get(symbol.upper())
    if cached:
        return HealthScoreResponse(**cached)

    service = get_financial_service()
    result = service.get_health_score(symbol)

    # Cache result
    health_score_cache.set(symbol.upper(), result.model_dump(mode="json"))

    return result


@router.get(
    "/{symbol}/trend-metrics",
    response_model=TrendMetricsResponse,
    dependencies=[Depends(standard_rate_limit)],
)
def get_trend_metrics(
    symbol: str,
    periods: int = Query(8, ge=4, le=16, description="Number of quarters"),
) -> TrendMetricsResponse:
    """Get trend metrics for financial charts.

    Returns arrays of metrics over N quarters for visualization:
    - Revenue & Net Profit
    - Gross/Net Margin
    - ROE/ROA
    - Cash Flow (CFO, CFI, CFF)
    """
    cache_key = f"{symbol.upper()}:{periods}"
    cached = trend_metrics_cache.get(cache_key)
    if cached:
        return TrendMetricsResponse(**cached)

    service = get_financial_service()
    result = service.get_trend_metrics(symbol, periods)

    # Cache result
    trend_metrics_cache.set(cache_key, result.model_dump(mode="json"))

    return result


@router.get(
    "/{symbol}/fcf-analysis",
    response_model=FCFAnalysisResponse,
    dependencies=[Depends(standard_rate_limit)],
)
def get_fcf_analysis(symbol: str) -> FCFAnalysisResponse:
    """Get Free Cash Flow analysis for a stock.

    Returns:
    - Net Income → CFO → CapEx → FCF waterfall
    - FCF Margin and FCF Yield
    - Cash Conversion Cycle (CCC = DSO + DIO - DPO)

    Note: CCC will be null for banks/financial companies.
    """
    cached = fcf_analysis_cache.get(symbol.upper())
    if cached:
        return FCFAnalysisResponse(**cached)

    service = get_financial_service()
    result = service.get_fcf_analysis(symbol)

    # Cache result
    fcf_analysis_cache.set(symbol.upper(), result.model_dump(mode="json"))

    return result
