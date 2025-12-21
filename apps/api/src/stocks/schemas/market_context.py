"""Pydantic schemas for market context feature."""
from datetime import date as date_type, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ==================== API Response Schemas ====================


class ChartDataPoint(BaseModel):
    """Single point in normalized price chart."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    stock: float = Field(..., description="Normalized stock price (base 100)")
    vnindex: float = Field(..., description="Normalized VNINDEX (base 100)")
    sector: Optional[float] = Field(None, description="Normalized sector benchmark (base 100)")


class MarketMetrics(BaseModel):
    """Market correlation and beta metrics."""

    beta_20d: Optional[float] = Field(None, description="20-day beta vs VNINDEX")
    beta_60d: Optional[float] = Field(None, description="60-day beta vs VNINDEX")
    correlation_20d: Optional[float] = Field(None, description="20-day correlation vs VNINDEX")
    correlation_60d: Optional[float] = Field(None, description="60-day correlation vs VNINDEX")
    rs_market_20d: Optional[float] = Field(None, description="20-day relative strength vs market")
    rs_sector_20d: Optional[float] = Field(None, description="20-day relative strength vs sector")


class TopPeer(BaseModel):
    """Top performing peer in sector."""

    symbol: str
    change_pct: float


class SectorContext(BaseModel):
    """Sector context information."""

    icb_code: str = Field(..., description="ICB Level 2 code")
    icb_name: str = Field(..., description="Sector name (Vietnamese)")
    rank: int = Field(..., description="Stock rank within sector")
    total: int = Field(..., description="Total stocks in sector")
    top_peers: List[TopPeer] = Field(default_factory=list, description="Top 3 peers")


class PerformanceSummary(BaseModel):
    """Performance comparison summary."""

    stock_return: float = Field(..., description="Stock return % over period")
    vnindex_return: float = Field(..., description="VNINDEX return % over period")
    sector_return: Optional[float] = Field(None, description="Sector return % over period")
    outperform_market: bool = Field(..., description="Stock outperformed market")
    outperform_sector: Optional[bool] = Field(None, description="Stock outperformed sector")


class MarketContextResponse(BaseModel):
    """Market context analysis response."""

    symbol: str = Field(..., description="Stock ticker symbol")
    period: Literal["1M", "3M", "6M", "1Y"] = Field(..., description="Analysis period")
    chart_data: List[ChartDataPoint] = Field(..., description="Normalized price series")
    metrics: MarketMetrics = Field(..., description="Current market metrics")
    sector: Optional[SectorContext] = Field(None, description="Sector context (null if Unclassified)")
    performance: PerformanceSummary = Field(..., description="Performance summary")
    generated_at: str = Field(..., description="Response generation timestamp")

    model_config = {"from_attributes": True}


# ==================== Database Model Schemas ====================


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
