"""Turning "this many sessions" into something a Provider Source can answer.

Two jobs load a bounded trailing window of stored sessions — the Warm-up in
``warmup.py`` and the market index load in ``market_index.py`` — and they are
deliberately separate: different Capabilities, different owners, different
cadences, and depths an order of magnitude apart (``docs/adr/0005``,
``docs/adr/0017``). What they are *not* free to differ on is the arithmetic
below, because both of them are answering the same two mechanical questions and
two answers would be one of them wrong.

Kept here rather than in either job, so that neither reads as the other's
utility drawer, and so a third loader inherits the arithmetic instead of
re-deriving it.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Protocol, TypeVar

# Five sessions a week is seven calendar days.
_CALENDAR_DAYS_PER_TRADING_DAY = 7 / 5

# On top of the weekends, Vietnam closes for roughly eleven public holidays a
# year and nine of those run together at Tet. Expressed per session rather than
# as a fixed allowance on the end, because the two loaders' windows differ by an
# order of magnitude: a fortnight is generous over a month of sessions and less
# than half of what the holidays take over a year of them.
_HOLIDAY_DAYS_PER_TRADING_DAY = 11 / 250

# One fortnight on top of the proportional terms, for the ordinary case of a run
# made after a long weekend. Reaching back further than needed costs nothing —
# it is one provider call either way, and sessions already held collapse in the
# store — while reaching back too little silently stores a short window.
_CALENDAR_SLACK_DAYS = 14


def calendar_days_for(trading_days: int) -> int:
    """How far back a window of this many sessions has to reach in calendar days.

    Sessions are counted by the exchange and asked for by date, so every loader
    has to translate, and every one of them has to over-reach rather than under-
    reach: the callers all trim what comes back to the newest ``n``, so an
    over-long span costs a slightly larger frame and an over-short one costs
    sessions nobody notices are missing.
    """
    return (
        round(
            max(0, trading_days)
            * (_CALENDAR_DAYS_PER_TRADING_DAY + _HOLIDAY_DAYS_PER_TRADING_DAY)
        )
        + _CALENDAR_SLACK_DAYS
    )


def reaches_back_to(today: date, trading_days: int) -> date:
    """The date a window of this many sessions ending today has to start from."""
    return today - timedelta(days=calendar_days_for(trading_days))


class _Dated(Protocol):
    """Anything carrying the metadata every normalized snapshot carries."""

    @property
    def metadata(self) -> object: ...


Snapshot = TypeVar("Snapshot", bound=_Dated)


def newest_sessions(
    sessions: Sequence[Snapshot],
    window: int,
) -> tuple[Snapshot, ...]:
    """The newest ``window`` sessions of what came back, and nothing older.

    The reach-back above deliberately over-asks, so a quiet stretch of market
    comes back with more sessions than were wanted. Trimming here is what keeps
    "bounded" a property of what is *written* rather than only of what was
    requested — without it, a repeatable load deepens a little every time the
    calendar is kind, and stops being distinguishable from a Backfill.
    """
    newest_first = sorted(
        sessions,
        key=lambda item: _effective_at(item),
        reverse=True,
    )
    return tuple(newest_first[: max(0, window)])


def _effective_at(snapshot: Snapshot) -> datetime:
    return snapshot.metadata.effective_at  # type: ignore[attr-defined]
