"""When the collection cycle runs, and what it leaves behind for an operator.

Everything that decides whether a cycle runs at all lives here: the calendar,
the one-at-a-time rule, and the on-demand override. The Collector itself knows
none of it — it collects when asked.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from src.core.job_status_store import job_store
from src.core.trading_calendar import is_trading_day

from .backfill import BackfillSummary, run_backfill
from .collector import CollectionSummary, run_cycle

logger = logging.getLogger(__name__)

VN_TZ_NAME = "Asia/Ho_Chi_Minh"

# The key this run is recorded under. "Job" is JobStatusStore's word for a
# tracked run, not this system's word for the Collector.
COLLECTOR_JOB_ID = "universe-snapshots"
COLLECTOR_JOB_NAME = "Thu thập Snapshot cho Universe"

BACKFILL_JOB_ID = "universe-backfill"
BACKFILL_JOB_NAME = "Nạp lịch sử cho Universe"


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
