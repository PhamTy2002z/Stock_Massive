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
    collect_sector_historical_job,
)

logger = logging.getLogger(__name__)
settings = get_settings()
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


async def collect_daily_ohlcv_job_async():
    """Async wrapper for sync collect_daily_ohlcv_job (runs in thread pool)."""
    logger.info("Starting daily OHLCV collection job (async wrapper)")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, collect_daily_ohlcv_job)
    logger.info(f"Daily OHLCV collection completed: {result}")
    return result


async def collect_intraday_job_wrapper():
    """Wrapper for intraday job with logging."""
    logger.info("=== SCHEDULED JOB TRIGGERED: Intraday Collection ===")
    try:
        result = await collect_intraday_data_job()
        logger.info(f"Intraday collection completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Intraday collection failed: {e}", exc_info=True)
        raise


async def cleanup_job_wrapper():
    """Wrapper for cleanup job with logging."""
    logger.info("=== SCHEDULED JOB TRIGGERED: Data Cleanup ===")
    try:
        result = await cleanup_old_data_job()
        logger.info(f"Data cleanup completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Data cleanup failed: {e}", exc_info=True)
        raise


async def ohlcv_job_wrapper():
    """Wrapper for OHLCV job with logging."""
    logger.info("=== SCHEDULED JOB TRIGGERED: Daily OHLCV Collection ===")
    try:
        result = await collect_daily_ohlcv_job_async()
        logger.info(f"Daily OHLCV completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Daily OHLCV failed: {e}", exc_info=True)
        raise


async def financial_statements_job_wrapper():
    """Wrapper for financial statements job with logging."""
    logger.info("=== SCHEDULED JOB TRIGGERED: Financial Statements Collection ===")
    try:
        result = await collect_financial_statements_job()
        logger.info(f"Financial statements collection completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Financial statements collection failed: {e}", exc_info=True)
        raise


async def sector_historical_job_wrapper():
    """Async wrapper for sector historical job (runs in thread pool)."""
    logger.info("=== SCHEDULED JOB TRIGGERED: Sector Historical Performance ===")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, collect_sector_historical_job)
        logger.info(f"Sector historical complete: {result}")
        return result
    except Exception as e:
        logger.error(f"Sector historical failed: {e}", exc_info=True)
        raise


async def setup_scheduler(scheduler: AsyncScheduler) -> None:
    """Configure scheduled jobs.

    Args:
        scheduler: APScheduler AsyncScheduler instance
    """
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled by config")
        return

    logger.info("=== Setting up scheduled jobs ===")

    # Daily intraday collection at configured time (default 15:30 Vietnam time)
    await scheduler.add_schedule(
        collect_intraday_job_wrapper,
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
        cleanup_job_wrapper,
        CronTrigger(hour=16, minute=0, timezone="Asia/Ho_Chi_Minh"),
        id="data-cleanup-daily",
    )
    logger.info("Scheduled data cleanup at 16:00 ICT")

    # Daily OHLCV collection at configured time (default 16:00 Vietnam time)
    if settings.daily_ohlcv_enabled:
        await scheduler.add_schedule(
            ohlcv_job_wrapper,
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
            financial_statements_job_wrapper,
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

    # Daily sector historical performance at 15:45 ICT (after sector-performance at 15:30)
    if settings.sector_historical_enabled:
        await scheduler.add_schedule(
            sector_historical_job_wrapper,
            CronTrigger(
                hour=settings.sector_historical_hour,
                minute=settings.sector_historical_minute,
                timezone="Asia/Ho_Chi_Minh",
            ),
            id="sector-historical-daily",
        )
        logger.info(
            f"Scheduled sector historical at "
            f"{settings.sector_historical_hour}:{settings.sector_historical_minute:02d} ICT"
        )

    logger.info("=== Scheduler setup complete ===")

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

    # Run if less than 500 symbols have data (incomplete collection)
    return count < 500


def _should_run_sector_historical_job() -> bool:
    """Check if sector historical job should run on startup.

    Conditions:
    - Job is enabled
    - Current time is after scheduled time (15:45 ICT)
    - Cache is empty (no data cached yet)
    """
    from src.stocks.analytics.sector_historical_service import sector_historical_cache

    if not settings.sector_historical_enabled:
        return False

    if not _time_passed_today(settings.sector_historical_hour, settings.sector_historical_minute):
        return False

    # Check if any period has cached data
    for period in ["1W", "2W", "1M"]:
        if sector_historical_cache.get(period) is not None:
            return False  # Cache exists, no need to run

    return True


async def run_startup_jobs_with_delay() -> None:
    """Run startup jobs after a short delay to allow server to fully start."""
    # Wait for server to be ready and accepting requests
    await asyncio.sleep(5)
    logger.info("=== Running startup job checks ===")
    await run_startup_jobs()


async def run_startup_jobs() -> None:
    """Run missed scheduled jobs on startup.

    Checks each job's conditions and runs if missed.
    """
    logger.info("Checking for missed scheduled jobs...")
    now_vn = datetime.now(VN_TZ)
    logger.info(f"Current time (Vietnam): {now_vn}")

    # Check and run intraday collection
    should_run_intraday = await _should_run_intraday_job()
    logger.info(f"Should run intraday job: {should_run_intraday}")
    if should_run_intraday:
        logger.info("Running missed intraday collection job")
        try:
            await collect_intraday_data_job()
            logger.info("Startup intraday job completed successfully")
        except Exception as e:
            logger.error(f"Startup intraday job failed: {e}", exc_info=True)

    # Check and run cleanup
    should_run_cleanup = await _should_run_cleanup_job()
    logger.info(f"Should run cleanup job: {should_run_cleanup}")
    if should_run_cleanup:
        logger.info("Running missed cleanup job")
        try:
            await cleanup_old_data_job()
            logger.info("Startup cleanup job completed successfully")
        except Exception as e:
            logger.error(f"Startup cleanup job failed: {e}", exc_info=True)

    # Check and run daily OHLCV collection
    should_run_ohlcv = await _should_run_ohlcv_job()
    logger.info(f"Should run OHLCV job: {should_run_ohlcv}")
    if should_run_ohlcv:
        logger.info("Running missed daily OHLCV collection job")
        try:
            await collect_daily_ohlcv_job_async()
            logger.info("Startup OHLCV job completed successfully")
        except Exception as e:
            logger.error(f"Startup OHLCV job failed: {e}", exc_info=True)

    # Check and run sector historical job
    should_run_sector_hist = _should_run_sector_historical_job()
    logger.info(f"Should run sector historical job: {should_run_sector_hist}")
    if should_run_sector_hist:
        logger.info("Running missed sector historical job")
        try:
            await sector_historical_job_wrapper()
            logger.info("Startup sector historical job completed successfully")
        except Exception as e:
            logger.error(f"Startup sector historical job failed: {e}", exc_info=True)

    logger.info("=== Startup job check complete ===")
