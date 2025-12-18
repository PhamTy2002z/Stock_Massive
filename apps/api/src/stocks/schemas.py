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
    # New fields for stock detail
    match_price: Optional[float] = None
    highest: Optional[float] = None
    lowest: Optional[float] = None
    accumulated_volume: Optional[int] = None
    accumulated_value: Optional[float] = None
    # Existing fields
    ceiling: Optional[float] = None
    floor: Optional[float] = None
    ref_price: Optional[float] = None
    last_price: Optional[float] = None
    last_vol: Optional[int] = None
    total_vol: Optional[int] = None
    total_val: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None


class MarketIndexItem(BaseModel):
    """Market index data (VN-INDEX, VN30, etc.)."""

    symbol: str
    name: str
    value: float
    change: float
    change_pct: float


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    code: str = "error"


# === Intraday Bar Schemas ===


class IntradayBarCreate(BaseModel):
    """Schema for creating intraday bar records."""

    symbol: str
    bar_time: datetime
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    volume: int
    trade_value: Optional[float] = None
    trade_count: Optional[int] = None


class IntradayBar(IntradayBarCreate):
    """Schema for intraday bar with database fields."""

    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class IntradayCollectionResult(BaseModel):
    """Result of intraday data collection operation."""

    success: list[str] = Field(default_factory=list)
    failed: list[dict] = Field(default_factory=list)
    total_bars: int = 0


# === Volume Analysis Schemas ===


class VolumeTimePeriod(BaseModel):
    """Volume data for a specific time period within trading session."""

    hour: int
    minute_bucket: int  # 0, 5, 10, 15, ...
    time_label: str  # "09:00", "09:05", etc.
    avg_volume: float
    total_volume: int
    sample_count: int


class VolumeAnalysisResponse(BaseModel):
    """Response for volume analysis endpoint."""

    symbol: str
    days_analyzed: int
    trading_session: str = "09:00-15:00"
    peak_periods: list[VolumeTimePeriod]
    generated_at: datetime


class StockDetail(BaseModel):
    """Comprehensive stock detail data combining price, company, and financial info."""

    # Basic Info
    symbol: str
    company_name: Optional[str] = None
    exchange: Optional[str] = None
    industry: Optional[str] = None

    # Real-time Price Data
    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    ceiling: Optional[float] = None
    floor: Optional[float] = None
    ref_price: Optional[float] = None

    # Intraday Range
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None

    # Volume & Value
    volume: Optional[int] = None
    trading_value: Optional[float] = None

    # Market Cap & Shares
    market_cap: Optional[float] = None
    outstanding_shares: Optional[float] = None
    issue_share: Optional[float] = None

    # 52-Week Data
    high_52_week: Optional[float] = None
    low_52_week: Optional[float] = None
    avg_volume_52_week: Optional[int] = None

    # Financial Ratios
    eps: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    beta: Optional[float] = None
    dividend_yield: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None

    # Company Details
    description: Optional[str] = None
    website: Optional[str] = None
    employees: Optional[int] = None
    established_year: Optional[int] = None
