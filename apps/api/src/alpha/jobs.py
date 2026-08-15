"""Scheduled work Alpha Desk owns.

One job for now: the sweep that stops a dead Analysis Run from holding a symbol.
It is separate from the state machine because the machine is a library the
nightly lane, the on-demand lane and a user's retry all call, while this is the
one thing nobody calls — it has to happen on a clock or not at all.
"""

import asyncio
import logging

from src.core.database import get_sync_db

from .analysis_run import sweep_stuck_runs

logger = logging.getLogger(__name__)


async def sweep_stuck_analysis_runs() -> int:
    """Clear runs abandoned mid-production, off the event loop.

    The store is synchronous, and this runs in the same process as the API, so
    the query goes to a thread rather than stalling every in-flight request for
    the length of it.
    """

    def sweep() -> int:
        with get_sync_db() as session:
            return sweep_stuck_runs(session)

    return await asyncio.to_thread(sweep)
