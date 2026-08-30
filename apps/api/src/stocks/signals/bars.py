"""The only path a computation may take to bars.

``prepare_bars()`` is one gateway, and everything about this module follows from
why there is exactly one. The Vietnamese-market hazard list — price bands dated
per bar, limit-lock sessions with no range at all, two price conventions in one
store, corporate actions that move a reference price and sometimes a share count
— is too long for each computation to remember, and a review checklist fails at
the sixth of them (``docs/adr/0010``). Enforced here, by construction, it cannot
fail at the sixth: a computation asking for a window either gets an honest window
with an honest account of what it is made of, or a named refusal.

## What comes back

A ``BarFrame`` and a ``WindowHealth``, or ``None`` and a ``WindowHealth``
carrying a refusal. **Window Health travels with every return**, refusals
included, because the reason a window could not be served is exactly what the
surface above has to say instead of a number.

Every field of it is derived from the rows actually loaded. None of it is read
from configuration: a flag flipping tomorrow does not change what an
already-stored window reports, which is the requirement ``docs/adr/0006`` puts
on ``adjustment`` in particular.

## Two series, and what the second one is not

``series`` names which stored session series the window is drawn from. The
default is the equity series — a listed company, everything below applies. The
other is the **market index**, and it is here rather than behind a reader of its
own so that ``prepare_bars()`` stays the only path to a bar even for the
benchmark a beta is regressed against (``docs/adr/0017``).

An index is not a tradeable symbol, and the gateway states what that costs
rather than discovering it:

- **No band is measured, on any session.** The band is a percentage of a board's
  reference price and the index sits on no board. Every index bar carries
  ``band_undecided_reason = band_not_applicable`` and ``limit_lock =
  not_applicable`` — neither is the ``indeterminate`` a session nobody could
  judge would carry — and the whole window carries no ``band_regime``. It
  follows that ``unexplained_price_gap`` cannot fire on
  an index either — that refusal reads a break of the band as evidence of a
  wrong anchor, and with no band there is no break to read. A 9% index session
  is the market, and the store has nothing to say against it.
- **No Corporate Action series is read.** The exchange absorbs member
  entitlements and reconstitutions into the index divisor, so the published
  series is already continuous. The window reports ``applied=False`` over zero
  actions, which is a measurement rather than a default: there were none to
  apply. ``volume_basis_break`` is likewise unreachable.
- **No liquidity standing.** ``adtv`` is ``None``: there is no peer cross-section
  an index belongs to, and ranking it among a hundred equities would answer a
  question nobody asked.

The **Price Basis** rule is *not* relaxed. An index level says what it means
like every other stored session does, and a series that mixed two would still be
refused — see ``Capability.MARKET_INDEX`` for why one source owns it.

The window itself is still cut from the market's own Trading Days. That is the
whole reason a beta is computable: the benchmark is read on exactly the sessions
the symbol was, so the two series line up by construction rather than by a join
done later.

## Projections, then four price refusals

The default ``price`` projection admits sessions with a close and enforces the
price-basis, band and adjustment contract below. The ``volume`` projection
admits sessions with a traded quantity instead: price availability and basis do
not decide whether a quantity exists, while share-count actions still travel as
``volume_basis_break``. Both projections use the same stored-session seam and
the same canonical Trading Days.

The following refusals apply to the price projection:

| Refusal | Cause |
| --- | --- |
| ``insufficient_history`` | fewer sessions than the field's minimum |
| ``mixed_price_basis`` | the window crosses a **Price Basis** seam |
| ``unexplained_price_gap`` | a session moved further than its band permits, and no stored action accounts for it |

``mixed_price_basis`` is not a degradation. A raw close and an
``adjusted_at_source`` close are not two measurements of the same thing, so a
window holding both is meaningless rather than weaker.

A window that is ``adjusted_at_source`` *throughout* **is served**, and this is
the one rule that changed when the daily spine became the source. It used to be
``unadjustable_price_basis``, on the reasoning that such a window was fixed at
somebody else's ``observed_at`` and could not be recomputed from anything
stored. That is still true and it is no longer a reason to refuse: the provider
restates the whole series when an action changes the factor behind it, so the
window is internally consistent, and every ratio a field takes over it — a
return, a range, a drawdown, a z-score — is unchanged by the constant the whole
window is scaled by. What such a window cannot answer is a question about a
*published* price: the band it traded inside, and whether a claimed price is the
one the exchange printed. Those are refused where they are asked rather than by
withholding the window.

The corollary is that ``_factors`` must not run on it. The adjustment machine
below rebases a raw window onto its own last session using the stored Corporate
Action series; run over prices the provider has already rebased, it applies
every entitlement twice and is wrong silently. It is skipped, and the factor is
1 for every bar.

## Two degradations

``volume_basis_break`` when a share-count-changing action falls in the window, so
every ``*_volume`` field changes unit partway through it; and
``unconfirmed_corporate_action`` when the window holds an action whose ex-date
nothing corroborates. Both are degradations rather than refusals because the
prices are still comparable: the first leaves money and price alone, and the
second is an action that may not drive arithmetic rather than one that broke the
series.

## Trailing windows only, and nothing computed from the whole sample

No statistic here reads the sample it is measured against. Every per-session
verdict this gateway produces — the limit-lock reading, the band it was judged
against, whether the session gapped — depends on that session and the one before
it, and on nothing else in the window. That is the measured failure being
designed out: the same event scored z = +151.5 on one run and z = +135.6 on a
longer one, because its baseline had quietly read the whole sample.

The one number that is window-relative is the **Adjustment Factor** applied to a
bar, and deliberately so. Adjustment is a rebasing rather than a statistic: it
expresses every price in the window in the share terms of the window's last
session, so that the last session's prices are the raw ones the exchange
published. Extending it to actions *after* the window would make a historical
window depend on the future, which is the same bias by another road.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.models import CorporateAction, ListingRoster, ProviderSnapshot

from ..providers.contracts import (
    Capability,
    Exchange,
    MarketSnapshot,
    PriceBasis,
    ReferenceSnapshot,
    SessionSnapshot,
    main_source,
)
from ..providers.normalize import VN_TZ
from ..trading_day import latest_trading_day, trading_days_before
from ..universe import build_universe
from .corporate_actions import CorporateActionStore, adjustment_factor
from .fields import DEGRADED_LIMIT_LOCK_SHARE, BarProjection, min_sample_for
from .issues import SignalIssue
from .reference import REFERENCE_STALE_DAYS
from .price_band import (
    EXCHANGE_MIGRATIONS,
    BandAnchorBasis,
    BandLimits,
    BandRegime,
    BandRegimeResolver,
    BandReading,
    ExchangeAsOf,
    ExchangeMigration,
    LimitLock,
    measure_band,
)
from .sessions import sessions_in_range, sessions_on_days

logger = logging.getLogger(__name__)

# How many of the window's newest sessions the liquidity reading averages over.
# Twenty because that is what ADTV means in this market's own vocabulary, and
# because it bounds the one cross-sectional read this gateway makes: a 273-session
# window would otherwise pull the whole Universe's history through it to answer a
# question about how thin the symbol is.
ADTV_SESSIONS = 20

# Below this many peers a percentile stops meaning anything, so none is reported
# (``docs/adr/0010``). Asked of the same function the cross-sectional fields
# refuse under rather than restated as a number: the two floors were both
# written as 30 with each comment claiming to be "the same floor", which is a
# claim nothing checked. Now they are one rule, and it scales with the sample.


class BarSeries(str, Enum):
    """Which stored session series a window is drawn from.

    Two members and no more, because there are two kinds of thing this system
    stores a session for. Everything the gateway does differently for an index
    hangs off this one value rather than off a symbol name: a reserved ticker
    tested for by string would be a rule every future reader has to remember,
    and the sixth of them is where a review checklist fails (``docs/adr/0010``).
    """

    EQUITY = "equity"
    MARKET_INDEX = "market_index"

    @property
    def capability(self) -> Capability:
        """The Capability this series' sessions are stored under."""
        if self is BarSeries.MARKET_INDEX:
            return Capability.MARKET_INDEX
        return Capability.MARKET

    # Three predicates rather than one ``is_equity``, because three different
    # questions are being asked and a single boolean standing for all of them
    # invites a wrong fourth use. Each site below says which capability of a
    # listed instrument it is reaching for, so a reader of that line does not
    # have to know why an index is different in general.
    @property
    def has_price_band(self) -> bool:
        """Whether a session of this series was permitted to move only so far.

        A band is a percentage of a board's reference price, and a market index
        sits on no board.
        """
        return self is BarSeries.EQUITY

    @property
    def has_corporate_actions(self) -> bool:
        """Whether an entitlement can move this series' prices.

        An index absorbs its members' entitlements and its own reconstitutions
        into the divisor the exchange publishes it with, so the level series is
        already continuous and there is nothing for read-time adjustment to do.
        """
        return self is BarSeries.EQUITY

    @property
    def has_peer_cross_section(self) -> bool:
        """Whether this series' instruments have peers to be ranked among.

        A composite trades among nothing; ranking its turnover would rank it
        against its own members.
        """
        return self is BarSeries.EQUITY


@dataclass(frozen=True)
class Bar:
    """One session of a served window.

    Prices are **adjusted** — the raw price the exchange published multiplied by
    ``adjustment_factor`` — because that is what makes them comparable with the
    other bars beside them. The raw price is recoverable by dividing it back out,
    and on a window with no action in it the factor is exactly 1.

    ``volume`` and ``total_value_vnd`` are never rescaled. A share-count change
    moves the unit of the first and leaves the second alone, and the price factor
    is not the quantity factor anyway: ACB's 2025 ex-date multiplies the share
    count by 1.15 while multiplying past prices by 0.8355 (``docs/adr/0006``).
    Whether the quantity is comparable across the window is Window Health's
    answer, not a rescaling's.
    """

    session_date: date
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int | None
    total_value_vnd: float | None
    adjustment_factor: Decimal
    limit_lock: LimitLock
    # The two prices this session was permitted to trade between, in the **raw**
    # terms the exchange published them in — the band is defined on a tick grid
    # and an adjusted price does not sit on one (``price_band``). Kept beside the
    # lock verdict rather than recomputed downstream, because the anchor it was
    # measured from is the previous session's raw close and only the gateway
    # still has it.
    #
    # ``band`` and ``band_undecided_reason`` move together and exactly one of
    # them is set on a served bar: a session either has the band it was judged
    # against, or the reason nobody could decide one — every UPCOM session,
    # whose anchor is not stored; every session whose predecessor the store does
    # not hold; and every ex-date whose band was measured from a pre-adjustment
    # close. A field reading an absent band therefore never has to guess why,
    # which is the difference between a named refusal and a plausible one.
    band: BandLimits | None = None
    band_undecided_reason: SignalIssue | None = None
    # What the provider valued the whole company at on this session. Money, and
    # therefore left alone by the rebasing above for the same reason traded
    # value is: a share-count change moves the count and the price together and
    # leaves their product where it was.
    market_cap_vnd: float | None = None
    # What foreign investors bought less what they sold in this session, in
    # **money**, exactly as the provider reported it — positive is net foreign
    # buying. Money and not shares, because money is what the Main Source
    # actually writes: it reports active buy and sell as quantity and foreign
    # buy and sell as value, and the naming split exists so the two can never be
    # swapped by accident.
    foreign_net_value_vnd: float | None = None
    # Kept exactly as the provider stated it. A caller such as Volume Spike
    # displays the session's own change while still reaching the session only
    # through this gateway; recomputing it from adjusted closes would subtly
    # change the existing wire value around corporate actions.
    change_pct: float | None = None

    @property
    def limit_locked(self) -> bool:
        return self.limit_lock in (LimitLock.CEILING, LimitLock.FLOOR)

    @property
    def raw_close(self) -> float | None:
        """This session's close in the terms its band was measured in.

        The band above is in the stored window's own prices and ``close`` is in
        the window's rebased ones, so a distance between the two is only a
        distance once the Adjustment Factor is divided back out. On a window with
        no action in it the factor is 1 and the two are the same number.

        **It is the exchange's published close only on a ``raw`` window.** On an
        ``adjusted_at_source`` window the factor is 1 by construction — the
        adjustment machine did not run — so this returns ``close`` unchanged, and
        ``close`` is the provider's rebased price rather than the one the
        exchange printed. Nothing here can undo that: the provider's factor and
        this system's are not guaranteed to be the same number, so multiplying
        one back through the other would invent a third price. A caller that
        needs the published figure has to say so and be refused, which is what
        ``price_band`` and ``check_price_claim`` do.
        """
        if self.close is None:
            return None
        return float(Decimal(str(self.close)) / self.adjustment_factor)


@dataclass(frozen=True)
class BarFrame:
    """A window of sessions, oldest first."""

    symbol: str
    bars: tuple[Bar, ...]

    def __len__(self) -> int:
        return len(self.bars)

    @property
    def sessions(self) -> tuple[date, ...]:
        return tuple(bar.session_date for bar in self.bars)

    def without_limit_locks(self) -> "BarFrame":
        """The same window with its limit-locked sessions removed.

        The seam every robust baseline needs and none may skip. A locked session
        has ``H=L=O=C``, so every range term in it is zero by construction; a run
        of them deflates a median-absolute-deviation baseline and manufactures
        significance on the sessions around it — the exact failure ADR-0010
        names. The count of what was dropped stays in Window Health, so a
        baseline that excluded them still reports that they were there.
        """
        return BarFrame(
            symbol=self.symbol,
            bars=tuple(bar for bar in self.bars if not bar.limit_locked),
        )


@dataclass(frozen=True, repr=False)
class BarPreparationContext:
    """An opaque market-wide window reused by per-symbol preparation."""

    _symbols: tuple[str, ...]
    _window_days: int
    _end: date | None
    _window: tuple[date, ...]
    _anchor_date: date | None
    _sessions: dict[str, dict[date, SessionSnapshot]]
    _actions: dict[str, tuple[CorporateAction, ...]]
    _listed_exchanges: dict[str, Exchange | None]
    # Loaded with the window rather than per symbol. A cross-sectional field
    # prepares one context and then calls ``prepare_bars`` a hundred times; a
    # share count read inside that loop would be a hundred queries for one
    # answer that does not change between them.
    _shares: dict[str, "SharesOnRecord"] = field(default_factory=dict)
    _projection: BarProjection = BarProjection.PRICE
    _series: BarSeries = BarSeries.EQUITY


@dataclass(frozen=True)
class AdjustmentReport:
    """Whether this window's prices were rebased, and off how many actions.

    Derived from the rows loaded rather than from a setting, which is what makes
    it answerable at all: on a served window the **Price Basis** is always
    ``raw`` and would carry no information, so what a reader needs to know is
    whether a transform ran and how much of the action series it rested on
    (``docs/adr/0006``).
    """

    applied: bool
    actions_applied: int
    actions_in_window: int
    ex_dates_applied: tuple[date, ...] = ()


@dataclass(frozen=True)
class WindowBandRegime:
    """The band the window was judged against, and whether it held throughout.

    ``uniform`` is the honest part. A symbol's board can change mid-history
    through the HNX→HOSE transfer programme, and a window straddling that date
    was judged against two different bands — reporting only the newer one would
    describe a window that never existed.
    """

    exchange: Exchange | None
    limit_ratio: Decimal | None
    anchor_basis: BandAnchorBasis | None
    exchange_as_of: ExchangeAsOf
    uniform: bool


@dataclass(frozen=True)
class AdtvStanding:
    """How much money this symbol traded, and where that sits among its peers.

    The one cross-sectional read the gateway makes, and it carries the two things
    ADR-0010 refuses a percentile without: the ``n`` it was ranked among and the
    date the ranking was cut at. A percentile over eleven names is a rank dressed
    up as a distribution, and a percentile with no date is one nobody can
    reproduce.

    ``average_value_vnd`` is traded **money**, never traded shares. Money is the
    one quantity a corporate action leaves alone: an ADTV in shares crosses an
    ex-date and changes unit, an ADTV in dong does not (``docs/adr/0006``).
    """

    average_value_vnd: float
    percentile: float
    n: int
    as_of: date


@dataclass(frozen=True)
class WindowHealth:
    """What the window is made of, stated beside whatever was computed from it.

    Echoed by every field that reads the window, which is the point: a list of
    numbers drawn from twelve sessions and one drawn from two hundred look
    identical until the answer says which it is.
    """

    symbol: str
    window_days: int
    min_sessions: int
    sessions_used: int
    first_session: date | None
    last_session: date | None
    limit_lock_days: int
    limit_lock_dates: tuple[date, ...]
    band_regime: WindowBandRegime | None
    adjustment: AdjustmentReport
    adtv: AdtvStanding | None
    # Sessions whose band could not be decided at all — an anchor the store does
    # not hold, an UPCOM reference that is not reconstructible, a board nothing
    # names. Counted rather than folded into ``limit_lock_days``: a session
    # nobody could judge is not a session that traded inside its band.
    #
    # Zero on a window nobody asked a band of — a quantity projection, or the
    # market index, which has none to ask about. Both are already named on every
    # bar of such a window, and counting them here would report a data gap where
    # there is no data to be missing.
    band_undecided_days: int
    band_undecided_reasons: tuple[SignalIssue, ...]
    refusal: SignalIssue | None
    degradations: tuple[SignalIssue, ...]

    @property
    def served(self) -> bool:
        return self.refusal is None

    @property
    def quantities_comparable(self) -> bool:
        """Whether a ``*_volume`` field may be read across this window.

        False exactly when a share-count-changing action falls inside it. A
        field reading money or price is unaffected — that is the distinction the
        exercise ratio carries and a dividend record does not.
        """
        return SignalIssue.VOLUME_BASIS_BREAK not in self.degradations

    @property
    def anchor_basis(self) -> BandAnchorBasis | None:
        """What this window's band was a percentage of, where a board is known.

        Reached through one name rather than walked to through the regime by
        every field that wants it: the walk is three optionals deep and a caller
        that got one of them wrong would report the wrong board's convention.
        """
        if self.band_regime is None:
            return None
        return self.band_regime.anchor_basis

    @property
    def limit_lock_degradation(self) -> SignalIssue | None:
        """Whether the window was too locked for a range reading to be ordinary.

        A property of the window rather than of any field that reads one, which
        is why it lives here: every range estimator in this package asks the same
        question, and asked separately in each of them it would be answered
        differently in each of them.

        Past a fifth of the window the estimate is measuring the band rather than
        the market, and ADR-0010 makes that a degradation with a named reason
        rather than a footnote.
        """
        if self.sessions_used == 0:
            return None
        if self.limit_lock_days / self.sessions_used > DEGRADED_LIMIT_LOCK_SHARE:
            return SignalIssue.LIMIT_LOCKED_WINDOW
        return None


def prepare_bars_context(
    session: Session,
    symbols: Sequence[str],
    window_days: int,
    *,
    end: date | None = None,
    projection: BarProjection = BarProjection.PRICE,
    series: BarSeries = BarSeries.EQUITY,
) -> BarPreparationContext:
    """Load one canonical window for several later ``prepare_bars`` calls."""
    wanted = tuple(sorted({symbol.upper() for symbol in symbols}))
    window_days = max(0, window_days)
    resolved_end = end or latest_trading_day(session)
    if resolved_end is None or window_days == 0:
        return BarPreparationContext(
            _symbols=wanted,
            _window_days=window_days,
            _end=resolved_end,
            _window=(),
            _anchor_date=None,
            _sessions={},
            _actions={},
            _listed_exchanges={},
            _shares={},
            _projection=projection,
            _series=series,
        )

    earlier = trading_days_before(session, resolved_end, window_days)
    window = tuple(reversed(earlier[: window_days - 1])) + (resolved_end,)
    anchor_date = earlier[window_days - 1] if len(earlier) >= window_days else None
    days = ((anchor_date,) if anchor_date is not None else ()) + window
    held = sessions_on_days(session, wanted, days, capability=series.capability)
    # Not asked for on the index series, and the emptiness is the statement: an
    # index has no corporate actions to hold, so a query that came back empty
    # and a question never asked would report identically while meaning
    # different things.
    actions = (
        CorporateActionStore(session).for_symbols(
            wanted,
            start=window[0],
            end=window[-1],
        )
        if series.has_corporate_actions
        else {}
    )
    listed_exchanges: dict[str, Exchange | None] = {}
    if series.has_price_band and projection is BarProjection.PRICE:
        roster = session.execute(
            select(ListingRoster.symbol, ListingRoster.exchange).where(
                ListingRoster.symbol.in_(wanted)
            )
        ).all()
        for symbol, exchange in roster:
            try:
                listed_exchanges[symbol] = Exchange.parse(str(exchange))
            except ValueError:
                listed_exchanges[symbol] = None
        for symbol in wanted:
            listed_exchanges.setdefault(symbol, None)
    return BarPreparationContext(
        _symbols=wanted,
        _window_days=window_days,
        _end=resolved_end,
        _window=window,
        _anchor_date=anchor_date,
        _sessions=held,
        _actions=actions,
        _listed_exchanges=listed_exchanges,
        # Only for the equity series. An index has no share count, and asking
        # for one would be a query answering nothing on every cross-sectional
        # read of the benchmark.
        _shares=(
            share_counts(session, wanted, on_or_before=resolved_end)
            if series is BarSeries.EQUITY
            else {}
        ),
        _projection=projection,
        _series=series,
    )


def prepare_bars(
    session: Session,
    symbol: str,
    window_days: int,
    *,
    min_sessions: int | None = None,
    end: date | None = None,
    peers: Sequence[str] | None = None,
    migrations: Sequence[ExchangeMigration] = EXCHANGE_MIGRATIONS,
    projection: BarProjection = BarProjection.PRICE,
    series: BarSeries = BarSeries.EQUITY,
    context: BarPreparationContext | None = None,
) -> tuple[BarFrame | None, WindowHealth]:
    """Serve ``window_days`` trailing sessions of one symbol, or refuse by name.

    ``end`` defaults to the newest Trading Day the store holds; a named one is a
    question about that session and is taken as asked. ``min_sessions`` is the
    calling field's floor and defaults to the whole window — below it the answer
    is an ``insufficient_history`` refusal, never a quietly shortened window.

    ``projection`` names the measurement the caller consumes. The default price
    projection enforces price-basis, band and adjustment rules; the volume
    projection requires volume instead and reports share-count seams without
    refusing quantities for an unrelated price condition.

    ``series`` names which stored session series the symbol belongs to, and the
    market index is not an equity: no band, no Corporate Action series, no
    liquidity standing. What each of those absences means is at the top of this
    module.

    ``peers`` is the cross-section the liquidity percentile is measured against,
    and defaults to the Universe. A caller preparing many symbols at once should
    pass it, so the Universe is resolved once rather than per symbol.
    """
    symbol = symbol.upper()
    window_days = max(0, window_days)
    floor = window_days if min_sessions is None else min_sessions

    if context is not None:
        if context._window_days != window_days:
            raise ValueError("bar context window does not match the request")
        if end is not None and context._end != end:
            raise ValueError("bar context end does not match the request")
        if context._series is not series:
            # Two series' sessions are stored under different Capabilities, so a
            # context loaded for one holds nothing for the other. Caught here
            # rather than answered with an empty window, which would read as a
            # symbol with no history.
            raise ValueError("bar context series does not match the request")
        if context._projection is not projection:
            raise ValueError("bar context projection does not match the request")
        if symbol not in context._symbols:
            raise ValueError(f"bar context does not contain {symbol}")
        end = context._end
    else:
        end = end or latest_trading_day(session)
    if end is None or window_days == 0:
        return None, _refused(
            symbol, window_days, floor, SignalIssue.INSUFFICIENT_HISTORY
        )

    # One extra session before the window: the first bar's band is measured
    # against the close before it, and without an anchor the window's oldest
    # session could never be judged for a lock or a gap.
    if context is None:
        earlier = trading_days_before(session, end, window_days)
        window = tuple(reversed(earlier[: window_days - 1])) + (end,)
        anchor_date = earlier[window_days - 1] if len(earlier) >= window_days else None
        held = sessions_in_range(
            session,
            symbol,
            anchor_date or window[0],
            end,
            capability=series.capability,
        )
        actions = (
            CorporateActionStore(session).for_symbol(
                symbol, start=window[0], end=window[-1]
            )
            if series.has_corporate_actions
            else ()
        )
    else:
        window = context._window
        anchor_date = context._anchor_date
        held = context._sessions.get(symbol, {})
        actions = context._actions.get(symbol, ())

    bars_held = {day: held[day] for day in window if day in held}
    if projection is BarProjection.VOLUME:
        usable = {day: row for day, row in bars_held.items() if row.volume is not None}
    else:
        usable = {
            day: row for day, row in bars_held.items() if row.last_price is not None
        }
    sessions_used = len(usable)
    if sessions_used < floor:
        used_days = sorted(usable)
        return None, _refused(
            symbol,
            window_days,
            floor,
            SignalIssue.INSUFFICIENT_HISTORY,
            sessions_used=sessions_used,
            first_session=used_days[0] if used_days else None,
            last_session=used_days[-1] if used_days else None,
        )

    by_ex_date: dict[date, list[CorporateAction]] = {}
    for action in actions:
        assert action.ex_date is not None  # for_symbol excludes the undated
        by_ex_date.setdefault(action.ex_date, []).append(action)

    regimes: dict[date, BandRegime] = {}
    bands: dict[date, BandReading] = {}
    undecided: dict[date, SignalIssue] = {}
    factors: dict[date, Decimal] = {}
    adjustment_issues: tuple[SignalIssue, ...] = ()
    if projection is BarProjection.PRICE:
        # Asked of both series. An index level says what it means with respect
        # to corporate actions like any other stored session, and a series that
        # somehow held two bases would be as meaningless there as here.
        basis_refusal = _basis_of(usable.values())
        if basis_refusal is not None:
            return None, _refused(
                symbol,
                window_days,
                floor,
                basis_refusal,
                sessions_used=sessions_used,
            )

    # The band and the adjustment are both questions about a listed company:
    # one takes a percentage of a board's reference price, the other reads a
    # Corporate Action series. An index has neither, so neither is asked — and
    # not asking is why `unexplained_price_gap` and `volume_basis_break` cannot
    # reach an index window.
    if projection is BarProjection.PRICE and series.has_price_band:
        resolver = BandRegimeResolver(
            session,
            symbol,
            migrations=migrations,
            listed_exchange=(
                context._listed_exchanges[symbol] if context is not None else None
            ),
            listing_resolved=(
                context is not None and context._projection is BarProjection.PRICE
            ),
        )
        regimes = {day: resolver.on(day) for day in usable}
        bands, gap_refusal, undecided = _read_bands(
            window,
            usable,
            regimes,
            anchor_date,
            held.get(anchor_date) if anchor_date else None,
            by_ex_date,
        )
        if gap_refusal is not None:
            return None, _refused(
                symbol,
                window_days,
                floor,
                gap_refusal,
                sessions_used=sessions_used,
            )
        if _adjusts_from_actions(usable.values()):
            factors, adjustment_issues = _factors(window, usable, by_ex_date)

    if series is not BarSeries.EQUITY:
        shares = None
    elif context is not None:
        shares = context._shares.get(symbol.upper())
    else:
        # Cut off at the window's own end, so a window asked about a past
        # session is not valued with a share count issued after it.
        shares = share_counts(session, [symbol], on_or_before=end).get(symbol.upper())
    frame = _frame(symbol, window, usable, bands, factors, projection, series, shares)

    degradations: list[SignalIssue] = []
    if any(action.changes_share_count for action in actions):
        degradations.append(SignalIssue.VOLUME_BASIS_BREAK)
    degradations.extend(
        issue for issue in adjustment_issues if issue not in degradations
    )

    applied_dates = tuple(sorted(factors))
    health = WindowHealth(
        symbol=symbol,
        window_days=window_days,
        min_sessions=floor,
        sessions_used=sessions_used,
        first_session=frame.bars[0].session_date if frame.bars else None,
        last_session=frame.bars[-1].session_date if frame.bars else None,
        limit_lock_days=sum(1 for bar in frame.bars if bar.limit_locked),
        limit_lock_dates=tuple(
            bar.session_date for bar in frame.bars if bar.limit_locked
        ),
        band_regime=_window_regime(window, regimes),
        adjustment=AdjustmentReport(
            applied=bool(applied_dates),
            actions_applied=sum(len(by_ex_date[day]) for day in applied_dates),
            actions_in_window=len(actions),
            ex_dates_applied=applied_dates,
        ),
        adtv=(
            # An index belongs to no cross-section: there is no set of peers it
            # trades among, so a percentile of its turnover would rank a
            # composite against its own members.
            _adtv_standing(session, symbol, window, usable, peers, context)
            if projection is BarProjection.PRICE and series.has_peer_cross_section
            else None
        ),
        band_undecided_days=len(undecided),
        band_undecided_reasons=tuple(
            sorted(set(undecided.values()), key=lambda issue: issue.value)
        ),
        refusal=None,
        degradations=tuple(degradations),
    )
    return frame, health


def _refused(
    symbol: str,
    window_days: int,
    floor: int,
    reason: SignalIssue,
    *,
    sessions_used: int = 0,
    first_session: date | None = None,
    last_session: date | None = None,
) -> WindowHealth:
    """A Window Health that carries the refusal and what was measured before it.

    The counts that were reached are kept rather than zeroed: a window refused
    for holding 40 of the 60 sessions asked for is a different situation from one
    holding none, and a caller deciding whether to wait for a Warm-up needs to
    tell them apart.
    """
    return WindowHealth(
        symbol=symbol,
        window_days=window_days,
        min_sessions=floor,
        sessions_used=sessions_used,
        first_session=first_session,
        last_session=last_session,
        limit_lock_days=0,
        limit_lock_dates=(),
        band_regime=None,
        adjustment=AdjustmentReport(
            applied=False, actions_applied=0, actions_in_window=0
        ),
        adtv=None,
        band_undecided_days=0,
        band_undecided_reasons=(),
        refusal=reason,
        degradations=(),
    )


def _basis_of(rows: Iterable[SessionSnapshot]) -> SignalIssue | None:
    """What the window's Price Basis values say about serving it, if anything.

    Three cases, and only the middle one refuses:

    - **all ``raw``** — served, and the adjustment machine rebases it onto its
      own last session from the stored Corporate Action series.
    - **two bases in one window** — ``mixed_price_basis``. A symbol's own
      Backfill seam has fallen inside the window, and the two halves are not two
      measurements of the same thing. Meaningless rather than degraded.
    - **all ``adjusted_at_source``** — served, with the adjustment machine
      **off**. The provider restated the whole series to one moment, so it is
      internally consistent, and every ratio taken over it is unchanged by the
      constant it is scaled by. Running ``_factors`` here would apply each
      entitlement a second time and be wrong without saying so.

    What such a window cannot answer is a question about a *published* price —
    the band a session traded inside, and whether a claimed price is the printed
    one. Those refuse where they are asked (``price_band._basis_of_the_pair``,
    ``agent.tools.price_check``) rather than by withholding the whole window from
    the seventeen fields that never look at a published price at all.
    """
    bases = {row.price_basis for row in rows}
    if len(bases) > 1:
        return SignalIssue.MIXED_PRICE_BASIS
    return None


def _adjusts_from_actions(rows: Iterable[SessionSnapshot]) -> bool:
    """Whether this window's prices still have their entitlements in them.

    True only for a window that is ``raw`` throughout. An empty window answers
    False, which costs nothing: there is nothing to rebase either way.
    """
    return {row.price_basis for row in rows} == {PriceBasis.RAW}


def _read_bands(
    window: Sequence[date],
    usable: dict[date, MarketSnapshot],
    regimes: dict[date, BandRegime],
    anchor_date: date | None,
    anchor_row: MarketSnapshot | None,
    by_ex_date: dict[date, list[CorporateAction]],
) -> tuple[dict[date, BandReading], SignalIssue | None, dict[date, SignalIssue]]:
    """Judge every session against its band, and refuse a move nothing explains.

    A session that broke its band is not a session the market went mad in; it is
    a session whose anchor is wrong. Usually that is an ex-date the exchange
    adjusted its reference for and the previous close did not follow, and the
    stored action series is what tells the two apart.

    A gap **downward** with an action on that date is accounted for, and the
    window is served with the adjustment applied. A gap downward with nothing on
    that date is ``unexplained_price_gap``. A gap **upward** is refused whatever
    the action series says: an entitlement is taken out of a share and never
    added to it, so no corporate action can produce one, and taking an action as
    its explanation would let a rally excuse a wrong anchor.
    """
    bands: dict[date, BandReading] = {}
    undecided: dict[date, SignalIssue] = {}

    previous_date = anchor_date
    previous_row = anchor_row
    for day in window:
        target = usable.get(day)
        if target is None:
            continue
        reading = measure_band(regimes[day], target, previous_row, previous_date)
        previous_date, previous_row = day, target

        if reading.degraded_reason is SignalIssue.PRICE_MOVE_EXCEEDS_BAND:
            downward = (
                reading.limits is not None
                and target.low_price is not None
                and Decimal(str(target.low_price)) < reading.limits.floor
            )
            if not downward or day not in by_ex_date:
                logger.info(
                    "Refusing %s's window: %s moved outside its band with %s",
                    regimes[day].symbol,
                    day,
                    "no action on that date"
                    if day not in by_ex_date
                    else "a break upward, which no action produces",
                )
                return bands, SignalIssue.UNEXPLAINED_PRICE_GAP, undecided
            # An ex-date the store knows about. The session is not judged for a
            # lock — its anchor is the pre-adjustment close, so the band it was
            # measured against was never this session's band, and neither the
            # verdict nor the limits it was measured from describe this session.
            # Recorded as undecided under the reason that made it so, like every
            # other session nobody could judge: left out, Window Health would
            # report a window with fewer unjudged sessions than it has, and a
            # field reading the bars would find an absent band the health does
            # not account for.
            bands[day] = _unmeasured(reading)
            undecided[day] = SignalIssue.PRICE_MOVE_EXCEEDS_BAND
            continue

        if reading.degraded_reason is not None:
            undecided[day] = reading.degraded_reason
        bands[day] = reading

    return bands, None, undecided


def _unmeasured(reading: BandReading) -> BandReading:
    """The same session with the band it was wrongly measured against removed."""
    return BandReading(
        symbol=reading.symbol,
        session_date=reading.session_date,
        regime=reading.regime,
        anchor=None,
        anchor_date=None,
        limits=None,
        lock=LimitLock.INDETERMINATE,
        degraded_reason=reading.degraded_reason,
    )


def _factors(
    window: Sequence[date],
    usable: dict[date, SessionSnapshot],
    by_ex_date: dict[date, list[CorporateAction]],
) -> tuple[dict[date, Decimal], list[SignalIssue]]:
    """The Adjustment Factor of every ex-date in the window that has a usable one.

    The factor comes from the actions' declared terms and never from the gap at
    the ex-date: that gap is the entitlement and the session's ordinary move
    together, so measuring the factor from it would fold one day of news into
    every price before the date, permanently, and it would be circular besides.

    An ex-date the store cannot price does not stop the window — it degrades it
    with the reason it could not be priced, which is either an action nothing
    corroborates or terms that do not add up to a factor.
    """
    factors: dict[date, Decimal] = {}
    issues: list[SignalIssue] = []

    ordered = [day for day in window if day in by_ex_date]
    for ex_date in ordered:
        previous_close = _close_before(window, usable, ex_date)
        if previous_close is None:
            # No stored session before the ex-date inside this window, so there
            # is nothing to rebase and nothing to rebase it from.
            continue
        reading = adjustment_factor(by_ex_date[ex_date], previous_close)
        if reading.factor is None:
            if reading.refusal is not None and reading.refusal not in issues:
                issues.append(reading.refusal)
            continue
        factors[ex_date] = reading.factor
    return factors, issues


def _close_before(
    window: Sequence[date],
    usable: dict[date, SessionSnapshot],
    day: date,
) -> Decimal | None:
    """The newest stored raw close strictly before this session in the window."""
    for candidate in reversed([item for item in window if item < day]):
        row = usable.get(candidate)
        if row is not None and row.last_price is not None and row.last_price > 0:
            return Decimal(str(row.last_price))
    return None


@dataclass(frozen=True)
class SharesOnRecord:
    """How many shares a symbol has, and when that was last observed.

    Named for the record rather than for the count, because
    ``providers/contracts.ShareCount`` already exists in this same tree and means
    something narrower — one typed count off a provider payload, with no date on
    it. Two dataclasses under one name in one package is a shadow waiting for the
    first person who adds an import; this one carries the observation day, which
    is the whole reason it exists.

    Two fields rather than one because a share count is only ever *last known*:
    the reference capability is written by a scan, not by a session, so a count
    read today may have been observed a fortnight ago. A caller multiplying a
    close by it is entitled to know which, and ``observed_on`` is what lets a
    frame say ``stale_shares`` instead of publishing a valuation as though it
    were measured on the session it is drawn against.
    """

    symbol: str
    shares: int
    share_type: str
    observed_on: date


def reference_snapshots(
    session: Session,
    symbols: Sequence[str],
    *,
    on_or_before: date | None = None,
) -> dict[str, tuple[ReferenceSnapshot, date]]:
    """The newest stored reference row for each symbol at or before a date.

    Reads ``provider_snapshots`` under the reference capability, which is where
    the scan writes a listing's share types and its foreign room.

    **``on_or_before`` is what makes a past window answerable.** The room and the
    share count carry no period of their own — they are dated by the session the
    board was read in — so a read with no cutoff answers *today* whatever day it
    was asked about. A cross-section computed for a session in March would then
    be multiplied by a share count issued in August, and the same historical
    cutoff would give a different answer every day it was recomputed. The cutoff
    is spelled exactly as ``reference.foreign_room_on_or_before`` spells it, for
    the same reason: two readers of one table that disagree about which day a row
    belongs to are two answers to one question.

    Newest observation per symbol wins and the rest are skipped. The table is
    append-only, so a symbol whose count changed at a share issue holds both
    rows, and the older one describes a company that no longer exists.

    Here rather than in a reader of its own, and not in ``providers/store.py``:
    two callers need exactly this — the market-capitalisation branch below, and
    the ``reference`` source of the query tool. ``src/stocks`` may not import
    ``src/agent``, so the shared read has to live on this side of that edge, and
    ``store.py``'s own docstring says not to grow it. It is not a rewrite of
    ``foreign_room_on_or_before`` either: that one answers one symbol's room,
    this one answers many symbols' whole reference row, and collapsing them would
    make the room read pay for a share count nobody asked it for.

    A row that does not validate is skipped with a warning rather than raising.
    One malformed payload is one symbol's problem, and a cross-sectional read of
    the whole Universe should not stop because a scan wrote a bad row for a
    company nobody asked about.
    """
    wanted = [symbol.strip().upper() for symbol in symbols if symbol and symbol.strip()]
    if not wanted:
        return {}

    query = select(ProviderSnapshot).where(
        ProviderSnapshot.capability == Capability.REFERENCE.value,
        ProviderSnapshot.symbol.in_(wanted),
        ProviderSnapshot.source == main_source(Capability.REFERENCE).value,
    )
    if on_or_before is not None:
        cutoff = datetime.combine(
            on_or_before + timedelta(days=1), time.min, tzinfo=VN_TZ
        )
        query = query.where(ProviderSnapshot.effective_at < cutoff)

    rows = session.execute(
        query.order_by(
            ProviderSnapshot.symbol,
            ProviderSnapshot.effective_at.desc(),
            ProviderSnapshot.observed_at.desc(),
        )
    ).scalars()

    newest: dict[str, tuple[ReferenceSnapshot, date]] = {}
    for row in rows:
        if row.symbol in newest:
            continue
        try:
            snapshot = ReferenceSnapshot.model_validate(row.payload)
        except Exception:  # noqa: BLE001 - a malformed row is one symbol, not the read
            logger.warning(
                "reference snapshot for %s did not validate; skipping", row.symbol
            )
            continue
        # ``astimezone(VN_TZ)`` and not ``.date()``: a row written at one in the
        # morning Vietnam time is a different calendar day in UTC, and the other
        # reader of this table already resolves it this way.
        newest[row.symbol] = (snapshot, row.effective_at.astimezone(VN_TZ).date())
    return newest


def share_counts(
    session: Session,
    symbols: Sequence[str],
    *,
    on_or_before: date | None = None,
) -> dict[str, SharesOnRecord]:
    """The newest stored share count for each symbol, in one query.

    A projection of :func:`reference_snapshots` rather than a second read. The
    choice between ``outstanding``, ``listed`` and ``issued`` is not made here —
    ``ReferenceSnapshot.canonical_shares()`` already owns it, and a second
    ordering written beside it is a second answer that can disagree.
    """
    counts: dict[str, SharesOnRecord] = {}
    for symbol, (snapshot, observed_on) in reference_snapshots(
        session, symbols, on_or_before=on_or_before
    ).items():
        count = snapshot.canonical_shares()
        if count is None or count.value <= 0:
            continue
        counts[symbol] = SharesOnRecord(
            symbol=symbol,
            shares=int(count.value),
            share_type=count.share_type.value,
            observed_on=observed_on,
        )
    return counts


def _frame(
    symbol: str,
    window: Sequence[date],
    usable: dict[date, SessionSnapshot],
    bands: dict[date, BandReading],
    factors: dict[date, Decimal],
    projection: BarProjection,
    series: BarSeries,
    shares: SharesOnRecord | None = None,
) -> BarFrame:
    """Build the window's bars, rebased onto its last session's share terms.

    A bar is multiplied by every factor whose ex-date falls *after* it. On the
    ex-date itself the exchange has already taken the entitlement out, so that
    session and everything after it are left as published — which is why the
    window's newest prices are the raw ones.
    """
    bars: list[Bar] = []
    for day in window:
        row = usable.get(day)
        if row is None:
            continue
        factor = Decimal(1)
        for ex_date, value in factors.items():
            if ex_date > day:
                factor *= value
        # Read off the contract rather than tested for here: only the stored
        # session knows whether there is a company behind it, and a second test
        # in this loop could disagree with the first.
        market_cap_vnd, foreign_net_value_vnd = row.company_figures
        if market_cap_vnd is None and shares is not None:
            # Derived, and only where the session did not carry one. ``bar_daily``
            # holds no market capitalisation — the column belonged to the source
            # retired on 2026-08-29 — so every equity session now arrives without
            # one, and three of VCB's Signal Fields refused for want of a number
            # the store has the two halves of.
            #
            # The close *as published on that session*, not the rebased one: a
            # share count is a count on the day it was observed, and multiplying
            # it by a price rescaled into the window's newest share terms would
            # apply the split twice. The raw close is ``row.last_price``; the
            # rebased one is what goes into ``Bar.close`` a few lines below.
            #
            # **Two dates have to agree before this is a number at all**, and
            # this is where the old honest refusal is kept rather than traded
            # away. A share count read *after* the session describes a company
            # the session did not have — a share issue between the two makes the
            # valuation wrong by exactly the issue. And a count older than the
            # reference Capability's own freshness contract describes a company
            # that has since moved: ``REFERENCE_STALE_DAYS`` is that contract,
            # read off it rather than restated here. Outside either bound the
            # bar keeps ``None``, and the field refuses with
            # ``market_cap_absent`` exactly as it did before this branch existed.
            # Serving a wrong number with every freshness signal reading "fine"
            # is strictly worse than refusing.
            age = (day - shares.observed_on).days
            close_as_published = row.last_price
            if close_as_published is not None and 0 <= age <= REFERENCE_STALE_DAYS:
                market_cap_vnd = float(close_as_published) * shares.shares
        bars.append(
            Bar(
                session_date=day,
                open=_scaled(row.open_price, factor),
                high=_scaled(row.high_price, factor),
                low=_scaled(row.low_price, factor),
                close=_scaled(row.last_price, factor),
                volume=row.volume,
                total_value_vnd=row.total_value_vnd,
                market_cap_vnd=market_cap_vnd,
                foreign_net_value_vnd=foreign_net_value_vnd,
                adjustment_factor=factor,
                limit_lock=_lock_of(bands.get(day), series),
                band=bands[day].limits if day in bands else None,
                band_undecided_reason=_undecided_reason(
                    bands.get(day), projection, series
                ),
                change_pct=row.change_pct,
            )
        )
    return BarFrame(symbol=symbol, bars=tuple(bars))


def _lock_of(reading: BandReading | None, series: BarSeries) -> LimitLock:
    """Whether this session traded at a limit, or why that is not a question.

    ``NOT_APPLICABLE`` on a series with no band, and it is a different answer
    from ``INDETERMINATE``: the latter is the store admitting it could not judge
    a session that does have a band, and using it for an index would leave an
    equity's word on the one bar that most needs not to carry one.
    """
    if not series.has_price_band:
        return LimitLock.NOT_APPLICABLE
    return reading.lock if reading is not None else LimitLock.INDETERMINATE


def _undecided_reason(
    reading: BandReading | None,
    projection: BarProjection,
    series: BarSeries,
) -> SignalIssue | None:
    """Why this session has no band, or nothing where it has one.

    The pairing ``Bar`` promises: a served bar carries either its band or the
    reason it has none, never neither, so a field downstream never has to guess
    why a band is absent.

    Three ways a band can be missing, and they are kept apart because the fix
    for each is different. An index has no band **at all** — no board, no
    reference price to take a percentage of — and that is answered first, before
    the projection: it is a fact about the instrument rather than about what
    this window asked for. A window prepared for quantities has no band because
    nobody asked. Anything left is a listed session the store could not judge,
    and it carries the reason it could not.
    """
    if not series.has_price_band:
        return SignalIssue.BAND_NOT_APPLICABLE
    if projection is not BarProjection.PRICE:
        return SignalIssue.BAND_NOT_MEASURED
    if reading is None:
        return SignalIssue.MISSING_TARGET_SESSION
    if reading.limits is not None:
        return None
    return reading.degraded_reason or SignalIssue.EXCHANGE_UNKNOWN


def _scaled(price: float | None, factor: Decimal) -> float | None:
    if price is None:
        return None
    if factor == 1:
        return price
    return float(Decimal(str(price)) * factor)


def _window_regime(
    window: Sequence[date],
    regimes: dict[date, BandRegime],
) -> WindowBandRegime | None:
    """The band that applied over the window, reported from the newest session.

    The newest rather than an average, because that is the regime a reader asking
    "what may this symbol move by" means. Whether it held for the whole window is
    the separate answer beside it.
    """
    dated = [regimes[day] for day in window if day in regimes]
    if not dated:
        return None
    newest = dated[-1]
    return WindowBandRegime(
        exchange=newest.exchange,
        limit_ratio=newest.limit_ratio,
        anchor_basis=newest.anchor_basis,
        exchange_as_of=newest.exchange_as_of,
        uniform=len({regime.exchange for regime in dated}) == 1,
    )


def _adtv_standing(
    session: Session,
    symbol: str,
    window: Sequence[date],
    usable: dict[date, SessionSnapshot],
    peers: Sequence[str] | None,
    context: BarPreparationContext | None = None,
) -> AdtvStanding | None:
    """Where this symbol's traded money sits among its peers over the same days.

    Traded **money** rather than traded shares, because money is the one quantity
    a corporate action leaves alone: an ADTV in shares crosses an ex-date and
    changes unit, an ADTV in dong does not (``docs/adr/0006``).

    ``None`` rather than a number wherever the answer would not mean one — too
    few peers to rank against, or a symbol whose own sessions carry no traded
    money at all. A percentile computed over eleven names is a rank dressed up as
    a distribution.
    """
    days = [day for day in window if day in usable][-ADTV_SESSIONS:]
    if not days:
        return None

    mine = average_over_sessions(usable[day].total_value_vnd for day in days)
    if mine is None:
        return None

    names = tuple(peers) if peers is not None else build_universe(session).symbols
    others = [name.upper() for name in names if name.upper() != symbol]
    floor = min_sample_for(len(others))
    if len(others) < floor:
        return None

    # A context already holds every one of these symbols' sessions across the
    # same window, loaded once for the whole batch. Read from it rather than
    # asking again: the standing is measured per prepared window, so a caller
    # preparing a hundred symbols would otherwise pay this cross-sectional read
    # a hundred times over for one answer that does not change between them.
    held = (
        context._sessions
        if context is not None and set(others) <= set(context._symbols)
        else sessions_on_days(session, others, days)
    )
    measured = [
        value
        for name in others
        if (value := _peer_average(held.get(name, {}), days)) is not None
    ]
    if len(measured) < floor:
        return None

    below = sum(1 for value in measured if value <= mine)
    return AdtvStanding(
        average_value_vnd=mine,
        percentile=below / len(measured),
        n=len(measured),
        as_of=days[-1],
    )


def _peer_average(
    held: dict[date, SessionSnapshot],
    days: Sequence[date],
) -> float | None:
    """One peer's average traded money over exactly these sessions."""
    return average_over_sessions(
        None if (row := held.get(day)) is None else row.total_value_vnd
        for day in days
    )


def average_over_sessions(values: Iterable[float | None]) -> float | None:
    """The average across exactly these sessions, or nothing if any is missing.

    All or nothing on purpose: a symbol that traded on twelve of the twenty days
    has an average over a different stretch of market than the symbol beside it,
    and ranking the two together would present them as comparable.

    Deliberately **unit-neutral**. The gateway averages traded money over rows
    it has just loaded while the liquidity fields average money over one window
    and shares over another, and all of them need the same all-or-nothing rule;
    a helper named for one of the two denominations would be read as licence to
    call it on the other, which is the swap the money/quantity naming split
    exists to prevent. Each caller states its own unit.
    """
    collected: list[float] = []
    for value in values:
        if value is None:
            return None
        collected.append(value)
    if not collected:
        return None
    return sum(collected) / len(collected)
