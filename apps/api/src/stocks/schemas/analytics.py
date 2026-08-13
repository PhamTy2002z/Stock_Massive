"""Analytics domain schemas."""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from .common import StrictModel

from src.stocks.schemas.price import VolumeAnomalyLevel


# === Volume Spike Detection Schemas ===


class VolumeSpikeItem(StrictModel):
    """Single stock with volume spike."""
    symbol: str = Field(..., description="Stock ticker")
    company_name: Optional[str] = Field(None, description="Company name")
    exchange: Optional[str] = Field(None, description="Exchange (HOSE/HNX/UPCOM)")
    current_volume: int = Field(..., description="Current session volume")
    avg_volume_20d: int = Field(..., description="20-day average volume")
    spike_ratio: float = Field(..., description="Volume spike ratio (current/avg)")
    price_change_pct: Optional[float] = Field(None, description="Price change %")
    close_price: Optional[float] = Field(None, description="Latest close price")
    anomaly_level: VolumeAnomalyLevel = Field(..., description="Anomaly severity")
    icb_code: Optional[str] = Field(None, description="ICB Level 2 code")
    icb_name: Optional[str] = Field(None, description="ICB Level 2 name")


class IndustryVolumeSpikeGroup(StrictModel):
    """Volume spikes grouped by ICB industry."""
    icb_code: str = Field(..., description="ICB Level 2 code")
    icb_name: str = Field(..., description="Industry name (Vietnamese)")
    spike_count: int = Field(..., description="Number of stocks with spikes")
    avg_spike_ratio: float = Field(..., description="Average spike ratio in group")
    stocks: List[VolumeSpikeItem] = Field(default_factory=list, description="Stocks in group")


class VolumeSpikeMetadata(StrictModel):
    """Metadata for volume spike response."""
    calculation_time_ms: int = Field(..., description="Calculation time in milliseconds")
    cache_hit: bool = Field(default=False, description="Whether result was cached")
    symbols_processed: int = Field(default=0, description="Total symbols analyzed")
    symbols_with_spikes: int = Field(default=0, description="Symbols meeting threshold")


class VolumeSpikeResponse(StrictModel):
    """Response for volume spikes endpoint."""
    trade_date: date = Field(..., description="Trading date analyzed")
    total_spikes: int = Field(..., description="Total stocks with volume spikes")
    industries: List[IndustryVolumeSpikeGroup] = Field(
        default_factory=list, description="Spikes grouped by industry"
    )
    metadata: VolumeSpikeMetadata = Field(..., description="Response metadata")
