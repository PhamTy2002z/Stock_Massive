"""Market domain schemas."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .common import StrictModel


class SectorPerformanceItem(StrictModel):
    """Sector performance data."""

    icb_code: str = Field(..., description="ICB Level 2 code")
    icb_name: str = Field(..., description="Sector name (Vietnamese)")
    change_pct: float = Field(..., description="Market-cap weighted change %")
    total_market_cap: float = Field(..., description="Total market cap (billion VND)")
    stock_count: int = Field(..., description="Number of stocks in sector")
    top_gainers: list[str] = Field(default_factory=list, description="Top 3 gaining symbols")
    top_losers: list[str] = Field(default_factory=list, description="Top 3 losing symbols")


class SectorPerformanceResponse(StrictModel):
    """Response for sector performance endpoint."""

    sectors: list[SectorPerformanceItem]
    generated_at: datetime
    total_sectors: int


# === Fund Certificates Schemas ===


class FundCertificateItem(StrictModel):
    """Fund certificate (ETF/Open-end fund) data."""

    symbol: str = Field(..., description="Fund symbol (e.g., E1VFVN30, FUEVFVND)")
    short_name: str = Field(..., description="Fund short name")
    fund_type: Optional[str] = Field(None, description="Fund type: STOCK, BOND, BALANCED")
    nav: Optional[float] = Field(None, description="Net Asset Value per unit")
    price: Optional[float] = Field(None, description="Current trading price")
    change_pct: Optional[float] = Field(None, description="Daily change percentage")


class FundCertificatesResponse(StrictModel):
    """Response for fund certificates endpoint."""

    funds: list[FundCertificateItem]
    generated_at: datetime
    total_count: int


# === VN30 Overview Schemas ===


class VN30OverviewItem(StrictModel):
    """VN30 stock overview item."""

    symbol: str = Field(..., description="Stock symbol")
    company_name: str = Field(..., description="Company name")
    price: Optional[float] = Field(None, description="Current price (VND)")
    change_pct: Optional[float] = Field(None, description="Daily change percentage")
    volume: Optional[float] = Field(None, description="Trading volume")
    market_cap: Optional[float] = Field(None, description="Market cap (billion VND)")


class VN30OverviewResponse(StrictModel):
    """Response for VN30 overview endpoint."""

    stocks: list[VN30OverviewItem]
    generated_at: datetime
    total_count: int


# === Sector Historical Performance Schemas ===

SectorHistoricalPeriod = Literal["1W", "2W", "1M"]


class SectorHistoricalItem(StrictModel):
    """Sector historical performance item."""

    icb_code: str = Field(..., description="ICB Level 2 code")
    icb_name: str = Field(..., description="Sector name (Vietnamese)")
    change_pct: float = Field(..., description="Average change percentage")


class SectorHistoricalResponse(StrictModel):
    """Response for sector historical performance endpoint."""

    period: str = Field(..., description="Period: 1W, 2W, or 1M")
    top_gainers: list[SectorHistoricalItem] = Field(default_factory=list)
    top_losers: list[SectorHistoricalItem] = Field(default_factory=list)
    generated_at: Optional[str] = Field(None, description="When data was calculated")
