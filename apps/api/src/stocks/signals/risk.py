"""How volatile a symbol has been, how far it has fallen, and what that is worth.

Four questions with one input, and each of them has a well-known answer that is
wrong in a specific, documented way. What this module is mostly about is the
corrections.

## Realized volatility — Yang-Zhang, with the components beside it

**Yang-Zhang (2000)**, *J. Business* 73(3) 477–491:

    V = V_overnight + k·V_open_to_close + (1 − k)·V_rogers_satchell
    k = 0.34 / (1.34 + (n + 1)/(n − 1))

Drift-independent *and* opening-jump-independent; they prove no single-period
estimator can be both. Peak efficiency about 14, decaying toward 1 as the
overnight share of variance grows.

Its three cheaper relatives come back beside it rather than instead of it, so a
reader can see when they disagree: **Parkinson (1980)** at `(ln H/L)²/(4 ln 2)`,
**Garman-Klass (1980)** at `0.5(ln H/L)² − (2 ln 2 − 1)(ln C/O)²`, and
**Rogers-Satchell (1991)** at `ln(H/C)ln(H/O) + ln(L/C)ln(L/O)`, which alone is
unbiased under any drift.

Two Vietnamese hazards bias every one of them **downward** and neither is
correctable from stored data, so both are reported instead: a limit-locked
session has no range at all by construction, and thin trading shrinks an
observed range — Garman-Klass's own Table 1 puts it at 0.38–0.55 of true variance
at five transactions a day.

`√252` on the **variance** is legitimate here and is not the Sharpe
annualization argued with below: aggregating variance over independent periods
is addition, and the square root falls out of it.

## Drawdown — with the benchmark that makes it readable

**Magdon-Ismail et al. (2004)**, *J. Applied Probability* 41(1) 147–161: for
driftless Brownian motion, E[MDD] = σ√(πT/2) ≈ 1.2533·σ√T. Without it a −18%
drawdown is alarming; with it, a −18% drawdown over 250 sessions at this
symbol's volatility is close to what a coin would have produced.

The band changes the shape of a crash rather than its size: at ±7% a −30% fall
takes at least five sessions, so the count of limit-locked sessions inside the
drawdown is part of the story and travels with it.

## Risk-adjusted return — where the honest headline is the uncertainty

**Sharpe (1994)** defines the ratio on *differential* return against a stated
benchmark, and this system states its benchmark as zero because it holds no
risk-free series; that is in the field's own interpretation rather than assumed.

**Lo (2002)**, *FAJ* 58(4): SE(ŜR) ≈ √((1 + SR²/2)/T) under iid, and the
annualization factor is q/√(q + 2Σ(q−k)ρ_k), which "reduces to √q **only** under
zero autocorrelation". Hedge-fund Sharpes are overstated "by as much as 65
percent" by ignoring that. So the √252 shortcut is refused here whenever ρ₁ is
significant, and the corrected factor is used and named in the answer — a
contract rule inside the field rather than a convention applied anyway.

**Sortino & van der Meer (1991)** with the correction from Sortino & Forsey
(1996): downside deviation divides by the **total** number of observations, not
by the count below the benchmark. The common implementation divides by the
latter and thereby understates downside risk exactly when most returns are
positive. Below a floor of downside observations the ratio is withheld rather
than printed.

## The price zone

The field the product's price-zone commitment rests on, and the reason that
commitment and ADR-0010's ban on direction can both stand: **the zone is a
number and the judgement is the model's**. One realized Yang-Zhang σ either side
of the reference price over twenty sessions, whose sanctioned reading is *this
symbol's ordinary daily range* — never *buy here*.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

from .bars import Bar, BarFrame
from .fields import FieldReading
from .issues import SignalIssue
from .volatility import garman_klass_variance

# Sessions in a trading year, for annualizing a variance. 252 rather than the
# ~250 Vietnam actually runs: it is the convention every published figure this
# would be compared against uses, and the 1% difference is far inside the
# estimator's own standard error.
TRADING_SESSIONS_PER_YEAR = 252

# Magdon-Ismail et al. (2004): E[MDD] of driftless Brownian motion is
# σ√(πT/2). Written as the constant it works out to, because that is the form
# the ADR, the research note and every reader of this quote it in.
EXPECTED_MDD_CONSTANT = math.sqrt(math.pi / 2.0)  # ≈ 1.2533

# How far each drawdown number moves when the same process runs again, measured
# under the Brownian null rather than asserted. The first two are in units of
# σ√T, the same units E[MDD] is in; the third is a share of the window, because
# how long a path has been under its high depends on where its sign changes fell
# and not at all on how big its moves were.
#
# These are what the drawdown estimators publish as their standard error, and
# they are the reason the estimators publish one at all: a realized drawdown is
# not an exact fact about a symbol, it is one draw from a wide distribution, and
# two symbols' drawdowns are usually the same number.
#
# Measured by ``src.stocks.signals.nulls`` at the registry's derivation seed and
# frozen here; ``tests/test_risk_metrics.py`` re-measures them at fewer paths.
MAX_DRAWDOWN_NULL_SCATTER = 0.38
CURRENT_DRAWDOWN_NULL_SCATTER = 0.48
DAYS_UNDERWATER_NULL_SCATTER = 0.35

# How many lags of autocorrelation Lo's annualization correction reads. Five is
# a week of trading: far enough for the settlement-driven dependence this market
# has, short enough that each ρ̂ is estimated from most of the sample rather
# than from its tail. Lo's own sum runs to q−1, which at q = 252 would be 251
# correlations estimated off a 250-session window — noise with a formula around
# it.
AUTOCORRELATION_LAGS = 5

# Below this the ratio is not distinguishable from zero at any sample this
# system holds, and Sortino's discrete downside deviation is documented as
# unstable there (Sortino & Forsey 1996, via Kidd 2012).
MIN_DOWNSIDE_OBSERVATIONS = 10

# The windows each field reads, in sessions, and the history each therefore
# needs. Every one is window **plus skip**, and none of these skips: the skip
# belongs to the momentum fields, and writing `+ 0` here would be pretending
# otherwise.
#
# These lengths are **domain choices, not null derivations**, and the difference
# is worth stating because ADR-0010 derives the other frozen constants in this
# package from the null harness. A threshold is a number the null can answer
# for — it asks how often a detector trips on noise. A window length is a
# question about what stretch of market a reader means by "recently", and a null
# has no opinion on it: run the harness at any of these lengths and the false
# positive rate is the same, because the threshold was derived at the length the
# field ships with. What each length is answerable to is the market — a quarter,
# a month, a year — and each is argued for where it is declared.
REALIZED_VOLATILITY_SESSIONS = 60
REALIZED_VOLATILITY_MIN_SESSIONS = REALIZED_VOLATILITY_SESSIONS + 1

PRICE_ZONE_SESSIONS = 20
PRICE_ZONE_MIN_SESSIONS = PRICE_ZONE_SESSIONS + 1

# A year of sessions. The drawdown benchmark is a √T statement, so it needs a
# T long enough for the square root to say something; a year is also the horizon
# the research note's own worked example uses.
DRAWDOWN_SESSIONS = 250
DRAWDOWN_MIN_SESSIONS = DRAWDOWN_SESSIONS

RISK_ADJUSTED_SESSIONS = 250
RISK_ADJUSTED_MIN_SESSIONS = RISK_ADJUSTED_SESSIONS

_LOG2 = math.log(2.0)


# --- Volatility estimators ------------------------------------------------


def _session_counts(frame: BarFrame, bars: Sequence[Bar]) -> dict[str, object]:
    """The three counts every reading in this module reports, spelled one way.

    ``sessions`` is how long the window was, ``estimator_sessions`` how many
    terms the arithmetic actually had — one fewer, because every estimator here
    reads a session against the one before it — and ``limit_lock_days`` how many
    of the window's sessions had no range at all.

    One helper rather than three literals, because the first two differ by one
    and were previously written both ways under the same key: a reader comparing
    two fields' ``sessions`` would have been comparing two different counts.
    """
    return {
        "sessions": len(frame.bars),
        "estimator_sessions": max(len(bars) - 1, 0),
        "limit_lock_days": sum(1 for bar in frame.bars if bar.limit_locked),
    }


def _usable(frame: BarFrame) -> list[Bar]:
    """Bars carrying all four prices, positive, in the order they traded."""
    return [
        bar
        for bar in frame.bars
        if None not in (bar.open, bar.high, bar.low, bar.close)
        and min(bar.open, bar.high, bar.low, bar.close) > 0  # type: ignore[type-var]
    ]


def parkinson_variance(bars: Sequence[Bar]) -> float | None:
    """Parkinson (1980): the range alone, assuming no drift and no opening jump."""
    terms = [math.log(bar.high / bar.low) ** 2 for bar in bars]  # type: ignore[arg-type]
    if not terms:
        return None
    return sum(terms) / (4.0 * _LOG2 * len(terms))


def garman_klass_mean_variance(bars: Sequence[Bar]) -> float | None:
    """Garman-Klass averaged over a window.

    The per-bar estimator itself lives in ``volatility`` and is imported rather
    than repeated: it is the input to the volatility-regime z as well as a
    component here, and two spellings of ``0.5(ln H/L)² − (2 ln 2 − 1)(ln C/O)²``
    would be two chances to write the close-to-close variant Molnár flags as a
    literature error.
    """
    terms = [
        value for bar in bars if (value := garman_klass_variance(bar)) is not None
    ]
    if not terms:
        return None
    return sum(terms) / len(terms)


def rogers_satchell_variance(bars: Sequence[Bar]) -> float | None:
    """Rogers-Satchell (1991): unbiased under **any** drift, at a variance cost.

    Their eq. (3) shows the expectation is independent of the drift, which is
    what makes it the right third term inside Yang-Zhang — the other two are
    drift-free only by assumption.
    """
    terms = []
    for bar in bars:
        hc = math.log(bar.high / bar.close)  # type: ignore[arg-type]
        ho = math.log(bar.high / bar.open)  # type: ignore[arg-type]
        lc = math.log(bar.low / bar.close)  # type: ignore[arg-type]
        lo = math.log(bar.low / bar.open)  # type: ignore[arg-type]
        terms.append(hc * ho + lc * lo)
    if not terms:
        return None
    return sum(terms) / len(terms)


def close_to_close_variance(bars: Sequence[Bar]) -> float | None:
    """The textbook estimator, kept as the baseline the others are efficient against."""
    returns = _close_returns(bars)
    return _sample_variance(returns)


def yang_zhang_variance(bars: Sequence[Bar]) -> float | None:
    """Yang-Zhang (2000): drift-independent and opening-jump-independent at once.

    ``None`` below three bars, where the ``(n+1)/(n−1)`` in k is undefined or the
    sample variances have no degrees of freedom left. That is a real refusal
    rather than a guard: two sessions do not have a volatility.
    """
    if len(bars) < 3:
        return None
    overnight = [
        math.log(bar.open / previous.close)  # type: ignore[arg-type]
        for previous, bar in zip(bars, bars[1:])
    ]
    open_to_close = [
        math.log(bar.close / bar.open)  # type: ignore[arg-type]
        for bar in bars[1:]
    ]
    v_overnight = _sample_variance(overnight)
    v_open_to_close = _sample_variance(open_to_close)
    v_rs = rogers_satchell_variance(bars[1:])
    if v_overnight is None or v_open_to_close is None or v_rs is None:
        return None

    n = len(overnight)
    k = 0.34 / (1.34 + (n + 1) / (n - 1))
    return v_overnight + k * v_open_to_close + (1.0 - k) * v_rs


def annualized_percent(variance: float) -> float:
    """A per-session variance as an annualized volatility in percent.

    ``√252`` on a **variance** is aggregation rather than the Sharpe
    annualization argued with below: variance over independent periods adds, and
    the square root falls straight out of that.
    """
    return 100.0 * math.sqrt(max(variance, 0.0) * TRADING_SESSIONS_PER_YEAR)


def realized_volatility_reading(frame: BarFrame) -> FieldReading:
    """Yang-Zhang as the headline, with its three relatives beside it.

    The components are returned rather than hidden because they disagree in a
    way that is informative: Parkinson and Garman-Klass ignore the opening jump,
    so on a symbol whose moves arrive overnight they sit well under Yang-Zhang,
    and the gap is the reader's cue that the headline is doing work.
    """
    bars = _usable(frame)
    variance = yang_zhang_variance(bars)
    if variance is None:
        return FieldReading(value=None, refusal=SignalIssue.INSUFFICIENT_HISTORY)

    volatility = annualized_percent(variance)
    sessions = len(bars) - 1
    components = {
        "parkinson": _component(parkinson_variance(bars)),
        "garman_klass": _component(garman_klass_mean_variance(bars)),
        "rogers_satchell": _component(rogers_satchell_variance(bars)),
        "close_to_close": _component(close_to_close_variance(bars)),
    }
    return FieldReading(
        value=volatility,
        extras={
            # The close-to-close bound rather than Yang-Zhang's own. Their
            # efficiency gain decays toward 1 as the overnight share of variance
            # grows, so claiming it here would understate the error on exactly
            # the symbols where it is largest.
            "standard_error": volatility / math.sqrt(2.0 * sessions),
            "components_annualized_pct": components,
            **_session_counts(frame, bars),
            # Both bias a range estimate downward, and neither is correctable
            # from what is stored, so both are counted instead.
            "zero_range_days": sum(
                1 for bar in bars if bar.high == bar.low  # type: ignore[operator]
            ),
        },
    )


def price_zone_reading(frame: BarFrame) -> FieldReading:
    """One realized σ either side of the anchor close, as a percentage.

    A number, and only a number. The zone says how far this symbol ordinarily
    travels in a session; what to do about that is the model's to say and the
    artifact's to cite, and this field carries no key that could be read as
    either.

    **The anchor is the window's own last close, and is named as one.** It is
    deliberately not the exchange's reference price: ADR-0006 records that the
    stored ``reference_price`` is the previous close of the same frame rather
    than the exchange's reference, and that on UPCOM the real anchor — the prior
    day's round-lot continuous VWAP — is not reconstructible from anything
    stored. A zone drawn around a number this system cannot reproduce would carry
    the exchange's authority and not its arithmetic.

    The band is drawn in logs, which is the space σ was estimated in. At an
    ordinary 2% it differs from the linear band by two hundredths of a percent
    and changes no reading; taken on a loud symbol the two diverge visibly, and
    the one that stays consistent with its own estimator is the one to ship.
    """
    bars = _usable(frame)
    variance = yang_zhang_variance(bars)
    if variance is None:
        return FieldReading(value=None, refusal=SignalIssue.INSUFFICIENT_HISTORY)

    sigma = math.sqrt(max(variance, 0.0))
    anchor = bars[-1].close
    if anchor is None or anchor <= 0:
        return FieldReading(value=None, refusal=SignalIssue.SESSION_PRICES_INCOMPLETE)

    return FieldReading(
        value=100.0 * sigma,
        extras={
            "anchor_close": anchor,
            "lower_price": anchor * math.exp(-sigma),
            "upper_price": anchor * math.exp(sigma),
            "anchor_session": bars[-1].session_date.isoformat(),
            "standard_error": 100.0 * sigma / math.sqrt(2.0 * (len(bars) - 1)),
            **_session_counts(frame, bars),
        },
    )


# --- Drawdown -------------------------------------------------------------


@dataclass(frozen=True)
class Drawdown:
    """How far below its own peak a series went, and for how long.

    Signs are the convention rather than an accident: a drawdown is **≤ 0**,
    always, so that "worse" is unambiguously "more negative" and a reader
    comparing two of them never has to ask which way round the field is written.
    """

    max_drawdown_pct: float
    current_drawdown_pct: float
    days_underwater: int
    max_drawdown_log: float
    peak_session: date
    trough_session: date


def drawdown_of(bars: Sequence[Bar]) -> Drawdown | None:
    """The deepest fall from a running peak, the present one, and its length."""
    closes = [bar.close for bar in bars if bar.close is not None and bar.close > 0]
    if len(closes) < 2:
        return None

    peak = closes[0]
    peak_index = 0
    worst = 0.0
    worst_peak_index = 0
    worst_index = 0
    last_peak_index = 0
    for index, close in enumerate(closes):
        if close >= peak:
            peak = close
            peak_index = index
            last_peak_index = index
        fall = close / peak - 1.0
        if fall < worst:
            worst = fall
            worst_peak_index = peak_index
            worst_index = index

    current = closes[-1] / peak - 1.0
    return Drawdown(
        max_drawdown_pct=100.0 * worst,
        current_drawdown_pct=100.0 * current,
        days_underwater=len(closes) - 1 - last_peak_index,
        # In logs, because that is the space the Brownian benchmark lives in.
        max_drawdown_log=abs(
            math.log(closes[worst_index] / closes[worst_peak_index])
        ),
        peak_session=bars[worst_peak_index].session_date,
        trough_session=bars[worst_index].session_date,
    )


def expected_max_drawdown(daily_sigma: float, sessions: int) -> float:
    """E[MDD] ≈ 1.2533·σ√T, for driftless Brownian motion, in log space."""
    return EXPECTED_MDD_CONSTANT * daily_sigma * math.sqrt(max(sessions, 0))


def drawdown_ratio(frame: BarFrame) -> float | None:
    """Observed maximum drawdown over the one a coin would have produced.

    The statistic the drawdown signal fires on, and the whole reason the
    benchmark is in the contract: a −18% fall is alarming until it is read
    against the −16% a driftless random walk at this volatility would have
    produced anyway.
    """
    bars = _usable(frame)
    fall = drawdown_of(bars)
    variance = yang_zhang_variance(bars)
    if fall is None or variance is None or variance <= 0:
        return None
    expected = expected_max_drawdown(math.sqrt(variance), len(bars) - 1)
    if expected <= 0:
        return None
    return fall.max_drawdown_log / expected


def _drawdown_reading(
    frame: BarFrame,
    pick: Callable[[Drawdown], float],
    scatter: Callable[[float, int], float | None],
) -> FieldReading:
    """One drawdown number, with how far it would move if the process ran again.

    ``scatter`` is where the honesty is. A realized drawdown is not an exact fact
    to be compared with another symbol's exact fact: rerun the same volatility
    over the same length and the number moves a great deal. How much it moves is
    measured under the Brownian null and frozen in this module, so the standard
    error beside each of these is a real sampling spread rather than the
    benchmark wearing a standard error's name.
    """
    bars = _usable(frame)
    fall = drawdown_of(bars)
    if fall is None:
        return FieldReading(value=None, refusal=SignalIssue.INSUFFICIENT_HISTORY)

    variance = yang_zhang_variance(bars)
    if variance is None or variance <= 0:
        # No measurable volatility over the window, so neither the benchmark nor
        # the spread exists. Refused rather than served without them: a drawdown
        # printed with no standard error and no expected fall beside it is the
        # exact number ADR-0010 forbids — an estimate wearing the clothes of a
        # fact.
        return FieldReading(value=None, refusal=SignalIssue.BASELINE_DISPERSION_ZERO)

    daily_sigma = math.sqrt(variance)
    estimator_sessions = len(bars) - 1
    standard_error = scatter(daily_sigma, estimator_sessions)
    if standard_error is None:
        return FieldReading(value=None, refusal=SignalIssue.BASELINE_DISPERSION_ZERO)

    return FieldReading(
        value=pick(fall),
        extras={
            "standard_error": standard_error,
            "expected_max_drawdown_pct": -100.0
            * (
                1.0
                - math.exp(
                    -expected_max_drawdown(daily_sigma, estimator_sessions)
                )
            ),
            "max_drawdown_pct": fall.max_drawdown_pct,
            "current_drawdown_pct": fall.current_drawdown_pct,
            "days_underwater": fall.days_underwater,
            "peak_session": fall.peak_session.isoformat(),
            "trough_session": fall.trough_session.isoformat(),
            **_session_counts(frame, bars),
        },
    )


def _percent_scatter(share: float) -> Callable[[float, int], float | None]:
    """A spread stated in units of σ√T, returned as a percentage of price."""

    def scatter(daily_sigma: float, sessions: int) -> float | None:
        return 100.0 * share * daily_sigma * math.sqrt(max(sessions, 0))

    return scatter


def max_drawdown_reading(frame: BarFrame) -> FieldReading:
    return _drawdown_reading(
        frame,
        lambda fall: fall.max_drawdown_pct,
        _percent_scatter(MAX_DRAWDOWN_NULL_SCATTER),
    )


def current_drawdown_reading(frame: BarFrame) -> FieldReading:
    return _drawdown_reading(
        frame,
        lambda fall: fall.current_drawdown_pct,
        _percent_scatter(CURRENT_DRAWDOWN_NULL_SCATTER),
    )


def days_underwater_reading(frame: BarFrame) -> FieldReading:
    """How long since the last peak, and how long that is under a coin.

    The scatter here does not scale with volatility at all — the length of an
    underwater stretch is a property of the path's sign changes rather than of
    its size — so it is a share of the window, and a large one: under a driftless
    walk the time since the last high is famously uniform-ish over the window,
    which is exactly the intuition a reader needs before treating "84 sessions
    underwater" as a finding.
    """
    return _drawdown_reading(
        frame,
        lambda fall: float(fall.days_underwater),
        lambda _sigma, sessions: DAYS_UNDERWATER_NULL_SCATTER * sessions,
    )


def drawdown_versus_benchmark_reading(frame: BarFrame) -> FieldReading:
    """The observed fall over the one a coin would have produced.

    Computed here rather than through ``drawdown_ratio`` so the benchmark that
    goes into the ratio is the one reported beside it: reading the ratio from one
    call and the benchmark from a second would recompute Yang-Zhang over the
    whole window twice to answer the same question two ways.
    """
    bars = _usable(frame)
    fall = drawdown_of(bars)
    variance = yang_zhang_variance(bars)
    if fall is None or variance is None or variance <= 0:
        return FieldReading(value=None, refusal=SignalIssue.INSUFFICIENT_HISTORY)

    expected = expected_max_drawdown(math.sqrt(variance), len(bars) - 1)
    if expected <= 0:
        return FieldReading(value=None, refusal=SignalIssue.BASELINE_DISPERSION_ZERO)

    return FieldReading(
        value=fall.max_drawdown_log / expected,
        extras={
            "expected_max_drawdown_log": expected,
            **_session_counts(frame, bars),
        },
    )


# --- Risk-adjusted return -------------------------------------------------


@dataclass(frozen=True)
class Annualization:
    """The factor a per-session ratio is scaled by, and why that one.

    Two candidates and a named winner, because Lo's whole point is that the
    √q everybody uses is a special case people apply as a general rule. The
    corrected factor is used whenever the first autocorrelation is significant,
    and which one was used travels with the number.
    """

    factor: float
    method: str
    first_autocorrelation: float
    significant: bool
    # How many lags the correction's sum actually ran over. Reported rather than
    # implied, because it is the one place this departs from the published
    # formula and a reader comparing against Lo's own arithmetic needs to know
    # where the sum stopped.
    lags: int


def autocorrelation(values: Sequence[float], lag: int) -> float:
    """The sample autocorrelation of a return series at one lag."""
    n = len(values)
    if n <= lag + 1:
        return 0.0
    mean = sum(values) / n
    denominator = sum((item - mean) ** 2 for item in values)
    if denominator <= 0:
        return 0.0
    numerator = sum(
        (values[index] - mean) * (values[index + lag] - mean)
        for index in range(n - lag)
    )
    return numerator / denominator


def annualization_of(returns: Sequence[float]) -> Annualization:
    """Lo (2002)'s factor, which reduces to √q only where it is entitled to.

    ``q/√(q + 2Σ(q−k)ρ_k)``. Under zero autocorrelation the sum vanishes and the
    expression is √q exactly; under positive autocorrelation it is smaller, which
    is the direction that matters — ignoring it overstates a Sharpe, by as much
    as 65% in the hedge-fund samples Lo measured.

    The shortcut is refused on significance rather than on size, at the standard
    ±1.96/√T band: a ρ̂₁ of 0.1 on 250 sessions is noise, and correcting for
    noise would make the annualization a function of the sample's luck.

    **The sum is truncated, and that is a departure from the published formula.**
    Lo's runs to q−1, which at q = 252 means 251 correlations estimated off a
    250-session window — each of the last ones from a handful of overlapping
    pairs, so the tail of the sum is noise with a formula around it. It stops at
    ``AUTOCORRELATION_LAGS`` instead, and the number of lags it used travels with
    every answer so the departure is on the wire rather than in a comment.
    """
    q = TRADING_SESSIONS_PER_YEAR
    n = len(returns)
    rho_1 = autocorrelation(returns, 1)
    significant = n > 1 and abs(rho_1) > 1.96 / math.sqrt(n)
    if not significant:
        return Annualization(
            factor=math.sqrt(q),
            method="sqrt_252",
            first_autocorrelation=rho_1,
            significant=False,
            lags=0,
        )

    lags = max(min(AUTOCORRELATION_LAGS, n - 1), 0)
    total = 0.0
    for lag in range(1, lags + 1):
        total += (q - lag) * autocorrelation(returns, lag)
    denominator = q + 2.0 * total
    if denominator <= 0:
        # Autocorrelation so negative that the corrected variance is not a
        # variance. Nothing to annualize by, and √q would be the number the
        # correction exists to refuse.
        return Annualization(
            factor=float("nan"),
            method="undefined",
            first_autocorrelation=rho_1,
            significant=True,
            lags=lags,
        )
    return Annualization(
        factor=q / math.sqrt(denominator),
        method="lo_corrected",
        first_autocorrelation=rho_1,
        significant=True,
        lags=lags,
    )


def sharpe_reading(frame: BarFrame) -> FieldReading:
    """The ratio, its Lo standard error, and the interval that usually contains zero.

    The interval is the headline rather than a caveat. On the samples this system
    holds, SE(ŜR) ≈ √((1 + SR²/2)/T) puts most ratios within two standard errors
    of zero, and a field that printed the point estimate alone would be inviting
    a comparison between two numbers that are the same number.
    """
    returns = _close_returns(_usable(frame))
    if len(returns) < 3:
        return FieldReading(value=None, refusal=SignalIssue.INSUFFICIENT_HISTORY)

    mean = sum(returns) / len(returns)
    variance = _sample_variance(returns)
    if variance is None or variance <= 0:
        return FieldReading(value=None, refusal=SignalIssue.BASELINE_DISPERSION_ZERO)

    per_session = mean / math.sqrt(variance)
    scale = annualization_of(returns)
    if math.isnan(scale.factor):
        return FieldReading(value=None, refusal=SignalIssue.AUTOCORRELATION_UNUSABLE)

    ratio = per_session * scale.factor
    standard_error = (
        math.sqrt((1.0 + 0.5 * per_session**2) / len(returns)) * scale.factor
    )
    return FieldReading(
        value=ratio,
        extras={
            "standard_error": standard_error,
            "confidence_interval": (
                ratio - 1.96 * standard_error,
                ratio + 1.96 * standard_error,
            ),
            "indistinguishable_from_zero": abs(ratio) <= 1.96 * standard_error,
            "annualization": scale.method,
            "annualization_lags": scale.lags,
            "first_autocorrelation": scale.first_autocorrelation,
            # Stated rather than assumed: this system holds no risk-free series,
            # so the differential return Sharpe (1994) defines is measured
            # against zero and says so.
            "benchmark": "zero",
            **_session_counts(frame, _usable(frame)),
        },
    )


def sortino_reading(frame: BarFrame) -> FieldReading:
    """Sortino, with the divisor the common implementation gets wrong.

    Downside deviation divides by the **total** number of observations, not by
    the count below the benchmark. Dividing by the latter understates downside
    risk precisely when most returns are positive — which is most of the time,
    and is the case a reader would most like to be warned about.
    """
    returns = _close_returns(_usable(frame))
    if len(returns) < 3:
        return FieldReading(value=None, refusal=SignalIssue.INSUFFICIENT_HISTORY)

    below = [item for item in returns if item < 0.0]
    if len(below) < MIN_DOWNSIDE_OBSERVATIONS:
        return FieldReading(
            value=None, refusal=SignalIssue.INSUFFICIENT_DOWNSIDE_OBSERVATIONS
        )

    downside = math.sqrt(sum(item * item for item in below) / len(returns))
    if downside <= 0:
        return FieldReading(value=None, refusal=SignalIssue.BASELINE_DISPERSION_ZERO)

    mean = sum(returns) / len(returns)
    scale = annualization_of(returns)
    if math.isnan(scale.factor):
        return FieldReading(value=None, refusal=SignalIssue.AUTOCORRELATION_UNUSABLE)

    ratio = (mean / downside) * scale.factor
    # Lo derives his standard error for the Sharpe, where the denominator is the
    # full standard deviation. Applied to a downside deviation it is an
    # approximation and is marked as one rather than dropped: ADR-0010 requires
    # an estimator to carry uncertainty, and shipping none would read as
    # exactness on precisely the ratio Sortino & Forsey document as unstable in
    # small samples. The observation count beside it is the number the research
    # note actually asks a reader to judge it by.
    per_session = mean / downside
    standard_error = (
        math.sqrt((1.0 + 0.5 * per_session**2) / len(returns)) * scale.factor
    )
    return FieldReading(
        value=ratio,
        extras={
            "standard_error": standard_error,
            "standard_error_basis": "lo_2002_applied_to_downside_deviation",
            "confidence_interval": (
                ratio - 1.96 * standard_error,
                ratio + 1.96 * standard_error,
            ),
            "downside_obs_count": len(below),
            "downside_deviation_pct": 100.0 * downside,
            "annualization": scale.method,
            "annualization_lags": scale.lags,
            "benchmark": "zero",
            **_session_counts(frame, _usable(frame)),
        },
    )


# --- Shared arithmetic ----------------------------------------------------


def _close_returns(bars: Sequence[Bar]) -> list[float]:
    """Session-to-session log returns of the adjusted closes."""
    closes = [bar.close for bar in bars if bar.close is not None and bar.close > 0]
    return [
        math.log(later / earlier) for earlier, later in zip(closes, closes[1:])
    ]


def _sample_variance(values: Sequence[float]) -> float | None:
    """The mean-adjusted sample variance, or nothing below two observations."""
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return sum((item - mean) ** 2 for item in values) / (len(values) - 1)


def _component(variance: float | None) -> float | None:
    return None if variance is None else annualized_percent(variance)
