"""Which symbols one user asked to keep being analysed, and the rules on it.

Three rules and nothing else. The cap is ten. Addition is restricted to the
**Universe**. Removal deletes nothing.

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

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import in_sync_session
from src.stocks.shared import StockServiceError, validate_symbol
from src.stocks.universe import build_universe

from .models import WatchlistEntry

# Ten per user, and unlike the Universe cap this one reaches the interface. A
# user collides with it every time they add a symbol, so it is shown as a count
# from the first entry rather than sprung on them at the eleventh.
WATCHLIST_MAX_SYMBOLS = 10


class WatchlistRefusal(Exception):
    """A Watchlist change refused for a named reason.

    The reason is a stable code the interface may branch on; the message is the
    sentence a person reads and is allowed to change. Folded into one string,
    every caller would have to parse the reason out of prose.
    """

    def __init__(self, reason: str, message: str, status_code: int) -> None:
        super().__init__(f"{reason}: {message}")
        self.reason = reason
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class WatchlistItem:
    """One symbol on the rail, as the interface needs it."""

    symbol: str
    added_at: datetime
    last_seen_analysis_date: date | None


@dataclass(frozen=True)
class WatchlistView:
    """A whole Watchlist, and the count the cap is read against.

    ``count`` is carried rather than derived from ``len(items)`` because the two
    are not the same question — the cap counts what still gets analysed, and the
    rail lists everything the user chose.
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


async def _in_universe(symbol: str) -> bool:
    """Whether the Universe currently carries this symbol.

    The Universe is read from a synchronous session because the store is
    synchronous, and this is a request path, so it crosses the one documented
    seam rather than blocking the event loop on a query.
    """
    return await in_sync_session(lambda session: build_universe(session).contains(symbol))


async def _view(session: AsyncSession, user_id: int) -> WatchlistView:
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
            added_at=row.added_at,
            last_seen_analysis_date=row.last_seen_analysis_date,
        )
        for row in rows
    )
    return WatchlistView(items=items, count=len(items))


async def list_watchlist(session: AsyncSession, user_id: int) -> WatchlistView:
    """Everything this user watches. Empty for a new user, and genuinely so —
    a seeded symbol is an Analysis produced that night for a holding nobody
    chose."""
    return await _view(session, user_id)


async def add_symbol(session: AsyncSession, user_id: int, symbol: str) -> WatchlistView:
    """Put a symbol on the Watchlist, or refuse with the reason named.

    Adding a symbol already watched is a no-op rather than a conflict. The
    request describes a state the Watchlist is already in, and a retried add —
    a double tap, a replayed request — must not read as a lost slot. It is also
    why the duplicate check comes before the cap: a full Watchlist re-adding
    something already on it is not full for that request.
    """
    normalized = _normalized(symbol)
    if normalized is None or not await _in_universe(normalized):
        raise WatchlistRefusal(
            reason="symbol_not_in_universe",
            message=(
                f"Mã {symbol.strip().upper()} không nằm trong Universe nên hệ thống "
                "không có dữ liệu để phân tích mỗi phiên."
            ),
            status_code=422,
        )

    view = await _view(session, user_id)
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
    return await _view(session, user_id)


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

    return await _view(session, user_id)
