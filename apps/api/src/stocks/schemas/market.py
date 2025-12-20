"""Market domain schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


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
