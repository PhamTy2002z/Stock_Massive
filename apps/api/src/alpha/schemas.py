"""Wire shapes for Alpha Desk."""

from datetime import date, datetime

from pydantic import BaseModel, Field

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
    # Advances only when that specific Analysis is opened, which is what makes
    # the unread badge mean anything.
    last_seen_analysis_date: date | None


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
