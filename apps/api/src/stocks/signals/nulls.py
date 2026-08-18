"""Windows that contain no signal, so a detector can be caught firing on one.

A threshold is only a number until somebody measures how often it trips on
nothing. **Null Calibration** is that measurement, and ADR-0010 requires two
nulls rather than one, ≥1000 paths each, with the published rate the maximum of
them:

1. **Matched-volatility geometric Brownian motion**, with and without the ±7%
   truncation the band imposes. The textbook null: no drift, no memory, no fat
   tails.
2. **A stationary block bootstrap on the symbol's own bars.** GBM has neither
   fat tails nor serial dependence, so a detector that is silent on GBM can
   still fire constantly on a real quiet series. This is the null that catches
   that, and it is the reason one null was never enough.

Both produce ``BarFrame``s, because the harness runs **the real field** rather
than a re-implementation of it. A statistic measured against a null it does not
share a code path with measures the re-implementation.

## What is synthetic here and what is not

The band mechanics are modelled the way the market works them: a session whose
overnight jump would carry it past its limit opens *at* the limit, and a session
that stays pinned there all day is a limit lock with no range at all. That is
what makes the truncated variant worth running separately — it is the only one
of the three that produces the zero-variance sessions the robust baselines are
built to exclude.

**The bootstrap's source series is a stand-in, and is marked as one.** The null
wants a real symbol's own bar history; this system's tests run against an
in-memory store, so the fixture here is generated instead — Student-t innovations
under a persistent stochastic volatility, truncated by the same band. It is not a
real series and does not claim to be. What it does carry is the two properties
GBM lacks and this null exists to test: fat tails and serial dependence in the
magnitude of moves. Replace it with a stored history the day one is available;
nothing else in the harness changes.

The tick grid is deliberately **not** modelled. Rounding a synthetic limit price
onto the HOSE ladder would change a range by a few basis points and change no
verdict, while making every path's arithmetic depend on the level it happens to
be drawn at.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import numpy as np

from .bars import Bar, BarFrame
from .fields import SignalField
from .price_band import LimitLock

# How finely a session is walked before its high and low are read off. Twenty-four
# steps is a quarter-hour grid over a Vietnamese session; the number sets how well
# the sampled extremes approximate the continuous range, which GK and Parkinson
# both assume, and past a couple of dozen it stops moving the answer.
INTRADAY_STEPS = 24

# The share of a session's variance that arrives overnight. Half is the middle of
# what Yang-Zhang report for equities, and it is what makes a truncated path
# possible at all: without an opening jump no session can gap to its limit, and
# the truncated null would be the untruncated one with extra arithmetic.
OVERNIGHT_VARIANCE_SHARE = 0.5

# The band the truncated variant clamps to. HOSE's ±7%, because that is the
# tightest of the three boards and therefore the one that truncates most.
TRUNCATION_BAND = 0.07

# The daily volatilities the GBM null is matched at. Three rather than one
# because "matched volatility" is matched to a symbol, and this system's symbols
# are not one volatility: 1% a day is a large-cap bank, 4% is a mid-cap on a bad
# month. The published rate is the worst of them, since a detector is shipped for
# all of them at once.
MATCHED_DAILY_VOLATILITIES: tuple[float, ...] = (0.01, 0.02, 0.04)

# The mean block length of the stationary bootstrap. Twenty sessions is a month
# of trading: long enough to carry a volatility cluster through intact, short
# enough that a thousand paths are not a thousand copies of the same year.
BOOTSTRAP_MEAN_BLOCK = 20

# How long the stand-in history is. Two thousand sessions is about eight years:
# long enough that one extreme session in it is not resampled into a tenth of
# every path, which is what makes a bootstrap over a short history a bootstrap of
# that history's luck.
REFERENCE_HISTORY_SESSIONS = 2000

# How many independent histories the bootstrap null is pooled over. One history
# calibrates against one symbol's luck; the catalog freezes one threshold for
# every symbol, so the null it is frozen from has to span more than one.
REFERENCE_HISTORIES = 8

# The stand-in's own shape. A 2% daily volatility is a liquid Vietnamese
# large-cap; the persistence and shock put the stationary spread of log-variance
# near 1.1, so a quiet regime and a loud one differ by roughly threefold, which
# is what a volatility cluster looks like. Five degrees of freedom is inside the
# four-to-six range measured on daily equity returns, and is the number every
# constant frozen in the registry was derived at.
REFERENCE_DAILY_VOLATILITY = 0.02
VARIANCE_PERSISTENCE = 0.95
VARIANCE_SHOCK = 0.35
REFERENCE_TAIL_DEGREES = 5.0

# What a null session trades, and how much of it is foreign. The level is
# arbitrary — every field calibrated against these reads a ratio — but it has to
# be a number, because a flow null with no denominator is not a flow.
NULL_SESSION_TURNOVER_VND = 10e9

# The spread of a session's net foreign flow as a share of its turnover. A tenth
# is the order of magnitude a liquid HOSE large-cap runs at; the constant sets
# the scale of both the numerator and the noise around it, so a rate measured
# against it does not depend on it.
NULL_FLOW_SCALE = 0.10

# How persistent the stand-in flow series is, session to session. This is the
# one property the flow null exists to carry: an independent-draw flow would
# make an ordinary streak look remarkable, which is the failure a block
# permutation of real flows is run to avoid. Half is a moderate reading of the
# persistence Froot-O'Connell-Seasholes and Richards both measure, and like the
# rest of the reference history it is a stand-in that says so rather than a
# claim about any symbol.
REFERENCE_FLOW_PERSISTENCE = 0.5

_LOG_CEILING = math.log(1.0 + TRUNCATION_BAND)
_LOG_FLOOR = math.log(1.0 - TRUNCATION_BAND)
_BASE_PRICE = 20_000.0
_EPOCH = date(2020, 1, 1)


@dataclass(frozen=True)
class BarShapes:
    """A stretch of sessions as ratios to the close before each one.

    Ratios rather than prices because every estimator in this package reads a
    bar's shape — ``H/L``, ``C/O`` — and never its level. Kept this way, a
    bootstrap can splice two stretches of history together without inventing a
    jump at the seam, and the band truncation stays expressible as a constant.

    ``flow`` is the session's net foreign money as a fraction of the money that
    traded in it, and it rides here rather than beside because the bootstrap
    resamples **whole bars**: a flow spliced independently of the bar it came
    from would have its serial dependence destroyed by the one null that exists
    to preserve it.
    """

    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    locked: np.ndarray
    flow: np.ndarray

    def __len__(self) -> int:
        return int(self.open.shape[-1])


def gbm_shapes(
    rng: np.random.Generator,
    *,
    paths: int,
    sessions: int,
    daily_volatility: float,
    truncated: bool,
) -> BarShapes:
    """Driftless GBM sessions, optionally clamped by the ±7% band.

    Zero drift and no memory, which is the whole point: any excursion a detector
    reports here is one it invented. The truncated variant additionally reproduces
    the two things a band does to a session — an opening jump that would carry
    past the limit opens *at* it, and a session that never leaves it has no range
    at all.
    """
    overnight_sigma = daily_volatility * math.sqrt(OVERNIGHT_VARIANCE_SHARE)
    intraday_sigma = daily_volatility * math.sqrt(1.0 - OVERNIGHT_VARIANCE_SHARE)
    step_sigma = intraday_sigma / math.sqrt(INTRADAY_STEPS)

    jump = rng.normal(0.0, overnight_sigma, size=(paths, sessions))
    walk = np.cumsum(
        rng.normal(0.0, step_sigma, size=(paths, sessions, INTRADAY_STEPS)),
        axis=2,
    )
    # Independent session to session, deliberately. This is the null in which a
    # foreign-flow streak is nothing but a coin landing the same way twice, and
    # the bootstrap below is the one that asks what a persistent flow does.
    flow = rng.normal(0.0, NULL_FLOW_SCALE, size=(paths, sessions))
    return _shapes_from_walk(jump, walk, flow, truncated=truncated)


def reference_bar_history(
    rng: np.random.Generator,
    *,
    sessions: int = REFERENCE_HISTORY_SESSIONS,
) -> BarShapes:
    """The stand-in history the block bootstrap resamples.

    Student-t innovations at ``REFERENCE_TAIL_DEGREES`` degrees of freedom under
    a persistent stochastic volatility, truncated by the band. Fat tails and serial dependence
    in the magnitude of moves are exactly the two properties GBM lacks, and the
    only two this null needs from its source; the series is otherwise not a claim
    about any symbol and is not presented as one.
    """
    log_variance = np.empty(sessions)
    level = math.log(REFERENCE_DAILY_VOLATILITY**2)
    for index in range(sessions):
        level = (
            (1.0 - VARIANCE_PERSISTENCE) * math.log(REFERENCE_DAILY_VOLATILITY**2)
            + VARIANCE_PERSISTENCE * level
            + VARIANCE_SHOCK * rng.normal()
        )
        log_variance[index] = level

    # The fat tail is a scale mixture at the **session** level, not a fat step
    # inside one. A Student-t is a Gaussian whose variance is inverse-gamma, so
    # scaling a whole session's Gaussian increments by this factor makes the
    # session's *return* Student-t and its range fat-tailed with it — coherently.
    # Drawn per step instead, twenty-four fat steps would average back toward
    # Gaussian by the central limit theorem and leave the daily return thin,
    # which is the wrong way round from every measured equity series.
    mixer = np.sqrt(
        REFERENCE_TAIL_DEGREES / rng.chisquare(REFERENCE_TAIL_DEGREES, size=sessions)
    )
    tail_scale = math.sqrt(
        (REFERENCE_TAIL_DEGREES - 2.0) / REFERENCE_TAIL_DEGREES
    )
    daily_sigma = np.sqrt(np.exp(log_variance)) * mixer * tail_scale

    overnight_sigma = daily_sigma * math.sqrt(OVERNIGHT_VARIANCE_SHARE)
    intraday_sigma = daily_sigma * math.sqrt(1.0 - OVERNIGHT_VARIANCE_SHARE)

    jump = rng.normal(0.0, 1.0, size=(1, sessions)) * overnight_sigma[None, :]
    steps = rng.normal(0.0, 1.0, size=(1, sessions, INTRADAY_STEPS)) * (
        intraday_sigma / math.sqrt(INTRADAY_STEPS)
    )[None, :, None]
    # An AR(1) flow, scaled so its stationary spread is the same NULL_FLOW_SCALE
    # the independent null draws at. Same size of flow, different memory: the
    # only thing this null adds is the persistence, so a threshold it demands
    # more of is demanding it for that reason and no other.
    innovation = math.sqrt(1.0 - REFERENCE_FLOW_PERSISTENCE**2) * NULL_FLOW_SCALE
    flow = np.empty((1, sessions))
    level = 0.0
    for index in range(sessions):
        level = REFERENCE_FLOW_PERSISTENCE * level + innovation * rng.normal()
        flow[0, index] = level

    shapes = _shapes_from_walk(jump, np.cumsum(steps, axis=2), flow, truncated=True)
    # One series rather than one path of one series: the bootstrap below indexes
    # bars, and a leading axis of length one would make every block start at the
    # same place.
    return BarShapes(
        open=shapes.open[0],
        high=shapes.high[0],
        low=shapes.low[0],
        close=shapes.close[0],
        locked=shapes.locked[0],
        flow=shapes.flow[0],
    )


def block_bootstrap_shapes(
    rng: np.random.Generator,
    history: BarShapes,
    *,
    paths: int,
    sessions: int,
    mean_block: int = BOOTSTRAP_MEAN_BLOCK,
) -> BarShapes:
    """Resample contiguous stretches of a real bar history, wrapping at the end.

    The stationary bootstrap of Politis and Romano: block lengths drawn
    geometrically so the resampled series is stationary rather than
    block-length-dependent, and the source read circularly so every bar has the
    same chance of starting a block.

    Whole **bars** are resampled rather than close-to-close returns, because the
    field being calibrated reads a session's range. Resampling returns would
    force the intraday shape to be re-invented under some distribution of the
    harness's choosing, and the detector would then be measured against that
    choice rather than against the history.
    """
    source = len(history)
    if source < 2:
        raise ValueError("a block bootstrap needs a history to resample")

    restart = rng.random(size=(paths, sessions)) < (1.0 / mean_block)
    restart[:, 0] = True
    starts = rng.integers(0, source, size=(paths, sessions))

    index = np.empty((paths, sessions), dtype=np.int64)
    carry = np.zeros(paths, dtype=np.int64)
    for column in range(sessions):
        carry = np.where(restart[:, column], starts[:, column], (carry + 1) % source)
        index[:, column] = carry

    return BarShapes(
        open=history.open[index],
        high=history.high[index],
        low=history.low[index],
        close=history.close[index],
        locked=history.locked[index],
        flow=history.flow[index],
    )


def frames_from(shapes: BarShapes, symbol: str = "NULL") -> list[BarFrame]:
    """Turn resampled shapes into the frames a field actually reads.

    Levels are chained so that each session opens where the ratios say it does
    relative to the close before it, which keeps the series continuous. Nothing
    downstream reads the level — every estimator here is scale-free — but a frame
    that jumped at every seam would be a frame no store could hold, and the point
    of running the real field is that it is given a real-shaped window.
    """
    paths, sessions = shapes.open.shape
    days = _session_days(sessions)
    frames: list[BarFrame] = []
    for path in range(paths):
        level = _BASE_PRICE
        bars: list[Bar] = []
        for index in range(sessions):
            open_price = level * float(shapes.open[path, index])
            close_price = level * float(shapes.close[path, index])
            bars.append(
                Bar(
                    session_date=days[index],
                    open=open_price,
                    high=level * float(shapes.high[path, index]),
                    low=level * float(shapes.low[path, index]),
                    close=close_price,
                    volume=1_000_000,
                    total_value_vnd=NULL_SESSION_TURNOVER_VND,
                    foreign_net_value_vnd=(
                        NULL_SESSION_TURNOVER_VND * float(shapes.flow[path, index])
                    ),
                    adjustment_factor=Decimal(1),
                    limit_lock=(
                        LimitLock.CEILING
                        if shapes.locked[path, index] > 0
                        else LimitLock.FLOOR
                        if shapes.locked[path, index] < 0
                        else LimitLock.NONE
                    ),
                )
            )
            level = close_price
        frames.append(BarFrame(symbol=symbol, bars=tuple(bars)))
    return frames


def false_positive_rate(field: SignalField, frames: Sequence[BarFrame]) -> float:
    """How often this field fires on windows that contain nothing to find.

    The field's own statistic and its own frozen threshold, so what is measured
    is the thing that ships. A window the statistic cannot answer for is not a
    false positive and not a pass either — it is excluded from the denominator,
    because a rate over windows a detector never ran on says nothing about the
    detector.
    """
    if field.statistic is None or field.threshold is None:
        raise ValueError(f"{field.name} has no threshold to measure a null against")

    fired = 0
    measured = 0
    for frame in frames:
        value = field.statistic(frame)
        if value is None:
            continue
        measured += 1
        if value >= field.threshold.value:
            fired += 1
    if measured == 0:
        raise ValueError(f"{field.name} answered for none of the null windows")
    return fired / measured


def null_quantile(
    statistic: Callable[[BarFrame], float | None],
    frames: Sequence[BarFrame],
    ceiling: float,
) -> float:
    """The threshold this null would demand for a false-positive rate of ``ceiling``.

    The derivation half, run offline against a bare statistic rather than a
    registered field — a field cannot be declared until its threshold exists, so
    taking one here would be asking for the answer as an input.

    It is deliberately never called at runtime: a threshold computed from today's
    data is one that loosens itself in a quiet market, which is exactly when a
    detector should be hardest to trip.
    """
    values = [value for frame in frames if (value := statistic(frame)) is not None]
    if not values:
        raise ValueError("the statistic answered for none of the null windows")
    return float(np.quantile(np.asarray(values), 1.0 - ceiling))


def _shapes_from_walk(
    jump: np.ndarray,
    walk: np.ndarray,
    flow: np.ndarray,
    *,
    truncated: bool,
) -> BarShapes:
    """Assemble OHLC ratios from an overnight jump and an intraday walk.

    Everything is expressed against the previous close, which is both what the
    band is a percentage of and what makes the whole construction independent of
    the level a path happens to sit at.
    """
    open_log = jump if not truncated else np.clip(jump, _LOG_FLOOR, _LOG_CEILING)
    path_log = open_log[:, :, None] + walk
    if truncated:
        path_log = np.clip(path_log, _LOG_FLOOR, _LOG_CEILING)

    high_log = np.maximum(path_log.max(axis=2), open_log)
    low_log = np.minimum(path_log.min(axis=2), open_log)
    close_log = path_log[:, :, -1]

    if truncated:
        # A session pinned at one limit for its whole length is a limit lock:
        # H=L=O=C, and every range term in it is zero by construction rather
        # than because the market was quiet.
        at_ceiling = (
            np.isclose(open_log, _LOG_CEILING)
            & np.isclose(low_log, _LOG_CEILING)
            & np.isclose(high_log, _LOG_CEILING)
        )
        at_floor = (
            np.isclose(open_log, _LOG_FLOOR)
            & np.isclose(low_log, _LOG_FLOOR)
            & np.isclose(high_log, _LOG_FLOOR)
        )
        locked = at_ceiling.astype(np.int8) - at_floor.astype(np.int8)
    else:
        locked = np.zeros(open_log.shape, dtype=np.int8)

    return BarShapes(
        open=np.exp(open_log),
        high=np.exp(high_log),
        low=np.exp(low_log),
        close=np.exp(close_log),
        locked=locked,
        flow=flow,
    )


def _session_days(count: int) -> list[date]:
    """A weekday calendar of the right length, so no bar shares a date.

    Dates carry no meaning in a null window — nothing here reads one — but two
    bars on one date would be a window no store could hold, and a frame that
    could not have come out of the gateway is a poor thing to calibrate against.
    """
    days: list[date] = []
    cursor = _EPOCH
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days
