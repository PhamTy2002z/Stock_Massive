"""Stable public contracts for the five Market Monitor lenses.

These schemas are intentionally separate from provider and realtime ingestion
contracts. A monitor response is a derived interpretation of stored evidence;
it must keep the evidence time, source, coverage, unit, and method needed to
judge that interpretation without exposing provider payloads.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Self

from pydantic import Field, field_validator, model_validator

from src.stocks.schemas.common import StrictModel


class MonitorExchange(str, Enum):
    ALL = "ALL"
    HOSE = "HOSE"
    HNX = "HNX"


class MonitorState(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    STALE = "stale"
    DISCONNECTED = "disconnected"
    UNAVAILABLE = "unavailable"


class MonitorLens(str, Enum):
    OVERVIEW = "overview"
    BREADTH = "breadth"
    FLOW = "flow"
    SECTORS = "sectors"
    STOCKS = "stocks"


class StockLens(str, Enum):
    OVERVIEW = "overview"
    TREND = "trend"
    FLOW = "flow"
    VALUATION = "valuation"


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class MonitorCoverage(StrictModel):
    """How much of the requested exchange scope produced a valid reading."""

    eligible: int = Field(ge=0)
    evaluated: int = Field(ge=0)
    missing: int = Field(ge=0)
    state: MonitorState

    @model_validator(mode="after")
    def validate_counts_and_state(self) -> Self:
        if self.evaluated > self.eligible:
            raise ValueError("evaluated coverage cannot exceed eligible coverage")
        if self.missing != self.eligible - self.evaluated:
            raise ValueError("missing coverage must equal eligible minus evaluated")
        if self.state is MonitorState.COMPLETE and self.evaluated != self.eligible:
            raise ValueError("complete coverage requires every eligible symbol")
        if self.state is MonitorState.PARTIAL and not 0 < self.evaluated < self.eligible:
            raise ValueError("partial coverage requires some but not all eligible symbols")
        if self.state is MonitorState.UNAVAILABLE and self.evaluated != 0:
            raise ValueError("unavailable coverage cannot contain evaluated symbols")
        return self


class MonitorSource(StrictModel):
    source: str = Field(min_length=1)
    effective_at: datetime
    observed_at: datetime
    freshness_seconds: float = Field(ge=0)
    stale: bool

    @field_validator("effective_at", "observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("source times must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_time_order(self) -> Self:
        if self.effective_at > self.observed_at:
            raise ValueError("source effective time cannot follow observation time")
        return self


class MonitorMeta(StrictModel):
    exchange: MonitorExchange
    as_of: datetime
    generated_at: datetime
    state: MonitorState
    coverage: MonitorCoverage
    realtime_coverage: MonitorCoverage | None = None
    sources: tuple[MonitorSource, ...] = ()
    issues: tuple[str, ...] = ()
    method_versions: dict[str, str]

    @field_validator("as_of", "generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("monitor times must be timezone-aware")
        return value

    @field_validator("method_versions")
    @classmethod
    def require_method_versions(cls, value: dict[str, str]) -> dict[str, str]:
        if not value or any(not key.strip() or not version.strip() for key, version in value.items()):
            raise ValueError("at least one non-empty method version is required")
        return value

    @model_validator(mode="after")
    def validate_times_and_state(self) -> Self:
        if self.as_of > self.generated_at:
            raise ValueError("monitor as-of cannot follow generation time")
        if self.state is MonitorState.COMPLETE and self.coverage.state is not MonitorState.COMPLETE:
            raise ValueError("complete monitor state requires complete coverage")
        if self.state is MonitorState.UNAVAILABLE and self.coverage.evaluated != 0:
            raise ValueError("unavailable monitor state cannot carry evaluated coverage")
        return self


MetricNumber = float | int


class MetricValue(StrictModel):
    """One comparable figure with enough context to interpret or refuse it."""

    value: MetricNumber | None
    unit: str = Field(min_length=1)
    as_of: datetime
    method: str = Field(min_length=1)
    issues: tuple[str, ...] = ()

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("metric as-of must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_reason_for_absence(self) -> Self:
        if self.value is None and not self.issues:
            raise ValueError("a missing metric requires at least one reason")
        return self


class EvidenceFlag(StrictModel):
    value: bool | None
    as_of: datetime
    method: str = Field(min_length=1)
    issues: tuple[str, ...] = ()

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evidence as-of must be timezone-aware")
        return value

    @model_validator(mode="after")
    def require_reason_for_absence(self) -> Self:
        if self.value is None and not self.issues:
            raise ValueError("a missing evidence flag requires at least one reason")
        return self


class MonitorSeriesPoint(StrictModel):
    session_date: date
    value: float | None
    issues: tuple[str, ...] = ()


class IndexPulse(StrictModel):
    symbol: str
    name: str
    level: MetricValue
    change: MetricValue
    change_pct: MetricValue
    above_ma20: EvidenceFlag
    above_ma50: EvidenceFlag
    above_ma200: EvidenceFlag


class BreadthSummary(StrictModel):
    advancing: MetricValue
    declining: MetricValue
    unchanged: MetricValue
    advance_decline_ratio: MetricValue
    above_ma20_pct: MetricValue
    above_ma50_pct: MetricValue
    above_ma200_pct: MetricValue


class ValuationSummary(StrictModel):
    market_pe: MetricValue
    market_pb: MetricValue
    pe_percentile: MetricValue
    pb_percentile: MetricValue
    coverage: MonitorCoverage


class DistributionBucket(StrictModel):
    key: str
    label: str
    count: int = Field(ge=0)


class SectorMonitorRow(StrictModel):
    code: str
    name: str
    exchange: MonitorExchange
    return_1d_pct: MetricValue
    return_5d_pct: MetricValue
    return_20d_pct: MetricValue
    relative_strength_1d_pct: MetricValue
    relative_strength_5d_pct: MetricValue
    relative_strength_20d_pct: MetricValue
    advancing_pct: MetricValue
    liquidity_ratio: MetricValue
    rotation: str
    coverage: MonitorCoverage


class FlowMonitorRow(StrictModel):
    symbol: str
    exchange: MonitorExchange
    foreign_net_1d_vnd: MetricValue
    foreign_net_5d_vnd: MetricValue
    foreign_net_20d_vnd: MetricValue
    foreign_flow_over_adtv: MetricValue
    active_flow_over_adtv: MetricValue
    quadrant: str | None = None


class StockMonitorRow(StrictModel):
    symbol: str
    name: str
    exchange: MonitorExchange
    sector_code: str | None = None
    sector_name: str | None = None
    metrics: dict[str, MetricValue]
    trend: dict[str, EvidenceFlag] = Field(default_factory=dict)
    issues: tuple[str, ...] = ()


class MarketOverviewResponse(StrictModel):
    meta: MonitorMeta
    indices: tuple[IndexPulse, ...]
    breadth: BreadthSummary
    liquidity: MetricValue
    foreign_flow: MetricValue
    active_flow_over_adtv: MetricValue
    valuation: ValuationSummary
    leading_sectors: tuple[SectorMonitorRow, ...] = ()
    lagging_sectors: tuple[SectorMonitorRow, ...] = ()
    notable_stocks: tuple[StockMonitorRow, ...] = ()


class MarketBreadthResponse(StrictModel):
    meta: MonitorMeta
    summary: BreadthSummary
    new_high_20: MetricValue
    new_low_20: MetricValue
    new_high_252: MetricValue
    new_low_252: MetricValue
    advancing_volume_share: MetricValue
    distribution: tuple[DistributionBucket, ...]
    advance_decline_line: tuple[MonitorSeriesPoint, ...]


class MarketFlowResponse(StrictModel):
    meta: MonitorMeta
    foreign_net_1d_vnd: MetricValue
    foreign_net_5d_vnd: MetricValue
    foreign_net_20d_vnd: MetricValue
    active_buy_share: MetricValue
    inflows: tuple[FlowMonitorRow, ...]
    outflows: tuple[FlowMonitorRow, ...]
    reversals: tuple[FlowMonitorRow, ...]


class MarketSectorResponse(StrictModel):
    meta: MonitorMeta
    sectors: tuple[SectorMonitorRow, ...]


class MarketStockPageResponse(StrictModel):
    meta: MonitorMeta
    lens: StockLens
    items: tuple[StockMonitorRow, ...]
    next_cursor: str | None = None


class MarketStockDetailResponse(StrictModel):
    meta: MonitorMeta
    stock: StockMonitorRow
    evidence: dict[str, Any]
