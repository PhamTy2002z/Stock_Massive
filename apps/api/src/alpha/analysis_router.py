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

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import CurrentUser
from src.core.database import get_db, in_sync_session, in_sync_write
from src.stocks.shared import StockServiceError, validate_symbol

from .analysis_reads import analysis_for, recent_analyses
from .analysis_run import AnalysisRefusal, request_retry
from .models import Analysis
from .naming import session_label
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


def _no_analysis(symbol: str, trading_day: date) -> AnalysisRefusal:
    """The one refusal a pair with no Analysis gets, wherever it is asked for.

    Reading one and opening one refuse identically on purpose: they are the same
    fact about the store, and two sentences for it would be two things the
    interface has to recognise.
    """
    return AnalysisRefusal(
        reason="analysis_not_found",
        message=f"Chưa có Analysis cho mã {symbol} ở {session_label(trading_day)}.",
        status_code=404,
    )


async def _published(symbol: str, trading_day: date) -> Analysis:
    """The Analysis for this pair, or the refusal that says there is none."""
    row = await in_sync_session(
        lambda session: analysis_for(session, symbol, trading_day)
    )
    if row is None:
        raise _no_analysis(symbol, trading_day)
    return row


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
        entries=[AnalysisSummaryResponse.of(row) for row in history.entries],
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
    row = await _published(_symbol(symbol), trading_day)
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
    await _published(normalized, trading_day)

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
    outcome = await in_sync_write(
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
