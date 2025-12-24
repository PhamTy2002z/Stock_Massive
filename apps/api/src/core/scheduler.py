"""APScheduler setup for scheduled jobs."""
import asyncio
import logging
from datetime import datetime, date

from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from src.core.config import get_settings
from src.stocks.jobs import (
    cleanup_old_data_job,
    collect_daily_ohlcv_job,
    collect_intraday_data_job,
    collect_financial_statements_job,
)

logger = logging.getLogger(__name__)
settings = get_settings()
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


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

    # Run startup checks for missed jobs in background (non-blocking)
    # This allows the server to start accepting requests immediately
    asyncio.create_task(run_startup_jobs_with_delay())


def _is_trading_day(d: date) -> bool:
    """Check if date is a trading day (Mon-Fri, excluding holidays)."""
    # Simple check: weekday only (0=Mon, 4=Fri)
    return d.weekday() < 5


def _time_passed_today(hour: int, minute: int) -> bool:
    """Check if specified time has passed today in Vietnam timezone."""
    now = datetime.now(VN_TZ)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return now >= target


async def _should_run_intraday_job() -> bool:
    """Check if intraday job should run on startup.

    Conditions:
    - Today is a trading day
    - Current time is after scheduled time (15:30)
    - No intraday data exists for today
    """
    from src.core.database import async_session_factory
    from src.stocks.models import StockIntradayBar
    from sqlalchemy import select, func

    today = date.today()

    if not _is_trading_day(today):
        return False

    if not _time_passed_today(settings.intraday_collect_hour, settings.intraday_collect_minute):
        return False

    # Check if data exists for today
    async with async_session_factory() as db:
        result = await db.execute(
            select(func.count()).select_from(StockIntradayBar).where(
                func.date(StockIntradayBar.bar_time) == today
            )
        )
        count = result.scalar()

    return count == 0


async def _should_run_cleanup_job() -> bool:
    """Check if cleanup job should run on startup.

    Conditions:
    - Current time is after 16:00
    - Always run cleanup if time passed (idempotent operation)
    """
    return _time_passed_today(16, 0)


async def _should_run_ohlcv_job() -> bool:
    """Check if daily OHLCV job should run on startup.

    Conditions:
    - Job is enabled
    - Today is a trading day
    - Current time is after scheduled time (17:00)
    - No OHLCV data exists for today
    """
    from src.core.database import async_session_factory
    from src.stocks.models import StockDailyOHLCV
    from sqlalchemy import select, func

    if not settings.daily_ohlcv_enabled:
        return False

    today = date.today()

    if not _is_trading_day(today):
        return False

    if not _time_passed_today(settings.daily_ohlcv_hour, settings.daily_ohlcv_minute):
        return False

    # Check if data exists for today
    async with async_session_factory() as db:
        result = await db.execute(
            select(func.count()).select_from(StockDailyOHLCV).where(
                StockDailyOHLCV.trade_date == today
            )
        )
        count = result.scalar()

    # Run if less than 100 symbols have data (incomplete collection)
    return count < 100


async def run_startup_jobs_with_delay() -> None:
    """Run startup jobs after a short delay to allow server to fully start."""
    # Wait for server to be ready and accepting requests
    await asyncio.sleep(5)
    await run_startup_jobs()


async def run_startup_jobs() -> None:
    """Run missed scheduled jobs on startup.

    Checks each job's conditions and runs if missed.
    """
    logger.info("Checking for missed scheduled jobs...")

    # Check and run intraday collection
    if await _should_run_intraday_job():
        logger.info("Running missed intraday collection job")
        try:
            await collect_intraday_data_job()
        except Exception as e:
            logger.error(f"Startup intraday job failed: {e}")

    # Check and run cleanup
    if await _should_run_cleanup_job():
        logger.info("Running missed cleanup job")
        try:
            await cleanup_old_data_job()
        except Exception as e:
            logger.error(f"Startup cleanup job failed: {e}")

    # Check and run daily OHLCV collection
    if await _should_run_ohlcv_job():
        logger.info("Running missed daily OHLCV collection job")
        try:
            await collect_daily_ohlcv_job_async()
        except Exception as e:
            logger.error(f"Startup OHLCV job failed: {e}")

    logger.info("Startup job check complete")
