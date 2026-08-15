"""Which symbols one user asked to keep being analysed, and the rules on it.

Four rules and nothing else. The cap is ten, counting active entries. Addition
is restricted to the **Universe**. Removal deletes nothing. A symbol the
Universe has dropped goes `unsupported` and stays where the user put it.

The last of those is the one worth stating out loud, because the obvious
implementation of "remove from my Watchlist" is a cascade. An **Analysis** is
keyed by ``(symbol, trading_day)`` and shared system-wide, so it never belonged
to this row in the first place: removing a symbol and adding it back the same
day re-reads the Analysis that is already there, at zero cost, which is why
there is no mutation rate limit to write here either. Removal is a statement
about what keeps being analysed, not about history.

The cap has to be visible from the first symbol, so every function here returns
the whole view rather than the row it changed. A caller that has to make a
second request to learn the count is a caller that will sometimes show a stale
one.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.core.database import in_sync_session
from src.stocks.shared import StockServiceError, validate_symbol
from src.stocks.universe import Universe, build_universe

from .models import WatchlistEntry
from .refusals import AlphaRefusal

# Ten per user, and unlike the Universe cap this one reaches the interface. A
# user collides with it every time they add a symbol, so it is shown as a count
# from the first entry rather than sprung on them at the eleventh.
WATCHLIST_MAX_SYMBOLS = 10


class WatchlistRefusal(AlphaRefusal):
    """A Watchlist change refused for a named reason."""


class WatchlistState(str, Enum):
    """Whether a watched symbol still gets analysed.

    Two values, not three. ``unsupported`` covers both a real delisting and an
    operator trimming the configured Universe, because v1 cannot tell them apart
    — and a state named for a cause it cannot establish would be a lie the
    interface repeats.
    """

    ACTIVE = "active"
    UNSUPPORTED = "unsupported"


def entry_state(symbol: str, universe: Universe) -> WatchlistState:
    """One watched symbol's state, which is a question about the Universe.

    The signature is the argument. A symbol and the Universe are everything this
    takes, so there is nowhere for a cause to enter: a symbol that was delisted
    and a symbol an operator dropped from the configuration arrive here as the
    same fact — not in the Universe — and leave as the same state.

    Derived rather than stored, which is what makes revival automatic. A stored
    state would need a writer, and the writer would have to be the thing that
    notices a symbol coming back; nothing notices, so it would not come back.
    """
    return WatchlistState.ACTIVE if universe.contains(symbol) else WatchlistState.UNSUPPORTED


@dataclass(frozen=True)
class WatchlistItem:
    """One symbol on the rail, as the interface needs it."""

    symbol: str
    state: WatchlistState
    added_at: datetime
    last_seen_analysis_date: date | None


@dataclass(frozen=True)
class WatchlistView:
    """A whole Watchlist, and the count the cap is read against.

    ``count`` is carried rather than derived from ``len(items)`` because the two
    are not the same question — the cap counts what still gets analysed, and the
    rail lists everything the user chose. An ``unsupported`` entry appears in
    ``items`` and not in ``count``: it costs the user nothing, because they did
    not cause it.

    ``count`` may therefore exceed ``cap``, and that is a real state rather than
    a bug — see ``add_symbol`` for why the overflow is allowed to stand.
    """

    items: tuple[WatchlistItem, ...]
    count: int
    cap: int = WATCHLIST_MAX_SYMBOLS


def _normalized(symbol: str) -> str | None:
    """The symbol as stored, or None when it could not be a symbol at all.

    Malformed input is not an upstream failure and must not escape as one, so
    it is folded into the same refusal as a symbol outside the Universe: in
    both cases the answer is that this is not something the system has data for.
    """
    try:
        return validate_symbol(symbol)
    except StockServiceError:
        return None


async def _current_universe() -> Universe:
    """The Universe as it stands, read from an async handler.

    The Universe is read from a synchronous session because the store is
    synchronous, so this crosses the one documented seam rather than blocking
    the event loop on a query. Read once per request and passed down: two reads
    inside one request could disagree, and a Watchlist where a symbol is
    ``active`` in the list and refused by the cap is not a state anyone can act
    on.
    """
    return await in_sync_session(build_universe)


async def _view(
    session: AsyncSession,
    user_id: int,
    universe: Universe,
) -> WatchlistView:
    rows = (
        await session.execute(
            select(WatchlistEntry)
            .where(WatchlistEntry.user_id == user_id)
            .order_by(WatchlistEntry.added_at, WatchlistEntry.id)
        )
    ).scalars().all()

    items = tuple(
        WatchlistItem(
            symbol=row.symbol,
            state=entry_state(row.symbol, universe),
            added_at=row.added_at,
            last_seen_analysis_date=row.last_seen_analysis_date,
        )
        for row in rows
    )
    active = sum(1 for item in items if item.state is WatchlistState.ACTIVE)
    return WatchlistView(items=items, count=active)


def watches(session: Session, user_id: int, symbol: str) -> bool:
    """Whether this user has the symbol on their Watchlist.

    Synchronous, unlike everything else here, because its caller is the Analysis
    Run lifecycle rather than a request. It lives in this module anyway: every
    query against ``watchlist_entries`` belongs to one place, or two modules end
    up with two answers to what "watched" means.
    """
    return (
        session.execute(
            select(WatchlistEntry.id).where(
                WatchlistEntry.user_id == user_id,
                WatchlistEntry.symbol == symbol,
            )
        ).scalar_one_or_none()
        is not None
    )


async def list_watchlist(session: AsyncSession, user_id: int) -> WatchlistView:
    """Everything this user watches. Empty for a new user, and genuinely so —
    a seeded symbol is an Analysis produced that night for a holding nobody
    chose."""
    return await _view(session, user_id, await _current_universe())


async def add_symbol(session: AsyncSession, user_id: int, symbol: str) -> WatchlistView:
    """Put a symbol on the Watchlist, or refuse with the reason named.

    Adding a symbol already watched is a no-op rather than a conflict. The
    request describes a state the Watchlist is already in, and a retried add —
    a double tap, a replayed request — must not read as a lost slot. It is also
    why the duplicate check comes before the cap: a full Watchlist re-adding
    something already on it is not full for that request.

    The cap counts active entries, so a Watchlist carrying `unsupported` symbols
    has room the user never lost. Where it has no room, the refusal is the only
    thing that happens — nothing is evicted to make space, because the system
    does not get to choose which of a user's symbols matters least.
    """
    normalized = _normalized(symbol)
    universe = await _current_universe()
    if normalized is None or not universe.contains(normalized):
        raise WatchlistRefusal(
            reason="not_in_universe",
            message=(
                f"Mã {symbol.strip().upper()} không nằm trong Universe nên hệ thống "
                "không có dữ liệu để phân tích mỗi phiên."
            ),
            status_code=422,
        )

    view = await _view(session, user_id, universe)
    if any(item.symbol == normalized for item in view.items):
        return view

    # Read-then-write, with no lock: two adds racing could seat an eleventh
    # symbol. That is left alone rather than serialized behind a row lock,
    # because a Watchlist sitting over the cap is a state the product already
    # has to tolerate — a symbol restored to the Universe revives whether or not
    # there is room — and the rule there is that the overflow stands and adding
    # is blocked until the user trims. A race produces exactly that state.
    if view.count >= WATCHLIST_MAX_SYMBOLS:
        raise WatchlistRefusal(
            reason="watchlist_full",
            message=(
                f"Watchlist đã đủ {WATCHLIST_MAX_SYMBOLS} mã. Gỡ một mã trước khi "
                "thêm mã mới."
            ),
            status_code=409,
        )

    session.add(WatchlistEntry(user_id=user_id, symbol=normalized))
    await session.flush()
    return await _view(session, user_id, universe)


async def remove_symbol(session: AsyncSession, user_id: int, symbol: str) -> WatchlistView:
    """Take a symbol off the Watchlist, and delete nothing else.

    No Analysis, no Thread, no message. The freed slot is immediately reusable:
    there is no cooling-off period to enforce because re-adding costs nothing to
    produce.
    """
    normalized = _normalized(symbol)
    removed = (
        await session.execute(
            delete(WatchlistEntry).where(
                WatchlistEntry.user_id == user_id,
                WatchlistEntry.symbol == normalized,
            )
        )
    ).rowcount if normalized is not None else 0

    if not removed:
        raise WatchlistRefusal(
            reason="symbol_not_watched",
            message=f"Mã {symbol.strip().upper()} không có trong Watchlist.",
            status_code=404,
        )

    return await _view(session, user_id, await _current_universe())
