"""The Watchlist rail's three requests.

Thin on purpose: the cap, the Universe restriction and what removal means are
in ``watchlist.py``, because they are rules about the domain rather than about
HTTP. What is here is the mapping — a user from a bearer token, and a refusal
turned into a status code.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import CurrentUser
from src.core.database import get_db

from .schemas import WatchlistAddRequest, WatchlistItemResponse, WatchlistResponse
from .watchlist import (
    WatchlistView,
    add_symbol,
    list_watchlist,
    remove_symbol,
)

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

Db = Annotated[AsyncSession, Depends(get_db)]


def _response(view: WatchlistView) -> WatchlistResponse:
    return WatchlistResponse(
        cap=view.cap,
        count=view.count,
        entries=[
            WatchlistItemResponse(
                symbol=item.symbol,
                state=item.state,
                added_at=item.added_at,
                last_seen_analysis_date=item.last_seen_analysis_date,
            )
            for item in view.items
        ],
    )


@router.get("", response_model=WatchlistResponse)
async def get_watchlist(current_user: CurrentUser, db: Db) -> WatchlistResponse:
    """Everything this user watches, with the count against the cap."""
    return _response(await list_watchlist(db, current_user.id))


@router.post("", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
async def post_watchlist(
    payload: WatchlistAddRequest,
    current_user: CurrentUser,
    db: Db,
) -> WatchlistResponse:
    """Start watching a symbol, or be told why not."""
    return _response(await add_symbol(db, current_user.id, payload.symbol))


@router.delete("/{symbol}", response_model=WatchlistResponse)
async def delete_watchlist_symbol(
    symbol: str,
    current_user: CurrentUser,
    db: Db,
) -> WatchlistResponse:
    """Stop watching a symbol. Nothing else is deleted."""
    return _response(await remove_symbol(db, current_user.id, symbol))
