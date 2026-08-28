"""The daily session history a Study is allowed to read, and nothing else.

``bar_daily`` is written market-wide by the backfill job (``stocks/
backfill_daily.py``) and read here. A Study reads the store and never a
provider, which is what lets an artifact be re-rendered a week later and what
makes a golden test possible at all.

Three rules, and each one is a decision a caller would otherwise have to make
again per Study:

**Closed sessions only.** The lane answers about sessions that are over
(``CLAUDE.md``), and the ingest writes today's half-finished session with
whatever the provider has of it so far. A 52-week high taken from a session
still trading is a number that changes under the reader. The cutoff is the same
constant the fifteen-minute reader uses — one market, one answer to "is this
session final".

**The series is stated, not inferred from the symbol.** ``bar_daily`` holds
equities in dong and the index in points in one table, and a read that trusted
the ticker to imply the scale would compare 74,500 with 1,821 the first time a
caller passed the wrong name. So ``series`` is an argument with a default, and
the query filters on it.

**Oldest first.** Every derivation over the window — a return, a drawdown, a
Wilder average — is written as a walk forward in time, so the read hands back
the order those are written in rather than the order the index answers in.

Prices stay :class:`~decimal.Decimal` as the column holds them. Converting to
float is the caller's step, taken where the arithmetic is, so nothing here
quietly loses precision on the way out of the store.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.intraday.reads import SESSION_SETTLED_AT
from src.stocks.models import BarDaily
from src.stocks.providers.normalize import VN_TZ

#: The two series ``bar_daily`` holds. Restated here rather than imported from
#: ``providers/vnstock_daily.py``, which imports pandas and vnstock at module
#: load so that only the backfill job pays for them; a reader on the answering
#: path must not drag that in. ``tests/studies/test_reads_daily.py`` holds the
#: two spellings equal, so the copy cannot drift silently.
SERIES_EQUITY = "equity"
SERIES_INDEX = "index"

#: The market index, whose sessions live in the same table under
#: ``series="index"``. Named here because a Study comparing a symbol with the
#: market should not have to know the provider's ticker for it.
INDEX_SYMBOL = "VNINDEX"


@dataclass(frozen=True)
class DailyBar:
    """One closed session, in the terms a Study computes in.

    ``price_basis`` travels with the prices because it is what makes them
    comparable: every row written today says ``adjusted_at_source``, and a
    window that mixed bases would silently put a pre-split price beside a
    post-split one in the same 52-week range.
    """

    symbol: str
    trading_day: date
    series: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    price_basis: str


def bars_for(
    session: Session,
    symbol: str,
    sessions: int,
    *,
    series: str = SERIES_EQUITY,
    now: datetime | None = None,
) -> tuple[DailyBar, ...]:
    """The ``sessions`` most recent closed sessions of one series, oldest first.

    Fewer come back when the store holds fewer, and deciding what a short window
    means belongs to the Study: it is the only layer that knows its own minimum
    sample, and a reader that refused here would refuse identically for a
    question that could have been answered.

    ``now`` is the Study's frozen as-of rather than the wall clock, so the same
    artifact rebuilt from the same instant reads the same window.
    """
    if sessions <= 0:
        return ()

    local = (now or datetime.now(VN_TZ)).astimezone(VN_TZ)
    statement = select(BarDaily).where(
        BarDaily.symbol == symbol.strip().upper(),
        BarDaily.series == series,
    )
    if local.time() < SESSION_SETTLED_AT:
        statement = statement.where(BarDaily.trading_day < local.date())

    rows = list(
        session.execute(
            statement.order_by(BarDaily.trading_day.desc()).limit(sessions)
        ).scalars()
    )

    return tuple(
        DailyBar(
            symbol=row.symbol,
            trading_day=row.trading_day,
            series=row.series,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
            price_basis=row.price_basis,
        )
        for row in reversed(rows)
    )


def sessions_available(
    session: Session,
    symbol: str,
    *,
    series: str = SERIES_EQUITY,
    now: datetime | None = None,
) -> int:
    """How many closed sessions the store holds, for a minimum-sample decision.

    Separate from :func:`bars_for` so a caller can say "the store is too thin"
    without loading a year of rows to find out.
    """
    local = (now or datetime.now(VN_TZ)).astimezone(VN_TZ)
    statement = select(BarDaily.trading_day).where(
        BarDaily.symbol == symbol.strip().upper(),
        BarDaily.series == series,
    )
    if local.time() < SESSION_SETTLED_AT:
        statement = statement.where(BarDaily.trading_day < local.date())
    return len(list(session.execute(statement.distinct()).scalars()))


__all__ = [
    "INDEX_SYMBOL",
    "SERIES_EQUITY",
    "SERIES_INDEX",
    "SESSION_SETTLED_AT",
    "DailyBar",
    "bars_for",
    "sessions_available",
]
