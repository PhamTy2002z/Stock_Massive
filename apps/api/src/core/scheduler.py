"""APScheduler setup — trimmed to the chat-lane pivot.

The market-data collectors (intraday, corporate action, nightly cohort,
sector historical, market cleanup) were all removed with the market surfaces.
Nothing this file used to schedule survives, so it now sets up no cron entries
by default.

The seam is kept because ``main.py`` still calls ``setup_scheduler`` inside its
lifespan block, and the harness may add its own scheduled jobs (context
compaction, memory GC, budget accounting) once the harness-first roadmap lands.
"""
from __future__ import annotations

import logging

from apscheduler import AsyncScheduler

logger = logging.getLogger(__name__)


async def setup_scheduler(scheduler: AsyncScheduler) -> None:
    """Register the empty schedule set.

    Kept so ``main.py``'s lifespan block does not have to change every time a
    scheduled job is added or removed. When the harness introduces its own
    periodic work, add it here.
    """
    logger.info("Scheduler configured with 0 jobs (post-rip-out baseline)")


async def run_startup_jobs() -> None:
    """No startup jobs after the collector rip. Kept as a no-op seam."""
    return None


async def run_startup_jobs_with_delay() -> None:
    """No delayed startup jobs. Kept as a no-op seam."""
    return None
