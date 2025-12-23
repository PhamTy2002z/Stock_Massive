"""APScheduler setup for scheduled jobs."""
import asyncio
import logging

from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger

from src.core.config import get_settings
from src.stocks.jobs import (
    cleanup_old_data_job,
    collect_daily_ohlcv_job,
    collect_intraday_data_job,
    collect_financial_statements_job,
)

logger = logging.getLogger(__name__)
settings = get_settings()


async def collect_daily_ohlcv_job_async():
    """Async wrapper for sync collect_daily_ohlcv_job (runs in thread pool)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, collect_daily_ohlcv_job)


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

    # Daily OHLCV collection at configured time (default 20:00 Vietnam time)
    # Note: collect_daily_ohlcv_job is sync, use async wrapper
    if settings.daily_ohlcv_enabled:
        await scheduler.add_schedule(
            collect_daily_ohlcv_job_async,
            CronTrigger(
                hour=settings.daily_ohlcv_hour,
                minute=settings.daily_ohlcv_minute,
                timezone="Asia/Ho_Chi_Minh",
            ),
            id="daily-ohlcv-collection",
        )
        logger.info(
            f"Scheduled daily OHLCV collection at "
            f"{settings.daily_ohlcv_hour}:{settings.daily_ohlcv_minute:02d} ICT "
            f"(delay={settings.daily_ohlcv_delay}s, batch={settings.daily_ohlcv_batch_size})"
        )

    # Weekly financial statements collection on Sunday at 02:00 ICT
    if settings.financial_statements_enabled:
        await scheduler.add_schedule(
            collect_financial_statements_job,
            CronTrigger(
                hour=settings.financial_statements_hour,
                minute=settings.financial_statements_minute,
                day_of_week="sun",
                timezone="Asia/Ho_Chi_Minh",
            ),
            id="collect-financial-statements",
        )
        logger.info(
            f"Scheduled financial statements collection: Sunday "
            f"{settings.financial_statements_hour:02d}:{settings.financial_statements_minute:02d} ICT"
        )
