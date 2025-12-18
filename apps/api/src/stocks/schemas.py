"""Pydantic schemas for stock data."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# === Stock Price Schemas ===

class StockPrice(BaseModel):
    """Historical OHLCV price data."""

    time: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class IntradayTick(BaseModel):
    """Intraday tick data."""

    time: datetime
    price: float
    volume: int
    accumulated_vol: int
    accumulated_val: int
    match_type: str


# === Company Schemas ===

class CompanyOverview(BaseModel):
    """Company overview information."""

    symbol: str
    company_name: Optional[str] = None
    exchange: Optional[str] = None
    industry: Optional[str] = None
    established_year: Optional[int] = None
    employees: Optional[int] = None
    website: Optional[str] = None
    description: Optional[str] = None


class StockSymbol(BaseModel):
    """Stock symbol listing."""

    symbol: str
    organ_name: Optional[str] = None
    exchange: Optional[str] = None
    organ_type_code: Optional[str] = None


# === Financial Schemas ===

class FinancialRatio(BaseModel):
    """Financial ratio data."""

    year: Optional[int] = None
    quarter: Optional[int] = None
    ticker: Optional[str] = None
    # Profitability
    roe: Optional[float] = Field(None, description="Return on Equity")
    roa: Optional[float] = Field(None, description="Return on Assets")
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    # Valuation
    pe: Optional[float] = Field(None, description="Price to Earnings")
    pb: Optional[float] = Field(None, description="Price to Book")
    ps: Optional[float] = Field(None, description="Price to Sales")
    # Liquidity
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    # Leverage
    debt_to_equity: Optional[float] = None
    debt_to_assets: Optional[float] = None


class IncomeStatementItem(BaseModel):
    """Income statement line item."""

    year: Optional[int] = None
    quarter: Optional[int] = None
    revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_profit: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None


class BalanceSheetItem(BaseModel):
    """Balance sheet line item."""

    year: Optional[int] = None
    quarter: Optional[int] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    cash: Optional[float] = None


# === Request/Response Schemas ===

class HistoryParams(BaseModel):
    """Query parameters for history endpoint."""

    start: date = Field(..., description="Start date (YYYY-MM-DD)")
    end: date = Field(..., description="End date (YYYY-MM-DD)")
    interval: str = Field("1D", description="Interval: 1D, 1W, 1M")


class PriceBoardItem(BaseModel):
    """Price board data for a single stock."""

    symbol: str
    ceiling: Optional[float] = None
    floor: Optional[float] = None
    ref_price: Optional[float] = None
    last_price: Optional[float] = None
    last_vol: Optional[int] = None
    total_vol: Optional[int] = None
    total_val: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    code: str = "error"
