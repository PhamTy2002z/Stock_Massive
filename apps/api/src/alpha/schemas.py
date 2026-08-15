"""Wire shapes for Alpha Desk."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from .on_demand import ON_DEMAND_ANALYSES_PER_DAY, OnDemandOutcome
from .watchlist import WatchlistState


class WatchlistAddRequest(BaseModel):
    """A symbol to start watching, as typed."""

    # Bounded rather than validated to a pattern: a symbol that cannot exist is
    # refused by the Universe rule with a reason the interface already handles,
    # and a second vocabulary of validation errors for the same rejection would
    # be one the rail has to learn twice.
    symbol: str = Field(min_length=1, max_length=32)


class WatchlistItemResponse(BaseModel):
    """One symbol on the rail."""

    symbol: str
    # `active` or `unsupported`, and nothing about why: a delisting and an
    # operator trimming the Universe are the same state here because v1 cannot
    # tell them apart.
    state: WatchlistState
    added_at: datetime


class WatchlistResponse(BaseModel):
    """A whole Watchlist, and the count it is read against.

    Every mutation returns this, not the row it changed: the cap is shown
    permanently, and a caller that has to ask a second time for the count is a
    caller that will sometimes show a stale one.
    """

    cap: int
    # Active entries only, and it may exceed `cap`: a symbol restored to the
    # Universe revives whether or not there is room, and the overflow stands.
    count: int
    entries: list[WatchlistItemResponse]


class OnDemandResponse(BaseModel):
    """What the addition did to the on-demand Analysis lane.

    Carried on the addition rather than left to be discovered by polling the
    rail: the two outcomes a user has to be told about — the allowance is spent,
    or no session has closed yet — are answers to the request they just made,
    and a rail that merely showed the symbol as `pending` would not explain
    either.
    """

    outcome: OnDemandOutcome
    # The session the Analysis is for, named by date. Null only when the store
    # holds no closed session at all.
    trading_day: date | None
    remaining: int
    allowance: int = ON_DEMAND_ANALYSES_PER_DAY
    # Vietnamese, and present only where nothing was produced for a reason the
    # user would otherwise have to guess at.
    message: str | None = None


class WatchlistAddResponse(WatchlistResponse):
    """An addition: the whole Watchlist, plus what it cost to produce.

    A subclass rather than a field on `WatchlistResponse`, because listing and
    removal have no lane to report and a permanently null field on two of three
    routes is one the client has to learn to ignore.
    """

    on_demand: OnDemandResponse
