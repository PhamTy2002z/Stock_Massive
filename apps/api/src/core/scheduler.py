"""APScheduler setup for scheduled jobs."""
import asyncio
import logging
from datetime import datetime, date

from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from zoneinfo import ZoneInfo

from src.alpha.jobs import sweep_stuck_analysis_runs
from src.core.config import get_settings
from src.core.trading_calendar import is_trading_day
from src.stocks.collector_schedule import (
    backfill_universe_history,
    catch_up_market_data,
    census_market_profits,
    collect_universe_snapshots,
    load_corporate_actions,
    load_market_index,
    retry_census_gaps,
)
from src.stocks.jobs import (
    cleanup_old_data_job,
    collect_intraday_data_job,
    collect_sector_historical_job,
)

logger = logging.getLogger(__name__)
settings = get_settings()
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def vn_cron(**fields) -> CronTrigger:
    """Build a cron trigger in Vietnam time, anchored to Vietnam time.

    ``start_time`` is passed explicitly, and that is the whole point of this
    function. APScheduler 4 alpha defaults it from the host's local clock. The
    API container runs in UTC, and ``CronTrigger`` matches the cron fields
    against those wall-clock digits without first converting the default start
    to its configured timezone. Vietnam runs seven hours ahead of UTC, so a
    trigger registered at 22:31 ICT is anchored at 15:31 and its next fire is
    computed as 17:00 *today* — an instant five hours in the past, which
    APScheduler runs immediately as a misfire.

    The effect is that every restart is also an unscheduled run of every job
    whose time falls in the seven hours behind it, all at once. That is worse
    than an early run: the collection cycle and the history backfill are 45
    minutes apart on purpose, because the process has one worker and the free
    FiinQuant tier grants one concurrent connection, so firing them together is
    exactly the contention the stagger exists to prevent.

    Every schedule in this module goes through here. A ``CronTrigger`` built
    directly would look correct and reintroduce the bug.
    """
    return CronTrigger(timezone=VN_TZ, start_time=datetime.now(VN_TZ), **fields)


def make_job_wrapper(ref_name: str, job_name: str, job, done_msg: str, fail_msg: str):
    """Create an async job wrapper with standard trigger/success/failure logging.

    Args:
        ref_name: Module-level name the result is bound to
        job_name: Display name used in the "SCHEDULED JOB TRIGGERED" log line
        job: Async callable to execute
        done_msg: Log message prefix on success
        fail_msg: Log message prefix on failure

    Returns:
        Async wrapper function suitable for scheduler registration
    """
    async def wrapper():
        logger.info(f"=== SCHEDULED JOB TRIGGERED: {job_name} ===")
        try:
            result = await job()
            logger.info(f"{done_msg}: {result}")
            return result
        except Exception as e:
            logger.error(f"{fail_msg}: {e}", exc_info=True)
            raise

    # APScheduler serialises a job as "module:qualname" and refuses any name
    # containing "<locals>". Each wrapper is bound to a module-level name below,
    # so point the reference at that name rather than at the closure.
    wrapper.__name__ = ref_name
    wrapper.__qualname__ = ref_name
    return wrapper


async def _run_sector_historical_job_async():
    """Run sync sector historical job in thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, collect_sector_historical_job)


collect_intraday_job_wrapper = make_job_wrapper(
    "collect_intraday_job_wrapper",
    "Intraday Collection",
    collect_intraday_data_job,
    "Intraday collection completed",
    "Intraday collection failed",
)
cleanup_job_wrapper = make_job_wrapper(
    "cleanup_job_wrapper",
    "Data Cleanup",
    cleanup_old_data_job,
    "Data cleanup completed",
    "Data cleanup failed",
)
profit_census_job_wrapper = make_job_wrapper(
    "profit_census_job_wrapper",
    "Profit Ranking Census",
    census_market_profits,
    "Profit census completed",
    "Profit census failed",
)
profit_census_retry_job_wrapper = make_job_wrapper(
    "profit_census_retry_job_wrapper",
    "Profit Ranking Census Retry",
    retry_census_gaps,
    "Profit census retry completed",
    "Profit census retry failed",
)
universe_snapshots_job_wrapper = make_job_wrapper(
    "universe_snapshots_job_wrapper",
    "Universe Snapshot Collection",
    collect_universe_snapshots,
    "Universe collection cycle completed",
    "Universe collection cycle failed",
)
universe_backfill_job_wrapper = make_job_wrapper(
    "universe_backfill_job_wrapper",
    "Universe History Backfill",
    backfill_universe_history,
    "Universe history backfill completed",
    "Universe history backfill failed",
)
market_catchup_job_wrapper = make_job_wrapper(
    "market_catchup_job_wrapper",
    "Market Catch-up",
    catch_up_market_data,
    "Market catch-up completed",
    "Market catch-up failed",
)
corporate_actions_job_wrapper = make_job_wrapper(
    "corporate_actions_job_wrapper",
    "Corporate Action Load",
    load_corporate_actions,
    "Corporate action load completed",
    "Corporate action load failed",
)
market_index_job_wrapper = make_job_wrapper(
    "market_index_job_wrapper",
    "Market Index Series",
    load_market_index,
    "Market index load completed",
    "Market index load failed",
)
analysis_run_sweep_job_wrapper = make_job_wrapper(
    "analysis_run_sweep_job_wrapper",
    "Analysis Run Sweep",
    sweep_stuck_analysis_runs,
    "Analysis Run sweep completed",
    "Analysis Run sweep failed",
)
sector_historical_job_wrapper = make_job_wrapper(
    "sector_historical_job_wrapper",
    "Sector Historical Performance",
    _run_sector_historical_job_async,
    "Sector historical complete",
    "Sector historical failed",
)


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
        vn_cron(
            hour=settings.intraday_collect_hour,
            minute=settings.intraday_collect_minute,
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
        vn_cron(hour=16, minute=0),
        id="data-cleanup-daily",
    )
    logger.info("Scheduled data cleanup at 16:00 ICT")

    # The market-wide profit census: a full pass weekly, and a daily pass that
    # only chases the symbols missing at the newest reporting period. Both are
    # tracked runs under one guard, so the retry cannot start on top of a weekly
    # pass that is still walking the market (docs/adr/0004).
    if settings.profit_census_enabled:
        await scheduler.add_schedule(
            profit_census_job_wrapper,
            vn_cron(
                hour=settings.profit_census_hour,
                minute=settings.profit_census_minute,
                day_of_week=settings.profit_census_weekday,
            ),
            id="profit-census-weekly",
        )
        logger.info(
            f"Scheduled the profit census: day_of_week="
            f"{settings.profit_census_weekday} at "
            f"{settings.profit_census_hour:02d}:{settings.profit_census_minute:02d} ICT"
        )

        await scheduler.add_schedule(
            profit_census_retry_job_wrapper,
            vn_cron(
                hour=settings.profit_census_retry_hour,
                minute=settings.profit_census_retry_minute,
            ),
            id="profit-census-retry-daily",
        )
        logger.info(
            f"Scheduled the profit census retry at "
            f"{settings.profit_census_retry_hour:02d}:"
            f"{settings.profit_census_retry_minute:02d} ICT"
        )

    # The Corporate Action series, on the slow cadence ADR-0006 calls for. A
    # weekend morning of its own: it shares vnstock's allowance with the census,
    # and read-time adjustment has no other input, so it must not be the job that
    # waits behind a market-wide pass that overran.
    if settings.corporate_actions_enabled:
        await scheduler.add_schedule(
            corporate_actions_job_wrapper,
            vn_cron(
                hour=settings.corporate_actions_hour,
                minute=settings.corporate_actions_minute,
                day_of_week=settings.corporate_actions_weekday,
            ),
            id="corporate-actions-weekly",
        )
        logger.info(
            f"Scheduled the corporate action load: day_of_week="
            f"{settings.corporate_actions_weekday} at "
            f"{settings.corporate_actions_hour:02d}:"
            f"{settings.corporate_actions_minute:02d} ICT"
        )

    # Daily sector historical performance at 15:45 ICT (after sector-performance at 15:30)
    if settings.sector_historical_enabled:
        await scheduler.add_schedule(
            sector_historical_job_wrapper,
            vn_cron(
                hour=settings.sector_historical_hour,
                minute=settings.sector_historical_minute,
            ),
            id="sector-historical-daily",
        )
        logger.info(
            f"Scheduled sector historical at "
            f"{settings.sector_historical_hour}:{settings.sector_historical_minute:02d} ICT"
        )

    # The collection cycle for the Universe, after the session closes.
    if settings.collector_enabled:
        await scheduler.add_schedule(
            universe_snapshots_job_wrapper,
            vn_cron(
                hour=settings.collector_hour,
                minute=settings.collector_minute,
            ),
            id="universe-snapshots",
        )
        logger.info(
            f"Scheduled the Universe collection cycle at "
            f"{settings.collector_hour}:{settings.collector_minute:02d} ICT"
        )

    # The one-time history load, after the day's cycle has had its turn at the
    # allowance the two of them share.
    if settings.backfill_enabled:
        await scheduler.add_schedule(
            universe_backfill_job_wrapper,
            vn_cron(
                hour=settings.backfill_hour,
                minute=settings.backfill_minute,
            ),
            id="universe-backfill",
        )
        logger.info(
            f"Scheduled the Universe history backfill at "
            f"{settings.backfill_hour}:{settings.backfill_minute:02d} ICT"
        )

    # Late enough that the Main Source has appended the session that closed
    # today. The 16:15 cycle routinely comes away with yesterday's session,
    # and without this run that day is never collected at all.
    if settings.market_catchup_enabled:
        await scheduler.add_schedule(
            market_catchup_job_wrapper,
            vn_cron(
                hour=settings.market_catchup_hour,
                minute=settings.market_catchup_minute,
            ),
            id="market-catchup",
        )
        logger.info(
            f"Scheduled the market catch-up at "
            f"{settings.market_catchup_hour}:{settings.market_catchup_minute:02d} ICT"
        )

    # The benchmark series, after the market catch-up has had its turn at the
    # single FiinQuant connection. Deliberately behind it rather than beside it:
    # a beta is only computable when the index and the symbols stop on the same
    # Trading Day, so the index is loaded once the session that just closed has
    # been collected for the Universe.
    if settings.market_index_enabled:
        await scheduler.add_schedule(
            market_index_job_wrapper,
            vn_cron(
                hour=settings.market_index_hour,
                minute=settings.market_index_minute,
            ),
            id="market-index",
        )
        logger.info(
            f"Scheduled the market index load at "
            f"{settings.market_index_hour}:{settings.market_index_minute:02d} ICT"
        )

    # An interval rather than a time of day: a run dies whenever the process
    # does, which is not on a schedule. Why the interval is the stuck window
    # itself is recorded on `analysis_run_stuck_minutes` in core/config.py.
    await scheduler.add_schedule(
        analysis_run_sweep_job_wrapper,
        IntervalTrigger(
            minutes=settings.analysis_run_stuck_minutes,
            start_time=datetime.now(VN_TZ),
        ),
        id="analysis-run-sweep",
    )
    logger.info(
        f"Scheduled the Analysis Run sweep every "
        f"{settings.analysis_run_stuck_minutes} minutes"
    )

    logger.info("=== Scheduler setup complete ===")

    # Run startup checks for missed jobs in background (non-blocking)
    # This allows the server to start accepting requests immediately
    asyncio.create_task(run_startup_jobs_with_delay())


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

    if not is_trading_day(today):
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
