"""When the collection cycle runs, and what it leaves behind for an operator.

Everything that decides whether a cycle runs at all lives here: the calendar,
the one-at-a-time rule, and the on-demand override. The Collector itself knows
none of it — it collects when asked.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from src.core.job_status_store import job_store
from src.core.trading_calendar import is_trading_day

from .backfill import BackfillSummary, run_backfill
from .collector import CollectionSummary, run_cycle
from .warmup import WarmupSummary, run_warmup

logger = logging.getLogger(__name__)

VN_TZ_NAME = "Asia/Ho_Chi_Minh"

# The key this run is recorded under. "Job" is JobStatusStore's word for a
# tracked run, not this system's word for the Collector.
COLLECTOR_JOB_ID = "universe-snapshots"
COLLECTOR_JOB_NAME = "Thu thập Snapshot cho Universe"

BACKFILL_JOB_ID = "universe-backfill"
BACKFILL_JOB_NAME = "Nạp lịch sử cho Universe"

WARMUP_JOB_ID = "universe-warmup"
WARMUP_JOB_NAME = "Nạp cửa sổ tín hiệu gần đây"


@dataclass(frozen=True)
class CycleOutcome:
    """How one attempted cycle ended, including the attempts that never ran.

    ``status`` is carried explicitly rather than inferred from the counts: a
    cycle that failed on its first call and one that ran cleanly over an empty
    Universe both write nothing, and a reader that cannot tell them apart
    reports a broken collector as a healthy one.
    """

    status: Literal["completed", "failed", "skipped"]
    snapshots_written: int = 0
    succeeded: tuple[str, ...] = ()
    failures: tuple[dict, ...] = ()
    missing: tuple[dict, ...] = field(default=())
    error: str | None = None

    @classmethod
    def of(cls, summary: CollectionSummary) -> "CycleOutcome":
        return cls(
            status="completed",
            snapshots_written=summary.snapshots_written,
            succeeded=summary.succeeded,
            failures=tuple(
                {
                    "symbol": failure.symbol,
                    "capability": failure.capability.value,
                    "reason": failure.reason,
                }
                for failure in summary.failures
            ),
            missing=tuple(
                {"symbol": item.symbol, "capability": item.capability.value}
                for item in summary.missing
            ),
        )

    def as_result(self) -> dict:
        """Flatten into the JSON the job record and the API serve it as."""
        return {
            "status": self.status,
            "snapshots_written": self.snapshots_written,
            "succeeded": list(self.succeeded),
            "failures": [dict(failure) for failure in self.failures],
            "missing": [dict(item) for item in self.missing],
            "error": self.error,
        }


def _guarded_run(job_id, job_name, label, work, to_outcome, outcome_type):
    """Run one job at a time, recording how it went and never raising.

    Two runs of the same job writing at once spend the same provider allowance
    twice over for the same Snapshots — and FiinQuant grants one connection.
    Shared by both runs here because the guard, the record and the refusal to
    throw are the same thing said about two different bodies of work.
    """
    if not job_store.try_start_job(job_id, job_name):
        logger.info("A %s is already running; leaving it to finish", label)
        return outcome_type(status="skipped")

    try:
        summary = work()
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        logger.error("The %s failed: %s", label, reason, exc_info=True)
        job_store.fail_job(job_id, reason)
        return outcome_type(status="failed", error=reason)

    outcome = to_outcome(summary)
    job_store.complete_job(job_id, outcome.as_result())
    return outcome


@dataclass(frozen=True)
class BackfillOutcome:
    """How one attempted pass of the history load ended.

    Carries its status for the same reason the cycle does: a pass that failed
    and a pass with nothing left to load both write nothing.
    """

    status: Literal["completed", "failed", "skipped"]
    snapshots_written: int = 0
    completed: tuple[str, ...] = ()
    in_progress: tuple[str, ...] = ()
    pending: tuple[str, ...] = ()
    failed: tuple[dict, ...] = ()
    error: str | None = None

    @classmethod
    def of(cls, summary: BackfillSummary) -> "BackfillOutcome":
        return cls(
            status="completed",
            snapshots_written=summary.snapshots_written,
            completed=summary.completed,
            in_progress=summary.in_progress,
            pending=summary.pending,
            failed=tuple(
                {"symbol": item.symbol, "reason": item.reason}
                for item in summary.failed
            ),
        )

    def as_result(self) -> dict:
        return {
            "status": self.status,
            "snapshots_written": self.snapshots_written,
            "completed": list(self.completed),
            "in_progress": list(self.in_progress),
            "pending": list(self.pending),
            "failed": [dict(item) for item in self.failed],
            "error": self.error,
        }


def run_collection_cycle(
    cycle: Callable[[], CollectionSummary] = run_cycle,
) -> CycleOutcome:
    """Run one cycle, at most one at a time, and record how it went.

    Never raises. A scheduled run that throws takes the scheduler's thread with
    it, and the reason is more use on the run's record than in a traceback
    nobody is watching for.
    """
    return _guarded_run(
        COLLECTOR_JOB_ID,
        COLLECTOR_JOB_NAME,
        "collection cycle",
        cycle,
        CycleOutcome.of,
        CycleOutcome,
    )


async def collect_universe_snapshots(
    force: bool = False,
    cycle: Callable[[], CollectionSummary] = run_cycle,
    today: date | None = None,
) -> CycleOutcome:
    """Run one collection cycle for the Universe, off the event loop.

    The cycle is synchronous — the store is, and FiinQuantX is — and can run
    for minutes. On the loop it would stop the API answering anything at all
    for that whole window, so it goes to a thread.

    A closed exchange is not worth a cycle, but an on-demand run ignores the
    calendar: filling a gap after a bad day is what it is for, and the day it
    is asked for is rarely the day the data is missing from.
    """
    from zoneinfo import ZoneInfo

    day = today or datetime.now(ZoneInfo(VN_TZ_NAME)).date()
    if not force and not is_trading_day(day):
        logger.info("Skipping the collection cycle: %s is not a trading day", day)
        return CycleOutcome(status="skipped")

    return await asyncio.to_thread(run_collection_cycle, cycle)


def run_history_backfill(
    load: Callable[[], BackfillSummary] = run_backfill,
) -> BackfillOutcome:
    """Run one pass of the history load, at most one at a time.

    Never raises, for the same reason the cycle does not: a scheduled run that
    throws takes the scheduler's thread with it.
    """
    return _guarded_run(
        BACKFILL_JOB_ID,
        BACKFILL_JOB_NAME,
        "history load",
        load,
        BackfillOutcome.of,
        BackfillOutcome,
    )


async def backfill_universe_history(
    load: Callable[[], BackfillSummary] = run_backfill,
) -> BackfillOutcome:
    """Run one pass of the history load off the event loop.

    No trading-day gate: this loads sessions that closed years ago, and the day
    it runs on says nothing about whether they exist.
    """
    return await asyncio.to_thread(run_history_backfill, load)


def _stored_trading_day() -> date | None:
    """The newest Trading Day the store holds, opening a session of its own."""
    from src.core.database import get_sync_db

    from .trading_day import latest_trading_day

    with get_sync_db() as session:
        return latest_trading_day(session)


def market_has_advanced_to(
    day: date,
    latest: Callable[[], date | None] = _stored_trading_day,
) -> bool:
    """Whether the store already holds a session for this day.

    Asked of the data rather than of the collection job's record, because the
    two answer different questions. A cycle that ran, succeeded and wrote
    nothing — because FiinQuant had not appended the session yet — records a
    success while the Trading Day has not moved at all. Reading the job record
    would call that done; reading the store sees the gap that is actually there.
    """
    stored = latest()
    return stored is not None and stored >= day


async def catch_up_market_data(
    force: bool = False,
    cycle: Callable[[], CollectionSummary] = run_cycle,
    today: date | None = None,
    latest: Callable[[], date | None] = _stored_trading_day,
) -> CycleOutcome:
    """Collect again late in the evening if the Trading Day never moved.

    The evening cycle runs shortly after the close, and the Main Source appends
    the session that just closed some hours later — so a perfectly healthy cycle
    routinely comes away with yesterday's session. Left alone, that day is never
    collected: the next cycle asks for the session that just closed, not the one
    before it, and the deep Backfill never looks at recent history.

    Runs under the Collector's own guard rather than a guard of its own. It is
    the same body of work spending the same single FiinQuant connection, and two
    of them at once would spend the allowance twice for one set of Snapshots.
    """
    from zoneinfo import ZoneInfo

    day = today or datetime.now(ZoneInfo(VN_TZ_NAME)).date()
    if not force and not is_trading_day(day):
        logger.info("Skipping the market catch-up: %s is not a trading day", day)
        return CycleOutcome(status="skipped")

    if not force and market_has_advanced_to(day, latest):
        logger.info("Skipping the market catch-up: the store already holds %s", day)
        return CycleOutcome(status="skipped")

    return await asyncio.to_thread(run_collection_cycle, cycle)


@dataclass(frozen=True)
class WarmupOutcome:
    """How one attempted Warm-up ended."""

    status: Literal["completed", "failed", "skipped"]
    sessions_written: int = 0
    completed: tuple[str, ...] = ()
    failed: tuple[dict, ...] = ()
    error: str | None = None

    @classmethod
    def of(cls, summary: WarmupSummary) -> "WarmupOutcome":
        return cls(
            status="completed",
            sessions_written=summary.sessions_written,
            completed=summary.completed,
            failed=tuple(
                {"symbol": item.symbol, "reason": item.reason}
                for item in summary.failed
            ),
        )

    def as_result(self) -> dict:
        return {
            "status": self.status,
            "sessions_written": self.sessions_written,
            "completed": list(self.completed),
            "failed": [dict(item) for item in self.failed],
            "error": self.error,
        }


def run_symbol_warmup(
    symbols: Sequence[str],
    warm: Callable[[Sequence[str]], WarmupSummary] = run_warmup,
) -> WarmupOutcome:
    """Warm the named symbols, at most one Warm-up at a time.

    Guarded separately from the collection cycle: a Warm-up reads a window of
    history for a handful of named symbols while a cycle reads one session for
    the whole Universe, so the two are not the same work and blocking one on
    the other would leave a new cohort member waiting a day to become evaluable.
    """
    return _guarded_run(
        WARMUP_JOB_ID,
        WARMUP_JOB_NAME,
        "warm-up",
        lambda: warm(symbols),
        WarmupOutcome.of,
        WarmupOutcome,
    )


async def warm_up_symbols(
    symbols: Sequence[str],
    warm: Callable[[Sequence[str]], WarmupSummary] = run_warmup,
) -> WarmupOutcome:
    """Run one Warm-up off the event loop.

    No trading-day gate: the window it loads is made of sessions that have
    already closed, and the day it is asked for says nothing about them.
    """
    return await asyncio.to_thread(run_symbol_warmup, symbols, warm)
