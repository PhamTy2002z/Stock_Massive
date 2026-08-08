"""Price domain schemas."""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from .common import StrictModel


class PriceLevel(StrictModel):
    """Single price level for bid/ask."""

    price: float
    volume: int


class PriceDepthResponse(StrictModel):
    """Price depth with bid/ask levels."""

    symbol: str
    bid_1: PriceLevel
    bid_2: Optional[PriceLevel] = None
    bid_3: Optional[PriceLevel] = None
    ask_1: PriceLevel
    ask_2: Optional[PriceLevel] = None
    ask_3: Optional[PriceLevel] = None
    total_bid_volume: int
    total_ask_volume: int
    spread: float
    spread_percent: float
    timestamp: datetime


class VolumeAnomalyLevel(str, Enum):
    """Anomaly severity levels based on volume ratio thresholds."""

    NORMAL = "normal"
    ELEVATED = "elevated"  # 1.5x-2x
    HIGH = "high"  # 2x-3x
    VERY_HIGH = "very_high"  # >3x


class StockPrice(StrictModel):
    """Historical OHLCV price data."""

    time: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class IntradayTick(StrictModel):
    """Intraday tick data."""

    time: datetime
    price: float
    volume: int
    accumulated_vol: Optional[int] = None  # Not always provided by vnstock
    accumulated_val: Optional[int] = None  # Not always provided by vnstock
    match_type: str


class PriceBoardItem(StrictModel):
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


class MarketIndexItem(StrictModel):
    """Market index data (VN-INDEX, VN30, etc.)."""

    symbol: str
    name: str
    value: float
    change: float
    change_pct: float


# === Intraday Bar Schemas ===


class IntradayBarCreate(StrictModel):
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


class IntradayCollectionResult(StrictModel):
    """Result of intraday data collection operation."""

    success: list[str] = Field(default_factory=list)
    failed: list[dict] = Field(default_factory=list)
    total_bars: int = 0


# === Volume Analysis Schemas ===


class VolumeTimePeriod(StrictModel):
    """Volume data for a specific time period within trading session."""

    hour: int
    minute_bucket: int  # 0, 5, 10, 15, ...
    time_label: str  # "09:00", "09:05", etc.
    avg_volume: float
    total_volume: int
    sample_count: int


class VolumeAnalysisResponse(StrictModel):
    """Response for volume analysis endpoint."""

    symbol: str
    days_analyzed: int
    trading_session: str = "09:00-15:00"
    peak_periods: list[VolumeTimePeriod]
    generated_at: datetime


# === Volume Anomaly Detection Schemas ===


class VolumeTimeSlot(StrictModel):
    """Volume data for a single 5-minute time slot with anomaly detection."""

    hour: int
    minute_bucket: int  # 0, 5, 10, 15, ...
    time_label: str  # "09:00", "09:05", etc.
    current_volume: int  # Latest day's volume
    avg_volume: float  # N-day average baseline
    volume_ratio: float  # current / avg
    anomaly_level: VolumeAnomalyLevel
    sample_count: int  # Number of days in baseline


class VolumeAnomalyResponse(StrictModel):
    """Response for volume anomaly detection endpoint."""

    symbol: str
    days_analyzed: int
    trading_session: str = "09:00-15:00"
    time_slots: list[VolumeTimeSlot]  # All 72 slots
    generated_at: datetime
    latest_date: Optional[date] = None  # Date of current_volume data
