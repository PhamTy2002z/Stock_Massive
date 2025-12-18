"""Scheduled job functions for intraday data collection and cleanup."""
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete

from src.core.config import get_settings
from src.core.database import async_session_factory
from src.stocks.intraday_collector import IntradayCollector
from src.stocks.models import StockIntradayBar

logger = logging.getLogger(__name__)
settings = get_settings()


async def collect_intraday_data_job() -> dict:
    """Daily job to collect intraday data for configured symbols.

    Returns:
        Dictionary with success/failed symbols and total bars count
    """
    symbols = [s.strip() for s in settings.intraday_symbols.split(",") if s.strip()]
    logger.info(f"Starting intraday collection for {len(symbols)} symbols: {symbols}")

    async with async_session_factory() as db:
        collector = IntradayCollector(db)
        result = await collector.collect_and_save(symbols)
        await db.commit()

    logger.info(
        f"Collection complete: {len(result['success'])} success, "
        f"{len(result['failed'])} failed, {result['total_bars']} bars"
    )
    return result


async def cleanup_old_data_job() -> int:
    """Daily job to remove data older than retention period.

    Returns:
        Number of deleted records
    """
    cutoff = datetime.now() - timedelta(days=settings.intraday_retention_days)
    logger.info(f"Cleaning up data older than {cutoff.date()}")

    async with async_session_factory() as db:
        stmt = delete(StockIntradayBar).where(StockIntradayBar.bar_time < cutoff)
        result = await db.execute(stmt)
        await db.commit()
        deleted_count = result.rowcount

    logger.info(f"Deleted {deleted_count} old records")
    return deleted_count
