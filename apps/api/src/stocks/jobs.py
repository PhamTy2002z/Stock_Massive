"""Scheduled job functions for intraday data collection and cleanup.

The market-wide daily OHLCV collection that used to live here is gone with the
signal it fed. It read roughly 1,600 symbols out of vnstock every evening to
answer a question ADR-0003 says this system does not answer, and it spent the
allowance the Universe's own collection cycle needs. Sessions for the symbols
this system does follow are written by the Collector, into ``provider_snapshots``.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from src.agent.persistence import TOOL_CALL_RETENTION_DAYS
from src.alpha.models import AgentToolCall
from src.core.config import get_settings
from src.core.database import async_session_factory
from src.core.job_status_store import job_store
from src.stocks.intraday_collector import IntradayCollector
from src.stocks.models import StockIntradayBar
from src.stocks.analytics.sector_historical_service import SectorHistoricalService

logger = logging.getLogger(__name__)
settings = get_settings()


async def collect_intraday_data_job() -> dict:
    """Daily job to collect intraday data for configured symbols.

    Returns:
        Dictionary with success/failed symbols and total bars count
    """
    symbols = [s.strip() for s in settings.intraday_symbols.split(",") if s.strip()]
    logger.info(f"Starting intraday collection for {len(symbols)} symbols: {symbols}")
    job_store.start_job("intraday", "Thu thập Intraday", len(symbols))

    try:
        async with async_session_factory() as db:
            collector = IntradayCollector(db)
            result = await collector.collect_and_save(symbols)

        logger.info(
            f"Collection complete: {len(result['success'])} success, "
            f"{len(result['failed'])} failed, {result['total_bars']} bars"
        )
        job_store.complete_job("intraday", result)
        return result
    except Exception as e:
        logger.error(f"Intraday collection job failed: {e}")
        job_store.fail_job("intraday", str(e))
        # Same shape as the success path: IntradayCollectionResult declares no
        # top-level `error`, and `failed` holds {symbol, error} entries. The
        # reason is already recorded on the job above.
        return {
            "success": [],
            "failed": [{"symbol": s, "error": str(e)} for s in symbols],
            "total_bars": 0,
        }


async def cleanup_old_data_job() -> int:
    """Daily 16:00 job for every bounded operational-data retention policy.

    Returns:
        Number of deleted records
    """
    intraday_cutoff = datetime.now() - timedelta(days=settings.intraday_retention_days)
    trace_cutoff = datetime.now(timezone.utc) - timedelta(days=TOOL_CALL_RETENTION_DAYS)
    logger.info(
        "Cleaning intraday data before %s and Tool Call Traces before %s",
        intraday_cutoff.date(),
        trace_cutoff.date(),
    )
    job_store.start_job("cleanup", "Dọn dẹp dữ liệu cũ", 1)

    try:
        async with async_session_factory() as db:
            intraday_result = await db.execute(
                delete(StockIntradayBar).where(
                    StockIntradayBar.bar_time < intraday_cutoff
                )
            )
            trace_result = await db.execute(
                delete(AgentToolCall).where(AgentToolCall.started_at < trace_cutoff)
            )
            await db.commit()
            intraday_deleted = intraday_result.rowcount or 0
            trace_deleted = trace_result.rowcount or 0
            deleted_count = intraday_deleted + trace_deleted

        logger.info(
            "Deleted %d intraday rows and %d Tool Call Traces",
            intraday_deleted,
            trace_deleted,
        )
        job_store.complete_job(
            "cleanup",
            {
                "deleted_count": deleted_count,
                "intraday_deleted_count": intraday_deleted,
                "tool_call_deleted_count": trace_deleted,
            },
        )
        return deleted_count
    except Exception as e:
        logger.error(f"Cleanup job failed: {e}")
        job_store.fail_job("cleanup", str(e))
        return 0


def collect_sector_historical_job() -> dict:
    """Daily job to calculate sector historical performance.

    Calculates top 5 gaining and top 5 losing sectors over 1W/2W/1M periods.
    Runs after market close (15:45 ICT) and caches results to Redis.

    Returns:
        Dict with results for each period or error
    """
    logger.info("Starting sector historical performance calculation")
    job_store.start_job("sector-historical", "Tính hiệu suất ngành", 1)

    try:
        service = SectorHistoricalService()
        result = service.calculate_all_periods()
        logger.info(f"Sector historical calculation complete: {len(result)} periods")
        job_store.complete_job("sector-historical", result)
        return result
    except Exception as e:
        logger.error(f"Sector historical job failed: {e}")
        job_store.fail_job("sector-historical", str(e))
        return {"error": str(e)}
