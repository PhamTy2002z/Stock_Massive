"""Schemas for market overview endpoint."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MarketBreadth(BaseModel):
    """Market breadth showing advances/declines/unchanged counts."""

    advances: int = Field(description="Number of stocks with price increase")
    declines: int = Field(description="Number of stocks with price decrease")
    unchanged: int = Field(description="Number of stocks with no price change")
    total: int = Field(description="Total stocks in calculation")


class TopMoverItem(BaseModel):
    """Top gainer/loser item."""

    symbol: str
    price: float = Field(description="Current price in VND")
    change_pct: float = Field(description="Price change percentage")
    volume: Optional[int] = Field(default=None, description="Trading volume")


class ForeignFlowItem(BaseModel):
    """Foreign flow item for a single stock."""

    symbol: str
    net_value: float = Field(description="Net value in VND")


class ForeignFlowData(BaseModel):
    """Aggregated foreign flow data."""

    net_buy: list[ForeignFlowItem] = Field(description="Top 5 net buy stocks")
    net_sell: list[ForeignFlowItem] = Field(description="Top 5 net sell stocks")
    total_net_value: float = Field(description="Total net value across all stocks")


class TopVolumeItem(BaseModel):
    """Top volume item."""

    symbol: str
    price: float = Field(description="Current price in VND")
    volume: int = Field(description="Trading volume")
    value: float = Field(description="Trading value in VND")


class MarketOverviewResponse(BaseModel):
    """Complete market overview response."""

    market_breadth: MarketBreadth
    top_gainers: list[TopMoverItem] = Field(description="Top 5 gainers")
    top_losers: list[TopMoverItem] = Field(description="Top 5 losers")
    foreign_flow: ForeignFlowData
    top_volume: list[TopVolumeItem] = Field(description="Top 5 by volume")
    generated_at: datetime
