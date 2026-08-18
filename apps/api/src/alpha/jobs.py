"""Scheduled work Alpha Desk owns.

Two jobs, and they are separate from the libraries they call for the same
reason: the state machine and the dispatcher are things the lanes invoke, while
these two are the things nobody invokes — they have to happen on a clock or not
at all.

*The sweep* stops a dead Analysis Run from holding a symbol.

*The drain* turns a captured cohort into published Analyses. It is one worker by
construction — one scheduled job in one process — and the claim it makes is what
holds even if that stops being true.

Both go to a thread. The store is synchronous and this runs in the same process
as the API, so a query on the loop would stall every in-flight request for the
length of it; the drain additionally *must* be off the loop, because the producer
runs its generation in an event loop of its own.
"""

import asyncio
import logging

from src.core.config import get_settings
from src.core.database import get_sync_db

from .analysis_run import sweep_stuck_runs
from .dispatcher import drain_queue
from .production import analysis_producer

logger = logging.getLogger(__name__)


async def sweep_stuck_analysis_runs() -> int:
    """Clear runs abandoned mid-production, off the event loop."""

    def sweep() -> int:
        with get_sync_db() as session:
            return sweep_stuck_runs(session)

    return await asyncio.to_thread(sweep)


async def drain_analysis_queue() -> dict:
    """Produce what the evening's cohort is still owed.

    Never raises. A tick that could not drain must not take the scheduler down
    with it, and the runs it did not reach are still in the table for the next
    one — the queue *is* the table, so there is no progress to lose.

    Silent while Alpha Desk is off. The drain is the one job in this package that
    spends money, so it is gated on the same flag that admits any provider call
    at all rather than on one of its own.
    """
    settings = get_settings()
    if not settings.alpha_desk_enabled:
        return {"skipped": "alpha_desk_disabled"}

    def drain() -> dict:
        # One producer per tick, so the evening's cross-sectional rankings are
        # measured once for everything this tick drains rather than once per
        # symbol.
        producer = analysis_producer()
        with get_sync_db() as session:
            return drain_queue(
                session,
                producer,
                limit=settings.analysis_dispatch_batch_size,
            ).as_result()

    try:
        report = await asyncio.to_thread(drain)
    except Exception as exc:  # noqa: BLE001 — a tick must not kill the scheduler
        logger.error("Draining the Analysis queue failed: %s", exc, exc_info=True)
        return {"error": str(exc)}

    if report["claimed"]:
        logger.info("Drained the Analysis queue: %s", report)
    return report
