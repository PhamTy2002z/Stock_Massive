"""Which days this market actually held a session for, and how stale that is.

A Trading Day here is not a day on the calendar. It is a day the daily spine
holds a closed session for, because this system has no holiday calendar of its
own: ``src.core.trading_calendar.is_trading_day`` knows only the day of the
week, so it reads Tet as nine ordinary sessions, and a signal labelled with a
session that never happened cannot be compared against the session after it.

**The spine, and specifically the index series.** ``bar_daily`` holds equities
and VNINDEX in one table, and the calendar is read off ``series = 'index'``
alone. VNINDEX is one symbol, so "the index has a session" is "the market has a
session" with no coverage question behind it — whereas a ``distinct`` over the
equity series is a *union*, and it would call a day a session because any one
of 1,522 shares had a row. Measured 2026-08-28, 845 of 1,522 shares had a row on
the newest session, so the union would declare sessions most symbols have no
history for. The two candidate definitions — VNINDEX, and the 30 declared
Universe symbols — agreed exactly on all 3,991 stored days; VNINDEX is chosen
because it needs no second table and no membership decision.

Resolution is market-wide, never per symbol. A twenty-day baseline resolved per
symbol would let a symbol with gaps reach further back and average a different
stretch of market than the symbol beside it, and the two numbers would be
presented as comparable. Resolved market-wide, the twenty days are the same
twenty for everyone, and a symbol missing any of them is unevaluable and says
so.

**A session is closed when the row was read after the close, not when a clock
says so.** ``vnstock_daily`` writes the current session during trading hours
with whatever the provider has of it, and the next run's upsert replaces it —
so a partial bar is indistinguishable from a closed one by its own numbers.
``observed_at`` is the fact that settles it. Reading ``datetime.now()`` here
instead would make the calendar non-deterministic inside one Turn: a Turn asking
at 14:59:50 and again at 15:00:10 would measure two different windows, which is
exactly what the market-wide resolution above exists to prevent.

The settled test is applied by ``latest_trading_day`` and by it alone. That
function is the one place a window's end is *chosen*, so it is the only place a
partial session can leak in; the two functions below it walk backward from a day
the caller has already named, and a day older than that one is behind the
partial session rather than in front of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from src.stocks.models import BarDaily

from .intraday.reads import SESSION_SETTLED_AT
from .providers.normalize import VN_TZ

#: The series the calendar is read off. See the module docstring for why it is
#: the index and not a union over the equity series.
CALENDAR_SERIES = "index"

#: How many trailing days ``latest_trading_day`` will walk back through looking
#: for one that has settled. A run interrupted mid-session leaves one partial
#: day; a spine that has been left partial for a week is stale rather than
#: merely mid-session, and ``spine_freshness`` is what reports that.
_SETTLE_PROBE = 5

#: Past this, the spine has stopped being fed. Calendar days rather than
#: sessions on purpose: the whole point is that nothing is arriving, so there is
#: no session count to measure the gap in.
STALE_AFTER_DAYS = 4


def _settled(day: date, observed_at: datetime | None) -> bool:
    """Whether this row was read after the session it describes had closed.

    ``observed_at`` is a machine clock written in UTC, so a value that came back
    without a zone is read as UTC — the same reading the store has always given
    it.
    """
    if observed_at is None:
        return False
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    close = datetime.combine(day, SESSION_SETTLED_AT, tzinfo=VN_TZ)
    return observed_at >= close


def latest_trading_day(session: Session) -> date | None:
    """The newest **closed** session the spine holds, or None.

    None is a real answer, not a failure: a fresh environment has collected
    nothing yet, and callers have to say so rather than substitute today. A
    session the provider was still filling in is skipped rather than served
    short, which is a different answer again and is why the walk-back exists.
    """
    rows = session.execute(
        select(BarDaily.trading_day, func.max(BarDaily.observed_at))
        .where(BarDaily.series == CALENDAR_SERIES)
        .group_by(BarDaily.trading_day)
        .order_by(BarDaily.trading_day.desc())
        .limit(_SETTLE_PROBE)
    ).all()
    for day, observed_at in rows:
        if _settled(day, observed_at):
            return day
    return None


def trading_days_before(session: Session, day: date, count: int) -> tuple[date, ...]:
    """The ``count`` Trading Days strictly before ``day``, newest first.

    Returns fewer than asked for when the spine does not hold them, and never
    pads with calendar days. A caller that needs exactly twenty sessions has to
    check the length: a baseline quietly built from seventeen is a baseline that
    means something different from the one beside it.
    """
    if count <= 0:
        return ()

    rows = session.execute(
        select(distinct(BarDaily.trading_day))
        .where(
            BarDaily.series == CALENDAR_SERIES,
            BarDaily.trading_day < day,
        )
        .order_by(BarDaily.trading_day.desc())
        .limit(count)
    ).scalars()
    return tuple(rows)


def trading_days_between(session: Session, start: date, end: date) -> tuple[date, ...]:
    """Every Trading Day in a closed window, oldest first.

    An empty window is a real answer: a stretch the exchange was shut for holds
    no sessions, which is not the same as a spine holding nothing.
    """
    if start > end:
        return ()

    rows = session.execute(
        select(distinct(BarDaily.trading_day))
        .where(
            BarDaily.series == CALENDAR_SERIES,
            BarDaily.trading_day >= start,
            BarDaily.trading_day <= end,
        )
        .order_by(BarDaily.trading_day.asc())
    ).scalars()
    return tuple(rows)


@dataclass(frozen=True)
class SpineFreshness:
    """How far behind the calendar's source has fallen, in terms a job can print.

    Separate from ``latest_trading_day`` deliberately. That function is on the
    path of every question anyone asks and has to stay a pure query; this one is
    read by whoever is responsible for feeding the spine, which is the only
    party that can act on the answer.
    """

    #: The newest closed session, or None while the spine holds nothing.
    latest_session: date | None
    #: When the newest row of the calendar series was read, whatever session it
    #: described. None while the spine holds nothing.
    last_observed_at: datetime | None
    #: Calendar days between the newest closed session and ``today``.
    age_days: int | None

    @property
    def is_empty(self) -> bool:
        """Nothing has ever been collected, which is not the same as stale."""
        return self.latest_session is None

    @property
    def is_stale(self) -> bool:
        return self.age_days is not None and self.age_days > STALE_AFTER_DAYS

    def describe(self) -> str:
        if self.is_empty:
            return "the daily spine holds no session at all"
        return (
            f"newest closed session {self.latest_session}, "
            f"{self.age_days} calendar days old, "
            f"last read {self.last_observed_at}"
        )


def spine_freshness(session: Session, *, today: date | None = None) -> SpineFreshness:
    """Whether anything is still feeding the daily spine, and how long ago.

    ``today`` is injectable so a test can state the day rather than depend on
    the one it runs on. Nothing on the serving path calls this: the clock is
    admissible here precisely because the answer is an operational fact rather
    than part of any window.
    """
    latest = latest_trading_day(session)
    observed_at = session.execute(
        select(func.max(BarDaily.observed_at)).where(
            BarDaily.series == CALENDAR_SERIES
        )
    ).scalar_one_or_none()
    if latest is None:
        return SpineFreshness(
            latest_session=None, last_observed_at=observed_at, age_days=None
        )
    reference = today if today is not None else datetime.now(VN_TZ).date()
    return SpineFreshness(
        latest_session=latest,
        last_observed_at=observed_at,
        age_days=(reference - latest).days,
    )

