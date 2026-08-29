"""APScheduler setup — trimmed to the chat-lane pivot.

The market-data collectors (intraday, corporate action, nightly cohort,
sector historical, market cleanup) were all removed with the market surfaces.
Nothing this file used to schedule survives.

One job lives here now: **filling the daily spine**. Everything the chat lane
answers is dated by that table — the Trading Day calendar is derived from it —
so a spine nobody feeds is not a stale table, it is a market whose newest
session stops moving while every answer still carries a confident date.

**It is off unless somebody turned it on.** ``scheduler_enabled`` defaults to
true, so a job registered unconditionally here would start calling an external
provider on every machine that brings this stack up, 1,523 requests at a time.
Opting in is a decision someone writes down.

The seam is otherwise unchanged: ``main.py`` calls ``setup_scheduler`` inside its
lifespan block, and the harness may add its own periodic work (context
compaction, memory GC, budget accounting) as the roadmap lands.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from apscheduler import AsyncScheduler, CoalescePolicy
from apscheduler.triggers.cron import CronTrigger

from src.core.config import get_settings
from src.stocks.providers.normalize import VN_TZ

logger = logging.getLogger(__name__)

#: The order the scopes run in, and it is not arbitrary. ``index`` is one call
#: and it is the one that defines the Trading Day calendar, so it goes first and
#: cheaply; ``declared`` is the thirty symbols the chat lane actually serves;
#: ``market`` is the long tail a screener needs. Sequential rather than
#: concurrent: all three write the same table and spend the same provider
#: allowance, so running them together would only divide their own ceiling.
BACKFILL_SCOPES = ("index", "declared", "market")

#: What the job is registered under, so a restart replaces its schedule instead
#: of adding a second one.
BACKFILL_SCHEDULE_ID = "daily-spine-backfill"


async def fill_the_daily_spine() -> None:
    """Run every backfill scope in turn, and say plainly what came of it.

    Off the event loop. ``backfill_daily.run`` is synchronous and spends most of
    its time waiting on a provider; awaiting it inline would stall every request
    this process is serving for as long as the market scope takes.

    Nothing is raised out of here. A scheduled job that raises is a log line
    nobody reads at 16:30, and the spine's own freshness — reported at the end
    of every scope — is the signal that actually matters. What this must never do
    is take the API process down with it.
    """
    from src.stocks import backfill_daily

    for scope in BACKFILL_SCOPES:
        try:
            report = await asyncio.to_thread(backfill_daily.run, scope=scope)
        except Exception:
            # Deliberately broad: one scope failing must not cost the scopes
            # after it, and the market scope is the most likely to fail and the
            # least important of the three.
            logger.exception("Daily spine backfill failed for scope %s", scope)
            continue
        logger.info(
            "Daily spine backfill scope=%s attempted=%d skipped=%d rows=%d "
            "failed=%d",
            scope,
            report.attempted,
            report.skipped,
            report.rows_written,
            len(report.failures),
        )
        if report.failures:
            logger.warning(
                "Scope %s could not fill: %s",
                scope,
                ", ".join(report.failures),
            )


async def setup_scheduler(scheduler: AsyncScheduler) -> None:
    """Register the schedule set this deployment asked for.

    Kept so ``main.py``'s lifespan block does not have to change every time a
    scheduled job is added or removed.
    """
    settings = get_settings()
    if not settings.backfill_daily_scheduled:
        logger.info(
            "Scheduler configured with 0 jobs; daily spine backfill is not "
            "scheduled (BACKFILL_DAILY_SCHEDULED is off). Fill it by hand with "
            "`make backfill-daily SCOPE=index|declared|market`."
        )
        return

    await scheduler.add_schedule(
        fill_the_daily_spine,
        CronTrigger(
            hour=settings.backfill_daily_hour,
            minute=settings.backfill_daily_minute,
            timezone=VN_TZ,
        ),
        id=BACKFILL_SCHEDULE_ID,
        # A run missed while the process was down is not made up for by running
        # it twice, and two of them at once would spend the allowance twice over.
        coalesce=CoalescePolicy.latest,
        # A restart at 16:35 should still fill today rather than wait a day: the
        # spine is dated by session, so a late run writes the same rows.
        misfire_grace_time=timedelta(hours=2),
    )
    logger.info(
        "Scheduler configured with 1 job: daily spine backfill at %02d:%02d %s, "
        "scopes %s",
        settings.backfill_daily_hour,
        settings.backfill_daily_minute,
        VN_TZ,
        " → ".join(BACKFILL_SCOPES),
    )


async def run_startup_jobs() -> None:
    """No startup jobs after the collector rip. Kept as a no-op seam."""
    return None


async def run_startup_jobs_with_delay() -> None:
    """No delayed startup jobs. Kept as a no-op seam."""
    return None
