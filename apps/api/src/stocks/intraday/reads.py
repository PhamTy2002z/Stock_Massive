"""The read a Study is allowed to make: whole sessions, already closed.

Two rules, both borrowed from the chat lane rather than invented here:

**Closed sessions only.** The lane answers about "the most recent closed
session" (``CLAUDE.md``), and a Study drawing today's half-finished session
beside thirty whole ones would put a short bar at the right-hand edge that means
nothing except that it is not four in the afternoon yet. A session counts as
closed once 15:00 Vietnam time has passed — the closing auction prints at 14:45
and the provider is given the quarter hour it sometimes takes.

**Whole sessions.** ``bars_for`` returns every stored bucket of the N most recent
closed sessions and never a partial one, so a caller cannot accidentally
normalise a share against a truncated day.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.models import BarIntraday15m
from src.stocks.providers.normalize import VN_TZ, day_in_vn

from .session_window import Phase

#: When a session is treated as final. 14:45 is the closing auction bucket; the
#: extra quarter hour is for the provider, which has been seen to publish the
#: last bucket late rather than never.
SESSION_SETTLED_AT = time(15, 0)


@dataclass(frozen=True)
class Bar15m:
    """One stored bucket, in the terms a Study computes in."""

    symbol: str
    trading_day: date
    bucket_start: datetime
    phase: Phase
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    @property
    def bucket_label(self) -> str:
        local = self.bucket_start.astimezone(VN_TZ)
        return f"{local.hour:02d}:{local.minute:02d}"

    @property
    def traded_value(self) -> Decimal:
        """Volume at the bucket's closing price, in VND.

        The close rather than a typical price: it is the only one of the four
        that is a price something actually traded at for certain, and a Study
        offering ``value`` as an alternative to ``volume`` is asking "how much
        money moved", not "what was the average level".
        """
        return self.close * self.volume


def latest_closed_session(
    session: Session, symbol: str, *, now: datetime | None = None
) -> date | None:
    """The most recent stored session that is over, or ``None`` if none is."""
    now = now or datetime.now(VN_TZ)
    today = now.astimezone(VN_TZ).date()
    settled_today = now.astimezone(VN_TZ).time() >= SESSION_SETTLED_AT

    statement = (
        select(BarIntraday15m.trading_day)
        .where(BarIntraday15m.symbol == symbol.upper())
        .order_by(BarIntraday15m.trading_day.desc())
        .limit(1)
    )
    if not settled_today:
        statement = statement.where(BarIntraday15m.trading_day < today)

    return session.execute(statement).scalar_one_or_none()


def sessions_available(
    session: Session, symbol: str, *, now: datetime | None = None
) -> int:
    """How many closed sessions the store holds, for a min-sample decision."""
    return len(_closed_days(session, symbol.upper(), now=now))


def bars_for(
    session: Session,
    symbol: str,
    sessions: int,
    *,
    now: datetime | None = None,
) -> tuple[Bar15m, ...]:
    """Every bucket of the ``sessions`` most recent closed sessions, oldest first.

    Fewer sessions come back when the store holds fewer; deciding what a short
    window means belongs to the Study, which is the only layer that knows its own
    minimum sample.
    """
    symbol = symbol.upper()
    days = _closed_days(session, symbol, now=now)[:sessions]
    if not days:
        return ()

    rows = session.execute(
        select(BarIntraday15m)
        .where(
            BarIntraday15m.symbol == symbol,
            BarIntraday15m.trading_day.in_(days),
        )
        .order_by(BarIntraday15m.bucket_start)
    ).scalars()

    return tuple(
        Bar15m(
            symbol=row.symbol,
            trading_day=row.trading_day,
            bucket_start=row.bucket_start,
            phase=row.phase,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
        )
        for row in rows
    )


def _closed_days(
    session: Session, symbol: str, *, now: datetime | None
) -> list[date]:
    """Stored sessions that are over, newest first."""
    now = now or datetime.now(VN_TZ)
    local = now.astimezone(VN_TZ)
    statement = (
        select(BarIntraday15m.trading_day)
        .where(BarIntraday15m.symbol == symbol)
        .distinct()
        .order_by(BarIntraday15m.trading_day.desc())
    )
    if local.time() < SESSION_SETTLED_AT:
        statement = statement.where(BarIntraday15m.trading_day < local.date())

    return list(session.execute(statement).scalars())


__all__ = [
    "Bar15m",
    "SESSION_SETTLED_AT",
    "bars_for",
    "day_in_vn",
    "latest_closed_session",
    "sessions_available",
]
