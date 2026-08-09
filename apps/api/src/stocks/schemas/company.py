"""Company domain schemas."""

from typing import Optional

from pydantic import BaseModel

from .common import StrictModel


class CompanyOverview(StrictModel):
    """Company overview information."""

    symbol: str
    company_name: Optional[str] = None
    exchange: Optional[str] = None
    industry: Optional[str] = None
    established_year: Optional[int] = None
    employees: Optional[int] = None
    website: Optional[str] = None
    description: Optional[str] = None


class StockSymbol(StrictModel):
    """Stock symbol listing."""

    symbol: str
    organ_name: Optional[str] = None
    exchange: Optional[str] = None
    organ_type_code: Optional[str] = None


class StockDetail(StrictModel):
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

    # VN30 Ranking
    vn30_rank: Optional[int] = None  # Rank by market cap within VN30 (1-30), None if not in VN30


# === Shareholders Schemas ===


class ShareholderItem(StrictModel):
    """Major shareholder data."""

    id: str
    name: str
    shares: float  # Number of shares
    ownership_pct: float  # Ownership percentage (0-100)
    update_date: Optional[str] = None


class ShareholdersResponse(StrictModel):
    """Response for shareholders endpoint."""

    symbol: str
    shareholders: list[ShareholderItem]
    total_count: int


class OfficerItem(StrictModel):
    """Company officer/insider data."""

    id: str
    name: str
    position: str
    position_short: Optional[str] = None
    shares: Optional[float] = None  # Number of shares
    ownership_pct: Optional[float] = None  # Ownership percentage
    update_date: Optional[str] = None
    status: Optional[str] = None  # working/resigned


class OfficersResponse(StrictModel):
    """Response for officers endpoint."""

    symbol: str
    officers: list[OfficerItem]
    total_count: int


class InsiderDealItem(StrictModel):
    """Insider trading deal data."""

    announce_date: str
    action: str  # Mua/Bán
    quantity: float
    price: Optional[float] = None
    ratio: Optional[float] = None


class InsiderDealsResponse(StrictModel):
    """Response for insider deals endpoint."""

    symbol: str
    deals: list[InsiderDealItem]
    total_count: int


# === News & Dividends Schemas ===


class NewsItem(StrictModel):
    """Company news item."""

    id: int
    title: str
    source: Optional[str] = None
    published_at: str
    price: Optional[float] = None
    price_change_pct: Optional[float] = None


class NewsResponse(StrictModel):
    """Response for company news endpoint."""

    symbol: str
    items: list[NewsItem]
    total_count: int


class DividendItem(StrictModel):
    """Dividend history item."""

    exercise_date: str
    year: int
    dividend_pct: float  # e.g., 18.1 for 18.1%
    method: str  # 'cash' or 'share'


class DividendsResponse(StrictModel):
    """Response for dividends endpoint."""

    symbol: str
    items: list[DividendItem]
    total_count: int


# === Advanced Deep Dive Schemas ===


class RatioSummaryResponse(StrictModel):
    """Financial ratios summary for advanced tab."""

    symbol: str
    pe: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    roic: Optional[float] = None
    current_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
