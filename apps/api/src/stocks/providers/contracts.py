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


class BatchTooLarge(Exception):
    """The provider refused a batch for its size rather than its contents.

    Raised by an adapter when the gateway gives up on a request — measured as a
    504 — so the caller knows the same symbols asked for in smaller batches may
    well succeed. It says nothing about the provider's health, which is why it
    is a type of its own rather than one more provider error: a caller that
    cannot tell the two apart either gives up on data it could have had, or
    retries a genuine outage in halves.
    """


class ProviderSource(str, Enum):
    """Upstream sources approved for the internal VN30 pilot."""

    FIINQUANT = "fiinquant"
    VNSTOCK = "vnstock"


class Capability(str, Enum):
    """Data classes with independent provider ownership."""

    MARKET = "market"
    VALUATION = "valuation"
    REFERENCE = "reference"
    FUNDAMENTAL = "fundamental"


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


class SourceOwnership(InternalSnapshot):
    """One row of the Main/Cover table measured in ``docs/adr/0002``.

    ``main`` serves the capability. ``cover`` serves only the part the main
    source cannot reach — outside the Universe, or deeper history than it is
    granted — and is never a runtime fallback: the two sources disagree on
    units, so silently swapping them would produce wrong numbers that look
    right. Readers ask for the cover source by name or not at all.
    """

    main: ProviderSource
    cover: ProviderSource | None = None

    @model_validator(mode="after")
    def validate_distinct_sources(self) -> "SourceOwnership":
        if self.cover is not None and self.cover is self.main:
            raise ValueError("cover source must differ from the main source")
        return self

    def owns(self, source: ProviderSource) -> bool:
        return source is self.main or source is self.cover


SOURCE_OWNERSHIP_BY_CAPABILITY: Mapping[Capability, SourceOwnership] = MappingProxyType(
    {
        Capability.MARKET: SourceOwnership(
            main=ProviderSource.FIINQUANT,
            cover=ProviderSource.VNSTOCK,
        ),
        Capability.VALUATION: SourceOwnership(
            main=ProviderSource.FIINQUANT,
            cover=ProviderSource.VNSTOCK,
        ),
        Capability.REFERENCE: SourceOwnership(main=ProviderSource.VNSTOCK),
        Capability.FUNDAMENTAL: SourceOwnership(main=ProviderSource.VNSTOCK),
    }
)


def main_source(capability: Capability) -> ProviderSource:
    """Return the source that serves this capability by default."""
    return SOURCE_OWNERSHIP_BY_CAPABILITY[capability].main


def cover_source(capability: Capability) -> ProviderSource | None:
    """Return the source covering what the main source cannot reach, if any."""
    return SOURCE_OWNERSHIP_BY_CAPABILITY[capability].cover


def owns_capability(capability: Capability, source: ProviderSource) -> bool:
    """Report whether this source is allowed to carry this capability at all."""
    return SOURCE_OWNERSHIP_BY_CAPABILITY[capability].owns(source)


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
    """Source-neutral hot market fields written by the collector.

    Every ``*_price`` and ``*_vnd`` field is denominated in ``price_unit``.
    Traded quantity is named ``*_volume`` and traded money ``*_value_vnd``, and
    no field carries both words: the provider reports active buy/sell as
    quantity but foreign buy/sell as money, so mixing the two silently changes
    the unit. ``market_cap_vnd`` is money but not traded, so it stays outside
    that pair; it is reported by the provider rather than derived from
    ``ReferenceSnapshot.canonical_shares()``.
    """

    price_unit: PriceUnit = PriceUnit.VND
    last_price: float | None = Field(default=None, gt=0)
    reference_price: float | None = Field(default=None, gt=0)
    open_price: float | None = Field(default=None, gt=0)
    high_price: float | None = Field(default=None, gt=0)
    low_price: float | None = Field(default=None, gt=0)
    ceiling_price: float | None = Field(default=None, gt=0)
    floor_price: float | None = Field(default=None, gt=0)
    change_pct: float | None = None
    volume: int | None = Field(default=None, ge=0)
    total_value_vnd: float | None = Field(default=None, ge=0)
    active_buy_volume: int | None = Field(default=None, ge=0)
    active_sell_volume: int | None = Field(default=None, ge=0)
    foreign_buy_volume: int | None = Field(default=None, ge=0)
    foreign_sell_volume: int | None = Field(default=None, ge=0)
    foreign_buy_value_vnd: float | None = Field(default=None, ge=0)
    foreign_sell_value_vnd: float | None = Field(default=None, ge=0)
    foreign_net_value_vnd: float | None = None
    market_cap_vnd: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_foreign_flow(self) -> "MarketSnapshot":
        """Bound the net foreign flow by the gross flow it is drawn from.

        The provider reports the net directly, so it is not recomputed here:
        put-through deals and rounding legitimately move it away from buy minus
        sell. What can never happen is a net larger than the gross, which is
        what a unit slip between the three fields looks like.
        """
        if (
            self.foreign_net_value_vnd is not None
            and self.foreign_buy_value_vnd is not None
            and self.foreign_sell_value_vnd is not None
            and abs(self.foreign_net_value_vnd)
            > self.foreign_buy_value_vnd + self.foreign_sell_value_vnd
        ):
            raise ValueError(
                "foreign net value cannot exceed foreign buy plus sell value"
            )
        return self


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


class ValuationSnapshot(SymbolSnapshot):
    """Ratios as published upstream, kept apart from statement-derived numbers.

    These arrive already computed from the ``valuation`` main source, so they
    are stored as reported rather than recomputed from ``FundamentalSnapshot``.
    """

    provider_pe: float | None = None
    provider_pb: float | None = None


class FundamentalSnapshot(SymbolSnapshot):
    """Financial-statement inputs used for app-owned valuation history."""

    period_end: date
    trailing_12_month_net_income_vnd: float | None = None
    parent_equity_vnd: float | None = None


class MarketDataProvider(Protocol):
    """Collect normalized hot market snapshots for a bounded universe."""

    source: ProviderSource

    def fetch_market(self, symbols: Sequence[str]) -> Sequence[MarketSnapshot]: ...


class ValuationDataProvider(Protocol):
    """Collect provider-published valuation ratios for a bounded universe.

    Ratios are a daily series rather than a single current value, so the window
    is required rather than defaulted: a collector asks for the session that
    just closed while a backfill asks for a stretch of history, and a default
    would quietly hand one of them the other's window.
    """

    source: ProviderSource

    def fetch_valuation(
        self,
        symbols: Sequence[str],
        from_date: date,
        to_date: date,
    ) -> Sequence[ValuationSnapshot]: ...


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
