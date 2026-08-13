"""The band a session traded under, and whether it was locked at it.

Two questions, one input. *Which band applied* is a fact about the exchange the
symbol was listed on **that day**; *was the session locked* is that band compared
against the session's own raw high and low. Both are computed here rather than
read off a stored field, because neither stored field can serve:

- ``MarketSnapshot.reference_price`` is the previous session's close from the
  same frame, which the Adapter derived. It is not the exchange's reference
  price, and on an ex-date the two differ by the entitlement.
- ``ceiling_price``/``floor_price`` are ``None`` on every history bar, because
  ``_fetch_history`` passes ``band=None`` deliberately rather than stamp today's
  band onto a 2019 session (``docs/adr/0006``).

Everything here reads ``raw`` prices only. An ``adjusted_at_source`` close is an
unrounded float that has been rescaled for every action since it was observed;
it does not sit on the tick grid a band is defined on, so a comparison against a
limit price is not merely imprecise but meaningless.

Downstream this is a primitive, not a signal. ``prepare_bars()`` counts limit
locks per window and reports them in Window Health, and Corporate Action
confirmation asks the same question in reverse — a gap is "unexplained" only
relative to the band that session permitted.

## What the numbers are, and where they come from

Bands are HOSE ±7%, HNX ±10%, UPCOM ±15%, verified against primary sources in
``docs/research/quant-methods-eod-vn.md`` §0 (HOSE's own trading rules of Feb
2026 citing VNX Decision 22/QĐ-HĐTV; UPCOM from Decision 23/QĐ-HĐTV Art. 18).
The widened first-day and post-suspension bands (±20/±30/±40) are **not**
applied: which of the two a session ran under is not derivable from the store,
because a symbol's first *stored* session is where its Backfill began rather than
where it listed, and a 25-session absence is indistinguishable from a collector
outage. Both cases surface as ``ANCHOR_MISSING`` instead, since a session with no
stored predecessor has no reference price either way.

The rounding rule and the tick grid are pinned against real stored sessions in
``tests/test_price_band.py`` — MBB's 2025-08-14 ceiling at 27,600 off 25,800, and
MWG's 2026-03-09 floor at 77,000 off 82,700 — rather than asserted from a
document alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.models import ListingRoster

from ..providers import Capability, Exchange, MarketSnapshot, PriceBasis, SnapshotStore
from ..providers.normalize import VN_TZ
from ..trading_day import trading_days_before

# The permitted daily move, per board. Decimal rather than float because the
# comparison that matters happens at the tick boundary: 82,700 × 0.93 is
# 76,911 exactly, and a binary float landing a hair either side of a tick
# multiple moves the floor by a whole step.
BAND_LIMIT_BY_EXCHANGE: Mapping[Exchange, Decimal] = MappingProxyType(
    {
        Exchange.HOSE: Decimal("0.07"),
        Exchange.HNX: Decimal("0.10"),
        Exchange.UPCOM: Decimal("0.15"),
    }
)

# HOSE quotes equities in three steps by price level. HNX and UPCOM quote every
# equity in one. Only the HOSE grid is checkable against this system's own store
# — its universe is HOSE-only today — so the other two are carried from the
# exchanges' published rules and marked as such rather than presented as
# measured.
_HOSE_TICK_LADDER: tuple[tuple[Decimal, Decimal], ...] = (
    (Decimal(10_000), Decimal(10)),
    (Decimal(50_000), Decimal(50)),
)
_HOSE_TOP_TICK = Decimal(100)
_FLAT_TICK = Decimal(100)

# The HNX→HOSE transfer programme runs to this date (Circular 139/2025/TT-BTC,
# secondary-confirmed in the research above). It is what makes a bar's board a
# question at all: past it, a symbol's board stops moving underneath its history.
MIGRATION_PROGRAMME_END = date(2026, 12, 31)

# The boards that programme can move a symbol *onto*. A symbol sitting on HNX or
# UPCOM today was not moved there by it, so its older bars carry no doubt from
# this source; a symbol on HOSE may have been HNX for part of its history.
_MIGRATION_DESTINATIONS = frozenset({Exchange.HOSE})


class ExchangeAsOf(str, Enum):
    """Where the board used for this bar came from.

    This is the ticket's first open question answered on the record. There is no
    stored exchange history to consult: ``listing_roster`` holds one row per
    symbol describing the market as it stands now, by design, so a symbol that
    changed board before this system first saw it leaves no trace in the store
    at all.

    The choice made is a **dated migration register in code**
    (``EXCHANGE_MIGRATIONS``), consulted first, with the current listing as the
    fallback. Not a database table: the set is small, publicly announced, and
    ends on a known date, so a table would add a migration, a collector and a
    staleness question in exchange for nothing the register does not already
    give. The limitation of the fallback is that it is an assumption, and it is
    named as one — on this field rather than as a degradation, because a warning
    attached to every HOSE bar in the store is a warning nobody reads.
    """

    # The register carries a dated move covering this bar.
    DATED_MIGRATION = "dated_migration"

    # Taken from the current listing, on a bar the transfer programme could not
    # have moved: dated after it ended, or on a board it does not move symbols
    # onto.
    CURRENT_LISTING = "current_listing"

    # Taken from the current listing and assumed unchanged, on a bar inside the
    # programme window. The band is the one this symbol trades under today; if
    # it moved from HNX during that window and the register does not say so,
    # this bar's band was ±10 rather than ±7.
    CURRENT_LISTING_ASSUMED = "current_listing_assumed"

    # No board for this symbol anywhere, so no band either.
    UNKNOWN = "unknown"


class BandAnchorBasis(str, Enum):
    """What the exchange computes the band as a percentage of."""

    # HOSE and HNX: the previous session's close, which the store holds.
    PREVIOUS_CLOSE = "previous_close"

    # UPCOM: the previous day's volume-weighted average of round-lot continuous
    # trades (Decision 23/QĐ-HĐTV Art. 19). Not stored, and not reconstructible
    # from what is — the stored turnover covers put-through and odd-lot trades
    # too, so ``total_value_vnd / volume`` is a different average that would
    # answer with the same shape and a wrong number.
    PRIOR_DAY_VWAP = "prior_day_vwap"


class BandIssue(str, Enum):
    """Why a session could not be judged against its band. A closed set.

    Stable strings, because they travel: Window Health echoes them and the tool
    layer serializes them for a model to cite. A reason that changed spelling
    between releases would break a reader that had learned to recognise it.
    """

    # No board for the symbol, so no band to measure against.
    EXCHANGE_UNKNOWN = "exchange_unknown"

    # The store holds no session for this symbol on this day. Not the same as a
    # session that did not move.
    SESSION_NOT_STORED = "session_not_stored"

    # The session is ``adjusted_at_source``: its prices have been rescaled off
    # the tick grid the band is defined on.
    SESSION_NOT_RAW = "session_not_raw"

    # The session is held without a high and a low, so what it did between the
    # limits is unknown. A close at the ceiling is not a lock.
    SESSION_PRICES_INCOMPLETE = "session_prices_incomplete"

    # The anchor this board's band is measured from is not in the store and
    # cannot be derived from it: UPCOM's prior-day VWAP.
    ANCHOR_NOT_STORED = "anchor_not_stored"

    # The symbol has no stored session on the trading day before this one, so
    # there is no previous close to anchor to.
    ANCHOR_MISSING = "anchor_missing"

    # The previous session is ``adjusted_at_source`` while this one is raw —
    # what a symbol's own Price Basis seam looks like from one day to the next.
    ANCHOR_NOT_RAW = "anchor_not_raw"

    # The session moved further than its band permits, which means the anchor is
    # wrong rather than that the market broke: an ex-date the exchange adjusted
    # its reference for and the previous close did not follow. Once the
    # Corporate Action series exists this same measurement is what separates an
    # accounted ex-date from ADR-0006's ``unexplained_price_gap``.
    PRICE_MOVE_EXCEEDS_BAND = "price_move_exceeds_band"


class LimitLock(str, Enum):
    """Whether the session traded anywhere other than at one of its limits."""

    CEILING = "ceiling"
    FLOOR = "floor"
    NONE = "none"

    # The question could not be decided from what is stored. Distinct from
    # ``NONE``: one says the session moved inside its band, the other says
    # nobody knows.
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class ExchangeMigration:
    """One symbol's dated move from one board to another.

    ``first_session`` is the first session traded under ``to_exchange``, not the
    last under ``from_exchange``, because that is the boundary the band changes
    on. ``citation`` is required rather than decorative: an undated or unsourced
    entry silently rewrites the band on every bar of that symbol's history, and
    a wrong entry is less detectable than a missing one.
    """

    symbol: str
    from_exchange: Exchange
    to_exchange: Exchange
    first_session: date
    citation: str


# The dated register. Empty on purpose: every entry rewrites a stretch of one
# symbol's history, so an entry goes in only with a dated primary source behind
# it, and none has been obtained — the transfer programme itself is only
# secondary-confirmed in the research. Empty, every bar falls back to the current
# listing and says so through ``ExchangeAsOf``, which is a limitation the reader
# can see; seeded from guesses, it would be a wrong answer the reader cannot.
EXCHANGE_MIGRATIONS: tuple[ExchangeMigration, ...] = ()


@dataclass(frozen=True)
class BandRegime:
    """Which band applied to one symbol on one session, and where it came from."""

    symbol: str
    session_date: date
    exchange: Exchange | None
    limit_ratio: Decimal | None
    anchor_basis: BandAnchorBasis | None
    exchange_as_of: ExchangeAsOf


@dataclass(frozen=True)
class BandLimits:
    """The two prices a session was permitted to trade between."""

    anchor: Decimal
    ceiling: Decimal
    floor: Decimal


@dataclass(frozen=True)
class BandReading:
    """One session measured against its band, or the reason it could not be.

    ``lock`` and ``degraded_reason`` move together: a reading with a reason is
    always ``INDETERMINATE``, because every reason here removes an input the
    verdict is made of. The regime travels regardless — which band applied is a
    separate question from whether this session can be compared with it, and a
    UPCOM reading still answers the first.
    """

    symbol: str
    session_date: date
    regime: BandRegime
    anchor: Decimal | None
    anchor_date: date | None
    limits: BandLimits | None
    lock: LimitLock
    degraded_reason: BandIssue | None

    @property
    def degraded(self) -> bool:
        return self.degraded_reason is not None


def tick_size(exchange: Exchange, price: Decimal) -> Decimal:
    """The quoting step an order at this price has to sit on."""
    if exchange is not Exchange.HOSE:
        return _FLAT_TICK
    for ceiling, tick in _HOSE_TICK_LADDER:
        if price < ceiling:
            return tick
    return _HOSE_TOP_TICK


def band_limits(exchange: Exchange, anchor: Decimal) -> BandLimits:
    """The ceiling and floor a session anchored here was permitted to reach.

    Both round **toward** the anchor — the ceiling down, the floor up — because
    a limit price has to be an order price the exchange would accept, and the
    unrounded product almost never is. The step is chosen from the limit price
    rather than from the anchor, for the same reason: a HOSE ceiling that lands
    above 50,000 must be a multiple of 100 whatever the anchor below it was.

    Where the rounding erases the band entirely — a penny name whose whole ±15%
    is narrower than one 100-VND step — the limit is widened to a single step.
    A ceiling equal to the anchor would say the session may not move at all,
    which no band says.
    """
    ratio = BAND_LIMIT_BY_EXCHANGE[exchange]
    raw_ceiling = anchor * (Decimal(1) + ratio)
    raw_floor = anchor * (Decimal(1) - ratio)

    ceiling = _round_to_tick(exchange, raw_ceiling, ROUND_FLOOR)
    floor = _round_to_tick(exchange, raw_floor, ROUND_CEILING)

    if ceiling <= anchor:
        ceiling = anchor + tick_size(exchange, anchor)
    if floor >= anchor:
        floor = anchor - tick_size(exchange, anchor)
    return BandLimits(anchor=anchor, ceiling=ceiling, floor=floor)


def resolve_band_regime(
    session: Session,
    symbol: str,
    day: date,
    *,
    migrations: Sequence[ExchangeMigration] = EXCHANGE_MIGRATIONS,
) -> BandRegime:
    """Which band applied to this symbol on this session, and on whose authority.

    The register is asked first and the listing roster second, so a symbol with
    a dated move is answered from its history rather than from its present. A
    symbol with neither is answered with no band at all: defaulting to HOSE
    would be the likeliest guess and the least detectable error, since a band
    quietly narrowed to ±7 reports limit locks on ordinary HNX sessions.
    """
    symbol = symbol.upper()
    exchange, as_of = _exchange_on(session, symbol, day, migrations)
    if exchange is None:
        return BandRegime(
            symbol=symbol,
            session_date=day,
            exchange=None,
            limit_ratio=None,
            anchor_basis=None,
            exchange_as_of=as_of,
        )
    return BandRegime(
        symbol=symbol,
        session_date=day,
        exchange=exchange,
        limit_ratio=BAND_LIMIT_BY_EXCHANGE[exchange],
        anchor_basis=(
            BandAnchorBasis.PRIOR_DAY_VWAP
            if exchange is Exchange.UPCOM
            else BandAnchorBasis.PREVIOUS_CLOSE
        ),
        exchange_as_of=as_of,
    )


def detect_limit_lock(
    session: Session,
    symbol: str,
    day: date,
    *,
    migrations: Sequence[ExchangeMigration] = EXCHANGE_MIGRATIONS,
) -> BandReading:
    """Whether this session traded anywhere other than at one of its limits.

    A lock is ``high == low == limit``: every trade of the session matched at
    the band. The open and the close follow from that and are not checked
    separately, which is also why ``H=L=O=C`` on its own is not the test — a
    thin name that matched once has the same flat bar and traded nowhere near
    its band.

    A session that *closed* at its ceiling after trading below it is ``NONE``
    here. The two are different facts: the first is buying pressure, and belongs
    to a band-pressure reading; the second is an order book that could not clear,
    which is what collapses a range estimator to zero and has to be excluded from
    one.
    """
    symbol = symbol.upper()
    regime = resolve_band_regime(session, symbol, day, migrations=migrations)

    previous = trading_days_before(session, day, 1)
    anchor_date = previous[0] if previous else None
    held = _sessions(session, symbol, anchor_date or day, day)

    target = held.get(day)
    if target is None:
        return _undecided(symbol, day, regime, BandIssue.SESSION_NOT_STORED)
    if target.price_basis is not PriceBasis.RAW:
        return _undecided(symbol, day, regime, BandIssue.SESSION_NOT_RAW)
    if target.high_price is None or target.low_price is None:
        return _undecided(symbol, day, regime, BandIssue.SESSION_PRICES_INCOMPLETE)
    if regime.exchange is None:
        return _undecided(symbol, day, regime, BandIssue.EXCHANGE_UNKNOWN)
    if regime.anchor_basis is BandAnchorBasis.PRIOR_DAY_VWAP:
        return _undecided(symbol, day, regime, BandIssue.ANCHOR_NOT_STORED)

    anchor_session = held.get(anchor_date) if anchor_date else None
    if anchor_session is None or anchor_session.last_price is None:
        return _undecided(symbol, day, regime, BandIssue.ANCHOR_MISSING)
    if anchor_session.price_basis is not PriceBasis.RAW:
        return _undecided(symbol, day, regime, BandIssue.ANCHOR_NOT_RAW)

    anchor = _price(anchor_session.last_price)
    limits = band_limits(regime.exchange, anchor)
    high = _price(target.high_price)
    low = _price(target.low_price)

    if high > limits.ceiling or low < limits.floor:
        return BandReading(
            symbol=symbol,
            session_date=day,
            regime=regime,
            anchor=anchor,
            anchor_date=anchor_date,
            limits=limits,
            lock=LimitLock.INDETERMINATE,
            degraded_reason=BandIssue.PRICE_MOVE_EXCEEDS_BAND,
        )

    if high == low == limits.ceiling:
        lock = LimitLock.CEILING
    elif high == low == limits.floor:
        lock = LimitLock.FLOOR
    else:
        lock = LimitLock.NONE

    return BandReading(
        symbol=symbol,
        session_date=day,
        regime=regime,
        anchor=anchor,
        anchor_date=anchor_date,
        limits=limits,
        lock=lock,
        degraded_reason=None,
    )


def _exchange_on(
    session: Session,
    symbol: str,
    day: date,
    migrations: Sequence[ExchangeMigration],
) -> tuple[Exchange | None, ExchangeAsOf]:
    """The board this symbol traded on that day, and how confidently."""
    dated = sorted(
        (entry for entry in migrations if entry.symbol.upper() == symbol),
        key=lambda entry: entry.first_session,
    )
    moved = [entry for entry in dated if entry.first_session <= day]
    if moved:
        return moved[-1].to_exchange, ExchangeAsOf.DATED_MIGRATION
    if dated:
        # Every recorded move is still ahead of this bar, so the symbol was on
        # whatever the earliest of them moved it off.
        return dated[0].from_exchange, ExchangeAsOf.DATED_MIGRATION

    listed = session.execute(
        select(ListingRoster.exchange).where(ListingRoster.symbol == symbol)
    ).scalar_one_or_none()
    if listed is None:
        return None, ExchangeAsOf.UNKNOWN
    try:
        current = Exchange.parse(str(listed))
    except ValueError:
        # A board name the enum does not recognise is not a board. Guessing one
        # would pick a band, and the wrong band is worse than none.
        return None, ExchangeAsOf.UNKNOWN

    assumed = day <= MIGRATION_PROGRAMME_END and current in _MIGRATION_DESTINATIONS
    return current, (
        ExchangeAsOf.CURRENT_LISTING_ASSUMED if assumed else ExchangeAsOf.CURRENT_LISTING
    )


def _sessions(
    session: Session,
    symbol: str,
    start: date,
    end: date,
) -> dict[date, MarketSnapshot]:
    """This symbol's stored sessions across a short window, keyed by day.

    Read through ``SnapshotStore.series`` rather than with a query of its own,
    because the Main-Source-wins resolution it already performs is what decides
    which of two copies of a session is read — and the two copies are on
    different price bases, so the choice decides whether the question can be
    asked at all. Redis is passed as ``None``: ``series`` is a Postgres read
    that never consults the cache, and the default would open a connection this
    path has no use for.
    """
    series = SnapshotStore(session, redis=None).series(
        Capability.MARKET, symbol, start=start, end=end
    )
    return {
        snapshot.metadata.effective_at.astimezone(VN_TZ).date(): snapshot
        for snapshot in series.snapshots
        if isinstance(snapshot, MarketSnapshot)
    }


def _undecided(
    symbol: str,
    day: date,
    regime: BandRegime,
    reason: BandIssue,
) -> BandReading:
    """A reading that withholds the verdict, and says which input it is short of."""
    return BandReading(
        symbol=symbol,
        session_date=day,
        regime=regime,
        anchor=None,
        anchor_date=None,
        limits=None,
        lock=LimitLock.INDETERMINATE,
        degraded_reason=reason,
    )


def _price(value: float) -> Decimal:
    """A stored price as an exact decimal.

    Through ``str`` deliberately: ``Decimal(27600.0)`` is exact but
    ``Decimal(0.07)`` is not, and prices arrive from JSON as floats. Going via
    the repr keeps the number the one that was stored.
    """
    return Decimal(str(value))


def _round_to_tick(exchange: Exchange, price: Decimal, rounding: str) -> Decimal:
    tick = tick_size(exchange, price)
    return (price / tick).to_integral_value(rounding=rounding) * tick
