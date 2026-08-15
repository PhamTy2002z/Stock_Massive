"""Where a symbol stands against the Universe rather than against its own past.

Four questions, and one rule they all share: **a cross-sectional field drops a
short-history symbol, it never hides it.** Every answer carries the number
actually ranked and the symbols left out with a reason each, and the whole call
refuses below thirty survivors — the point at which a percentile stops being a
position in a distribution and becomes a rank with a percent sign on it.

## Momentum — and the naming inconsistency, settled

**Jegadeesh-Titman (1993)** and the French data library's own definition: the
formation stretch is the prior **(2-12)** return, twelve months of it with the
most recent month skipped, and the skip is there to step around the short-horizon
reversal Jegadeesh (1990) and Lehmann (1990) measured.

The inherited inconsistency (spec 0003 §14.1) is that the registered field is
named ``percentile_12_2`` while its ``min_sessions`` of 273 is ``252 + 21`` — a
**one**-month skip, which the research shortlist calls 12-1. It resolves as two
spellings of one window rather than as a disagreement: "12-2" names the
formation by its month endpoints, twelve months back to two months back, and
"12-1" names the same stretch by the length of what it skips. Both describe 252
sessions of formation after skipping 21, which is what is implemented here and
what the registered 273 is the sum of. The name stays, the skip stays, and
``test_cross_sectional`` pins the arithmetic against the constant so the two
spellings cannot drift into two windows.

**A one-day rank is not a valid read of this field.** The ±7% band spreads a
single shock across consecutive limit days, so a formation shorter than about a
month is measuring a move still in flight. The formation length is refused below
``MOMENTUM_MIN_FORMATION_SESSIONS`` rather than served short.

Vietnamese evidence is thin and is not oversold: Vo & Truong (2018) find 10 of 16
J/K strategies profitable on HOSE 2007–2015 and Alphonse & Nguyen (2013) find
momentum only in pre-2008 subsamples. Rouwenhorst (1999) replicates it across 17
of 20 emerging markets but at 0.39–0.58%/month, and Vietnam was not in that
sample. A rank is long-only actionable as *overweight winners, do not add to
losers*, which is exactly what a percentile narrates without a short leg.

## Trend — whose evidence is from futures, and says so in its own contract

**Moskowitz-Ooi-Pedersen (2012)**: the sign of an instrument's own past
twelve-month excess return predicts the next one to twelve months in all 58
futures instruments they test. The sample is liquid futures. Applying it to a
single Vietnamese equity is an extrapolation rather than a result, and that
sentence lives in the field's ``interpretation`` — the contract a model reads
before calling — rather than in a narration nobody is obliged to produce.

## Relative strength — refused, with the missing benchmark named

Rolling beta and correlation need a market index series, and **this system does
not store one**. The VN-Index appears only as an alias inside a live price path,
which is precisely the substitution spec 0003 §13 forbids: a legacy live read
used to make a registered field look available. So the field is registered and
refuses under ``unavailable`` with the input it is short of on the refusal.

Ledoit-Wolf shrinkage is what the field would use the day the benchmark exists —
a hundred symbols on 250 observations is the ill-conditioned regime their
estimator was written for, and the shrinkage intensity is the honesty signal, an
intensity approaching one meaning the data was insufficient. None of that is
implemented against a benchmark that is not there.

## Factor percentiles — quarterly, and stamped with their age

**Huang-Liu-Shu (2023)**, the best-venue Vietnamese factor study: size is
significant in Vietnam, unusually for an emerging market, and **earnings-to-price
beats book-to-market** as the value signal. Both are registered, E/P first.

No long-short factor portfolios: there is no shorting and a hundred symbols does
not make a portfolio. What is registered is the symbol's position within the
Universe on each factor, and every one of them carries the ``period_end`` of the
quarter behind it. Past ``FUNDAMENTAL_STALE_DAYS`` the answer is degraded rather
than withheld: the figure was true of its quarter, and what is wrong is only
narrating it as current.

**Size is ranked large-first, and that is a departure from the shortlist.** The
research declares its direction as "+ = smaller", which encodes the small-cap
premium — an expected-return claim — into the sign of a descriptive field.
ADR-0010 does not admit that in v1, so the percentile here means what it says
without a premium attached: higher is a larger company.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .bars import Bar, BarFrame
from .fields import FieldReading, FieldWindow
from .fundamentals import FundamentalStanding
from .issues import SignalIssue

# Sessions in a trading year and in the shorter windows the trend field also
# reports. 252 is the convention every published figure this would be compared
# against uses; the quarter and half-year are that divided by four and two,
# which is what "3 months" and "6 months" mean in sessions.
TRADING_SESSIONS_PER_YEAR = 252
TREND_QUARTER_SESSIONS = 63
TREND_HALF_YEAR_SESSIONS = 126
TREND_YEAR_SESSIONS = TRADING_SESSIONS_PER_YEAR
TREND_MIN_SESSIONS = TREND_YEAR_SESSIONS

# The prior (2-12) formation and the month it skips. Their sum is the registered
# ``min_sessions``, and it is a sum rather than a literal so the two can never
# be edited apart.
MOMENTUM_FORMATION_SESSIONS = 252
MOMENTUM_SKIP_SESSIONS = 21
MOMENTUM_MIN_SESSIONS = MOMENTUM_FORMATION_SESSIONS + MOMENTUM_SKIP_SESSIONS

# The shortest formation this field will measure a return over. A month, because
# the band spreads one shock across consecutive limit days and anything shorter
# is ranking a move that has not finished arriving. This is the documented
# refusal behind "never read a one-day rank".
MOMENTUM_MIN_FORMATION_SESSIONS = 21

# What relative strength would regress against, named on the refusal so the
# missing precursor is a fact on the wire rather than a gap in a document.
RELATIVE_STRENGTH_BENCHMARK = "VNINDEX"
RELATIVE_STRENGTH_MIN_SESSIONS = 250

# The factor percentiles need one session — the one the market capitalisation is
# read from — and their other input is a quarterly statement that is not a
# session at all. Declared as the window it actually reads rather than padded to
# look like a trailing statistic.
FACTOR_MIN_SESSIONS = 1

# Below this many surviving symbols a percentile stops meaning anything, and the
# whole call refuses rather than each survivor answering with a number nobody
# can read. The same floor the gateway's own liquidity standing uses.
CROSS_SECTION_MIN_SYMBOLS = 30


# --- Shared arithmetic ----------------------------------------------------


def _closes(frame: BarFrame) -> list[float]:
    return [bar.close for bar in frame.bars if bar.close is not None and bar.close > 0]


def _simple_return_pct(start: float, end: float) -> float:
    return 100.0 * (end / start - 1.0)


def _log_returns(closes: Sequence[float]) -> list[float]:
    return [math.log(later / earlier) for earlier, later in zip(closes, closes[1:])]


def _return_standard_error_pct(closes: Sequence[float], sessions: int) -> float | None:
    """How far a cumulative return over this many sessions would move on a rerun.

    The sample volatility of the window's own daily moves, grown by √T, and
    expressed in percent of the level. It is the sampling spread of a sum of
    returns rather than a claim about the mean: a twelve-month return on a 40%
    annualized symbol is ±40 points before anything is said about direction,
    which is the number a reader needs beside the headline.
    """
    returns = _log_returns(closes)
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
    return 100.0 * math.sqrt(variance * max(sessions, 0))


# --- Momentum -------------------------------------------------------------


def momentum_return_pct(
    closes: Sequence[float],
    *,
    formation: int = MOMENTUM_FORMATION_SESSIONS,
    skip: int = MOMENTUM_SKIP_SESSIONS,
) -> float | None:
    """The prior (2-12) return: ``formation`` sessions ending ``skip`` ago.

    ``None`` where the formation is shorter than a month, which is the refusal
    behind "never read a one-day rank": under the ±7% band a single shock is
    spread across consecutive limit days, so a short formation ranks a move that
    is still arriving rather than one that has arrived.
    """
    if formation < MOMENTUM_MIN_FORMATION_SESSIONS:
        return None
    if len(closes) < formation + skip:
        return None
    end = closes[-(skip + 1)]
    start = closes[-(skip + formation)]
    if start <= 0:
        return None
    return _simple_return_pct(start, end)


def momentum_ranked(window: FieldWindow) -> FieldReading:
    """The raw formation return this symbol is ranked on, with the skip stated."""
    closes = _closes(window.frame)
    value = momentum_return_pct(closes)
    if value is None:
        return FieldReading(value=None, refusal=SignalIssue.INSUFFICIENT_HISTORY)
    return FieldReading(
        value=value,
        extras={
            "formation_return_pct": value,
            "formation_sessions": MOMENTUM_FORMATION_SESSIONS,
            "skipped_sessions": MOMENTUM_SKIP_SESSIONS,
            "sessions": len(window.frame.bars),
            "limit_lock_days": sum(1 for bar in window.frame.bars if bar.limit_locked),
        },
    )


# --- Trend ----------------------------------------------------------------


def _trend_leg(closes: Sequence[float], sessions: int) -> tuple[float, int] | None:
    """One window's total return and the sign of it, or nothing if it is short."""
    if len(closes) < sessions + 1:
        return None
    value = _simple_return_pct(closes[-(sessions + 1)], closes[-1])
    return value, (1 if value > 0 else -1 if value < 0 else 0)


def trend_reading(window: FieldWindow) -> FieldReading:
    """Time-series momentum: the sign of this symbol's own past total return.

    Three windows rather than one, because a quarter and a year disagreeing is
    itself the reading — a symbol positive over twelve months and negative over
    three has given back what it made, and one number cannot say so.

    The evidence behind reading a sign at all is from futures, and the
    extrapolation to a single Vietnamese equity is carried in the field's own
    contract rather than left to whoever narrates it.
    """
    closes = _closes(window.frame)
    year = _trend_leg(closes, TREND_YEAR_SESSIONS)
    if year is None:
        return FieldReading(value=None, refusal=SignalIssue.INSUFFICIENT_HISTORY)

    extras: dict[str, object] = {
        "standard_error": _return_standard_error_pct(closes, TREND_YEAR_SESSIONS),
        "sessions": len(window.frame.bars),
        "limit_lock_days": sum(1 for bar in window.frame.bars if bar.limit_locked),
        # Named on every answer as well as in the contract. A reader who reaches
        # the payload without reading the schema still gets told what the sign
        # rests on.
        "evidence_basis": "moskowitz_ooi_pedersen_2012_futures",
    }
    for label, sessions in (
        ("3m", TREND_QUARTER_SESSIONS),
        ("6m", TREND_HALF_YEAR_SESSIONS),
        ("12m", TREND_YEAR_SESSIONS),
    ):
        leg = _trend_leg(closes, sessions)
        extras[f"return_{label}_pct"] = None if leg is None else leg[0]
        extras[f"sign_{label}"] = None if leg is None else leg[1]
    return FieldReading(value=year[0], extras=extras)


# --- Relative strength ----------------------------------------------------


def relative_strength_reading(window: FieldWindow) -> FieldReading:
    """Refused: there is no stored benchmark to regress this symbol against.

    Registered and refused rather than left out, so the Analysis Field Profile
    stays honest — a profile that silently dropped a field would make two
    Analyses carrying the same profile version mean different things. The input
    it is short of travels with the refusal, and the live price path's VN-Index
    alias is deliberately not read: substituting a legacy live call to make a
    registered field look available is the failure spec 0003 §13 names.
    """
    return FieldReading(
        value=None,
        refusal=SignalIssue.UNAVAILABLE,
        extras={
            "missing_input": (
                "a stored session series for the market index; the index exists "
                "only as an alias in the live price path and is never read here"
            ),
            "benchmark": RELATIVE_STRENGTH_BENCHMARK,
            "shrinkage": "ledoit_wolf",
        },
    )


# --- Factor percentiles ---------------------------------------------------


def _market_cap(frame: BarFrame) -> float | None:
    """What the newest session of the window valued the company at."""
    for bar in reversed(frame.bars):
        if bar.market_cap_vnd is not None and bar.market_cap_vnd > 0:
            return bar.market_cap_vnd
    return None


def _stamped(
    value: float,
    standing: FundamentalStanding | None,
    frame: BarFrame,
) -> FieldReading:
    """One factor figure with the age of what it was computed from on it.

    A quarterly figure narrated as current is a false positive by a mechanism no
    threshold catches, so the quarter travels with every one of these and the
    answer degrades past the staleness bound rather than being served flat.
    """
    newest: Bar | None = frame.bars[-1] if frame.bars else None
    return FieldReading(
        value=value,
        extras={
            "period_end": None if standing is None else standing.period_end.isoformat(),
            "period_age_days": None if standing is None else standing.age_days,
            "price_session": None if newest is None else newest.session_date.isoformat(),
        },
        degraded_reason=(
            SignalIssue.STALE_FUNDAMENTAL_PERIOD
            if standing is not None and standing.stale
            else None
        ),
    )


def _needs_statement(window: FieldWindow) -> FundamentalStanding | None:
    return window.fundamental


def earnings_yield_ranked(window: FieldWindow) -> FieldReading:
    """Trailing twelve-month net income over market capitalisation.

    Earnings-to-price rather than its reciprocal, because a yield is orderable
    through zero and a P/E is not: a loss-making company has a negative yield
    that ranks below every profitable one, while its P/E is a negative number
    that sorts as though it were the cheapest name in the Universe.
    """
    standing = _needs_statement(window)
    if standing is None:
        return FieldReading(value=None, refusal=SignalIssue.FUNDAMENTAL_NOT_STORED)
    earnings = standing.trailing_12_month_net_income_vnd
    cap = _market_cap(window.frame)
    if earnings is None or cap is None:
        return FieldReading(value=None, refusal=SignalIssue.FUNDAMENTAL_NOT_STORED)
    return _stamped(100.0 * earnings / cap, standing, window.frame)


def book_yield_ranked(window: FieldWindow) -> FieldReading:
    """Parent-company equity over market capitalisation."""
    standing = _needs_statement(window)
    if standing is None:
        return FieldReading(value=None, refusal=SignalIssue.FUNDAMENTAL_NOT_STORED)
    equity = standing.parent_equity_vnd
    cap = _market_cap(window.frame)
    if equity is None or cap is None:
        return FieldReading(value=None, refusal=SignalIssue.FUNDAMENTAL_NOT_STORED)
    return _stamped(100.0 * equity / cap, standing, window.frame)


def roe_ranked(window: FieldWindow) -> FieldReading:
    """Trailing twelve-month net income over parent-company equity."""
    standing = _needs_statement(window)
    if standing is None:
        return FieldReading(value=None, refusal=SignalIssue.FUNDAMENTAL_NOT_STORED)
    earnings = standing.trailing_12_month_net_income_vnd
    equity = standing.parent_equity_vnd
    if earnings is None or equity is None or equity <= 0:
        return FieldReading(value=None, refusal=SignalIssue.FUNDAMENTAL_NOT_STORED)
    return _stamped(100.0 * earnings / equity, standing, window.frame)


def size_ranked(window: FieldWindow) -> FieldReading:
    """Market capitalisation as the provider reported it on the newest session.

    Ranked large-first, which the shortlist's own "+ = smaller" convention is
    not: that sign carries the small-cap premium, and a premium is a claim about
    returns that a descriptive field may not make in v1. The staleness here is a
    session's rather than a quarter's, and is stamped as one.
    """
    cap = _market_cap(window.frame)
    if cap is None:
        return FieldReading(value=None, refusal=SignalIssue.MISSING_TARGET_SESSION)
    return _stamped(cap, None, window.frame)


def percentile_of(value: float, sample: Sequence[float]) -> float:
    """Where a value sits in a sample, from 0 to 100, counting ties as below.

    Ties count as below so the convention matches the gateway's own liquidity
    standing: a Universe in which every symbol traded the same money puts every
    one of them at 100, which is honest — none of them is below any other.
    """
    below = sum(1 for item in sample if item <= value)
    return 100.0 * below / len(sample)
