"""Analytics domain schemas."""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from src.stocks.schemas.price import VolumeAnomalyLevel


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


class TopPerformersCollectionResult(BaseModel):
    """Result of top performers collection job."""
    success: int = Field(..., description="Number of records successfully stored")
    failed: int = Field(..., description="Number of failed symbol fetches")
    rate_limited: int = Field(default=0, description="Number of rate-limited requests")
    total_symbols: int = Field(default=0, description="Total symbols processed")
    elapsed_seconds: float = Field(default=0.0, description="Time taken in seconds")
    error: Optional[str] = Field(None, description="Error message if job failed")


# === Volume Spike Detection Schemas ===


class VolumeSpikeItem(BaseModel):
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


class IndustryVolumeSpikeGroup(BaseModel):
    """Volume spikes grouped by ICB industry."""
    icb_code: str = Field(..., description="ICB Level 2 code")
    icb_name: str = Field(..., description="Industry name (Vietnamese)")
    spike_count: int = Field(..., description="Number of stocks with spikes")
    avg_spike_ratio: float = Field(..., description="Average spike ratio in group")
    stocks: List[VolumeSpikeItem] = Field(default_factory=list, description="Stocks in group")


class VolumeSpikeMetadata(BaseModel):
    """Metadata for volume spike response."""
    calculation_time_ms: int = Field(..., description="Calculation time in milliseconds")
    cache_hit: bool = Field(default=False, description="Whether result was cached")
    symbols_processed: int = Field(default=0, description="Total symbols analyzed")
    symbols_with_spikes: int = Field(default=0, description="Symbols meeting threshold")


class VolumeSpikeResponse(BaseModel):
    """Response for volume spikes endpoint."""
    trade_date: date = Field(..., description="Trading date analyzed")
    total_spikes: int = Field(..., description="Total stocks with volume spikes")
    industries: List[IndustryVolumeSpikeGroup] = Field(
        default_factory=list, description="Spikes grouped by industry"
    )
    metadata: VolumeSpikeMetadata = Field(..., description="Response metadata")
