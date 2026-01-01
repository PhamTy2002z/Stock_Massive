"""Scheduled job functions for intraday data collection and cleanup."""
import logging
import time
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import delete, text

from src.core.config import get_settings
from src.core.database import async_session_factory, get_sync_db
from src.core.vnstock_wrapper import (
    VnstockRateLimitError,
    get_adaptive_delay,
    get_all_symbols,
    get_stock_history,
)
from src.core.job_status_store import job_store
from src.stocks.intraday_collector import IntradayCollector
from src.stocks.models import StockDailyOHLCV, StockIntradayBar
from src.stocks.financial_statements_collector import FinancialStatementsCollector
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
        return {"success": [], "failed": symbols, "total_bars": 0, "error": str(e)}


async def cleanup_old_data_job() -> int:
    """Daily job to remove data older than retention period.

    Returns:
        Number of deleted records
    """
    cutoff = datetime.now() - timedelta(days=settings.intraday_retention_days)
    logger.info(f"Cleaning up data older than {cutoff.date()}")
    job_store.start_job("cleanup", "Dọn dẹp dữ liệu cũ", 1)

    try:
        async with async_session_factory() as db:
            stmt = delete(StockIntradayBar).where(StockIntradayBar.bar_time < cutoff)
            result = await db.execute(stmt)
            await db.commit()
            deleted_count = result.rowcount

        logger.info(f"Deleted {deleted_count} old records")
        job_store.complete_job("cleanup", {"deleted_count": deleted_count})
        return deleted_count
    except Exception as e:
        logger.error(f"Cleanup job failed: {e}")
        job_store.fail_job("cleanup", str(e))
        return 0


def collect_daily_ohlcv_job() -> dict:
    """Daily job to collect OHLCV data for all symbols.

    Runs synchronously due to vnstock blocking calls.
    Uses safe wrapper with SystemExit protection and adaptive delays.

    Returns:
        Dictionary with success/failed counts and total rows
    """
    if not settings.daily_ohlcv_enabled:
        logger.info("Daily OHLCV collection disabled")
        return {"success": 0, "failed": 0, "total_rows": 0, "skipped": True}

    logger.info("Starting daily OHLCV collection for all symbols")
    start_time = datetime.now()

    # Get all symbols using safe wrapper
    all_symbols = get_all_symbols(max_retries=3, base_delay=5.0)
    if not all_symbols:
        logger.error("Failed to get symbol list (rate limited or error)")
        job_store.fail_job("daily-ohlcv", "Failed to fetch symbols")
        return {"success": 0, "failed": 0, "total_rows": 0, "error": "Failed to fetch symbols"}

    job_store.start_job("daily-ohlcv", "Thu thập OHLCV", len(all_symbols))

    logger.info(f"Found {len(all_symbols)} symbols to process")

    # Date range: last 7 days (for daily updates, we only need recent data)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    success_count = 0
    error_count = 0
    rate_limit_count = 0
    total_rows = 0
    batch_size = settings.daily_ohlcv_batch_size
    base_delay = settings.daily_ohlcv_delay

    # Process in batches
    for batch_idx in range(0, len(all_symbols), batch_size):
        batch = all_symbols[batch_idx : batch_idx + batch_size]
        batch_num = batch_idx // batch_size + 1
        total_batches = (len(all_symbols) + batch_size - 1) // batch_size

        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} symbols)")

        batch_data = []
        for symbol in batch:
            try:
                # Use safe wrapper (VCI only, TCBS discontinued)
                df = get_stock_history(
                    symbol=symbol,
                    start=start_date,
                    end=end_date,
                    interval="1D",
                    source="VCI",
                    max_retries=2,
                    base_delay=3.0,
                )

                if df is not None and not df.empty:
                    df["symbol"] = symbol
                    batch_data.append(df)
                    success_count += 1
                    total_rows += len(df)
                else:
                    error_count += 1

            except VnstockRateLimitError:
                rate_limit_count += 1
                logger.warning(f"Rate limited for {symbol}, skipping")

            except Exception as e:
                logger.debug(f"Error fetching {symbol}: {e}")
                error_count += 1

            # Adaptive delay based on recent failures
            delay = get_adaptive_delay(base_delay)
            time.sleep(delay)

        # Save batch to database
        if batch_data:
            _save_ohlcv_batch(batch_data)

        logger.info(
            f"Batch {batch_num} complete: {success_count} success, "
            f"{error_count} errors, {rate_limit_count} rate limited"
        )

        # Update progress after each batch
        job_store.update_progress(
            "daily-ohlcv",
            batch_idx + len(batch),
            f"Batch {batch_num}/{total_batches}",
        )

        # Extra pause between batches if rate limits detected
        if rate_limit_count > 0:
            batch_pause = min(30, rate_limit_count * 5)
            logger.info(f"Rate limits detected, pausing {batch_pause}s between batches")
            time.sleep(batch_pause)

    elapsed = (datetime.now() - start_time).total_seconds() / 60
    logger.info(
        f"Daily OHLCV collection complete in {elapsed:.1f} min: "
        f"{success_count} success, {error_count} failed, "
        f"{rate_limit_count} rate limited, {total_rows} rows"
    )

    result = {
        "success": success_count,
        "failed": error_count,
        "rate_limited": rate_limit_count,
        "total_rows": total_rows,
        "elapsed_minutes": round(elapsed, 1),
    }
    job_store.complete_job("daily-ohlcv", result)
    return result


def _save_ohlcv_batch(batch_data: list) -> int:
    """Save batch of OHLCV dataframes to database using upsert.

    Args:
        batch_data: List of pandas DataFrames with OHLCV data

    Returns:
        Number of rows inserted/updated
    """
    if not batch_data:
        return 0

    combined = pd.concat(batch_data, ignore_index=True)
    combined = combined.rename(
        columns={
            "time": "trade_date",
            "open": "open_price",
            "high": "high_price",
            "low": "low_price",
            "close": "close_price",
        }
    )
    combined["trade_date"] = pd.to_datetime(combined["trade_date"]).dt.date

    rows_saved = 0
    with get_sync_db() as conn:
        for _, row in combined.iterrows():
            try:
                conn.execute(
                    text(
                        """
                    INSERT INTO stock_daily_ohlcv
                        (symbol, trade_date, open_price, high_price, low_price, close_price, volume)
                    VALUES
                        (:symbol, :trade_date, :open_price, :high_price, :low_price, :close_price, :volume)
                    ON CONFLICT (symbol, trade_date) DO UPDATE SET
                        open_price = EXCLUDED.open_price,
                        high_price = EXCLUDED.high_price,
                        low_price = EXCLUDED.low_price,
                        close_price = EXCLUDED.close_price,
                        volume = EXCLUDED.volume
                """
                    ),
                    {
                        "symbol": row["symbol"],
                        "trade_date": row["trade_date"],
                        "open_price": (
                            float(row["open_price"])
                            if pd.notna(row["open_price"])
                            else None
                        ),
                        "high_price": (
                            float(row["high_price"])
                            if pd.notna(row["high_price"])
                            else None
                        ),
                        "low_price": (
                            float(row["low_price"])
                            if pd.notna(row["low_price"])
                            else None
                        ),
                        "close_price": (
                            float(row["close_price"])
                            if pd.notna(row["close_price"])
                            else None
                        ),
                        "volume": (
                            int(row["volume"]) if pd.notna(row["volume"]) else 0
                        ),
                    },
                )
                rows_saved += 1
            except Exception as e:
                logger.debug(f"Error saving row: {e}")

    return rows_saved


async def collect_financial_statements_job() -> dict:
    """Scheduled job to collect financial statements data.

    Runs weekly to fetch quarterly financials for HOSE+HNX symbols.
    Returns dict with success/failed counts.
    """
    logger.info("Starting financial statements collection job")
    job_store.start_job("financial-statements", "Thu thập BCTC", 1)

    try:
        async with async_session_factory() as db:
            collector = FinancialStatementsCollector(db)
            result = await collector.collect()

        logger.info(f"Financial statements job complete: {result}")
        job_store.complete_job("financial-statements", result)
        return result
    except Exception as e:
        logger.error(f"Financial statements collection job failed: {e}")
        job_store.fail_job("financial-statements", str(e))
        return {"success": 0, "failed": 0, "error": str(e)}


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
