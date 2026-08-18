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

Both read the ``market`` Capability by default and the ``market_index``
Capability when asked. **Which Capability is a parameter and not a second
reader**, because the resolution rule is the same rule either way: an index
series has one owning source today, but a Capability's ownership table is
allowed to change and a hand-written index read would be the copy that did not
follow it (``docs/adr/0017``). What the caller may name is bounded to those two
— the store's other Capabilities are not session series at all, and a
``fundamental`` window resolved by this reader would be a quarter dressed as a
session.

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
    SessionSnapshot,
    cover_source,
    main_source,
)
from ..providers.normalize import VN_TZ
from ..providers.store import SNAPSHOT_MODEL_BY_CAPABILITY, resolve_sessions

# The Capabilities that hold one row per instrument per session. Named as a set
# rather than left implicit so a caller reaching this reader with `fundamental`
# is refused where it is written, instead of being handed a quarterly statement
# keyed by a date that means something else.
SESSION_CAPABILITIES: frozenset[Capability] = frozenset(
    {Capability.MARKET, Capability.MARKET_INDEX}
)


def _day_start(day: date, after: int = 0) -> datetime:
    """Midnight in Vietnam, which is how a session is stamped.

    A range built in UTC would start seven hours into its first session and drop
    it, so the bound has to be expressed in the market's own zone.
    """
    return datetime.combine(day + timedelta(days=after), time.min, tzinfo=VN_TZ)


def _sources_for(capability: Capability) -> list[str]:
    """Every source that may write this Capability's sessions, Main first."""
    return [
        source.value
        for source in (main_source(capability), cover_source(capability))
        if source is not None
    ]


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

    stamps = [_day_start(day) for day in days]
    wanted = sorted({symbol.upper() for symbol in symbols})
    rows = session.execute(
        select(ProviderSnapshot)
        .where(
            ProviderSnapshot.capability == capability.value,
            ProviderSnapshot.symbol.in_(wanted),
            # The same sources the single-symbol read admits. Left off, a row
            # written by a source since retired from this Capability would be a
            # session to one reader and not to the other, and the two would
            # disagree about a symbol without either of them being wrong.
            ProviderSnapshot.source.in_(_sources_for(capability)),
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
        select(ProviderSnapshot)
        .where(
            ProviderSnapshot.capability == capability.value,
            ProviderSnapshot.symbol == symbol.upper(),
            ProviderSnapshot.source.in_(_sources_for(capability)),
            ProviderSnapshot.effective_at >= _day_start(start),
            ProviderSnapshot.effective_at < _day_start(end, after=1),
        )
        .order_by(
            ProviderSnapshot.effective_at.asc(),
            ProviderSnapshot.observed_at.asc(),
        )
    ).scalars()
    return _as_sessions(rows, capability)


def _as_sessions(
    rows: Iterable[ProviderSnapshot],
    capability: Capability,
) -> dict[date, SessionSnapshot]:
    """Resolve two-copy sessions and validate the winners, keyed by VN date."""
    model = SNAPSHOT_MODEL_BY_CAPABILITY[capability]
    resolved = resolve_sessions(rows, capability)
    return {
        stamp.astimezone(VN_TZ).date(): model.model_validate(row.payload)
        for stamp, row in sorted(resolved.items())
    }
