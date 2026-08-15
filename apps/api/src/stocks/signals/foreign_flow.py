"""What foreign investors did in a symbol, with the claim marked honestly.

The distinctive dataset in this system, and the one whose contract does the most
work. Two numbers: trailing net foreign buy value over the same window's average
daily traded value, and the run length of that flow's sign. Both are
**descriptive**, and here that is a schema constraint rather than a disclaimer.

## The predictive claim is unverified for Vietnam

The international evidence is real and is not the same claim. **Froot-O'Connell-
Seasholes (2001)** find inflows forecast returns in emerging markets across 44
countries; **Richards (2005)** finds the price impact of foreign net purchases in
six Asian markets is large and **largely contemporaneous**, with what predictive
content there is coming from persistence rather than foresight.

For Vietnam specifically: **Vo (2017)** confirms foreigners positive-feedback
trade on HOSE 2006–2015 and stops short of showing that net buying forecasts
subsequent returns. **No published result we could verify shows HOSE foreign net
buying predicts returns.** So the field says what foreigners did and never what
the price will do — no direction-bearing key, no expected return — and the
sentence above lives in the field's own ``interpretation``, which is the contract
a model reads before it decides to call.

## Room limits stop buying mechanically

A statutory ceiling on foreign ownership means a flow can flatten because there
is nothing left to buy. That is not a change of view, and a field that cannot
tell the two apart must not imply it can. So the room state travels with every
answer and an exhausted room **degrades** the reading under a named reason —
the number is real, and what changes is how it may be read.

Where the store holds no room reading the state is ``unknown`` rather than open.
That is not a degradation: the room changes over months, its absence is a
collection gap the state already names, and a warning attached to every window
is a warning nobody reads.

## Money over money, and the share-denominated ratio that is refused

The Main Source writes foreign buy, sell and net **value** for each session, so a
money-denominated ratio over a money ADTV has stored inputs and is served. It
writes no foreign **volume** at all — no adapter in this system does — so the
share-denominated ratio has no inputs, and it is registered as refused
``unavailable`` with the missing input named rather than quietly filled with the
money figure. The naming split between traded quantity and traded money exists
precisely to make that swap impossible to do by accident, and this is the field
where the temptation is largest.

An ADTV in money crosses an ex-date safely; an ADTV in shares does not, which is
the second reason the served ratio is the money one.

## The null is a block permutation of the daily flows

A run length is exactly the statistic that looks impressive on serially dependent
noise: flows are persistent for reasons that have nothing to do with a view, and
an independent-draw null would call an ordinary streak remarkable. The harness's
stationary block bootstrap resamples contiguous stretches of a flow series that
carries that persistence, which is the block permutation this field's threshold
is frozen from.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .bars import BarFrame, average_over_sessions
from .fields import Denomination, FieldReading, FieldWindow
from .issues import SignalIssue
from .reference import ForeignRoomStanding, ForeignRoomState

# The stretch the pressure ratio measures over, which is also the stretch its
# denominator averages: an ADTV means twenty sessions in this market, and a
# numerator and a denominator drawn from different windows would be a ratio of
# two different months.
FOREIGN_FLOW_SESSIONS = 20
FOREIGN_FLOW_MIN_SESSIONS = FOREIGN_FLOW_SESSIONS

# The stretch the run length is looked for in. A quarter rather than the twenty
# above, because the statistic is the length of a streak and a window of twenty
# cannot report one longer than twenty — the ceiling would be the window's
# rather than the market's, which is the same failure the mean-reversion gauge
# suppresses its z for.
FOREIGN_PERSISTENCE_SESSIONS = 60
FOREIGN_PERSISTENCE_MIN_SESSIONS = FOREIGN_PERSISTENCE_SESSIONS

# How many lags the ratio's standard error corrects for serial dependence over.
# Five is a week of trading. Foreign flows are persistent — that persistence is
# the other field in this module — so an independent-observation standard error
# on the sum would understate it, and by a factor that grows with the
# persistence it is ignoring.
FLOW_NEWEY_WEST_LAGS = 5

# The room percentage is not a trailing statistic and reads no stretch of
# market: its inputs are one reference snapshot and the date being answered for.
# The window exists only because every registered field reaches the store
# through the one gateway, and one session is the shortest honest thing to ask
# it for.
FOREIGN_ROOM_MIN_SESSIONS = 1

# The threshold the run length fires at, in sessions, frozen from the null
# harness at the registry's derivation seed and path count. Derived rather than
# conventional: there is no published convention for how long a foreign-flow
# streak has to be before it is remarkable, which is itself part of why the field
# needed a null rather than a number somebody liked.
PERSISTENCE_RUN_THRESHOLD = 15.0


def _flows(
    frame: BarFrame, sessions: int
) -> tuple[list[float] | None, SignalIssue | None]:
    """The newest sessions' net foreign flows, or nothing if any is missing.

    All or nothing, like the ADTV beside it: a sum over the twelve sessions that
    happened to carry a flow is a sum over a different stretch of market, and a
    run length over a series with holes in it is a run through the holes.
    """
    bars = frame.bars[-sessions:]
    if len(bars) < sessions:
        return None, SignalIssue.INSUFFICIENT_HISTORY
    values: list[float] = []
    for bar in bars:
        if bar.foreign_net_value_vnd is None:
            return None, SignalIssue.FOREIGN_FLOW_NOT_STORED
        values.append(bar.foreign_net_value_vnd)
    return values, None


def _room_extras(room: ForeignRoomStanding | None) -> dict[str, object]:
    """The room state every answer in this module carries, present or not.

    A standing describes itself; what is left here is the case where there is no
    standing at all, which is a fact about the store rather than about the room
    and is therefore not the standing's to describe.
    """
    if room is not None:
        return room.as_extras()
    return {
        "foreign_room_state": ForeignRoomState.UNKNOWN.value,
        "foreign_room_available_share": None,
        "foreign_room_as_of": None,
    }


def _room_degradation(room: ForeignRoomStanding | None) -> SignalIssue | None:
    """Which of the two things wrong with a room reading gets reported.

    Staleness first. A reading three months old describes a book that has since
    traded, so "the room was full then" is a weaker statement than "nobody has
    looked lately" — reporting the exhaustion of a stale reading would assert
    today's constraint on last quarter's evidence.
    """
    if room is None:
        return None
    if room.stale:
        return SignalIssue.STALE_REFERENCE_READING
    if room.exhausted:
        return SignalIssue.FOREIGN_ROOM_EXHAUSTED
    return None


def _long_run_standard_error(values: Sequence[float]) -> float | None:
    """Newey-West (1987) with a Bartlett kernel: the SE of a mean that has memory.

    The plain ``s/√n`` assumes each session's flow is a fresh draw. Foreign flows
    are not — persistence is the other statistic in this module — and ignoring it
    understates the error on the sum by a factor that grows with the very thing
    the second field measures. The Bartlett weights ``1 − k/(L+1)`` are what keep
    the estimate non-negative.
    """
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    centred = [item - mean for item in values]
    gamma0 = sum(item * item for item in centred) / n
    total = gamma0
    lags = min(FLOW_NEWEY_WEST_LAGS, n - 1)
    for lag in range(1, lags + 1):
        covariance = (
            sum(centred[index] * centred[index + lag] for index in range(n - lag)) / n
        )
        total += 2.0 * (1.0 - lag / (lags + 1.0)) * covariance
    if total <= 0:
        return 0.0
    return math.sqrt(total / n)


def net_value_over_adtv_reading(window: FieldWindow) -> FieldReading:
    """Net foreign buying over the window, in days of the symbol's own turnover.

    Both numerator and denominator are **money**: the sum of the session net
    foreign values divided by the average daily traded value over the same
    sessions. Positive means net foreign buying. The unit is days of typical
    turnover — a reading of 0.4 says foreigners net-bought about four tenths of
    one ordinary session's trading over the window.

    The room state travels with it, and an exhausted room degrades the answer.
    A flow that stopped because there was nothing left to buy is not a flow that
    stopped because anybody changed their mind, and this field cannot tell the
    two apart — so it says which of them the room permits.
    """
    frame = window.frame
    flows, missing = _flows(frame, FOREIGN_FLOW_SESSIONS)
    if flows is None:
        return FieldReading(value=None, refusal=missing)

    bars = frame.bars[-FOREIGN_FLOW_SESSIONS:]
    adtv = average_over_sessions(bar.total_value_vnd for bar in bars)
    if adtv is None:
        return FieldReading(
            value=None, refusal=SignalIssue.TRADED_FIGURE_NOT_STORED
        )
    if adtv <= 0:
        # Every session in the window traded nothing, so there is no turnover to
        # express the flow in. A fact about the symbol, not a short window.
        return FieldReading(value=None, refusal=SignalIssue.NO_TRADED_SESSIONS)

    net = sum(flows)
    mean_error = _long_run_standard_error(flows)
    return FieldReading(
        value=net / adtv,
        extras={
            "standard_error": (
                None if mean_error is None else len(flows) * mean_error / adtv
            ),
            "standard_error_basis": "newey_west_bartlett",
            "standard_error_lags": min(FLOW_NEWEY_WEST_LAGS, len(flows) - 1),
            "net_value_vnd": net,
            "adtv_vnd": adtv,
            # Both sides named, every time. The whole reason a share-denominated
            # ratio is refused rather than approximated is that nothing on the
            # wire would otherwise say which unit a reader is holding.
            "numerator_basis": Denomination.MONEY.value,
            "denominator_basis": Denomination.MONEY.value,
            "sessions": len(flows),
            **_room_extras(window.foreign_room),
        },
        degraded_reason=_room_degradation(window.foreign_room),
    )


def persistence_run_days(frame: BarFrame) -> float | None:
    """How many sessions the newest net flow has held its sign for, unbroken.

    The pure statistic, over the bars and nothing else, which is what lets the
    null harness run the shipped field over synthetic windows rather than a
    re-implementation of it.

    A session of exactly zero net flow ends a run and starts no new one: no
    foreign money moved, which is neither buying nor selling, and counting it
    into either would lengthen a streak with a session that had no side.
    """
    flows, _missing = _flows(frame, FOREIGN_PERSISTENCE_SESSIONS)
    if flows is None:
        return None

    newest = flows[-1]
    if newest == 0.0:
        return 0.0
    sign = 1.0 if newest > 0 else -1.0
    run = 0
    for value in reversed(flows):
        if value == 0.0 or (value > 0) != (sign > 0):
            break
        run += 1
    return float(run)


def persistence_run_days_reading(window: FieldWindow) -> FieldReading:
    """The current streak of same-signed foreign flow, in sessions.

    Non-negative, with the streak's direction beside it: a fifteen-session run of
    selling and a fifteen-session run of buying are the same length and are not
    the same fact. The field says how long the flow has held one side; it says
    nothing about how long it will.
    """
    frame = window.frame
    flows, missing = _flows(frame, FOREIGN_PERSISTENCE_SESSIONS)
    run = persistence_run_days(frame)
    if run is None or flows is None:
        return FieldReading(value=None, refusal=missing)

    newest = flows[-1] if flows else 0.0
    return FieldReading(
        value=run,
        extras={
            # Which way the streak ran, as a fact about the sessions behind it.
            # Positive is a run of net foreign buying.
            "run_sign": 0 if newest == 0.0 else (1 if newest > 0 else -1),
            "run_net_value_vnd": sum(flows[-int(run):]) if run else 0.0,
            "sessions": len(flows),
            **_room_extras(window.foreign_room),
        },
        degraded_reason=_room_degradation(window.foreign_room),
    )


def foreign_room_pct_reading(window: FieldWindow) -> FieldReading:
    """How much of this symbol's foreign ownership cap is still open, in percent.

    The Money-flow field the Analysis Field Profile names beside the two flow
    figures, and the one the spec's prerequisite list assumed had no inputs.
    It does: the reference Capability is collected on every cycle and the price
    board publishes both the remaining room and the cap it sits under, so this
    is served rather than refused — spec 0003 §13 forbids fictionalising a
    field's availability in **either** direction, and registering a refusal over
    stored data would be the same dishonesty with the sign flipped.

    Refused where no reference reading exists at or before the window's cutoff.
    An uncollected room is unknown, and reporting 100% for it would assert the
    thing nobody looked at.
    """
    room = window.foreign_room
    if room is None or room.available_share is None:
        return FieldReading(
            value=None,
            refusal=SignalIssue.FOREIGN_ROOM_NOT_STORED,
            extras=_room_extras(room),
        )
    return FieldReading(
        value=100.0 * room.available_share,
        extras={
            "current_room_shares": room.current_room,
            "total_room_shares": room.total_room,
            **_room_extras(room),
        },
        degraded_reason=_room_degradation(room),
    )


def net_volume_over_adtv_reading(window: FieldWindow) -> FieldReading:
    """Refused: no adapter in this system writes foreign traded volume.

    The share-denominated twin of the served ratio, registered so the profile
    stays honest about the difference between a figure this system does not have
    and a figure it has in another unit. Nothing here falls back to the money
    ratio: the two are not the same number, an ADTV in shares does not survive an
    ex-date, and the naming split exists to make the substitution impossible to
    make by accident rather than merely discouraged.
    """
    return FieldReading(
        value=None,
        refusal=SignalIssue.UNAVAILABLE,
        extras={
            "missing_input": (
                "foreign traded volume per session; the Main Source reports "
                "foreign buy and sell as money and no adapter writes the share "
                "counts, so no share-denominated ratio can be formed"
            ),
            "available_instead": "foreign_flow_pressure.net_value_over_adtv",
            **_room_extras(window.foreign_room),
        },
    )
