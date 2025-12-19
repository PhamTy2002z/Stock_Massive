"""Financial domain schemas."""

from typing import Optional

from pydantic import BaseModel, Field


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
