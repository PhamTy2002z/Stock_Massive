"""How tradeable a symbol is, where it sits in its band, and how stretched it is.

Three questions about one symbol's own behaviour, and the liquidity answer gates
the other two. Thin trading on this market is not a nuisance to be smoothed over
before the interesting statistics run — on UPCOM it is the fact a reader most
needs, and a band distance or a mean-reversion z computed over a symbol that
matched eleven times in a month is arithmetic about nothing.

## Liquidity — and why there are two ADTVs rather than one with a note

**Amihud (2002)**, *J. Financial Markets* 5(1) 31–56: illiquidity is the price
move a unit of traded money buys, ``mean(|R_t| / DVOL_t)``. Reported here in
percent of price per **billion** dong, because a Vietnamese mid-cap trades in
single-digit billions a session and a ratio quoted per dong is a number with
eleven leading zeros.

The traded-money and traded-share averages are **separate registered fields**,
not one figure carrying a unit label. A share-count-changing action moves the
unit of the second partway through a window and leaves the first alone
(``docs/adr/0006``), so they are not two spellings of one quantity: the money
ADTV crosses an ex-date safely and the share ADTV does not. Splitting them is
what makes the degradation attachable — the serving layer reads the declared
unit and degrades the share figure, so a field cannot forget to say so.

A session with no trading at all is **counted, not averaged**. Dividing a price
move by no traded money is not a measurement of illiquidity, and a zero-volume
count is the honest form of what that session had to say.

## Band pressure — where the anchor comes from the exchange, or nowhere

The band is dated per session and its anchor is the board's, not this system's:
HOSE and HNX measure from the previous close, which the store holds; UPCOM
measures from the previous day's round-lot continuous VWAP, which it does not
and cannot reconstruct — the stored turnover covers put-through and odd-lot
trades too (``price_band``). So a UPCOM session reaches this field with no band
at all, and the distance is **withheld under ``anchor_not_stored``** rather than
measured off the previous close, which would answer with the right shape and the
wrong number.

Base rates are the symbol's own, over its own trailing window. Never a
full-sample norm and never a market-wide one: that is the measured failure the
whole package is built against, where the same event scored z = +151.5 on one
run and +135.6 on a longer one.

Two counts, not one. A session **locked** at its ceiling never traded away from
it — an order book that could not clear, and a bar with no range at all. A
session that **closed** at its ceiling after trading below it is buying pressure
and has a perfectly readable range. Folding them together would make the two
look like one fact.

## Mean reversion — descriptive, and with two contract rules that bite

A z against the symbol's own trailing mean, plus the AR(1) half-life that says
whether the series reverts at all: ``half-life = −ln 2 / ln φ̂``, with φ̂ from
regressing Δx on its own lag with an intercept. That is exponential-decay
arithmetic on the OU/AR(1) model and standard practice (Chan 2013 ch. 2) — there
is no originating half-life paper and this module does not pretend one exists.

**Where the half-life reaches the window length, the z is suppressed.** At that
point the sample carries no reversion to measure and the z is describing the
window's own mean rather than the market. Suppressed rather than flagged,
because a number with a caveat beside it is a number that gets read.

**Where the half-life is under about three sessions, the gauge says the signal
is not round-trip actionable.** Vietnamese settlement is T+2, so a move that has
half-decayed before the shares are deliverable cannot be traded round trip at
all. The tool states the floor rather than leaving a reader to discover it.

Pairs trading and cointegration are **rejected** and no part of this module. They
need a short leg VN retail cannot take, they lose a third of their return to one
day of execution delay (Gatev et al. 2006: 1.44 → 0.90%/month), and a hundred
symbols is nearly five thousand pairs of multiple testing on around 250
observations.

## Nothing here fires

No field in this cluster carries a threshold, and that is a decision rather than
work left undone. Every candidate — a "stretched" z, a "thin" liquidity flag —
is one narration away from a claim about what the price does next, and the
research behind this cluster could verify no such claim for this market. A later
author who wants one derives it from the null harness like any other; what is
refused is shipping one because the shape of the statistic invites it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from .bars import ADTV_SESSIONS, Bar, BarFrame, average_over_sessions
from .fields import Denomination, FieldReading, FieldWindow
from .issues import SignalIssue
from .moments import mean_standard_error

# The stretch an ADTV averages over. Twenty sessions because that is what ADTV
# means in this market's own vocabulary, and it is the same twenty the gateway
# ranks a symbol's peers over — one number, not two that nearly agree.
LIQUIDITY_SESSIONS = ADTV_SESSIONS

# Window plus skip, and this one skips nothing. The extra session is the close
# Amihud's return term is measured from.
LIQUIDITY_MIN_SESSIONS = LIQUIDITY_SESSIONS + 1

# What a billion dong is, written once. Amihud's ratio is quoted per billion
# because a Vietnamese mid-cap trades single-digit billions a session, and per
# dong the same number is eleven leading zeros.
ONE_BILLION_VND = 1e9

# The trailing stretch band pressure counts over. A quarter of trading: long
# enough that a base rate over it is not one bad week, short enough that "how
# often does this symbol lock" is still a question about the symbol as it trades
# now. The gateway serves the session before the window as the first bar's
# anchor, so nothing is added here for it.
BAND_PRESSURE_SESSIONS = 60
BAND_PRESSURE_MIN_SESSIONS = BAND_PRESSURE_SESSIONS

# The stretch the mean-reversion gauge fits over, and the length its own
# half-life is compared against. Sixty for the same reason as the volatility
# regime's baseline: long enough for a mean to mean something, short enough that
# "its own recent history" is still recent.
MEAN_REVERSION_SESSIONS = 60
MEAN_REVERSION_MIN_SESSIONS = MEAN_REVERSION_SESSIONS + 1

# Vietnamese settlement. A signal whose half-life is under this cannot be traded
# round trip at all, because the shares are not deliverable until it has already
# decayed — so the gauge says so rather than leaving a reader to find out.
SETTLEMENT_FLOOR_SESSIONS = 3

# The half-life interval is block-resampled, so it needs a block length, a path
# count and a seed. The seed is frozen and the reading is therefore
# deterministic: a field whose confidence interval moved between two calls on
# the same window would be one nobody could cite.
#
# Ten sessions is a fortnight of trading — long enough to carry the local
# dependence a half-life is estimated from, short enough that a sixty-session
# window is not resampled as three copies of one block.
MEAN_REVERSION_BLOCK_SESSIONS = 10

# Four hundred paths is what a 90% interval needs and no more: its bounds are
# the 20th and 380th order statistics, each resting on hundreds of draws, so a
# rerun moves them by a fraction of a session. This is **not** a null
# calibration and ADR-0010's floor of a thousand paths does not apply to it —
# that floor bounds a measured false-positive rate, a tail quantity where a
# handful of paths decide the answer, while this is an interval around a point
# estimate computed on every call and therefore paying for itself per request.
MEAN_REVERSION_BOOTSTRAP_PATHS = 400
MEAN_REVERSION_BOOTSTRAP_SEED = 20260815

# The interval reported around the half-life. The 90% band rather than 95%,
# because the tails of a bootstrapped half-life on sixty observations are where
# the censoring below lives and a 95% band would mostly be reporting it.
HALF_LIFE_INTERVAL = 0.90

# How close a rebased close has to sit to a limit price to be that limit price.
# A raw close divided back out of its Adjustment Factor is a float that has been
# through a decimal round trip, so it lands within a few units in the last place
# of the number the exchange published rather than exactly on it. A relative
# tolerance of a billionth is a thousand times that error and a millionth of one
# tick, so it cannot admit a close that was genuinely a tick away.
CLOSE_AT_BAND_TOLERANCE = 1e-9

_LOG2 = math.log(2.0)


# --- Liquidity ------------------------------------------------------------


def _recent(frame: BarFrame, sessions: int) -> tuple[Bar, ...]:
    """The newest ``sessions`` bars of a window, oldest first."""
    return frame.bars[-sessions:] if sessions > 0 else ()


def adtv_money_reading(window: FieldWindow) -> FieldReading:
    """Average daily traded **money** over the newest twenty sessions.

    Refused rather than averaged where any of the twenty is missing its traded
    money: an average over twelve of them is an average over a different stretch
    of market, and printing it beside another symbol's twenty would present the
    two as comparable.

    The per-session money is an estimate — close times volume, because the
    source reports no traded value — so this average inherits that estimate's
    error. ``sessions.py::_traded_value`` is where it is derived and what it is
    worth. A session that did not trade arrives as missing rather than as zero,
    which is what makes the refusal above fire instead of the average silently
    sagging.
    """
    bars = _recent(window.frame, LIQUIDITY_SESSIONS)
    values = [bar.total_value_vnd for bar in bars]
    average = average_over_sessions(values)
    if average is None:
        return FieldReading(
            value=None, refusal=SignalIssue.TRADED_FIGURE_NOT_STORED
        )

    measured = [value for value in values if value is not None]
    return FieldReading(
        value=average,
        extras={
            "standard_error": mean_standard_error(measured),
            # Stated on the field rather than left to the name. The whole point
            # of splitting money from shares is that a reader never has to infer
            # which one a figure is.
            "adtv_basis": Denomination.MONEY.value,
            "sessions": len(bars),
            "limit_lock_days": sum(1 for bar in bars if bar.limit_locked),
        },
    )


def adtv_shares_reading(window: FieldWindow) -> FieldReading:
    """Average daily traded **shares** over the newest twenty sessions.

    The figure that does not survive an ex-date. Nothing here rescales it — the
    price factor is not the quantity factor and ACB's 2025 action multiplies the
    share count by 1.15 while multiplying past prices by 0.8355 — so a window
    holding a share-count change degrades this field, decided from its declared
    unit in ``serving``.
    """
    bars = _recent(window.frame, LIQUIDITY_SESSIONS)
    volumes = [
        None if bar.volume is None else float(bar.volume) for bar in bars
    ]
    average = average_over_sessions(volumes)
    if average is None:
        return FieldReading(
            value=None, refusal=SignalIssue.TRADED_FIGURE_NOT_STORED
        )

    measured = [value for value in volumes if value is not None]
    return FieldReading(
        value=average,
        extras={
            "standard_error": mean_standard_error(measured),
            "adtv_basis": Denomination.SHARES.value,
            "sessions": len(bars),
            "quantities_comparable": window.health.quantities_comparable,
        },
    )


def amihud_illiquidity_reading(window: FieldWindow) -> FieldReading:
    """Amihud (2002): percent of price moved per billion dong traded.

    ``mean(|R_t| / DVOL_t)`` over the newest twenty sessions, with ``R`` the
    simple session return the published definition uses rather than the log
    return the rest of this package computes volatility from — the ratio is
    Amihud's and is reported in his terms.

    Sessions that did not trade are counted and left out of the mean. A price
    move divided by no traded money is not an unbounded illiquidity, it is a
    session with nothing to measure, and the count beside the number is what
    that session actually said.

    **The denominator is an estimate, and this is the field it hurts most.**
    Traded money is derived as close times volume
    (``sessions.py::_traded_value``); its error is close-versus-session-average
    and is therefore largest on the sessions that moved furthest. Those are
    exactly the sessions this ratio weights heaviest, because ``|R_t|`` is its
    numerator. The ratio is still the right shape — a big move on thin money
    still reads as illiquid — but a single session's term should not be quoted
    as a measurement.
    """
    bars = _recent(window.frame, LIQUIDITY_SESSIONS + 1)
    terms: list[float] = []
    zero_volume = 0
    for previous, bar in zip(bars, bars[1:]):
        traded = bar.total_value_vnd
        if traded is None or traded <= 0 or bar.volume == 0:
            zero_volume += 1
            continue
        if previous.close is None or bar.close is None or previous.close <= 0:
            continue
        move = abs(bar.close / previous.close - 1.0) * 100.0
        terms.append(move / (traded / ONE_BILLION_VND))

    if not terms:
        # Every session in the window traded nothing, so there is no price move
        # per unit of money to average. Not short history — the sessions are all
        # there and each of them is the same fact about the symbol.
        return FieldReading(value=None, refusal=SignalIssue.NO_TRADED_SESSIONS)

    return FieldReading(
        value=sum(terms) / len(terms),
        extras={
            "standard_error": mean_standard_error(terms),
            "measured_sessions": len(terms),
            "zero_volume_days": zero_volume,
            "limit_lock_days": sum(1 for bar in bars if bar.limit_locked),
            "sessions": len(bars),
        },
    )


def adtv_percentile_reading(window: FieldWindow) -> FieldReading:
    """Where this symbol's traded money sits among its peers, as a percentile.

    Read off the standing the gateway measured while serving the window rather
    than computed again here. The gateway needs the same number for its own
    liquidity gate, and two computations of one percentile would be two chances
    for the figure a model cites and the figure a window was judged by to
    disagree.

    Refused where there is no standing: too few peers to rank against, or a
    symbol whose own sessions carry no traded money. A percentile over eleven
    names is a rank dressed up as a distribution.
    """
    standing = window.health.adtv
    if standing is None:
        return FieldReading(value=None, refusal=SignalIssue.RANKING_UNAVAILABLE)
    return FieldReading(
        value=100.0 * standing.percentile,
        extras={
            "n": standing.n,
            "as_of": standing.as_of.isoformat(),
            "adtv_vnd": standing.average_value_vnd,
            "adtv_basis": Denomination.MONEY.value,
            "sessions": min(len(window.frame.bars), LIQUIDITY_SESSIONS),
        },
    )


# --- Band pressure --------------------------------------------------------


def band_pressure_reading(window: FieldWindow) -> FieldReading:
    """How often this symbol reached its band, and how far it is from it now.

    The value is the count of limit-locked sessions in the window, with its
    binomial spread beside it: a symbol that locked three times in sixty
    sessions has a base rate of 5% and a count that would land anywhere between
    one and six on a rerun, which is what the standard error says.

    The distances are measured on the newest session from the band that session
    was permitted to trade in, with one sign convention for both: **positive
    means the limit sits above the close**. The ceiling distance is therefore
    the room the price still had and the floor distance is negative.

    Two things withhold rather than approximate. Where no session in the window
    could be judged at all, the field refuses under the reason the gateway
    recorded — which on UPCOM is ``anchor_not_stored``, that board's band being
    a percentage of a VWAP nothing stores. Where only some could, the count is
    served over those and the answer is degraded under the same reason.
    """
    bars = _recent(window.frame, BAND_PRESSURE_SESSIONS)
    if not bars:
        return FieldReading(value=None, refusal=SignalIssue.INSUFFICIENT_HISTORY)

    decided = [bar for bar in bars if bar.band is not None]
    undecided = [bar for bar in bars if bar.band is None]
    reason = _undecided_reason(undecided)

    if not decided:
        # Every bar without a band carries the reason it has none, so a window
        # nobody could judge always has one to refuse under.
        return FieldReading(value=None, refusal=reason or SignalIssue.EXCHANGE_UNKNOWN)

    locked = sum(1 for bar in decided if bar.limit_locked)
    at_ceiling = sum(1 for bar in decided if _closed_at(bar, ceiling=True))
    at_floor = sum(1 for bar in decided if _closed_at(bar, ceiling=False))
    rate = locked / len(decided)

    newest = bars[-1]
    distances = _distances(newest)
    return FieldReading(
        value=float(locked),
        extras={
            # A binomial spread on the symbol's **own** base rate. A count of
            # three locks in sixty sessions is not an exact property of the
            # symbol: rerun the same base rate over the same length and the
            # count moves by about this much.
            "standard_error": math.sqrt(len(decided) * rate * (1.0 - rate)),
            "base_rate_pct": 100.0 * rate,
            "closes_at_ceiling": at_ceiling,
            "closes_at_floor": at_floor,
            "distance_to_ceiling_pct": distances[0],
            "distance_to_floor_pct": distances[1],
            "anchor_basis": (
                None if (basis := window.health.anchor_basis) is None else basis.value
            ),
            "decided_days": len(decided),
            "undecided_days": len(undecided),
            "sessions": len(bars),
        },
        degraded_reason=reason if undecided else None,
    )


def _undecided_reason(bars: Sequence[Bar]) -> SignalIssue | None:
    """Why these sessions had no band, in the one Signal Issue vocabulary.

    Read off the bars themselves rather than off Window Health. The gateway
    pairs an absent band with the reason it is absent on the bar, so the field
    looking at a session is the thing that knows why that session could not be
    judged — asking the window instead would be asking a question about the
    whole window to answer one about a session, and the two disagree the moment
    a window holds more than one kind of unjudgeable session.

    Several reasons collapse to the first in sorted order, which is stable
    across runs and is the code a surface renders one sentence for.
    """
    reasons = sorted(
        {bar.band_undecided_reason for bar in bars if bar.band_undecided_reason},
        key=lambda issue: issue.value,
    )
    return reasons[0] if reasons else None


def _closed_at(bar: Bar, *, ceiling: bool) -> bool:
    """Whether this session's published close sat exactly on one of its limits.

    Compared in the **raw** prices the exchange published, because that is what
    the band is defined on: a limit price sits on a tick and a rebased price
    does not. On the window's newest session the two are the same number, the
    Adjustment Factor there being 1 by construction.
    """
    if bar.band is None:
        return False
    close = bar.raw_close
    if close is None:
        return False
    limit = bar.band.ceiling if ceiling else bar.band.floor
    return math.isclose(close, float(limit), rel_tol=CLOSE_AT_BAND_TOLERANCE)


def _distances(bar: Bar) -> tuple[float | None, float | None]:
    """How far the ceiling and the floor sit from this session's close, in percent."""
    close = bar.raw_close
    if bar.band is None or close is None or close <= 0:
        return None, None
    return (
        100.0 * (float(bar.band.ceiling) - close) / close,
        100.0 * (float(bar.band.floor) - close) / close,
    )


# --- Mean reversion -------------------------------------------------------


@dataclass(frozen=True)
class AR1Fit:
    """An AR(1) coefficient fitted to a series, and what it was fitted on.

    ``phi`` is ``1 + b`` from regressing ``Δx_t`` on ``x_{t−1}`` **with an
    intercept**. The intercept is not a detail: without it the fit would be
    measuring the level the series happens to sit at as though it were the mean
    it reverts to, and a demeaned series and a raw one would give two answers.
    """

    phi: float
    observations: int


def fit_ar1(series: Sequence[float]) -> AR1Fit | None:
    """The AR(1) coefficient of a series, or nothing where it has no dispersion."""
    if len(series) < 3:
        return None
    lagged = np.asarray(series[:-1], dtype=float)
    steps = np.diff(np.asarray(series, dtype=float))
    spread = float(np.var(lagged))
    if spread <= 0:
        return None
    slope = float(np.cov(lagged, steps, bias=True)[0, 1] / spread)
    return AR1Fit(phi=1.0 + slope, observations=len(steps))


def half_life_of(phi: float) -> float | None:
    """``−ln 2 / ln φ̂`` — how long a deviation takes to decay by half.

    ``None`` at or above one, where the series does not revert at all and the
    expression has no finite value to give. At or below zero the series
    alternates rather than decays, which is a half-life inside a single session
    and is reported as zero rather than as an undefined logarithm.
    """
    if phi >= 1.0:
        return None
    if phi <= 0.0:
        return 0.0
    return -_LOG2 / math.log(phi)


def _log_closes(frame: BarFrame) -> list[float]:
    """The window's closes in logs, which is the space a decay is exponential in."""
    return [
        math.log(bar.close)
        for bar in frame.bars
        if bar.close is not None and bar.close > 0
    ]


@dataclass(frozen=True)
class ReversionGauge:
    """One window's reversion reading: the z, the half-life, and its interval."""

    z: float
    half_life: float
    interval: tuple[float, float]
    phi: float
    censored_paths: int
    baseline_sessions: int

    @property
    def reaches_window(self) -> bool:
        """Whether the decay is slower than the window it was measured over.

        The line the two fields part company on. The half-life is still a
        finite estimate here and is served; the z is not, because a deviation
        that takes longer than the whole window to half-decay makes the
        window's own mean the thing the z is measuring.
        """
        return self.half_life >= MEAN_REVERSION_SESSIONS


def _gauge(frame: BarFrame) -> tuple[ReversionGauge | None, SignalIssue | None]:
    """Fit the gauge, or say in one vocabulary why the window has none."""
    series = _log_closes(frame)
    if len(series) < MEAN_REVERSION_MIN_SESSIONS:
        return None, SignalIssue.INSUFFICIENT_HISTORY

    baseline = series[:-1]
    centre = sum(baseline) / len(baseline)
    spread = math.sqrt(
        sum((item - centre) ** 2 for item in baseline) / (len(baseline) - 1)
    )
    if spread <= 0:
        return None, SignalIssue.BASELINE_DISPERSION_ZERO

    fit = fit_ar1(series)
    if fit is None:
        return None, SignalIssue.BASELINE_DISPERSION_ZERO

    half_life = half_life_of(fit.phi)
    if half_life is None:
        # φ̂ at or above one: the series does not revert at all and the estimate
        # is unbounded rather than merely large. Neither field has a number.
        return None, SignalIssue.HALF_LIFE_EXCEEDS_WINDOW

    interval, censored = _half_life_interval(series)
    return (
        ReversionGauge(
            z=(series[-1] - centre) / spread,
            half_life=half_life,
            interval=interval,
            phi=fit.phi,
            censored_paths=censored,
            baseline_sessions=len(baseline),
        ),
        None,
    )


def _half_life_interval(series: Sequence[float]) -> tuple[tuple[float, float], int]:
    """A stationary-block-bootstrap interval for the half-life, and its censoring.

    Whole ``(x_{t−1}, Δx_t)`` pairs are resampled in contiguous blocks — the
    stationary bootstrap of Politis and Romano, with block lengths drawn
    geometrically and the source read circularly — so the local dependence the
    coefficient is estimated from survives the resampling. Resampling the pairs
    independently would destroy exactly the thing being measured and report an
    interval far too narrow.

    A path whose fit shows no reversion has no finite half-life, and is
    **censored at the window length** rather than dropped. Dropping them would
    report an interval conditioned on the paths that happened to revert, which
    is the optimistic half of the answer; the count of censored paths travels so
    a reader can see how much of the interval is that boundary.
    """
    lagged = np.asarray(series[:-1], dtype=float)
    steps = np.diff(np.asarray(series, dtype=float))
    n = lagged.shape[0]

    rng = np.random.default_rng(MEAN_REVERSION_BOOTSTRAP_SEED)
    paths = MEAN_REVERSION_BOOTSTRAP_PATHS
    restart = rng.random(size=(paths, n)) < (1.0 / MEAN_REVERSION_BLOCK_SESSIONS)
    restart[:, 0] = True
    starts = rng.integers(0, n, size=(paths, n))

    index = np.empty((paths, n), dtype=np.int64)
    carry = np.zeros(paths, dtype=np.int64)
    for column in range(n):
        carry = np.where(restart[:, column], starts[:, column], (carry + 1) % n)
        index[:, column] = carry

    x = lagged[index]
    y = steps[index]
    x_centred = x - x.mean(axis=1, keepdims=True)
    y_centred = y - y.mean(axis=1, keepdims=True)
    variance = (x_centred * x_centred).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        slope = np.where(
            variance > 0, (x_centred * y_centred).sum(axis=1) / variance, 0.0
        )
    phi = 1.0 + slope

    ceiling = float(MEAN_REVERSION_SESSIONS)
    reverting = (phi > 0.0) & (phi < 1.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        lives = np.where(reverting, -_LOG2 / np.log(np.where(reverting, phi, 0.5)), ceiling)
    lives = np.where(phi <= 0.0, 0.0, lives)
    lives = np.clip(lives, 0.0, ceiling)

    tail = (1.0 - HALF_LIFE_INTERVAL) / 2.0
    low, high = np.quantile(lives, [tail, 1.0 - tail])
    censored = int(np.count_nonzero(~reverting & (phi > 0.0)))
    return (float(low), float(high)), censored


def _gauge_extras(gauge: ReversionGauge, frame: BarFrame) -> dict[str, object]:
    """What both mean-reversion fields say beside their own number.

    One dictionary rather than two, because the two fields are two readings of
    one fit: a z quoted without the half-life that sanctioned it, or a half-life
    quoted without the settlement floor it falls under, is the half of the
    answer that reads as more certain than it is.

    **The z is not in here**, and its absence is the suppression rule holding.
    The z field's own value is the z; republishing it in the shared extras would
    hand a reader the number through the half-life field on exactly the windows
    where the z field refused to give it.
    """
    return {
        "confidence_interval": gauge.interval,
        "half_life_sessions": gauge.half_life,
        "half_life_reaches_window": gauge.reaches_window,
        "ar1_phi": gauge.phi,
        "settlement_floor_sessions": SETTLEMENT_FLOOR_SESSIONS,
        # Under T+2 the shares are not deliverable until the move has already
        # half-decayed, so the round trip does not exist. Stated as a fact about
        # settlement rather than as advice about trading.
        "half_life_under_settlement_floor": (
            gauge.half_life < SETTLEMENT_FLOOR_SESSIONS
        ),
        "bootstrap_paths_without_reversion": gauge.censored_paths,
        "baseline_sessions": gauge.baseline_sessions,
        "sessions": len(frame.bars),
        "limit_lock_days": sum(1 for bar in frame.bars if bar.limit_locked),
    }


def mean_reversion_z_reading(window: FieldWindow) -> FieldReading:
    """How far the newest close sits from this symbol's own trailing mean.

    In standard deviations of that trailing mean, positive above and negative
    below, and suppressed entirely where the fitted half-life reaches the window
    length. It is descriptive: it says where the price is relative to its own
    recent history and carries no view on where it goes next.
    """
    gauge, reason = _gauge(window.frame)
    if gauge is None:
        return FieldReading(value=None, refusal=reason)
    if gauge.reaches_window:
        # Suppressed rather than served with a caveat, because a number with a
        # caveat beside it is a number that gets read. The half-life field is
        # still served here: it is a finite estimate and it is the estimate that
        # explains why this one is missing.
        return FieldReading(
            value=None,
            refusal=SignalIssue.HALF_LIFE_EXCEEDS_WINDOW,
            extras=_gauge_extras(gauge, window.frame),
        )
    return FieldReading(value=gauge.z, extras=_gauge_extras(gauge, window.frame))


def mean_reversion_half_life_reading(window: FieldWindow) -> FieldReading:
    """How long a deviation from this symbol's own mean takes to decay by half."""
    gauge, reason = _gauge(window.frame)
    if gauge is None:
        return FieldReading(value=None, refusal=reason)
    return FieldReading(
        value=gauge.half_life, extras=_gauge_extras(gauge, window.frame)
    )
