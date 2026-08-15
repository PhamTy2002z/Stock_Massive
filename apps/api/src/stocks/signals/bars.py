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

## Four refusals

| Refusal | Cause |
| --- | --- |
| ``insufficient_history`` | fewer sessions than the field's minimum |
| ``mixed_price_basis`` | the window crosses a **Price Basis** seam |
| ``unadjustable_price_basis`` | the window lies wholly in the adjusted-at-source era |
| ``unexplained_price_gap`` | a session moved further than its band permits, and no stored action accounts for it |

The two basis refusals are not degradations. A raw close and an
``adjusted_at_source`` close are not two measurements of the same thing, so a
window holding both is meaningless rather than weaker, and a window holding only
the second cannot be recomputed from anything stored — that basis was fixed at
``observed_at`` and has decayed with every action since.

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
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.stocks.models import CorporateAction

from ..providers.contracts import Exchange, MarketSnapshot, PriceBasis
from ..trading_day import latest_trading_day, trading_days_before
from ..universe import build_universe
from .corporate_actions import CorporateActionStore, adjustment_factor
from .fields import DEGRADED_LIMIT_LOCK_SHARE
from .issues import SignalIssue
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
# (``docs/adr/0010``, the same floor the cross-sectional fields refuse under).
ADTV_MIN_PEERS = 30


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
    # and an adjusted price does not sit on one (``price_band``). ``None`` where
    # the band could not be decided at all, which is every UPCOM session (its
    # anchor is not stored) and every session whose predecessor the store does
    # not hold. Kept beside the lock verdict rather than recomputed downstream,
    # because the anchor it was measured from is the previous session's raw
    # close and only the gateway still has it.
    band: BandLimits | None = None
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

    @property
    def limit_locked(self) -> bool:
        return self.limit_lock in (LimitLock.CEILING, LimitLock.FLOOR)

    @property
    def raw_close(self) -> float | None:
        """This session's close as the exchange published it.

        The band above is in raw prices and ``close`` is in the window's rebased
        ones, so a distance between the two is only a distance once the
        Adjustment Factor is divided back out. On a window with no action in it
        the factor is 1 and the two are the same number.
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


def prepare_bars(
    session: Session,
    symbol: str,
    window_days: int,
    *,
    min_sessions: int | None = None,
    end: date | None = None,
    peers: Sequence[str] | None = None,
    migrations: Sequence[ExchangeMigration] = EXCHANGE_MIGRATIONS,
) -> tuple[BarFrame | None, WindowHealth]:
    """Serve ``window_days`` trailing sessions of one symbol, or refuse by name.

    ``end`` defaults to the newest Trading Day the store holds; a named one is a
    question about that session and is taken as asked. ``min_sessions`` is the
    calling field's floor and defaults to the whole window — below it the answer
    is an ``insufficient_history`` refusal, never a quietly shortened window.

    ``peers`` is the cross-section the liquidity percentile is measured against,
    and defaults to the Universe. A caller preparing many symbols at once should
    pass it, so the Universe is resolved once rather than per symbol.
    """
    symbol = symbol.upper()
    window_days = max(0, window_days)
    floor = window_days if min_sessions is None else min_sessions

    end = end or latest_trading_day(session)
    if end is None or window_days == 0:
        return None, _refused(
            symbol, window_days, floor, SignalIssue.INSUFFICIENT_HISTORY
        )

    # One extra session before the window: the first bar's band is measured
    # against the close before it, and without an anchor the window's oldest
    # session could never be judged for a lock or a gap.
    earlier = trading_days_before(session, end, window_days)
    window = tuple(reversed(earlier[: window_days - 1])) + (end,)
    anchor_date = earlier[window_days - 1] if len(earlier) >= window_days else None

    held = sessions_in_range(session, symbol, anchor_date or window[0], end)
    bars_held = {day: held[day] for day in window if day in held}
    usable = {
        day: row for day, row in bars_held.items() if row.last_price is not None
    }
    sessions_used = len(usable)
    if sessions_used < floor:
        return None, _refused(
            symbol,
            window_days,
            floor,
            SignalIssue.INSUFFICIENT_HISTORY,
            sessions_used=sessions_used,
        )

    basis_refusal = _basis_of(usable.values())
    if basis_refusal is not None:
        return None, _refused(
            symbol,
            window_days,
            floor,
            basis_refusal,
            sessions_used=sessions_used,
        )

    resolver = BandRegimeResolver(session, symbol, migrations=migrations)
    regimes = {day: resolver.on(day) for day in usable}

    actions = CorporateActionStore(session).for_symbol(
        symbol, start=window[0], end=window[-1]
    )
    by_ex_date: dict[date, list[CorporateAction]] = {}
    for action in actions:
        assert action.ex_date is not None  # for_symbol excludes the undated
        by_ex_date.setdefault(action.ex_date, []).append(action)

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

    factors, adjustment_issues = _factors(window, usable, by_ex_date)
    frame = _frame(symbol, window, usable, bands, factors)

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
        adtv=_adtv_standing(session, symbol, window, usable, peers),
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
        first_session=None,
        last_session=None,
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


def _basis_of(rows: Iterable[MarketSnapshot]) -> SignalIssue | None:
    """What the window's Price Basis values say about serving it, if anything.

    Only an all-``raw`` window is served. Two bases in one window is a symbol's
    own Backfill seam falling inside it, which is meaningless rather than
    degraded; one basis that is ``adjusted_at_source`` throughout is a window
    fixed at somebody else's ``observed_at``, which nothing stored can undo.
    """
    bases = {row.price_basis for row in rows}
    if not bases or bases == {PriceBasis.RAW}:
        return None
    if len(bases) > 1:
        return SignalIssue.MIXED_PRICE_BASIS
    return SignalIssue.UNADJUSTABLE_PRICE_BASIS


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
            bands[day] = _unmeasured(reading)
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
    usable: dict[date, MarketSnapshot],
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
    usable: dict[date, MarketSnapshot],
    day: date,
) -> Decimal | None:
    """The newest stored raw close strictly before this session in the window."""
    for candidate in reversed([item for item in window if item < day]):
        row = usable.get(candidate)
        if row is not None and row.last_price is not None and row.last_price > 0:
            return Decimal(str(row.last_price))
    return None


def _frame(
    symbol: str,
    window: Sequence[date],
    usable: dict[date, MarketSnapshot],
    bands: dict[date, BandReading],
    factors: dict[date, Decimal],
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
        bars.append(
            Bar(
                session_date=day,
                open=_scaled(row.open_price, factor),
                high=_scaled(row.high_price, factor),
                low=_scaled(row.low_price, factor),
                close=_scaled(row.last_price, factor),
                volume=row.volume,
                total_value_vnd=row.total_value_vnd,
                market_cap_vnd=row.market_cap_vnd,
                foreign_net_value_vnd=row.foreign_net_value_vnd,
                adjustment_factor=factor,
                limit_lock=(
                    bands[day].lock if day in bands else LimitLock.INDETERMINATE
                ),
                band=bands[day].limits if day in bands else None,
            )
        )
    return BarFrame(symbol=symbol, bars=tuple(bars))


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
    usable: dict[date, MarketSnapshot],
    peers: Sequence[str] | None,
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

    mine = average_traded_money(usable[day].total_value_vnd for day in days)
    if mine is None:
        return None

    names = tuple(peers) if peers is not None else build_universe(session).symbols
    others = [name.upper() for name in names if name.upper() != symbol]
    if len(others) < ADTV_MIN_PEERS:
        return None

    held = sessions_on_days(session, others, days)
    measured = [
        value
        for name in others
        if (value := _peer_average(held.get(name, {}), days)) is not None
    ]
    if len(measured) < ADTV_MIN_PEERS:
        return None

    below = sum(1 for value in measured if value <= mine)
    return AdtvStanding(
        average_value_vnd=mine,
        percentile=below / len(measured),
        n=len(measured),
        as_of=days[-1],
    )


def _peer_average(
    held: dict[date, MarketSnapshot],
    days: Sequence[date],
) -> float | None:
    """One peer's average traded money over exactly these sessions."""
    return average_traded_money(
        None if (row := held.get(day)) is None else row.total_value_vnd
        for day in days
    )


def average_traded_money(values: Iterable[float | None]) -> float | None:
    """Average traded money across these sessions, or nothing if any is missing.

    All or nothing on purpose: a symbol that traded on twelve of the twenty days
    has an average over a different stretch of market than the symbol beside it,
    and ranking the two together would present them as comparable.

    Shared with the liquidity field rather than spelled twice, because the
    gateway measures this over rows it has just loaded while the field measures
    it over the bars it was served, and the two have to be the same ADTV or the
    percentile beside a number would be ranking something else.
    """
    collected: list[float] = []
    for value in values:
        if value is None:
            return None
        collected.append(value)
    if not collected:
        return None
    return sum(collected) / len(collected)
