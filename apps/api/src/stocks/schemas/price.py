"""Price domain schemas."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


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
