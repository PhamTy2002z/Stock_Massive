"""Producing an Analysis exactly once, without any machinery for exactly once.

Two invariants do all the work, and neither is enforced by code in this file:

**A row in ``analysis`` existing means it is complete.** In-flight state lives
only in ``analysis_run``. That is what makes *serve yesterday instantly while
today runs* need no mechanism at all — ``ORDER BY trading_day DESC LIMIT 1`` —
because there is never a half-written Analysis to filter out.

**A run marked ready implies the Analysis row exists.** So the Analysis is
written first and the status flipped second, in two transactions. Dying between
them leaves the run ``producing``; the retry finds the Analysis already there
and flips the status without producing again. Idempotency is a consequence of
``UNIQUE(symbol, trading_day)``, not of a lock, a lease, or a job id.

The order is the whole design, which is why the two writes are two named
functions rather than one convenient helper. Reversed — status first, Analysis
second — a death in the middle produces a run claiming an Analysis that does not
exist, and every reader of the rail would need a mechanism to detect it.

This file owns the lifecycle and nothing else. Generation is a parameter
(``src/alpha/producer.py``), the nightly cohort and the backoff schedule belong
to the pipeline milestone, and the on-demand allowance belongs to the lane that
creates on-demand runs.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.stocks.shared import validate_symbol
from src.stocks.universe import build_universe

from .models import Analysis, AnalysisRun
from .producer import AnalysisDraft, Producer, ProductionFailure, sanitized_reason
from .refusals import AlphaRefusal
from .watchlist import watches

logger = logging.getLogger(__name__)


class RunStatus(str, Enum):
    """Where the production of one Analysis has got to.

    ``pending`` is "the Trading Day has a Snapshot but this symbol's turn has not
    come". It is a real state and not a synonym for absent: without it, a symbol
    that failed looks exactly like one not yet reached, and the interface cannot
    tell whether to offer a retry.
    """

    PENDING = "pending"
    PRODUCING = "producing"
    READY = "ready"
    FAILED = "failed"


class RunOrigin(str, Enum):
    """What asked for this run.

    Kept because a symbol only ever produced on demand is a different
    operational story from one the nightly pass keeps missing. Written once, at
    creation: a retry does not rewrite the origin, or a nightly run repaired by a
    user's retry would lose the fact that the nightly pass was where it started.
    """

    NIGHTLY = "nightly"
    ON_DEMAND = "on_demand"
    RETRY = "retry"


# Three attempts per symbol per session, then locked until the next one. Per
# session rather than per hour because the thing being retried is tied to a
# Trading Day: a symbol whose session data never arrived will not start working
# at midnight, and a fourth attempt would be the same failure re-read.
MAX_ATTEMPTS_PER_SESSION = 3

# Not one of the pipeline's failure codes, and deliberately outside that
# taxonomy: those describe a production attempt reporting why it could not
# finish. This one describes an attempt that stopped existing — a crash, a
# deploy — and nothing was there to report anything.
ABANDONED_CODE = "run_abandoned"


class AnalysisRefusal(AlphaRefusal):
    """A request against an Analysis Run refused for a named reason."""


@dataclass(frozen=True)
class RunOutcome:
    """What a caller needs to know, without re-reading the run row."""

    status: RunStatus
    analysis: Analysis | None
    # Whether this call produced the Analysis, as opposed to finding one. A
    # rerun of a ready pair is a no-op returning the existing artifact, and a
    # caller charging for production has to be able to tell the difference.
    produced: bool
    attempts: int
    # The three-attempt ceiling has been reached and nothing more will run for
    # this pair until the next session.
    locked: bool = False
    error_code: str | None = None
    error_message: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def published_analysis(
    session: Session,
    symbol: str,
    trading_day: date,
) -> Analysis | None:
    """The Analysis for this pair, if one has been published.

    There is at most one, by the unique key, and its existence means it is
    complete — so this needs no status filter and never returns something half
    written.
    """
    return session.execute(
        select(Analysis).where(
            Analysis.symbol == symbol,
            Analysis.trading_day == trading_day,
        )
    ).scalar_one_or_none()


def latest_analysis(session: Session, symbol: str) -> Analysis | None:
    """The newest Analysis this system holds for a symbol.

    The rail's answer when today's is not ready yet: `failed` shows the most
    recent Analysis that does exist rather than an empty cell, and this is the
    query that finds it. No status filter, for the same reason as above.
    """
    return session.execute(
        select(Analysis)
        .where(Analysis.symbol == symbol)
        .order_by(Analysis.trading_day.desc())
        .limit(1)
    ).scalar_one_or_none()


def _stored_run(session: Session, symbol: str, trading_day: date) -> AnalysisRun | None:
    return session.execute(
        select(AnalysisRun).where(
            AnalysisRun.symbol == symbol,
            AnalysisRun.trading_day == trading_day,
        )
    ).scalar_one_or_none()


def _run_for(
    session: Session,
    symbol: str,
    trading_day: date,
    origin: RunOrigin,
) -> AnalysisRun:
    """The run row for this pair, created at ``pending`` if there is none.

    One row per pair, for the reason ``AnalysisRun`` records: it is what makes
    two people retrying the same symbol one run.
    """
    existing = _stored_run(session, symbol, trading_day)
    if existing is not None:
        return existing

    run = AnalysisRun(
        symbol=symbol,
        trading_day=trading_day,
        status=RunStatus.PENDING.value,
        origin=origin.value,
        attempts=0,
    )
    session.add(run)
    try:
        session.commit()
    except IntegrityError:
        # Another caller created it between the select and the insert. Theirs is
        # as good as ours: the row identifies the pair, not the requester.
        session.rollback()
        created = _stored_run(session, symbol, trading_day)
        if created is None:
            raise
        return created
    return run


def _begin_attempt(session: Session, run: AnalysisRun) -> None:
    """Take the run to ``producing`` and commit, before anything is produced.

    Committed first on purpose. A process that dies during production has to
    leave evidence that it was producing — that is what the sweep looks for, and
    without the commit a crash would leave the run looking untouched and the
    attempt uncounted.
    """
    run.status = RunStatus.PRODUCING.value
    run.attempts = (run.attempts or 0) + 1
    run.started_at = _now()
    run.finished_at = None
    run.error_code = None
    run.error_message = None
    session.commit()


def write_analysis(
    session: Session,
    symbol: str,
    trading_day: date,
    draft: AnalysisDraft,
) -> Analysis:
    """Publish the Analysis. The first of the two writes, and it commits.

    A losing race hits ``UNIQUE(symbol, trading_day)`` and reads the winner's
    row rather than producing a second. That is the idempotency: it is the
    constraint, not code guarding against a second producer.
    """
    analysis = Analysis(
        symbol=symbol,
        trading_day=trading_day,
        verdict=draft.verdict,
        payload=draft.payload,
        schema_version=draft.schema_version,
    )
    session.add(analysis)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        published = published_analysis(session, symbol, trading_day)
        if published is None:
            raise
        logger.info(
            "Analysis for %s %s was already published; keeping it",
            symbol,
            trading_day,
        )
        return published
    return analysis


def mark_run_ready(session: Session, run: AnalysisRun) -> None:
    """Flip the run to ``ready``. The second of the two writes, and it commits.

    Only ever called once the Analysis is committed, which is what makes
    ``ready`` mean the row exists.
    """
    run.status = RunStatus.READY.value
    run.finished_at = _now()
    run.error_code = None
    run.error_message = None
    session.commit()


def _mark_failed(session: Session, run: AnalysisRun, code: str, message: str) -> None:
    run.status = RunStatus.FAILED.value
    run.finished_at = _now()
    run.error_code = code
    run.error_message = sanitized_reason(message)
    session.commit()


def produce_analysis(
    session: Session,
    symbol: str,
    trading_day: date,
    producer: Producer,
    origin: RunOrigin = RunOrigin.NIGHTLY,
) -> RunOutcome:
    """Produce the Analysis for one pair, or repair the run that already did.

    Owns its transaction boundaries — it commits several times, and it has to:
    the ordering guarantee this whole file rests on is only a guarantee if the
    Analysis is committed before the status is.

    A ``ProductionFailure`` is recorded as a code and a sentence. Anything else
    propagates untouched and leaves the run ``producing``, which is honest: the
    taxonomy has no code for "something nobody anticipated", inventing one would
    put a lie in the column the interface renders, and a run left producing is
    exactly what the sweep exists to find.
    """
    symbol = validate_symbol(symbol)
    run = _run_for(session, symbol, trading_day, origin)

    published = published_analysis(session, symbol, trading_day)
    if published is not None:
        # Nothing to produce. The only thing that can be wrong is the run's
        # status, and this is the repair the invariant promises: a retry after a
        # death between the two writes flips the status and produces nothing.
        if run.status != RunStatus.READY.value:
            mark_run_ready(session, run)
        return RunOutcome(
            status=RunStatus.READY,
            analysis=published,
            produced=False,
            attempts=run.attempts,
        )

    if run.status == RunStatus.PRODUCING.value:
        # Someone else is mid-flight. Producing alongside them would cost a
        # second generation to write an Analysis the unique key would throw
        # away. A run stuck here is the sweep's problem, not this caller's.
        return RunOutcome(
            status=RunStatus.PRODUCING,
            analysis=None,
            produced=False,
            attempts=run.attempts,
        )

    if run.attempts >= MAX_ATTEMPTS_PER_SESSION:
        return RunOutcome(
            status=RunStatus(run.status),
            analysis=None,
            produced=False,
            attempts=run.attempts,
            locked=True,
            error_code=run.error_code,
            error_message=run.error_message,
        )

    _begin_attempt(session, run)

    try:
        draft = producer(symbol, trading_day)
    except ProductionFailure as failure:
        _mark_failed(session, run, failure.code, failure.message)
        return RunOutcome(
            status=RunStatus.FAILED,
            analysis=None,
            produced=False,
            attempts=run.attempts,
            locked=run.attempts >= MAX_ATTEMPTS_PER_SESSION,
            error_code=run.error_code,
            error_message=run.error_message,
        )

    analysis = write_analysis(session, symbol, trading_day, draft)
    mark_run_ready(session, run)
    return RunOutcome(
        status=RunStatus.READY,
        analysis=analysis,
        produced=True,
        attempts=run.attempts,
    )


def retry_analysis(
    session: Session,
    user_id: int,
    symbol: str,
    trading_day: date,
    producer: Producer,
) -> RunOutcome:
    """Retry on behalf of a user who watches the symbol.

    Any watcher may, not only whoever added it first: production is idempotent
    per ``(symbol, trading_day)`` and the artifact is shared system-wide, so two
    people retrying is one run and there is nothing to ration by restricting it.

    Two refusals, both about the request rather than the production. A user who
    does not watch the symbol has no standing to spend the system's budget on
    it, and a symbol that has left the Universe produces nothing at all — that
    is what `unsupported` means, and the retry button is the one path a user
    could otherwise use to argue with it.
    """
    normalized = validate_symbol(symbol)

    if not watches(session, user_id, normalized):
        raise AnalysisRefusal(
            reason="symbol_not_watched",
            message=f"Mã {normalized} không có trong Watchlist của bạn.",
            status_code=404,
        )

    if not build_universe(session).contains(normalized):
        raise AnalysisRefusal(
            reason="not_in_universe",
            message=(
                f"Mã {normalized} không còn trong Universe nên hệ thống không "
                "dựng Analysis mới cho nó."
            ),
            status_code=422,
        )

    return produce_analysis(
        session,
        normalized,
        trading_day,
        producer,
        origin=RunOrigin.RETRY,
    )


def sweep_stuck_runs(
    session: Session,
    now: datetime | None = None,
    stuck_minutes: int | None = None,
) -> int:
    """Fail every run left ``producing`` past the window, and say how many.

    A crash or a deploy in the middle of production leaves a run at
    ``producing`` with nothing coming to move it. Without this, that symbol
    shows as in-flight until a person notices — which on a nightly cadence means
    a day — and no retry can start, because a run already producing is one this
    module refuses to duplicate.

    Marked ``failed`` rather than back to ``pending`` so the attempt that died
    still counts. Three attempts that each crashed is a symbol that needs
    looking at, not one that should be retried forever.
    """
    now = now or _now()
    if stuck_minutes is None:
        stuck_minutes = get_settings().analysis_run_stuck_minutes
    cutoff = now - timedelta(minutes=stuck_minutes)

    swept = session.execute(
        update(AnalysisRun)
        .where(
            AnalysisRun.status == RunStatus.PRODUCING.value,
            AnalysisRun.started_at.is_not(None),
            AnalysisRun.started_at < cutoff,
        )
        .values(
            status=RunStatus.FAILED.value,
            finished_at=now,
            error_code=ABANDONED_CODE,
            error_message=(
                f"Lượt dựng Analysis bị gián đoạn quá {stuck_minutes} phút và đã "
                "được thu dọn. Có thể thử lại."
            ),
        )
    ).rowcount
    session.commit()

    if swept:
        logger.warning(
            "Swept %d Analysis Run(s) left producing for more than %d minutes",
            swept,
            stuck_minutes,
        )
    return swept
