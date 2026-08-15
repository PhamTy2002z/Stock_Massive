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

from .on_demand import OnDemandRequest, open_on_demand_lane
from .schemas import (
    OnDemandResponse,
    WatchlistAddRequest,
    WatchlistAddResponse,
    WatchlistItemResponse,
    WatchlistResponse,
)
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
            )
            for item in view.items
        ],
    )


@router.get("", response_model=WatchlistResponse)
async def get_watchlist(current_user: CurrentUser, db: Db) -> WatchlistResponse:
    """Everything this user watches, with the count against the cap."""
    return _response(await list_watchlist(db, current_user.id))


@router.post("", response_model=WatchlistAddResponse, status_code=status.HTTP_201_CREATED)
async def post_watchlist(
    payload: WatchlistAddRequest,
    current_user: CurrentUser,
    db: Db,
) -> WatchlistAddResponse:
    """Start watching a symbol, or be told why not.

    Two acts in a fixed order, and the order is the point. The addition is
    committed first and stands whatever happens next: it is the thing the user
    asked for, and the on-demand Analysis is a consequence the system may refuse
    on its own budget without taking the symbol away with it.
    """
    view = await add_symbol(db, current_user.id, payload.symbol)
    await db.commit()

    # Run for a re-add too. The lane is idempotent per `(symbol, trading_day)`,
    # so it finds the existing run rather than making a second one — which is
    # why nothing here has to track whether this request seated a new row.
    lane = await open_on_demand_lane(current_user.id, payload.symbol)

    base = _response(view)
    return WatchlistAddResponse(
        cap=base.cap,
        count=base.count,
        entries=base.entries,
        on_demand=_lane_response(lane),
    )


def _lane_response(lane: OnDemandRequest) -> OnDemandResponse:
    return OnDemandResponse(
        outcome=lane.outcome,
        trading_day=lane.trading_day,
        remaining=lane.remaining,
        allowance=lane.allowance,
        message=lane.message,
    )


@router.delete("/{symbol}", response_model=WatchlistResponse)
async def delete_watchlist_symbol(
    symbol: str,
    current_user: CurrentUser,
    db: Db,
) -> WatchlistResponse:
    """Stop watching a symbol. Nothing else is deleted."""
    return _response(await remove_symbol(db, current_user.id, symbol))
