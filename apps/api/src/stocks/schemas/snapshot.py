"""Public shape of what the store holds for one symbol.

These are REST response models, deliberately separate from the ingestion
contracts in ``src.stocks.providers.contracts``: the wire shape is a promise to
the interface, and it must not move every time a provider's normalized form
does.

The separation costs something. A section is built by dumping a snapshot into
the model here, and these models forbid unknown fields, so a field added to an
ingestion contract and forgotten here raises while a request is being served —
a 500 rather than a quietly missing number. ``test_snapshot_serving`` compares
the two field-by-field so the mismatch is caught in the suite instead.
"""

from datetime import date, datetime

from .common import StrictModel


class SnapshotSection(StrictModel):
    """Where one part of the answer came from, and how old it is.

    Age travels with the data rather than beside it, because a caller holding a
    figure without its age has no way to ask later.
    """

    source: str
    effective_at: datetime
    observed_at: datetime
    age_seconds: int
    stale: bool


class MarketData(StrictModel):
    """The traded session, in VND, as the collector normalized it.

    ``price_basis`` says what the ``*_price`` fields mean with respect to
    corporate actions — ``raw`` is what the exchange published for that session,
    ``adjusted_at_source`` is what the provider had already rescaled when it
    answered. It reaches the price fields and nothing else: every ``*_volume``
    and every ``*_value_vnd`` is reported as traded, on either basis, and
    nothing here rescales one (``docs/adr/0006``).
    """

    price_basis: str
    price_unit: str
    last_price: float | None = None
    reference_price: float | None = None
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    ceiling_price: float | None = None
    floor_price: float | None = None
    change_pct: float | None = None
    volume: int | None = None
    total_value_vnd: float | None = None
    active_buy_volume: int | None = None
    active_sell_volume: int | None = None
    foreign_buy_volume: int | None = None
    foreign_sell_volume: int | None = None
    foreign_buy_value_vnd: float | None = None
    foreign_sell_value_vnd: float | None = None
    foreign_net_value_vnd: float | None = None
    market_cap_vnd: float | None = None


class MarketSection(SnapshotSection):
    data: MarketData


class ValuationData(StrictModel):
    """Ratios as the provider published them, not recomputed here."""

    provider_pe: float | None = None
    provider_pb: float | None = None


class ValuationSection(SnapshotSection):
    data: ValuationData


class ShareCountItem(StrictModel):
    """A share count that keeps saying which count it is.

    Outstanding, listed and issued are different numbers, and a response that
    dropped the distinction would invite someone to divide by the wrong one.
    """

    share_type: str
    value: int


class ReferenceData(StrictModel):
    """Ownership structure — slow-changing, and never inferred from price."""

    shares: list[ShareCountItem] = []
    current_foreign_room: int | None = None
    total_foreign_room: int | None = None


class ReferenceSection(SnapshotSection):
    data: ReferenceData


class FundamentalData(StrictModel):
    """Statement inputs, dated by the period they close rather than by run."""

    period_end: date
    trailing_12_month_net_income_vnd: float | None = None
    parent_equity_vnd: float | None = None


class FundamentalSection(SnapshotSection):
    data: FundamentalData


class SymbolSnapshotResponse(StrictModel):
    """Everything the store holds for one symbol, part by part.

    A part the store has nothing for is ``null`` rather than absent: the symbol
    is watched either way, and the interface needs to tell "not collected yet"
    apart from "this symbol is not ours".
    """

    symbol: str
    market: MarketSection | None = None
    valuation: ValuationSection | None = None
    reference: ReferenceSection | None = None
    fundamental: FundamentalSection | None = None


class SeriesPoint(StrictModel):
    """One session in a series, with the source that answered for it.

    The source travels per point rather than per series because history is two
    providers end to end — the Cover Source loaded the deep years, the Main
    Source writes each session as it closes — and a reader comparing a 2019 bar
    with last week's is comparing two measurements, not one.
    """

    effective_at: datetime
    source: str


class MarketBar(SeriesPoint):
    """One bar. Aggregated bars carry the source of the sessions they span.

    ``price_basis`` travels with the bar for the same reason the source does:
    the deep years were loaded already adjusted by the Cover Source and every
    session since is raw, so the two ends of a long chart are two different
    measurements and the seam has to stay visible (``docs/adr/0002``).

    At ``1D`` it is one session's own basis. A weekly or monthly bar that spans
    the seam reports ``mixed`` rather than picking a side: those sessions are
    not on one scale, and naming either of them would be a claim about prices
    that were never on it. That value exists at this level only — a stored
    session is always one basis or the other.
    """

    price_basis: str
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    close_price: float | None = None
    volume: int | None = None
    total_value_vnd: float | None = None


class ValuationPoint(SeriesPoint):
    provider_pe: float | None = None
    provider_pb: float | None = None


class SeriesResponse(StrictModel):
    """A stretch of sessions, dated the same way a snapshot is.

    ``age_seconds`` and ``stale`` describe the newest session only. The rest of
    the series is old by definition, and a flag per point would turn a healthy
    decade into a decade of warnings. ``age_seconds`` is null for a window the
    store holds no sessions in, which is what a shut week looks like.
    """

    symbol: str
    age_seconds: int | None = None
    stale: bool = False


class MarketSeriesResponse(SeriesResponse):
    interval: str
    points: list[MarketBar] = []


class ValuationSeriesResponse(SeriesResponse):
    points: list[ValuationPoint] = []
