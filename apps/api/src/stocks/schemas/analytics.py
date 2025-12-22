"""Analytics domain schemas."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class TopPerformerItem(BaseModel):
    """Single top performer entry."""
    rank: int = Field(..., description="Ranking position")
    symbol: str = Field(..., description="Stock ticker")
    company_name: Optional[str] = Field(None, description="Company name")
    exchange: Optional[str] = Field(None, description="Exchange (HOSE/HNX)")
    net_profit: Optional[int] = Field(None, description="Net profit in VND")
    revenue: Optional[int] = Field(None, description="Revenue in VND")
    profit_margin: Optional[float] = Field(None, description="Profit margin %")
    eps: Optional[float] = Field(None, description="Earnings per share")
    year: int = Field(..., description="Fiscal year")
    quarter: int = Field(..., description="Fiscal quarter (1-4)")

    model_config = {"from_attributes": True}


class TopPerformersResponse(BaseModel):
    """Top performers list response."""
    period: str = Field(..., description="Period label e.g. 'Q4-2024'")
    updated_at: Optional[datetime] = Field(None, description="Last data update")
    total: int = Field(..., description="Total records available")
    data: List[TopPerformerItem] = Field(..., description="Top performers list")
