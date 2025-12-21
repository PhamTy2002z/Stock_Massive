"""Pydantic schemas for market context feature."""
from datetime import date as date_type
from typing import Optional

from pydantic import BaseModel, Field


class StockDailyReturnSchema(BaseModel):
    """Daily return data for a stock."""
    symbol: str = Field(..., description="Stock ticker symbol")
    date: date_type = Field(..., description="Trading date")
    close_price: float = Field(..., description="Closing price")
    return_1d: Optional[float] = Field(None, description="Simple daily return")
    return_1d_log: Optional[float] = Field(None, description="Log daily return")

    model_config = {"from_attributes": True}


class StockMarketMetricSchema(BaseModel):
    """Market correlation and beta metrics for a stock."""
    symbol: str = Field(..., description="Stock ticker symbol")
    date: date_type = Field(..., description="Calculation date")
    corr_5d: Optional[float] = Field(None, description="5-day correlation vs VNINDEX")
    corr_20d: Optional[float] = Field(None, description="20-day correlation vs VNINDEX")
    corr_60d: Optional[float] = Field(None, description="60-day correlation vs VNINDEX")
    beta_20d: Optional[float] = Field(None, description="20-day beta vs VNINDEX")
    beta_60d: Optional[float] = Field(None, description="60-day beta vs VNINDEX")
    rs_market_20d: Optional[float] = Field(None, description="20-day relative strength vs market")
    corr_sector_20d: Optional[float] = Field(None, description="20-day correlation vs sector")
    rs_sector_20d: Optional[float] = Field(None, description="20-day relative strength vs sector")
    sector_rank: Optional[int] = Field(None, description="Rank within sector")
    sector_total: Optional[int] = Field(None, description="Total stocks in sector")

    model_config = {"from_attributes": True}


class SectorDailyBenchmarkSchema(BaseModel):
    """Sector benchmark data."""
    icb_code: str = Field(..., description="ICB Level 2 sector code")
    date: date_type = Field(..., description="Trading date")
    mcap_weighted_return: float = Field(..., description="Market-cap weighted return")
    total_mcap: int = Field(..., description="Total market cap in VND")
    stock_count: int = Field(..., description="Number of stocks in sector")

    model_config = {"from_attributes": True}
