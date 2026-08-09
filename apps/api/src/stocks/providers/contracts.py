"""Provider boundaries and source-neutral stock snapshots.

These models are internal ingestion contracts. Public REST response models stay
owned by ``src.stocks.schemas`` and are intentionally not coupled to a data
provider.
"""

from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Protocol, Sequence

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas.common import StrictModel
from ..shared import StockServiceError, validate_symbol


class ProviderSource(str, Enum):
    """Upstream sources approved for the internal VN30 pilot."""

    FIINQUANT = "fiinquant"
    VNSTOCK = "vnstock"


class Capability(str, Enum):
    """Data classes with independent provider ownership."""

    MARKET = "market"
    REFERENCE = "reference"
    FUNDAMENTAL = "fundamental"


PRIMARY_SOURCE_BY_CAPABILITY: Mapping[Capability, ProviderSource] = MappingProxyType(
    {
        Capability.MARKET: ProviderSource.FIINQUANT,
        Capability.REFERENCE: ProviderSource.VNSTOCK,
        Capability.FUNDAMENTAL: ProviderSource.VNSTOCK,
    }
)


class PriceUnit(str, Enum):
    """Canonical price unit used after provider normalization."""

    VND = "VND"


class ShareType(str, Enum):
    """Share-count semantics that must not be silently interchanged."""

    OUTSTANDING = "outstanding"
    LISTED = "listed"
    ISSUED = "issued"


class InternalSnapshot(StrictModel):
    """Immutable base for records crossing a provider boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SnapshotMetadata(InternalSnapshot):
    """Traceability shared by every normalized snapshot."""

    source: ProviderSource
    effective_at: datetime
    observed_at: datetime
    schema_version: int = Field(default=1, ge=1)

    @field_validator("effective_at", "observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("snapshot timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_timestamp_order(self) -> "SnapshotMetadata":
        if self.effective_at > self.observed_at:
            raise ValueError("effective_at cannot be later than observed_at")
        return self


class SymbolSnapshot(InternalSnapshot):
    """Snapshot for one canonical Vietnamese equity symbol."""

    symbol: str
    metadata: SnapshotMetadata

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        try:
            return validate_symbol(value)
        except StockServiceError as exc:
            raise ValueError(str(exc)) from exc


class MarketSnapshot(SymbolSnapshot):
    """Source-neutral hot market fields written by the FiinQuant collector."""

    price_unit: PriceUnit = PriceUnit.VND
    last_price: float | None = Field(default=None, gt=0)
    reference_price: float | None = Field(default=None, gt=0)
    open_price: float | None = Field(default=None, gt=0)
    high_price: float | None = Field(default=None, gt=0)
    low_price: float | None = Field(default=None, gt=0)
    change_pct: float | None = None
    volume: int | None = Field(default=None, ge=0)
    foreign_buy_volume: int | None = Field(default=None, ge=0)
    foreign_sell_volume: int | None = Field(default=None, ge=0)


class ShareCount(InternalSnapshot):
    """A share count carrying its exact business meaning."""

    share_type: ShareType
    value: int = Field(gt=0)


class ReferenceSnapshot(SymbolSnapshot):
    """Slow-changing company and ownership fields collected from vnstock."""

    shares: tuple[ShareCount, ...] = ()
    current_foreign_room: int | None = Field(default=None, ge=0)
    total_foreign_room: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_reference_fields(self) -> "ReferenceSnapshot":
        share_types = [item.share_type for item in self.shares]
        if len(share_types) != len(set(share_types)):
            raise ValueError("share types must be unique within a snapshot")
        if (
            self.current_foreign_room is not None
            and self.total_foreign_room is not None
            and self.current_foreign_room > self.total_foreign_room
        ):
            raise ValueError("current foreign room cannot exceed total foreign room")
        return self

    def canonical_shares(self) -> ShareCount | None:
        """Choose the approved market-cap input without losing raw semantics."""
        by_type = {item.share_type: item for item in self.shares}
        for share_type in (
            ShareType.OUTSTANDING,
            ShareType.LISTED,
            ShareType.ISSUED,
        ):
            if share_type in by_type:
                return by_type[share_type]
        return None


class FundamentalSnapshot(SymbolSnapshot):
    """Inputs used for app-owned valuation history."""

    period_end: date
    trailing_12_month_net_income_vnd: float | None = None
    parent_equity_vnd: float | None = None
    provider_pe: float | None = None
    provider_pb: float | None = None


class MarketDataProvider(Protocol):
    """Collect normalized hot market snapshots for a bounded universe."""

    source: ProviderSource

    def fetch_market(self, symbols: Sequence[str]) -> Sequence[MarketSnapshot]: ...


class ReferenceDataProvider(Protocol):
    """Collect scheduled reference snapshots without serving user requests."""

    source: ProviderSource

    def fetch_reference(self, symbols: Sequence[str]) -> Sequence[ReferenceSnapshot]: ...


class FundamentalDataProvider(Protocol):
    """Collect scheduled fundamental inputs for app-owned analytics."""

    source: ProviderSource

    def fetch_fundamentals(
        self,
        symbols: Sequence[str],
    ) -> Sequence[FundamentalSnapshot]: ...
