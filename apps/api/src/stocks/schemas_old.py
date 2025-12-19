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
    """Income statement line item - simplified summary."""

    year: Optional[int] = None
    quarter: Optional[int] = None
    revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_profit: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None


class IncomeStatementRow(BaseModel):
    """Detailed income statement row for financial table display."""

    id: str  # Unique identifier for the row
    label: str  # Vietnamese label for display
    values: dict[str, Optional[float]]  # Period -> value mapping (e.g., "Q3/2025": 1234.5)
    level: int = 0  # Indentation level (0 = root, 1 = child, etc.)
    is_header: bool = False  # Bold section headers
    is_summary: bool = False  # Bold summary rows


class IncomeStatementResponse(BaseModel):
    """Response for detailed income statement endpoint."""

    symbol: str
    periods: list[str]  # List of period labels (e.g., ["Q3/2025", "Q2/2025", ...])
    rows: list[IncomeStatementRow]
    unit: str = "VND"  # Currency unit


class BalanceSheetItem(BaseModel):
    """Balance sheet line item."""

    year: Optional[int] = None
    quarter: Optional[int] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    cash: Optional[float] = None


class BalanceSheetRow(BaseModel):
    """Detailed balance sheet row for financial table display."""

    id: str  # Unique identifier for the row
    label: str  # Vietnamese label for display
    values: dict[str, Optional[float]]  # Period -> value mapping (e.g., "Q3/2025": 1234.5)
    level: int = 0  # Indentation level (0 = root, 1 = child, etc.)
    is_header: bool = False  # Bold section headers
    is_summary: bool = False  # Bold summary rows


class BalanceSheetResponse(BaseModel):
    """Response for detailed balance sheet endpoint."""

    symbol: str
    periods: list[str]  # List of period labels (e.g., ["Q3/2025", "Q2/2025", ...])
    rows: list[BalanceSheetRow]
    unit: str = "VND"  # Currency unit


class CashFlowRow(BaseModel):
    """Detailed cash flow row for financial table display."""

    id: str  # Unique identifier for the row
    label: str  # Vietnamese label for display
    values: dict[str, Optional[float]]  # Period -> value mapping (e.g., "Q3/2025": 1234.5)
    level: int = 0  # Indentation level (0 = root, 1 = child, etc.)
    is_header: bool = False  # Bold section headers
    is_summary: bool = False  # Bold summary rows


class CashFlowResponse(BaseModel):
    """Response for detailed cash flow endpoint."""

    symbol: str
    periods: list[str]  # List of period labels (e.g., ["Q3/2025", "Q2/2025", ...])
    rows: list[CashFlowRow]
    unit: str = "VND"  # Currency unit


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


# === Shareholders Schemas ===


class ShareholderItem(BaseModel):
    """Major shareholder data."""

    id: str
    name: str
    shares: float  # Number of shares
    ownership_pct: float  # Ownership percentage (0-100)
    update_date: Optional[str] = None


class ShareholdersResponse(BaseModel):
    """Response for shareholders endpoint."""

    symbol: str
    shareholders: list[ShareholderItem]
    total_count: int


class OfficerItem(BaseModel):
    """Company officer/insider data."""

    id: str
    name: str
    position: str
    position_short: Optional[str] = None
    shares: Optional[float] = None  # Number of shares
    ownership_pct: Optional[float] = None  # Ownership percentage
    update_date: Optional[str] = None
    status: Optional[str] = None  # working/resigned


class OfficersResponse(BaseModel):
    """Response for officers endpoint."""

    symbol: str
    officers: list[OfficerItem]
    total_count: int


class InsiderDealItem(BaseModel):
    """Insider trading deal data."""

    announce_date: str
    action: str  # Mua/Bán
    quantity: float
    price: Optional[float] = None
    ratio: Optional[float] = None


class InsiderDealsResponse(BaseModel):
    """Response for insider deals endpoint."""

    symbol: str
    deals: list[InsiderDealItem]
    total_count: int


# === Sector Performance Schemas ===


class SectorPerformanceItem(BaseModel):
    """Sector performance data."""

    icb_code: str = Field(..., description="ICB Level 2 code")
    icb_name: str = Field(..., description="Sector name (Vietnamese)")
    change_pct: float = Field(..., description="Market-cap weighted change %")
    total_market_cap: float = Field(..., description="Total market cap (billion VND)")
    stock_count: int = Field(..., description="Number of stocks in sector")
    top_gainers: list[str] = Field(default_factory=list, description="Top 3 gaining symbols")
    top_losers: list[str] = Field(default_factory=list, description="Top 3 losing symbols")


class SectorPerformanceResponse(BaseModel):
    """Response for sector performance endpoint."""

    sectors: list[SectorPerformanceItem]
    generated_at: datetime
    total_sectors: int


# === Fund Certificates Schemas ===


class FundCertificateItem(BaseModel):
    """Fund certificate (ETF/Open-end fund) data."""

    symbol: str = Field(..., description="Fund symbol (e.g., E1VFVN30, FUEVFVND)")
    short_name: str = Field(..., description="Fund short name")
    fund_type: Optional[str] = Field(None, description="Fund type: STOCK, BOND, BALANCED")
    nav: Optional[float] = Field(None, description="Net Asset Value per unit")
    price: Optional[float] = Field(None, description="Current trading price")
    change_pct: Optional[float] = Field(None, description="Daily change percentage")


class FundCertificatesResponse(BaseModel):
    """Response for fund certificates endpoint."""

    funds: list[FundCertificateItem]
    generated_at: datetime
    total_count: int
