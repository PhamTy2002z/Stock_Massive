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


def run_collection_cycle(
    cycle: Callable[[], CollectionSummary] = run_cycle,
) -> CycleOutcome:
    """Run one cycle, at most one at a time, and record how it went.

    Never raises. A scheduled run that throws takes the scheduler's thread with
    it, and the reason is more use on the run's record than in a traceback
    nobody is watching for.
    """
    if not job_store.try_start_job(COLLECTOR_JOB_ID, COLLECTOR_JOB_NAME):
        # Two cycles writing at once spend the same provider allowance twice
        # over for the same Snapshots — and FiinQuant grants one connection.
        logger.info("A collection cycle is already running; leaving it to finish")
        return CycleOutcome(status="skipped")

    try:
        summary = cycle()
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        logger.error("Collection cycle failed: %s", reason, exc_info=True)
        job_store.fail_job(COLLECTOR_JOB_ID, reason)
        return CycleOutcome(status="failed", error=reason)

    outcome = CycleOutcome.of(summary)
    job_store.complete_job(COLLECTOR_JOB_ID, outcome.as_result())
    return outcome


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
    pass_: Callable[[], BackfillSummary] = run_backfill,
) -> dict:
    """Run one pass of the history load, at most one at a time.

    Never raises, for the same reason the cycle does not: a scheduled run that
    throws takes the scheduler's thread with it.
    """
    if not job_store.try_start_job(BACKFILL_JOB_ID, BACKFILL_JOB_NAME):
        logger.info("A history load is already running; leaving it to finish")
        return {"status": "skipped"}

    try:
        summary = pass_()
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        logger.error("History load failed: %s", reason, exc_info=True)
        job_store.fail_job(BACKFILL_JOB_ID, reason)
        return {"status": "failed", "error": reason}

    result = {
        "status": "completed",
        "snapshots_written": summary.snapshots_written,
        "completed": list(summary.completed),
        "in_progress": list(summary.in_progress),
        "failed": [
            {"symbol": item.symbol, "reason": item.reason} for item in summary.failed
        ],
    }
    job_store.complete_job(BACKFILL_JOB_ID, result)
    return result


async def backfill_universe_history(
    pass_: Callable[[], BackfillSummary] = run_backfill,
) -> dict:
    """Run one pass of the history load off the event loop.

    No trading-day gate: this loads sessions that closed years ago, and the day
    it runs on says nothing about whether they exist.
    """
    return await asyncio.to_thread(run_history_backfill, pass_)
