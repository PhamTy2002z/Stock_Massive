"""Wire shapes for Alpha Desk."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from .analysis_reads import HISTORY_DEPTH_SESSIONS, AnalysisState
from .analysis_run import MAX_ATTEMPTS_PER_SESSION, RunStatus
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


class AnalysisSummaryResponse(BaseModel):
    """One Analysis as a list shows it: everything except the payload.

    `schema_version` is on the wire because a reader meets several across days
    and has to know which template it is rendering. It is not part of the row's
    identity and nothing selects on it — there is one Analysis per
    `(symbol, trading_day)` and every read is by exactly that pair.
    """

    symbol: str
    trading_day: date
    verdict: str
    schema_version: int
    created_at: datetime

    @classmethod
    def of(cls, row: Any) -> "AnalysisSummaryResponse":
        """Map anything shaped like an Analysis onto the wire.

        Three routes serve this shape from two different sources — the ORM row
        and the summary the rail reads — and each had written the same five
        assignments out. One of them is where a field gets forgotten.
        """
        return cls(
            symbol=row.symbol,
            trading_day=row.trading_day,
            verdict=row.verdict,
            schema_version=row.schema_version,
            created_at=row.created_at,
        )


class AnalysisDetailResponse(AnalysisSummaryResponse):
    """One Analysis in full. The payload is the artifact the user reads."""

    payload: dict


class AnalysisHistoryResponse(BaseModel):
    """A bounded window of one symbol's Analyses, newest first.

    `depth` and `older_exist` are both stated rather than left to be inferred
    from the length of `entries`: eighty-one rows may be everything the store
    holds or the first eighty-one of three hundred, and an interface that cannot
    tell renders an empty scroll at the boundary instead of an edge.
    """

    symbol: str
    entries: list[AnalysisSummaryResponse]
    depth: int = HISTORY_DEPTH_SESSIONS
    older_exist: bool


class RunFailureResponse(BaseModel):
    """Why a session's production stopped, and whether it can be asked again."""

    code: str | None
    message: str | None
    attempts: int
    max_attempts: int = MAX_ATTEMPTS_PER_SESSION
    # The ceiling is reached and nothing more runs for this pair until the next
    # session, so the interface drops the retry rather than offering one more
    # press that does nothing.
    exhausted: bool


class RailEntryResponse(BaseModel):
    """One symbol on the rail, in the state the user should see it.

    `latest` is the newest Analysis that exists whatever session it is for,
    which is what keeps a `failed` cell from rendering empty: it shows the last
    thing there was to read beside the label naming the session that is missing.
    """

    symbol: str
    state: AnalysisState
    added_at: datetime
    latest: AnalysisSummaryResponse | None
    failure: RunFailureResponse | None
    unread: bool
    last_seen_analysis_date: date | None


class RailResponse(BaseModel):
    """The whole rail in one request: the session, the cap, and the symbols.

    One response rather than a Watchlist call plus an Analysis call, because the
    two would be answered at two moments — and a rail labelled with one Trading
    Day whose cells were computed against another is wrong in the one place a
    user checks first.
    """

    cap: int
    count: int
    # The session the rail is showing, named by date. Null only on a store that
    # holds no closed session at all; it is never substituted with today.
    trading_day: date | None
    entries: list[RailEntryResponse]


class AnalysisOpenedResponse(BaseModel):
    """Where this user's last-seen date for one symbol now stands.

    Returned rather than assumed, because the write does not always move it: an
    older Analysis opened after a newer one leaves the stored date where it was.
    """

    symbol: str
    last_seen_analysis_date: date


class RetryResponse(BaseModel):
    """What asking for another attempt did to the run.

    `status` is the run's, not the request's: a retry queues an attempt and the
    interface renders whatever state that leaves the pair in.
    """

    symbol: str
    trading_day: date
    status: RunStatus
    attempts: int
    max_attempts: int = MAX_ATTEMPTS_PER_SESSION
    locked: bool
    error_code: str | None = None
    error_message: str | None = None
