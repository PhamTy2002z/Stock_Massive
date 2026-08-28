"""The one read that turns stored rows into a symbol's sessions.

Every signal in this package starts by asking the same question — *which stored
session is this symbol's session on this day* — and this module is the two
shapes it is asked in:

- ``sessions_on_days`` — several symbols, an explicit list of days, one query.
  What a cross-sectional field needs: every symbol measured against the same
  sessions, resolved market-wide rather than per symbol.
- ``sessions_in_range`` — one symbol, a date range. What ``prepare_bars()`` and
  the band regime need.

**The source is ``bar_daily``, and there is no two-copy problem left to
resolve.** Sessions used to come out of ``provider_snapshots``, where two
sources wrote the same ``market`` Capability, their windows overlapped, and the
two copies of an overlapping session were on different Price Basis values — so
picking the wrong one turned a computable window into a refused one, and a
Main-Source-wins rule decided it. ``bar_daily`` is keyed on
``(symbol, trading_day)``: one session is one row, the provider re-states it in
place when an adjustment factor changes behind it, and there is nothing to pick
between.

**Which series is a parameter and not a second reader**, for the same reason the
Capability was: an index series has one owning source today, but a hand-written
index read would be the copy that stopped following the rule. What the caller
may name is bounded to the two Capabilities that are session series at all — the
store's others are not, and a ``fundamental`` window resolved by this reader
would be a quarter dressed as a session.

``Capability`` is still the vocabulary the callers speak, because ``BarSeries``
lives in ``bars.py`` and ``bars.py`` reads this module. It is mapped to the
``series`` column here, in one place, rather than at each call site.

The stored row is narrower than the snapshot it becomes. ``bar_daily`` holds
OHLCV and nothing else — no traded value, no market capitalisation, no foreign
split, no session change — so those arrive as ``None``. That is the honest
reading: a field that needs one refuses by name rather than being handed a
number nobody measured.

Neither read consults Redis. It holds the current view of one session, and
filling it with ranges would evict exactly that.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.models import BarDaily

from ..providers.contracts import (
    MARKET_SCHEMA_VERSION,
    Capability,
    PriceBasis,
    ProviderSource,
    SessionSnapshot,
    SnapshotMetadata,
)
from ..providers.normalize import VN_TZ
from ..providers.store import SNAPSHOT_MODEL_BY_CAPABILITY

# The Capabilities that hold one row per instrument per session. Named as a set
# rather than left implicit so a caller reaching this reader with `fundamental`
# is refused where it is written, instead of being handed a quarterly statement
# keyed by a date that means something else.
SESSION_CAPABILITIES: frozenset[Capability] = frozenset(
    {Capability.MARKET, Capability.MARKET_INDEX}
)

# Which ``bar_daily.series`` each session Capability is stored as. One mapping
# rather than a test at each query: the two names come from different eras of
# this codebase, and a reader that guessed the correspondence in two places
# could guess it differently in each.
_SERIES_BY_CAPABILITY: dict[Capability, str] = {
    Capability.MARKET: "equity",
    Capability.MARKET_INDEX: "index",
}


def _require_session_capability(capability: Capability) -> Capability:
    if capability not in SESSION_CAPABILITIES:
        raise ValueError(
            f"{capability.value} is not a session series: this reader resolves "
            f"{', '.join(sorted(item.value for item in SESSION_CAPABILITIES))}"
        )
    return capability


def sessions_on_days(
    session: Session,
    symbols: Sequence[str],
    days: Sequence[date],
    *,
    capability: Capability = Capability.MARKET,
) -> dict[str, dict[date, SessionSnapshot]]:
    """These symbols' sessions on exactly these days, in one query.

    Days are named rather than bounded, because a cross-sectional field measures
    every symbol against one market-wide window: bounding by first and last
    would quietly re-admit a session that one symbol has and the window does not.
    """
    _require_session_capability(capability)
    if not symbols or not days:
        return {}

    wanted = sorted({symbol.upper() for symbol in symbols})
    rows = session.execute(
        select(BarDaily)
        .where(
            BarDaily.series == _SERIES_BY_CAPABILITY[capability],
            BarDaily.symbol.in_(wanted),
            BarDaily.trading_day.in_(list(days)),
        )
        .order_by(BarDaily.trading_day.asc())
    ).scalars()

    by_symbol: dict[str, list[BarDaily]] = {}
    for row in rows:
        by_symbol.setdefault(row.symbol, []).append(row)

    return {
        symbol: _as_sessions(held, capability)
        for symbol, held in by_symbol.items()
    }


def sessions_in_range(
    session: Session,
    symbol: str,
    start: date,
    end: date,
    *,
    capability: Capability = Capability.MARKET,
) -> dict[date, SessionSnapshot]:
    """One symbol's stored sessions across a date range, keyed by session day."""
    _require_session_capability(capability)
    rows = session.execute(
        select(BarDaily)
        .where(
            BarDaily.series == _SERIES_BY_CAPABILITY[capability],
            BarDaily.symbol == symbol.upper(),
            BarDaily.trading_day >= start,
            BarDaily.trading_day <= end,
        )
        .order_by(BarDaily.trading_day.asc())
    ).scalars()
    return _as_sessions(rows, capability)


def _as_sessions(
    rows: Iterable[BarDaily],
    capability: Capability,
) -> dict[date, SessionSnapshot]:
    """Every stored row as the snapshot its Capability is served under."""
    model = SNAPSHOT_MODEL_BY_CAPABILITY[capability]
    return {row.trading_day: _as_snapshot(model, row) for row in rows}


def _as_snapshot(model: type[SessionSnapshot], row: BarDaily) -> SessionSnapshot:
    """One stored bar as the session contract the signals package reads.

    ``effective_at`` is midnight in Vietnam on the day it traded, which is the
    stamp every session in this system has always carried and what the band
    regime and the Corporate Action series line up against.
    """
    return model(
        symbol=row.symbol,
        metadata=SnapshotMetadata(
            source=ProviderSource(row.source),
            effective_at=datetime.combine(row.trading_day, time.min, tzinfo=VN_TZ),
            observed_at=_utc(row.observed_at),
            schema_version=MARKET_SCHEMA_VERSION,
        ),
        price_basis=PriceBasis(row.price_basis),
        open_price=_price(row.open),
        high_price=_price(row.high),
        low_price=_price(row.low),
        last_price=_price(row.close),
        volume=int(row.volume) if row.volume is not None else None,
    )


def _utc(value: datetime) -> datetime:
    """A machine clock as an instant, however the driver handed it back.

    ``observed_at`` is written in UTC and Postgres returns it with its zone;
    SQLite has no such type and returns it bare. Read as UTC either way, which
    is the reading this store has always given a naive timestamp.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _price(value: object) -> float | None:
    """A stored price as a number, or nothing where it cannot be one.

    Zero and below are read as absent rather than as a price. The contract bounds
    every price above zero, so a row carrying one would fail validation and take
    a whole window with it; a session whose close is not a price is a session the
    gateway should drop, which is exactly what ``None`` makes it do.
    """
    if value is None:
        return None
    number = float(value)
    return number if number > 0 else None
