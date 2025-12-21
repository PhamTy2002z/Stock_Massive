"""APScheduler setup for scheduled jobs."""
import logging

from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger

from src.core.config import get_settings
from src.stocks.jobs import cleanup_old_data_job, collect_intraday_data_job, run_market_context_eod_job

logger = logging.getLogger(__name__)
settings = get_settings()


async def setup_scheduler(scheduler: AsyncScheduler) -> None:
    """Configure scheduled jobs.

    Args:
        scheduler: APScheduler AsyncScheduler instance
    """
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled by config")
        return

    # Daily intraday collection at configured time (default 15:30 Vietnam time)
    await scheduler.add_schedule(
        collect_intraday_data_job,
        CronTrigger(
            hour=settings.intraday_collect_hour,
            minute=settings.intraday_collect_minute,
            timezone="Asia/Ho_Chi_Minh",
        ),
        id="intraday-collection-daily",
    )
    logger.info(
        f"Scheduled intraday collection at "
        f"{settings.intraday_collect_hour}:{settings.intraday_collect_minute:02d} ICT"
    )

    # Daily cleanup at 16:00 Vietnam time (30 min after collection)
    await scheduler.add_schedule(
        cleanup_old_data_job,
        CronTrigger(hour=16, minute=0, timezone="Asia/Ho_Chi_Minh"),
        id="data-cleanup-daily",
    )
    logger.info("Scheduled data cleanup at 16:00 ICT")

    # Market context EOD pipeline at 15:45 Vietnam time (after market close)
    await scheduler.add_schedule(
        run_market_context_eod_job,
        CronTrigger(hour=15, minute=45, timezone="Asia/Ho_Chi_Minh"),
        id="market-context-eod-daily",
    )
    logger.info("Scheduled market context EOD pipeline at 15:45 ICT")
