"""Scheduled job functions for intraday data collection and cleanup."""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import delete

from src.core.config import get_settings
from src.core.database import async_session_factory, get_sync_db
from src.stocks.intraday_collector import IntradayCollector
from src.stocks.models import StockIntradayBar

logger = logging.getLogger(__name__)
settings = get_settings()


def run_market_context_eod_job(target_date: Optional[date] = None) -> dict:
    """Scheduled job for market context EOD pipeline.

    Computes daily returns, rolling metrics, sector benchmarks for all stocks.
    Runs synchronously as vnstock API is blocking.

    Args:
        target_date: Date to compute metrics for (default: today)

    Returns:
        Dictionary with pipeline results
    """
    from src.stocks.market_context_service import MarketContextService

    logger.info(f"Starting market context EOD job for {target_date or 'today'}")

    try:
        with get_sync_db() as db:
            service = MarketContextService(db)
            result = service.run_eod_pipeline(target_date)

        logger.info(f"Market context EOD job completed: {result.get('status')}")
        return result

    except Exception as e:
        logger.error(f"Market context EOD job failed: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}


async def collect_intraday_data_job() -> dict:
    """Daily job to collect intraday data for configured symbols.

    Returns:
        Dictionary with success/failed symbols and total bars count
    """
    symbols = [s.strip() for s in settings.intraday_symbols.split(",") if s.strip()]
    logger.info(f"Starting intraday collection for {len(symbols)} symbols: {symbols}")

    try:
        async with async_session_factory() as db:
            collector = IntradayCollector(db)
            result = await collector.collect_and_save(symbols)

        logger.info(
            f"Collection complete: {len(result['success'])} success, "
            f"{len(result['failed'])} failed, {result['total_bars']} bars"
        )
        return result
    except Exception as e:
        logger.error(f"Intraday collection job failed: {e}")
        return {"success": [], "failed": symbols, "total_bars": 0, "error": str(e)}


async def cleanup_old_data_job() -> int:
    """Daily job to remove data older than retention period.

    Returns:
        Number of deleted records
    """
    cutoff = datetime.now() - timedelta(days=settings.intraday_retention_days)
    logger.info(f"Cleaning up data older than {cutoff.date()}")

    try:
        async with async_session_factory() as db:
            stmt = delete(StockIntradayBar).where(StockIntradayBar.bar_time < cutoff)
            result = await db.execute(stmt)
            await db.commit()
            deleted_count = result.rowcount

        logger.info(f"Deleted {deleted_count} old records")
        return deleted_count
    except Exception as e:
        logger.error(f"Cleanup job failed: {e}")
        return 0
