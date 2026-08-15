"""How wide a session traded, and whether that is wide for this symbol.

Two numbers with one input. Garman-Klass turns one session's open, high, low and
close into a variance; the volatility-regime z asks whether today's is unusual
against the symbol's own recent normal, measured robustly.

## The estimator, and the literature error it is not

Garman-Klass (1980), *J. Business* 53(1) 67–78, practical estimator:

    σ² = 0.5·(ln(H/L))² − (2·ln 2 − 1)·(ln(C/O))²

**The second term is ln(C/O), not ln(Cᵢ/Cᵢ₋₁).** Molnár (2012, IRFA 23:20–29)
flags the close-to-close version as a literature error that "sometimes produces
negative estimates"; with C/O the estimator is non-negative by construction,
since ln(H/L) ≥ |ln(C/O)| for any bar and 0.5 > 2·ln 2 − 1.

Two Vietnamese-market facts sit on top of it, both pointing the same way. A
limit-locked session has H=L=O=C, so every range term in it is zero **by
construction** rather than because the market was quiet — Yang-Zhang's own
Appendix A requires an estimator to return zero on a constant series. And thin
or discrete trading biases an observed range downward: GK's own Table 1 puts the
range estimator's expected value at 0.38–0.55 of true variance at 5
transactions a day. Both mean the number is biased **downward** where they
apply, which is why the count of locked sessions travels with every answer.

## The regime reading, and why the baseline is robust

The z is a trailing one: today's variance against the median and
median-absolute-deviation of the sessions before it, **with limit-locked
sessions excluded from that baseline**. Excluded rather than kept, because a run
of zeros deflates MAD and then manufactures significance on every ordinary
session around it — the exact failure ADR-0010 names. Excluded rather than
dropped: the count stays in Window Health, so an answer computed without them
still says they were there.

Median and MAD rather than mean and standard deviation because the quantity is a
variance: right-skewed, occasionally enormous, and a mean baseline chases the one
session it is supposed to be measuring against.

The sign is interpretable and is not a direction. Positive means this symbol's
range is wide against its own recent normal, which is a statement about
volatility and says nothing whatever about which way the price is going.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import median

from .bars import Bar, BarFrame
from .fields import FieldReading, FieldWindow
from .issues import SignalIssue

# The trailing stretch today's session is judged against. Sixty sessions is the
# short end of the 60–120 the research shortlist gives: long enough for a median
# to mean something, short enough that "this symbol's recent normal" is still
# recent in a market whose regimes turn over in a quarter.
VOLATILITY_REGIME_BASELINE_DAYS = 60

# Window plus skip, and this field skips nothing: sixty baseline sessions plus
# the one being judged.
VOLATILITY_REGIME_MIN_SESSIONS = VOLATILITY_REGIME_BASELINE_DAYS + 1

# How much of the baseline has to survive the limit-lock exclusion before the
# median and MAD are worth taking. Half of sixty: below it the baseline is no
# longer the stretch of market the window described.
VOLATILITY_REGIME_MIN_BASELINE = 30

# MAD estimates σ for a normal sample once scaled by this. Named rather than
# inlined because the alternative convention — 0.6745 in the numerator — is the
# same constant written upside down, and the two get mixed.
MAD_TO_SIGMA = 1.4826

_GK_CO_WEIGHT = 2.0 * math.log(2.0) - 1.0


def garman_klass_variance(bar: Bar) -> float | None:
    """One session's variance from its four prices, or nothing if it lacks them.

    ``None`` rather than zero for a session the store holds without a full range:
    a bar with no high is not a bar that did not move, and folding the two
    together would put a manufactured zero into a baseline built to exclude them.
    """
    if bar.open is None or bar.high is None or bar.low is None or bar.close is None:
        return None
    if bar.open <= 0 or bar.high <= 0 or bar.low <= 0 or bar.close <= 0:
        return None
    hl = math.log(bar.high / bar.low)
    co = math.log(bar.close / bar.open)
    return 0.5 * hl * hl - _GK_CO_WEIGHT * co * co


def robust_z(value: float, baseline: Sequence[float]) -> float | None:
    """How far a number sits from a baseline's median, in robust sigmas.

    ``None`` where the baseline has no dispersion at all. A zero MAD is not a
    baseline that agrees with itself, it is one every reading of which was
    identical — a thin name that matched at the same price every session — and
    dividing by it would report the first session that moved as an unbounded
    excursion.
    """
    if len(baseline) < 2:
        return None
    centre = median(baseline)
    spread = median([abs(item - centre) for item in baseline])
    if spread <= 0:
        return None
    return (value - centre) / (MAD_TO_SIGMA * spread)


def volatility_regime_z(frame: BarFrame) -> float | None:
    """This window's newest session, in robust sigmas of its own recent range.

    The pure statistic, over a frame and nothing else. It is what the null
    harness runs over synthetic windows, so it must reach no store, no clock and
    no configuration: a statistic that read anything outside the frame could not
    be measured against a null at all.
    """
    return _reading(frame)[0]


def volatility_regime_reading(window: FieldWindow) -> FieldReading:
    """The registered field's own answer over one window.

    Pure, like every other reading in this package: it is what ``serve_field``
    dresses with Window Health, and it reaches nothing outside the window it was
    handed. This one reads only the bars of it — the statistic the null harness
    runs is the same arithmetic over the same frame, which is what lets a field
    be calibrated against synthetic windows at all.
    """
    frame = window.frame
    value, reason = _reading(frame)
    if value is None:
        return FieldReading(value=None, refusal=reason)
    return FieldReading(
        value=value,
        extras={
            "garman_klass_variance": garman_klass_variance(frame.bars[-1]),
            "sessions": len(frame.bars),
            "baseline_sessions": len(_baseline_log_variances(frame)),
            "limit_lock_days": sum(1 for bar in frame.bars if bar.limit_locked),
        },
    )


def log_variance(bar: Bar) -> float | None:
    """One session's Garman-Klass variance in logs, or nothing where it has none.

    **The transform is the point, not a detail.** A variance is multiplicative:
    a loud regime is three times a quiet one rather than three units above it,
    and under the fat tails a real return series carries the raw variance has a
    power-law tail with no usable second moment. A location-scale z over that
    measures the tail rather than the regime, which is not a judgement call but a
    measured one — see the note on the registered field's threshold, where the
    same null demands z of about 25 on the raw variance and under 3 in logs.

    In logs the same scale mixture is a location shift, the median/MAD baseline
    is the natural one for it, and the sign keeps its meaning exactly: positive
    is a range wide against this symbol's own recent normal.

    ``None`` for a session with no range at all. That is not a variance of zero
    to be logged, it is a session a range estimator has nothing to read.
    """
    variance = garman_klass_variance(bar)
    if variance is None or variance <= 0:
        return None
    return math.log(variance)


def _reading(frame: BarFrame) -> tuple[float | None, SignalIssue | None]:
    """The z and, where there is none, the reason in the one Signal Issue vocabulary."""
    if not frame.bars:
        return None, SignalIssue.INSUFFICIENT_HISTORY
    target = log_variance(frame.bars[-1])
    if target is None:
        newest = frame.bars[-1]
        if newest.open is None or newest.high is None or newest.low is None:
            return None, SignalIssue.SESSION_PRICES_INCOMPLETE
        return None, SignalIssue.ZERO_RANGE_SESSION

    baseline = _baseline_log_variances(frame)
    if len(baseline) < VOLATILITY_REGIME_MIN_BASELINE:
        return None, SignalIssue.INSUFFICIENT_HISTORY

    value = robust_z(target, baseline)
    if value is None:
        return None, SignalIssue.BASELINE_DISPERSION_ZERO
    return value, None


def _baseline_log_variances(frame: BarFrame) -> list[float]:
    """Every session before the newest that may sit in a robust baseline.

    Trailing, so the session being judged is not in the sample judging it; and
    limit-locked sessions are gone, because their variance is zero by
    construction and a run of them deflates the MAD that everything else is
    measured against. A session that was not locked and still never moved is
    gone for the same reason and by the same test — it has no range to log.
    """
    trailing = BarFrame(symbol=frame.symbol, bars=frame.bars[:-1])
    return [
        value
        for bar in trailing.without_limit_locks().bars
        if (value := log_variance(bar)) is not None
    ]

