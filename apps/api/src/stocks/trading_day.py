"""Which days this system actually holds a session for, and whether it moved.

A Trading Day here is not a day on the calendar. It is a day the store has an
end-of-day market Snapshot for — ``date(max(effective_at))`` in
``provider_snapshots`` — because this system has no holiday calendar of its own.
``src.core.trading_calendar.is_trading_day`` knows only the day of the week, so
it reads Tet as nine ordinary sessions; a signal or an Analysis labelled with a
session that never happened cannot be compared against the session after it.

Resolution is market-wide, never per symbol. A twenty-day baseline resolved per
symbol would let a symbol with gaps reach further back and average a different
stretch of market than the symbol beside it, and the two numbers would be
presented as comparable. Resolved market-wide, the twenty days are the same
twenty for everyone, and a symbol missing any of them is unevaluable and says
so.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from src.stocks.models import ProviderSnapshot

from .providers.contracts import Capability
from .providers.normalize import VN_TZ, day_in_vn

# Every adapter that writes a market Snapshot dates it at midnight in Vietnam on
# the day it traded — FiinQuant through ``_session_start``, vnstock through
# ``datetime.combine(..., tzinfo=VN_TZ)``. One distinct ``effective_at`` is
# therefore exactly one Trading Day, which is what lets these queries count
# sessions without grouping by an expression the index cannot serve.
_MARKET = Capability.MARKET.value


def _day_start(day: date) -> datetime:
    """Midnight in Vietnam, which is how a session is stamped."""
    return datetime.combine(day, time.min, tzinfo=VN_TZ)


def latest_trading_day(session: Session) -> date | None:
    """The newest day the store holds a market Snapshot for, or None.

    None is a real answer, not a failure: a fresh environment has collected
    nothing yet, and callers have to say so rather than substitute today.
    """
    newest = session.execute(
        select(func.max(ProviderSnapshot.effective_at)).where(
            ProviderSnapshot.capability == _MARKET
        )
    ).scalar_one_or_none()
    return None if newest is None else day_in_vn(newest)


def trading_days_before(session: Session, day: date, count: int) -> tuple[date, ...]:
    """The ``count`` Trading Days strictly before ``day``, newest first.

    Returns fewer than asked for when the store does not hold them, and never
    pads with calendar days. A caller that needs exactly twenty sessions has to
    check the length: a baseline quietly built from seventeen is a baseline that
    means something different from the one beside it.
    """
    if count <= 0:
        return ()

    rows = session.execute(
        select(distinct(ProviderSnapshot.effective_at))
        .where(
            ProviderSnapshot.capability == _MARKET,
            ProviderSnapshot.effective_at < _day_start(day),
        )
        .order_by(ProviderSnapshot.effective_at.desc())
        .limit(count)
    ).scalars()
    return tuple(day_in_vn(stamp) for stamp in rows)


def trading_days_between(session: Session, start: date, end: date) -> tuple[date, ...]:
    """Every Trading Day in a closed window, oldest first.

    An empty window is a real answer: a stretch the exchange was shut for holds
    no sessions, which is not the same as a store holding nothing.
    """
    if start > end:
        return ()

    rows = session.execute(
        select(distinct(ProviderSnapshot.effective_at))
        .where(
            ProviderSnapshot.capability == _MARKET,
            ProviderSnapshot.effective_at >= _day_start(start),
            ProviderSnapshot.effective_at < _day_start(end + timedelta(days=1)),
        )
        .order_by(ProviderSnapshot.effective_at.asc())
    ).scalars()
    return tuple(day_in_vn(stamp) for stamp in rows)


def market_generation(session: Session) -> datetime | None:
    """A token that advances whenever stored market data moves.

    ``max(observed_at)`` over market Snapshots, and deliberately not a counter
    of its own: it advances exactly when a Collector or Warm-up transaction
    commits, it survives a restart, and there is no second thing to keep in step
    with the data. Signal cache keys carry it, so an entry computed before a
    write is unreachable afterwards rather than merely unlikely to be read.

    Unlike ``effective_at``, ``observed_at`` is a machine clock rather than a
    session stamp: it is written in UTC, so a value that came back without a
    zone is read as UTC.
    """
    newest = session.execute(
        select(func.max(ProviderSnapshot.observed_at)).where(
            ProviderSnapshot.capability == _MARKET
        )
    ).scalar_one_or_none()
    if newest is None:
        return None
    if newest.tzinfo is None:
        return newest.replace(tzinfo=timezone.utc)
    return newest
