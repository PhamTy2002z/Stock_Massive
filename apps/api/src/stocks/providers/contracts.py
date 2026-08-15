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


class PriceBasis(str, Enum):
    """What a stored session's prices mean with respect to corporate actions.

    Written by the Adapter, which is the only code that knows which flag it
    passed upstream, and never inferred from a session date: the seam between
    the two eras is ``HistoryWindow.crossover()`` evaluated on the day a
    symbol's Backfill ran, so each symbol's seam falls where its own Backfill
    put it (``docs/adr/0006``).
    """

    # The numbers the exchange published for that session, permanently. Nothing
    # rewrites them when a later action rescales the symbol; adjustment is a
    # read-time transform over a persisted Corporate Action series.
    RAW = "raw"

    # Rescaled by the provider for every action up to the moment it answered.
    # Not recomputable from what is stored, and it decays with every action
    # since — which is why a window lying wholly here is refused rather than
    # adjusted.
    ADJUSTED_AT_SOURCE = "adjusted_at_source"


# What a market payload written today looks like. Version 1 is the unstamped
# era: those rows carry no Price Basis, and the one-time repair in
# ``d1f4b7c02e93`` moves them here rather than re-collecting them, because
# schema_version is part of uq_provider_snapshot_identity and a re-fetch under 2
# would write a second row beside the first.
MARKET_SCHEMA_VERSION = 2


class ShareType(str, Enum):
    """Share-count semantics that must not be silently interchanged."""

    OUTSTANDING = "outstanding"
    LISTED = "listed"
    ISSUED = "issued"


class Exchange(str, Enum):
    """The boards a Vietnamese equity can be listed on.

    An enum rather than free text because eligibility is decided by it: the
    Profit Ranking Census ranks HOSE and HNX and excludes UPCOM, so a board name
    arriving in one of its other spellings — "HSX" for HOSE is in use elsewhere
    in this codebase — would drop real companies out of the cohort without
    anything failing.
    """

    HOSE = "HOSE"
    HNX = "HNX"
    UPCOM = "UPCOM"

    @classmethod
    def parse(cls, value: str) -> "Exchange":
        """Read a provider's spelling of a board name, or refuse it."""
        text = value.strip().upper()
        if text == "HSX":
            return cls.HOSE
        return cls(text)


# The boards a Profit Ranking Census ranks. UPCOM is excluded by ADR-0003: it
# lists companies under lighter disclosure rules, so a profit figure there is not
# comparable with one from the two main boards.
RANKED_EXCHANGES: frozenset[Exchange] = frozenset({Exchange.HOSE, Exchange.HNX})


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

    ``price_basis`` reaches the ``*_price`` fields and nothing else. Every
    ``*_volume`` is the count of shares that changed hands in that session, and
    every ``*_value_vnd`` the money they changed hands for, both exactly as
    reported and on either basis: no code here rescales a quantity or a sum of
    money, because a share-count-changing action moves the unit of the former
    while leaving the latter alone, and the price factor is not the quantity
    factor anyway (``docs/adr/0006``).
    """

    # Required, with no default on purpose: a payload that never says what its
    # prices mean must fail validation loudly rather than be read as raw.
    price_basis: PriceBasis
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
    def validate_schema_version(self) -> "MarketSnapshot":
        """Refuse a market payload claiming a version older than the basis.

        The basis was introduced at ``MARKET_SCHEMA_VERSION``, so a row that
        carries one and calls itself version 1 describes a store state that has
        never existed: the repair moves a row's version and its basis together,
        and both Adapters write them together. Left unchecked, such a row would
        be re-stamped by a repair keyed on version 1 — or worse, saved beside
        the row it is a copy of, since ``schema_version`` is part of the store's
        identity. Compared with ``>=`` rather than ``==`` so that a later
        version can still be read by the contract that introduced this one.
        """
        if self.metadata.schema_version < MARKET_SCHEMA_VERSION:
            raise ValueError(
                "a market snapshot carrying a price basis cannot be at schema "
                f"version {self.metadata.schema_version}; "
                f"the basis exists from {MARKET_SCHEMA_VERSION} onward"
            )
        return self

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


class MarketHistoryProvider(Protocol):
    """Read a stretch of one symbol's session history.

    Per symbol rather than per batch, unlike ``MarketDataProvider``: a window of
    sessions is what a provider will answer for one ticker at a time, and both
    callers — the one-time deep Backfill and the bounded Warm-up — walk symbols
    one at a time anyway.

    ``source`` is part of the contract because the two callers are not free to
    use either provider. A Warm-up reads the Main Source only (``docs/adr/0005``)
    while a Backfill reads the Cover Source for the deep years, and a reader that
    cannot tell which one it was handed cannot enforce that.
    """

    source: ProviderSource

    def fetch_market_history(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
    ) -> Sequence[MarketSnapshot]: ...


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


class ListingEntry(InternalSnapshot):
    """One company as the exchanges currently list it.

    Not a ``SymbolSnapshot``: it carries no per-symbol observation metadata
    because it is not an observation *about* a company the system follows. It is
    a line from the market's own register, and the whole register is read at once
    and stamped once.
    """

    symbol: str
    exchange: Exchange
    is_listed: bool
    company_name: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        try:
            return validate_symbol(value)
        except StockServiceError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("exchange", mode="before")
    @classmethod
    def normalize_exchange(cls, value: object) -> object:
        return Exchange.parse(value) if isinstance(value, str) else value


class ListingRosterProvider(Protocol):
    """Read the whole market's listing register in one pass.

    Market-wide and unbatched by design: the Profit Ranking Census has to know
    which companies exist before it can decide which fifty to rank, and asking
    per symbol would mean already knowing the answer.
    """

    source: ProviderSource

    def fetch_listing_roster(self) -> Sequence[ListingEntry]: ...


class FundamentalDataProvider(Protocol):
    """Collect scheduled fundamental inputs for app-owned analytics."""

    source: ProviderSource

    def fetch_fundamentals(
        self,
        symbols: Sequence[str],
    ) -> Sequence[FundamentalSnapshot]: ...


class CorporateActionEvent(InternalSnapshot):
    """One row of a company's event feed, as the provider declares it.

    Deliberately the provider's own vocabulary and nothing more. What kind of
    action this is, whether it moves the share count, and what Adjustment Factor
    it implies are all read off these fields by
    ``src.stocks.signals.corporate_actions`` — an adapter that decided them here
    would be one place the provider's wording and this system's arithmetic could
    drift apart silently.

    Three fields carry the whole load, and two of them are traps:

    - ``exercise_ratio`` means **two different things** by ``event_code``. On an
      ``ISS`` row it is the share ratio: 0.15 is fifteen new shares per hundred
      held. On a ``DIV`` row it is the cash paid as a fraction of the 10,000 VND
      par — TCB's 700 VND dividend arrives as 0.07 — and reading that as a share
      ratio would invent a 7% bonus issue out of a cash payment.
    - ``ex_date`` is optional because the feed leaves it null on real rows. TCB's
      2026 bonus issue at ratio 0.6 carries only a ``public_date``.
    - ``title`` is free text, and the only place the *kind* of a share issue
      appears: "Stock dividend ratio 15.0%", "Rights issue ratio 10.0%", "ESOP
      ratio 0.3%" all arrive as ``ISS``. Kept verbatim rather than parsed here,
      so what the provider said stays readable next to what was made of it.
    """

    symbol: str
    event_code: str
    title: str
    ex_date: date | None = None
    record_date: date | None = None
    public_date: date | None = None
    exercise_ratio: float | None = None
    value_per_share: float | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        try:
            return validate_symbol(value)
        except StockServiceError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("event_code")
    @classmethod
    def normalize_event_code(cls, value: str) -> str:
        code = value.strip().upper()
        if not code:
            raise ValueError("a corporate action must carry an event code")
        return code

    @model_validator(mode="after")
    def require_something_to_key_on(self) -> "CorporateActionEvent":
        """Refuse a row that cannot be told apart from the next one.

        Identity is ``(symbol, ex-date, event code)``, and a row with neither
        date is not addressable under it or under the fallback the store keeps
        for null ex-dates. Stored anyway, such a row would be written afresh on
        every collection run — the one thing an idempotent load must not do.
        """
        if self.ex_date is None and self.public_date is None:
            raise ValueError(
                "a corporate action needs an ex-date or a public date: with "
                "neither it cannot be stored idempotently"
            )
        return self


class CorporateActionProvider(Protocol):
    """Read one company's declared corporate actions.

    Per symbol because the feed is: there is no batched form, which is what makes
    this a slow cadence rather than part of the per-session cycle. Corporate
    actions are annual events, so a Universe walked over days costs nothing.
    """

    source: ProviderSource

    def fetch_corporate_actions(
        self,
        symbol: str,
    ) -> Sequence[CorporateActionEvent]: ...
