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

**What this module reads is prices on the tick grid, whatever their basis says.**
It used to read ``raw`` only, and that rule outlived its own reason: the store now
holds nothing but ``adjusted_at_source``, so refusing that label refused every
session of every symbol — silently, because a withheld band verdict reads as
*not locked* rather than as an error.

The reasoning underneath was always about the prices and not the label. A
rescaled close is an unrounded float that has been multiplied for every action
since it was observed, so it does not sit on the tick grid a band is defined on,
and comparing it against a limit price is not imprecise but meaningless. The
converse is what the old rule missed: a symbol with no entitlement behind it
carries the published prices under the adjusted label, and those can be judged.
``off_tick_grid`` asks that directly.

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

from ..providers import Exchange, MarketSnapshot, PriceBasis
from ..trading_day import trading_days_before
from .issues import SignalIssue
from .sessions import sessions_in_range

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


class LimitLock(str, Enum):
    """Whether the session traded anywhere other than at one of its limits."""

    CEILING = "ceiling"
    FLOOR = "floor"
    NONE = "none"

    # The question could not be decided from what is stored. Distinct from
    # ``NONE``: one says the session moved inside its band, the other says
    # nobody knows.
    INDETERMINATE = "indeterminate"

    # There is no question. The instrument has no band to lock at — a market
    # index sits on no board (``docs/adr/0017``). Distinct from
    # ``INDETERMINATE``, which is the store admitting it could not judge a
    # session that does have a band: reusing that here would put an equity's
    # vocabulary on an instrument the word does not apply to.
    NOT_APPLICABLE = "not_applicable"


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
    degraded_reason: SignalIssue | None

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


class BandRegimeResolver:
    """The band regime of one symbol, across as many sessions as are asked for.

    A class rather than a function because the listing register is read once and
    every further date is decided in process. ``prepare_bars()`` asks this
    question for every bar of a window that can run to 273 of them, and a
    per-date query would make the gateway's cost a multiple of its window
    length for an answer that changes at most once in the store's whole history.

    The register of dated migrations is asked first and the listing roster
    second, so a symbol with a dated move is answered from its history rather
    than from its present. A symbol with neither is answered with no band at
    all: defaulting to HOSE would be the likeliest guess and the least
    detectable error, since a band quietly narrowed to ±7 reports limit locks on
    ordinary HNX sessions.
    """

    def __init__(
        self,
        session: Session,
        symbol: str,
        *,
        migrations: Sequence[ExchangeMigration] = EXCHANGE_MIGRATIONS,
        listed_exchange: Exchange | None = None,
        listing_resolved: bool = False,
    ) -> None:
        self.symbol = symbol.upper()
        self._migrations = sorted(
            (entry for entry in migrations if entry.symbol.upper() == self.symbol),
            key=lambda entry: entry.first_session,
        )
        self._listed = (
            listed_exchange if listing_resolved else self._current_exchange(session)
        )

    def on(self, day: date) -> BandRegime:
        """Which band applied on this session, and on whose authority."""
        exchange, as_of = self._exchange_on(day)
        if exchange is None:
            return BandRegime(
                symbol=self.symbol,
                session_date=day,
                exchange=None,
                limit_ratio=None,
                anchor_basis=None,
                exchange_as_of=as_of,
            )
        return BandRegime(
            symbol=self.symbol,
            session_date=day,
            exchange=exchange,
            limit_ratio=BAND_LIMIT_BY_EXCHANGE[exchange],
            # UPCOM measures its band from the prior session's round-lot
            # continuous VWAP, and the daily spine holds an open, a high, a low,
            # a close and a volume — no VWAP, and none derivable from those. So
            # every UPCOM session is undecided, **permanently**, and under
            # ``anchor_not_stored`` rather than under a code about this window:
            # nothing about a longer window or a fresher backfill changes it.
            # That is 819 of the 1,751 symbols on the listing register — though
            # none of the declared Universe, every one of which is on HOSE, so
            # the chat lane does not meet this today. Stated here so a later
            # reader looking for something to fix knows there is nothing to fix
            # short of a source that reports the VWAP.
            anchor_basis=(
                BandAnchorBasis.PRIOR_DAY_VWAP
                if exchange is Exchange.UPCOM
                else BandAnchorBasis.PREVIOUS_CLOSE
            ),
            exchange_as_of=as_of,
        )

    def _current_exchange(self, session: Session) -> Exchange | None:
        listed = session.execute(
            select(ListingRoster.exchange).where(ListingRoster.symbol == self.symbol)
        ).scalar_one_or_none()
        if listed is None:
            return None
        try:
            return Exchange.parse(str(listed))
        except ValueError:
            # A board name the enum does not recognise is not a board. Guessing
            # one would pick a band, and the wrong band is worse than none.
            return None

    def _exchange_on(self, day: date) -> tuple[Exchange | None, ExchangeAsOf]:
        """The board this symbol traded on that day, and how confidently."""
        moved = [entry for entry in self._migrations if entry.first_session <= day]
        if moved:
            return moved[-1].to_exchange, ExchangeAsOf.DATED_MIGRATION
        if self._migrations:
            # Every recorded move is still ahead of this bar, so the symbol was
            # on whatever the earliest of them moved it off.
            return self._migrations[0].from_exchange, ExchangeAsOf.DATED_MIGRATION

        if self._listed is None:
            return None, ExchangeAsOf.UNKNOWN

        assumed = (
            day <= MIGRATION_PROGRAMME_END and self._listed in _MIGRATION_DESTINATIONS
        )
        return self._listed, (
            ExchangeAsOf.CURRENT_LISTING_ASSUMED
            if assumed
            else ExchangeAsOf.CURRENT_LISTING
        )


def resolve_band_regime(
    session: Session,
    symbol: str,
    day: date,
    *,
    migrations: Sequence[ExchangeMigration] = EXCHANGE_MIGRATIONS,
) -> BandRegime:
    """Which band applied to this symbol on this session, and on whose authority.

    One session's worth of the resolver above, for the caller that has exactly
    one to ask about.
    """
    return BandRegimeResolver(session, symbol, migrations=migrations).on(day)


def measure_band(
    regime: BandRegime,
    target: MarketSnapshot | None,
    anchor: MarketSnapshot | None,
    anchor_date: date | None,
) -> BandReading:
    """Judge one session against its band, from rows a caller already holds.

    The whole verdict, and no reading of the store: a caller that has loaded a
    window has both sessions in hand already, and ``prepare_bars()`` would
    otherwise re-read two rows per bar.

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

    The two sessions this reads are a two-day window, and the Price Basis
    vocabulary applies to it as to any other: both adjusted is
    ``unadjustable_price_basis``, one of each is ``mixed_price_basis``, and only
    an all-raw pair is measured.
    """
    symbol = regime.symbol
    day = regime.session_date

    if target is None:
        return _undecided(symbol, day, regime, SignalIssue.MISSING_TARGET_SESSION)
    if regime.exchange is None:
        return _undecided(symbol, day, regime, SignalIssue.EXCHANGE_UNKNOWN)
    if regime.anchor_basis is BandAnchorBasis.PRIOR_DAY_VWAP:
        return _undecided(symbol, day, regime, SignalIssue.ANCHOR_NOT_STORED)
    if anchor is None or anchor.last_price is None or anchor_date is None:
        return _undecided(symbol, day, regime, SignalIssue.ANCHOR_MISSING)

    basis_issue = _basis_of_the_pair(target, anchor)
    if basis_issue is not None:
        return _undecided(symbol, day, regime, basis_issue)
    if target.high_price is None or target.low_price is None:
        return _undecided(symbol, day, regime, SignalIssue.SESSION_PRICES_INCOMPLETE)

    anchor_price = _price(anchor.last_price)
    high = _price(target.high_price)
    low = _price(target.low_price)

    # The three prices the verdict is arithmetic on: the anchor the band is a
    # percentage of, and the two extremes compared against it. Checked together
    # rather than one at a time because a verdict needs all three to be the
    # published ones — an anchor off the grid moves both limits, and a high off
    # the grid can never equal a limit that is on it.
    if off_tick_grid(regime.exchange, anchor_price, high, low):
        return _undecided(symbol, day, regime, SignalIssue.PRICE_OFF_TICK_GRID)

    limits = band_limits(regime.exchange, anchor_price)

    if high > limits.ceiling or low < limits.floor:
        return BandReading(
            symbol=symbol,
            session_date=day,
            regime=regime,
            anchor=anchor_price,
            anchor_date=anchor_date,
            limits=limits,
            lock=LimitLock.INDETERMINATE,
            degraded_reason=SignalIssue.PRICE_MOVE_EXCEEDS_BAND,
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
        anchor=anchor_price,
        anchor_date=anchor_date,
        limits=limits,
        lock=lock,
        degraded_reason=None,
    )


def detect_limit_lock(
    session: Session,
    symbol: str,
    day: date,
    *,
    migrations: Sequence[ExchangeMigration] = EXCHANGE_MIGRATIONS,
) -> BandReading:
    """Whether this session traded anywhere other than at one of its limits.

    The loading half: it reads the session and the one before it, and hands both
    to ``measure_band`` for the verdict.
    """
    symbol = symbol.upper()
    regime = resolve_band_regime(session, symbol, day, migrations=migrations)

    previous = trading_days_before(session, day, 1)
    anchor_date = previous[0] if previous else None
    held = sessions_in_range(session, symbol, anchor_date or day, day)

    return measure_band(
        regime,
        held.get(day),
        held.get(anchor_date) if anchor_date else None,
        anchor_date,
    )


def _basis_of_the_pair(
    target: MarketSnapshot,
    anchor: MarketSnapshot,
) -> SignalIssue | None:
    """What the two sessions' bases say about reading them together, if anything.

    A pair on one basis can be measured; one of each cannot. Two rows of
    different bases are ``mixed_price_basis`` — a symbol's own seam falling
    between two consecutive days, where the ratio between them is not a price
    move at all.

    **A pair adjusted throughout is now measured, where it used to be refused.**
    This is the same narrowing the window gateway's rule went through when the
    daily spine became the source of sessions, applied to the two-day window a
    session and its anchor are. Every stored row is ``adjusted_at_source``, so
    refusing that pair refused every session of every symbol — and it did it
    without raising anything: the verdict became ``INDETERMINATE``, which reads
    as *no lock*, so ``Bar.limit_locked`` was ``False`` everywhere,
    ``BarFrame.without_limit_locks()`` dropped nothing, and a baseline volatility
    that documents itself as excluding limit-locked sessions was quietly computed
    over windows still holding them. Nothing was refused and no test went red.

    What replaces it is a check on the prices rather than on the label, in
    ``off_tick_grid`` below: the question a band asks is an equality against a
    grid-rounded limit, so what matters is whether these particular prices are
    still the ones the board printed, not what the column says about the series.
    A symbol with no entitlement in the window carries published prices under the
    adjusted label and can be judged; a rebased one cannot, and says so under its
    own code.
    """
    if target.price_basis is not anchor.price_basis:
        return SignalIssue.MIXED_PRICE_BASIS
    return None


def off_tick_grid(exchange: Exchange, *prices: Decimal) -> bool:
    """Whether any of these prices is off the board's quoting grid.

    Public because two callers need the same question answered and must not
    answer it twice: this module decides whether a session can be judged against
    its band, and ``agent.tools.price_check`` decides whether a price a web page
    claimed can be. Two copies of a rule about what a published price looks like
    would be two chances to disagree about it.

    The test that replaced the basis label for band verdicts. A limit price is a
    price the exchange would accept an order at, so it sits on a tick by
    construction; ``band_limits`` rounds both limits onto the grid for exactly
    that reason. A stored price that is *not* on the grid has therefore been
    multiplied by something since it was published, and an equality between it
    and a grid-rounded limit can only come out false — which is a wrong verdict,
    not a missing one.

    **Necessary, not sufficient.** A rebased price can land back on the grid by
    coincidence — a factor of exactly 2 on a price already at a multiple of the
    step will — so passing this check is not proof the price is published. It was
    measured to decide 93% of HOSE sessions and to catch the rest; treat it as
    what it is and do not build a proof on top of it.

    The step is taken per price rather than once, because the HOSE ladder changes
    at 10,000 and 50,000 and two prices in one pair can sit on either side of a
    boundary.
    """
    return any(price % tick_size(exchange, price) != 0 for price in prices)


def _undecided(
    symbol: str,
    day: date,
    regime: BandRegime,
    reason: SignalIssue,
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
