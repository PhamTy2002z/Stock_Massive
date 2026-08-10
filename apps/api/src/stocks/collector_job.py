"""Running the collection cycle as a job, scheduled or on demand.

The cycle itself knows nothing about jobs. This is the layer that decides one
run at a time, records what happened where an operator can read it, and turns
a failure into a recorded reason rather than an exception nobody catches.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from src.core.job_status_store import job_store

from .collector import CollectionSummary, run_cycle

logger = logging.getLogger(__name__)

COLLECTOR_JOB_ID = "universe-snapshots"
COLLECTOR_JOB_NAME = "Thu thập Snapshot cho Universe"


def run_collection_cycle(
    cycle: Callable[[], CollectionSummary] = run_cycle,
) -> dict:
    """Run one cycle, at most one at a time, and record how it went.

    Never raises. A scheduled job that throws takes the scheduler's thread with
    it, and the reason is more use on the run's record than in a traceback
    nobody is watching for.
    """
    if not job_store.try_start_job(COLLECTOR_JOB_ID, COLLECTOR_JOB_NAME):
        # Two cycles writing at once spend the same provider allowance twice
        # over for the same Snapshots — and FiinQuant grants one connection.
        logger.info("A collection cycle is already running; leaving it to finish")
        return _empty_result(skipped=True)

    try:
        summary = cycle()
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        logger.error("Collection cycle failed: %s", reason, exc_info=True)
        job_store.fail_job(COLLECTOR_JOB_ID, reason)
        return _empty_result(skipped=False)

    result = as_result(summary)
    job_store.complete_job(COLLECTOR_JOB_ID, result)
    return result


def as_result(summary: CollectionSummary) -> dict:
    """Flatten a summary into the JSON an operator reads it as."""
    return {
        "skipped": False,
        "snapshots_written": summary.snapshots_written,
        "succeeded": list(summary.succeeded),
        "failures": [
            {
                "symbol": failure.symbol,
                "capability": failure.capability.value,
                "reason": failure.reason,
            }
            for failure in summary.failures
        ],
        "missing": [
            {"symbol": item.symbol, "capability": item.capability.value}
            for item in summary.missing
        ],
    }


def _empty_result(skipped: bool) -> dict:
    return {
        "skipped": skipped,
        "snapshots_written": 0,
        "succeeded": [],
        "failures": [],
        "missing": [],
    }
