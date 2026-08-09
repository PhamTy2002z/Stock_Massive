"""Financial domain schemas."""

from typing import Optional

from pydantic import BaseModel, Field

from .common import StrictModel


class FinancialRatio(StrictModel):
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


class IncomeStatementItem(StrictModel):
    """Income statement line item - simplified summary."""

    year: Optional[int] = None
    quarter: Optional[int] = None
    revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_profit: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None


class IncomeStatementRow(StrictModel):
    """Detailed income statement row for financial table display."""

    id: str  # Unique identifier for the row
    label: str  # Vietnamese label for display
    values: dict[str, Optional[float]]  # Period -> value mapping (e.g., "Q3/2025": 1234.5)
    level: int = 0  # Indentation level (0 = root, 1 = child, etc.)
    is_header: bool = False  # Bold section headers
    is_summary: bool = False  # Bold summary rows


class IncomeStatementResponse(StrictModel):
    """Response for detailed income statement endpoint."""

    symbol: str
    periods: list[str]  # List of period labels (e.g., ["Q3/2025", "Q2/2025", ...])
    rows: list[IncomeStatementRow]
    unit: str = "VND"  # Currency unit


class BalanceSheetItem(StrictModel):
    """Balance sheet line item."""

    year: Optional[int] = None
    quarter: Optional[int] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    cash: Optional[float] = None


class BalanceSheetRow(StrictModel):
    """Detailed balance sheet row for financial table display."""

    id: str  # Unique identifier for the row
    label: str  # Vietnamese label for display
    values: dict[str, Optional[float]]  # Period -> value mapping (e.g., "Q3/2025": 1234.5)
    level: int = 0  # Indentation level (0 = root, 1 = child, etc.)
    is_header: bool = False  # Bold section headers
    is_summary: bool = False  # Bold summary rows


class BalanceSheetResponse(StrictModel):
    """Response for detailed balance sheet endpoint."""

    symbol: str
    periods: list[str]  # List of period labels (e.g., ["Q3/2025", "Q2/2025", ...])
    rows: list[BalanceSheetRow]
    unit: str = "VND"  # Currency unit


class CashFlowRow(StrictModel):
    """Detailed cash flow row for financial table display."""

    id: str  # Unique identifier for the row
    label: str  # Vietnamese label for display
    values: dict[str, Optional[float]]  # Period -> value mapping (e.g., "Q3/2025": 1234.5)
    level: int = 0  # Indentation level (0 = root, 1 = child, etc.)
    is_header: bool = False  # Bold section headers
    is_summary: bool = False  # Bold summary rows


class CashFlowResponse(StrictModel):
    """Response for detailed cash flow endpoint."""

    symbol: str
    periods: list[str]  # List of period labels (e.g., ["Q3/2025", "Q2/2025", ...])
    rows: list[CashFlowRow]
    unit: str = "VND"  # Currency unit


# ==================== Health Score Schemas ====================


class HealthScoreDimension(StrictModel):
    """Score and metrics for a single health dimension."""

    score: int = Field(..., ge=0, le=100)
    metrics: dict[str, Optional[float]]


class FScoreDetails(StrictModel):
    """Piotroski F-Score breakdown (6 criteria)."""

    positive_roa: bool
    positive_cfo: bool
    roa_improving: bool
    accrual_quality: bool
    leverage_decreasing: bool
    liquidity_improving: bool


class HealthScoreResponse(StrictModel):
    """Financial health scorecard response."""

    symbol: str
    health_score: int = Field(..., ge=0, le=100)
    dimensions: dict[str, HealthScoreDimension]
    f_score: int = Field(..., ge=0, le=9)
    f_score_details: FScoreDetails
    period: Optional[str] = None  # e.g., "Q4/2024"


# ==================== Trend Metrics Schemas ====================


class TrendMetricsResponse(StrictModel):
    """Trend metrics for charts (8 quarters of data)."""

    symbol: str
    periods: list[str]  # e.g., ["Q1/2023", "Q2/2023", ...]
    revenue: list[Optional[float]]
    net_profit: list[Optional[float]]
    gross_profit: list[Optional[float]]
    gross_margin: list[Optional[float]]
    net_margin: list[Optional[float]]
    roe: list[Optional[float]]
    roa: list[Optional[float]]
    cfo: list[Optional[float]]
    cfi: list[Optional[float]]
    cff: list[Optional[float]]


# ==================== FCF Analysis Schemas ====================


class FCFAnalysisResponse(StrictModel):
    """Free Cash Flow analysis response."""

    symbol: str
    period: str  # e.g., "Q4/2024"
    net_income: Optional[float] = None
    cfo: Optional[float] = None
    capex: Optional[float] = None
    fcf: Optional[float] = None
    fcf_margin: Optional[float] = None
    ccc: Optional[float] = None  # Cash Conversion Cycle (null for banks)
    dso: Optional[float] = None  # Days Sales Outstanding
    dio: Optional[float] = None  # Days Inventory Outstanding
    dpo: Optional[float] = None  # Days Payable Outstanding
    market_cap: Optional[float] = None
    fcf_yield: Optional[float] = None


# ==================== Sector Peers Schemas ====================


class SectorMedian(StrictModel):
    """Sector median values for comparison."""

    pe: Optional[float] = None
    pb: Optional[float] = None
    # Only reported for non-financial companies; revenue multiples say nothing
    # about a bank, so the source omits it there.
    ps: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    market_cap: Optional[float] = None


class PeerMetrics(StrictModel):
    """Financial metrics for a peer company."""

    symbol: str
    company_name: Optional[str] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    market_cap: Optional[float] = None
    # Premium/discount vs sector median (%)
    premium_pe: Optional[float] = None
    premium_pb: Optional[float] = None
    premium_ps: Optional[float] = None
    premium_roe: Optional[float] = None
    premium_roa: Optional[float] = None


class SectorPeersResponse(StrictModel):
    """Sector peers comparison response."""

    symbol: str
    icb_code: str
    icb_name: str
    peers: list[PeerMetrics]
    sector_median: Optional[SectorMedian] = None
    target_premium: Optional[dict[str, Optional[float]]] = None
