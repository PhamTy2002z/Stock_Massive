"""The four trusted values a Turn is rendered against (#85).

:class:`~src.agent.prompt.RuntimeContext` is a closed set — a user id, a Trading
Day, a market state and an optional symbol — and it is closed precisely so that
no figure, tool result or piece of user prose can reach the system prompt.  This
module resolves the two the request cannot carry.

**The Trading Day comes from the store, never from the clock.**  A Trading Day
is a day the store holds an end-of-day market Snapshot for; today is frequently
not one, and a Turn labelled with a session that never happened would compare
against a session that does not exist.

**The market state comes from the clock, because no tool can supply it.**  That
is the one reason ``docs/adr/0015`` §7 gives for injecting it at all: without
it the model calls yesterday's close "the current price", and no tool result
catches that sentence.  The phases below are HOSE's continuous-session
timetable, which is the market the Universe is built from; HNX and UPCOM differ
at the margins, and a phase label that is fifteen minutes optimistic for UPCOM
is a far smaller error than no phase at all.
"""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from src.core.trading_calendar import is_trading_day
from src.stocks.trading_day import latest_trading_day

from .prompt import MarketState

ICT = ZoneInfo("Asia/Ho_Chi_Minh")

# HOSE's session boundaries, local time. Ordered, and read as "the state that
# holds until this moment".
_PHASES: tuple[tuple[time, MarketState], ...] = (
    (time(9, 0), MarketState.PRE_OPEN),
    (time(9, 15), MarketState.ATO),
    (time(11, 30), MarketState.CONTINUOUS),
    (time(13, 0), MarketState.LUNCH_BREAK),
    (time(14, 30), MarketState.CONTINUOUS),
    (time(14, 45), MarketState.ATC),
    (time(15, 0), MarketState.POST_CLOSE),
)


def market_state_at(moment: datetime) -> MarketState:
    """Which phase the exchange is in, by the clock in Vietnam.

    A day the exchange does not trade is ``closed`` for all of it.
    ``is_trading_day`` knows only the weekday, so Tet reads as nine ordinary
    sessions — the same limit the rest of the system carries, and stated here
    rather than hidden: the cost of being wrong is a phase label, not a dated
    artifact.
    """
    local = moment.astimezone(ICT)
    if not is_trading_day(local.date()):
        return MarketState.CLOSED
    for boundary, state in _PHASES:
        if local.time() < boundary:
            return state
    return MarketState.CLOSED


def resolve_trading_day(session, *, fallback: date) -> date:
    """The newest session the store holds, or the caller's fallback.

    ``latest_trading_day`` answers ``None`` on a store that has collected
    nothing, and that is a real answer rather than a failure. A Turn still has
    to be answerable there — the tools will refuse for want of data and say so,
    which is a better outcome than a 500 on an empty environment.
    """
    return latest_trading_day(session) or fallback


__all__ = ["ICT", "market_state_at", "resolve_trading_day"]
