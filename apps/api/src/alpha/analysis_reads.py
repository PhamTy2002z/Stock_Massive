"""Reading Analyses: the newest per symbol, one by pair, and recent history.

**Serving the newest needs no mechanism.** A row in ``analysis`` existing means
it is complete — in-flight state lives only in ``analysis_run`` — so the newest
Trading Day wins and there is never a half-written row to filter out. That is
the payoff of the split, and this module is where it shows: not one query here
carries a status filter, and adding one later would be the first sign that the
invariant had been given up somewhere else.

**Every read is by ``(symbol, trading_day)``.** ``analysis``'s unique key
excludes ``schema_version`` deliberately, so a reader never chooses between two
rows for one pair; it handles several template versions across days instead,
which is what the column is for. Nothing here groups or filters by it.

**History is bounded at ninety sessions**, and the bound travels in the response
rather than being implied by the length of a list — a list of eighty-one is
otherwise indistinguishable from a window that stopped early. Anything deeper is
the agent's ``get_analysis(symbol, date)`` later; Analyses themselves are kept
indefinitely, so ninety is a browsing depth and never a retention policy.

The bound counts *this symbol's* Analyses rather than the last ninety Trading
Days the market held. The two coincide for a symbol analysed every session, and
where they differ — one added mid-history, one the pipeline missed for a week —
counting rows shows the reader everything the store actually has instead of a
window that is mostly gaps.

Nothing produces an Analysis until the pipeline milestone. Everything here is
therefore exercised against directly inserted rows, and the tests say so rather
than implying a producer exists.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.trading_day import latest_trading_day

from .analysis_run import MAX_ATTEMPTS_PER_SESSION, RunStatus
from .models import Analysis, AnalysisRun

logger = logging.getLogger(__name__)

# How far back the rail browses. Not a retention policy: Analyses are kept
# indefinitely and the agent reaches deeper by exact date.
HISTORY_DEPTH_SESSIONS = 90


class AnalysisState(str, Enum):
    """What the rail shows for one watched symbol against one session.

    Five values, and only one of them is a fact about ``analysis``: `ready`
    means the row for that session exists. The three in the middle come from
    ``analysis_run``, and `unsupported` is a question about the Universe that
    this module never asks — the Watchlist owns it, and it is listed here only
    because a caller assembling the rail has to place it among the other four.
    """

    READY = "ready"
    PENDING = "pending"
    PRODUCING = "producing"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class AnalysisSummary:
    """One Analysis as the rail lists it: everything but the payload.

    ``schema_version`` rides along because a reader may meet several across
    days and has to be able to tell which template it is looking at. It is not
    part of the identity of the row and nothing selects on it.
    """

    symbol: str
    trading_day: date
    verdict: str
    schema_version: int
    created_at: datetime


@dataclass(frozen=True)
class RunFailure:
    """Why the session's production stopped, as the rail renders it.

    Two fields, for the reason every Alpha Desk refusal has two: the code is
    branched on and the sentence is read. ``exhausted`` is carried so the
    interface can drop the retry action rather than offer one more press that
    does nothing.
    """

    code: str | None
    message: str | None
    attempts: int
    exhausted: bool


def _summary(row: Analysis) -> AnalysisSummary:
    return AnalysisSummary(
        symbol=row.symbol,
        trading_day=row.trading_day,
        verdict=row.verdict,
        schema_version=row.schema_version,
        created_at=row.created_at,
    )


def latest_analyses(
    session: Session,
    symbols: tuple[str, ...],
) -> dict[str, AnalysisSummary]:
    """The newest Analysis for each symbol, keyed by symbol.

    One ``DISTINCT ON`` rather than a query per symbol: the rail asks this for
    every symbol at once, and the index on ``(symbol, trading_day DESC)`` makes
    the answer the first row of each group.

    A symbol with nothing is absent from the mapping rather than mapped to None.
    "Never analysed" and "analysed, verdict null" are different states and the
    shape should not let a caller confuse them.
    """
    if not symbols:
        return {}

    rows = session.execute(
        select(Analysis)
        .where(Analysis.symbol.in_(symbols))
        .distinct(Analysis.symbol)
        .order_by(Analysis.symbol, Analysis.trading_day.desc())
    ).scalars()
    return {row.symbol: _summary(row) for row in rows}


def analysis_for(session: Session, symbol: str, trading_day: date) -> Analysis | None:
    """The Analysis for exactly this pair, payload included, or None.

    No status filter, and there cannot be more than one: the unique key is the
    pair, and a row existing means it is complete.
    """
    return session.execute(
        select(Analysis).where(
            Analysis.symbol == symbol,
            Analysis.trading_day == trading_day,
        )
    ).scalar_one_or_none()


@dataclass(frozen=True)
class AnalysisHistory:
    """A bounded window of one symbol's Analyses, newest first.

    ``depth`` and ``older_exist`` are both here because the length of ``entries``
    answers neither question. Eighty-one rows may be everything the store holds
    or the first eighty-one of three hundred, and a reader that cannot tell will
    render an empty scroll at the boundary instead of an edge.
    """

    symbol: str
    entries: tuple[AnalysisSummary, ...]
    depth: int
    older_exist: bool


def recent_analyses(
    session: Session,
    symbol: str,
    depth: int = HISTORY_DEPTH_SESSIONS,
) -> AnalysisHistory:
    """One symbol's last ``depth`` Analyses, and whether there are more.

    Reads one row past the bound to answer ``older_exist``, which is cheaper
    than a second count and cannot disagree with the page it describes.
    """
    rows = list(
        session.execute(
            select(Analysis)
            .where(Analysis.symbol == symbol)
            .order_by(Analysis.trading_day.desc())
            .limit(depth + 1)
        ).scalars()
    )
    return AnalysisHistory(
        symbol=symbol,
        entries=tuple(_summary(row) for row in rows[:depth]),
        depth=depth,
        older_exist=len(rows) > depth,
    )


def _runs_for(
    session: Session,
    symbols: tuple[str, ...],
    trading_day: date,
) -> dict[str, AnalysisRun]:
    if not symbols:
        return {}

    rows = session.execute(
        select(AnalysisRun).where(
            AnalysisRun.symbol.in_(symbols),
            AnalysisRun.trading_day == trading_day,
        )
    ).scalars()
    return {row.symbol: row for row in rows}


def _state_of(
    symbol: str,
    trading_day: date,
    latest: AnalysisSummary | None,
    run: AnalysisRun | None,
    max_attempts: int,
) -> tuple[AnalysisState, RunFailure | None]:
    """One symbol's state for one session, and why if it failed.

    ``ready`` is read off the Analysis rather than off the run, which is the
    invariant expressed as a query: the artifact is the thing the user reads, so
    its existence is what the interface reports. A run claiming `ready` without
    it is the one state the design says cannot happen, and it is logged rather
    than rendered — inventing a display for it would hide the bug.
    """
    if latest is not None and latest.trading_day == trading_day:
        return AnalysisState.READY, None

    if run is None:
        # The session has a Snapshot and this symbol's turn has not come. Not a
        # synonym for absent: without it a symbol that failed would look exactly
        # like one not yet reached.
        return AnalysisState.PENDING, None

    if run.status == RunStatus.READY.value:
        logger.error(
            "Run for %s %s is ready with no Analysis row; showing it as pending",
            symbol,
            trading_day,
        )
        return AnalysisState.PENDING, None

    if run.status == RunStatus.PRODUCING.value:
        return AnalysisState.PRODUCING, None

    attempts = run.attempts or 0
    failure = (
        RunFailure(
            code=run.error_code,
            message=run.error_message,
            attempts=attempts,
            exhausted=attempts >= max_attempts,
        )
        if run.error_code is not None
        else None
    )

    if run.status == RunStatus.FAILED.value:
        return AnalysisState.FAILED, failure

    # A queued run that has already failed once keeps its reason. The state is
    # `pending` — it really is waiting its turn — but a symbol waiting with no
    # account of why it is waiting is what a retry would otherwise leave behind
    # for as long as the queue takes to reach it.
    return AnalysisState.PENDING, failure


@dataclass(frozen=True)
class SymbolReading:
    """Everything the rail knows about one watched symbol.

    ``latest`` is the newest Analysis that exists, whatever session it is for,
    which is what makes `failed` never render empty: the cell shows the last
    thing there was to read alongside the label naming the session that is
    missing.
    """

    state: AnalysisState
    latest: AnalysisSummary | None
    failure: RunFailure | None


def read_symbols(
    session: Session,
    symbols: tuple[str, ...],
    trading_day: date | None,
    max_attempts: int,
) -> dict[str, SymbolReading]:
    """The Analysis half of the rail, for every watched symbol at once.

    ``trading_day`` is the session the rail is labelled with — the latest one
    the store holds a Snapshot for. None is a real answer on a fresh
    environment, and every symbol is then `pending`: nothing has closed, so
    nothing is late.

    The Universe half is not here. A caller overlays `unsupported` from the
    Watchlist, because whether a symbol is still analysed is a question about
    the Universe and this module has no business answering it twice.
    """
    latest = latest_analyses(session, symbols)
    runs = _runs_for(session, symbols, trading_day) if trading_day is not None else {}

    readings: dict[str, SymbolReading] = {}
    for symbol in symbols:
        newest = latest.get(symbol)
        if trading_day is None:
            readings[symbol] = SymbolReading(AnalysisState.PENDING, newest, None)
            continue
        state, failure = _state_of(
            symbol, trading_day, newest, runs.get(symbol), max_attempts
        )
        readings[symbol] = SymbolReading(state, newest, failure)
    return readings


@dataclass(frozen=True)
class RailReading:
    """The Analysis half of one user's rail, against one dated session."""

    trading_day: date | None
    symbols: dict[str, SymbolReading]


def read_rail(session: Session, symbols: tuple[str, ...]) -> RailReading:
    """Resolve the session and read every watched symbol against it, together.

    One function, and one read, so the Trading Day and the states computed
    against it cannot come from two moments. A rail labelled with one session
    while its cells were computed against another is wrong in the one place the
    user checks first.

    Which symbols to read is the caller's question, answered before this and
    passed in: the Watchlist is one user's membership list, and the Universe
    rule that turns a row `unsupported` belongs to the module that owns it. A
    symbol added between the two reads is simply not in ``symbols``, so it
    cannot appear here with a state nobody computed.
    """
    trading_day = latest_trading_day(session)
    return RailReading(
        trading_day=trading_day,
        symbols=read_symbols(session, symbols, trading_day, MAX_ATTEMPTS_PER_SESSION),
    )


def is_unread(latest: AnalysisSummary | None, last_seen: date | None) -> bool:
    """Whether this symbol has an Analysis the user has not opened.

    Derived from the stored last-seen date on every read rather than kept as a
    flag, so there is exactly one write path — opening an Analysis — and no
    second thing to fall out of step with it.
    """
    if latest is None:
        return False
    return last_seen is None or last_seen < latest.trading_day
