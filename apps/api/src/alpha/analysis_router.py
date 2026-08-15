"""Reading one Analysis, browsing a symbol's recent ones, and opening one.

Mounted beside ``/watchlist`` rather than under it, because an **Analysis** is
not one user's: it is keyed by ``(symbol, trading_day)`` and shared system-wide,
which is exactly why removing a symbol deletes nothing and why two watchers cost
one production. Any signed-in user may read any Analysis.

The one thing here that *is* per user is ``last_seen_analysis_date``, and its
ownership check is structural: every query touching it is scoped to the caller's
own Watchlist row, so there is no request shape that could read or move somebody
else's.
"""

import asyncio
from datetime import date
from typing import Annotated, Callable, TypeVar

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.auth.dependencies import CurrentUser
from src.core.database import get_db, get_sync_db, in_sync_session
from src.stocks.shared import StockServiceError, validate_symbol

from .analysis_reads import analysis_for, recent_analyses
from .analysis_run import AnalysisRefusal, request_retry
from .schemas import (
    AnalysisDetailResponse,
    AnalysisHistoryResponse,
    AnalysisOpenedResponse,
    AnalysisSummaryResponse,
    RetryResponse,
)
from .watchlist import mark_analysis_seen

router = APIRouter(prefix="/analyses", tags=["analyses"])

Db = Annotated[AsyncSession, Depends(get_db)]

_T = TypeVar("_T")


async def _in_sync_write(work: Callable[[Session], _T]) -> _T:
    """A synchronous write from an async handler, off the event loop.

    Not ``in_sync_session``, which is read-only by contract, and not the
    request's async session, which belongs to a different driver. Same seam as
    the on-demand lane (`src/alpha/on_demand.py`) and documented there in full.
    """

    def run() -> _T:
        with get_sync_db() as session:
            return work(session)

    return await asyncio.to_thread(run)


def _symbol(raw: str) -> str:
    """The symbol as stored, or a clean not-found.

    A malformed symbol has no Analysis for the same reason a well-formed
    unwatched one does not, so it leaves by the same door rather than as an
    upstream failure the interface has to learn a second vocabulary for.
    """
    try:
        return validate_symbol(raw)
    except StockServiceError:
        raise AnalysisRefusal(
            reason="analysis_not_found",
            message=f"Không có Analysis cho mã {raw.strip().upper()}.",
            status_code=404,
        )


def _summary(row) -> AnalysisSummaryResponse:
    return AnalysisSummaryResponse(
        symbol=row.symbol,
        trading_day=row.trading_day,
        verdict=row.verdict,
        schema_version=row.schema_version,
        created_at=row.created_at,
    )


@router.get("/{symbol}", response_model=AnalysisHistoryResponse)
async def get_analysis_history(symbol: str, current_user: CurrentUser) -> AnalysisHistoryResponse:
    """One symbol's recent Analyses, newest first and bounded at ninety.

    The bound and whether anything lies beyond it are both in the response.
    Ninety is a browsing depth, not a retention policy: Analyses are kept
    indefinitely and the agent reaches deeper by exact date.
    """
    normalized = _symbol(symbol)
    history = await in_sync_session(lambda session: recent_analyses(session, normalized))
    return AnalysisHistoryResponse(
        symbol=history.symbol,
        entries=[_summary(row) for row in history.entries],
        depth=history.depth,
        older_exist=history.older_exist,
    )


@router.get("/{symbol}/{trading_day}", response_model=AnalysisDetailResponse)
async def get_analysis(
    symbol: str,
    trading_day: date,
    current_user: CurrentUser,
) -> AnalysisDetailResponse:
    """The Analysis for exactly this pair, payload included.

    A pair with none is a clean not-found. An empty artifact would render as a
    briefing with nothing in it, which reads as a broken Analysis rather than as
    a session that was never analysed.
    """
    normalized = _symbol(symbol)
    row = await in_sync_session(
        lambda session: analysis_for(session, normalized, trading_day)
    )
    if row is None:
        raise AnalysisRefusal(
            reason="analysis_not_found",
            message=(
                f"Chưa có Analysis cho mã {normalized} ở phiên "
                f"{trading_day.strftime('%d/%m/%Y')}."
            ),
            status_code=404,
        )
    return AnalysisDetailResponse(
        symbol=row.symbol,
        trading_day=row.trading_day,
        verdict=row.verdict,
        schema_version=row.schema_version,
        created_at=row.created_at,
        payload=row.payload,
    )


@router.post("/{symbol}/{trading_day}/opened", response_model=AnalysisOpenedResponse)
async def post_analysis_opened(
    symbol: str,
    trading_day: date,
    current_user: CurrentUser,
    db: Db,
) -> AnalysisOpenedResponse:
    """Report that this user opened this Analysis, advancing their last-seen.

    An explicit act the client reports, and deliberately not a side effect of
    listing the rail: opening the app must not clear ten badges at once, which
    would empty the indicator exactly when it has work to do.

    The Analysis has to exist. Advancing past a session that was never published
    would mark a symbol read on the strength of a URL.
    """
    normalized = _symbol(symbol)
    row = await in_sync_session(
        lambda session: analysis_for(session, normalized, trading_day)
    )
    if row is None:
        raise AnalysisRefusal(
            reason="analysis_not_found",
            message=(
                f"Chưa có Analysis cho mã {normalized} ở phiên "
                f"{trading_day.strftime('%d/%m/%Y')}."
            ),
            status_code=404,
        )

    seen = await mark_analysis_seen(db, current_user.id, normalized, trading_day)
    return AnalysisOpenedResponse(symbol=normalized, last_seen_analysis_date=seen)


@router.post("/{symbol}/{trading_day}/retry", response_model=RetryResponse)
async def post_analysis_retry(
    symbol: str,
    trading_day: date,
    current_user: CurrentUser,
) -> RetryResponse:
    """Ask for one more attempt at a failed session.

    Queues rather than produces — generation belongs to whoever drains the
    queue, and a handler that produced inline would hold the request open for
    the length of an LLM call. Any watcher may ask: production is idempotent per
    pair and the artifact is shared, so two people retrying is one run.
    """
    normalized = _symbol(symbol)
    outcome = await _in_sync_write(
        lambda session: request_retry(session, current_user.id, normalized, trading_day)
    )
    return RetryResponse(
        symbol=normalized,
        trading_day=trading_day,
        status=outcome.status,
        attempts=outcome.attempts,
        locked=outcome.locked,
        error_code=outcome.error_code,
        error_message=outcome.error_message,
    )
