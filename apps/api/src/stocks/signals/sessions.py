"""The one read that turns stored rows into a symbol's sessions.

Every signal in this package starts by asking the same question — *which stored
session is this symbol's session on this day* — and the answer is not a row
lookup. Two sources write the ``market`` Capability, their windows overlap, and
the two copies of an overlapping session disagree about more than detail: since
``docs/adr/0006`` they are on different **Price Basis** values, so picking the
wrong one turns a computable window into a refused one.

So the resolution lives once, in ``providers.store.resolve_sessions``, and this
module is the two shapes the signals package asks it in:

- ``sessions_on_days`` — several symbols, an explicit list of days, one query.
  What a cross-sectional field needs: every symbol measured against the same
  sessions, resolved market-wide rather than per symbol.
- ``sessions_in_range`` — one symbol, a date range. What ``prepare_bars()`` and
  the band regime need.

Neither consults Redis. It holds the current view of one session, and filling it
with ranges would evict exactly that.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.models import ProviderSnapshot

from ..providers.contracts import (
    Capability,
    MarketSnapshot,
    cover_source,
    main_source,
)
from ..providers.normalize import VN_TZ
from ..providers.store import resolve_sessions

_MARKET = Capability.MARKET.value


def _day_start(day: date, after: int = 0) -> datetime:
    """Midnight in Vietnam, which is how a session is stamped.

    A range built in UTC would start seven hours into its first session and drop
    it, so the bound has to be expressed in the market's own zone.
    """
    return datetime.combine(day + timedelta(days=after), time.min, tzinfo=VN_TZ)


def _market_sources() -> list[str]:
    """Both sources that write a market session, Main first."""
    return [
        source.value
        for source in (main_source(Capability.MARKET), cover_source(Capability.MARKET))
        if source is not None
    ]


def sessions_on_days(
    session: Session,
    symbols: Sequence[str],
    days: Sequence[date],
) -> dict[str, dict[date, MarketSnapshot]]:
    """These symbols' sessions on exactly these days, in one query.

    Days are named rather than bounded, because a cross-sectional field measures
    every symbol against one market-wide window: bounding by first and last
    would quietly re-admit a session that one symbol has and the window does not.
    """
    if not symbols or not days:
        return {}

    stamps = [_day_start(day) for day in days]
    wanted = sorted({symbol.upper() for symbol in symbols})
    rows = session.execute(
        select(ProviderSnapshot)
        .where(
            ProviderSnapshot.capability == _MARKET,
            ProviderSnapshot.symbol.in_(wanted),
            ProviderSnapshot.effective_at.in_(stamps),
        )
        .order_by(
            ProviderSnapshot.effective_at.asc(),
            ProviderSnapshot.observed_at.asc(),
        )
    ).scalars()

    # Resolved per symbol: the Main-Source-wins rule is about two copies of one
    # symbol's session, and a single dictionary keyed on the timestamp alone
    # would let one symbol's row stand in for another's.
    by_symbol: dict[str, list[ProviderSnapshot]] = {}
    for row in rows:
        by_symbol.setdefault(row.symbol, []).append(row)

    return {
        symbol: _as_market_sessions(held)
        for symbol, held in by_symbol.items()
    }


def sessions_in_range(
    session: Session,
    symbol: str,
    start: date,
    end: date,
) -> dict[date, MarketSnapshot]:
    """One symbol's stored sessions across a date range, keyed by session day."""
    rows = session.execute(
        select(ProviderSnapshot)
        .where(
            ProviderSnapshot.capability == _MARKET,
            ProviderSnapshot.symbol == symbol.upper(),
            ProviderSnapshot.source.in_(_market_sources()),
            ProviderSnapshot.effective_at >= _day_start(start),
            ProviderSnapshot.effective_at < _day_start(end, after=1),
        )
        .order_by(
            ProviderSnapshot.effective_at.asc(),
            ProviderSnapshot.observed_at.asc(),
        )
    ).scalars()
    return _as_market_sessions(rows)


def _as_market_sessions(
    rows: Iterable[ProviderSnapshot],
) -> dict[date, MarketSnapshot]:
    """Resolve two-copy sessions and validate the winners, keyed by VN date."""
    resolved = resolve_sessions(rows, Capability.MARKET)
    return {
        stamp.astimezone(VN_TZ).date(): MarketSnapshot.model_validate(row.payload)
        for stamp, row in sorted(resolved.items())
    }
