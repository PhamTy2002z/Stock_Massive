"""Scheduled job functions for intraday data collection and cleanup."""
import logging
import time
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import delete, text
from vnstock import Listing, Vnstock

from src.core.config import get_settings
from src.core.database import async_session_factory, get_sync_db
from src.stocks.intraday_collector import IntradayCollector
from src.stocks.models import StockDailyOHLCV, StockIntradayBar

logger = logging.getLogger(__name__)
settings = get_settings()


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


def collect_daily_ohlcv_job() -> dict:
    """Daily job to collect OHLCV data for all symbols.

    Runs synchronously due to vnstock blocking calls.
    Uses batch processing with delays to avoid rate limiting.

    Returns:
        Dictionary with success/failed counts and total rows
    """
    if not settings.daily_ohlcv_enabled:
        logger.info("Daily OHLCV collection disabled")
        return {"success": 0, "failed": 0, "total_rows": 0, "skipped": True}

    logger.info("Starting daily OHLCV collection for all symbols")
    start_time = datetime.now()

    # Get all symbols
    try:
        listing = Listing()
        all_symbols_df = listing.all_symbols()
        all_symbols = all_symbols_df["symbol"].tolist()
        logger.info(f"Found {len(all_symbols)} symbols to process")
    except Exception as e:
        logger.error(f"Failed to get symbol list: {e}")
        return {"success": 0, "failed": 0, "total_rows": 0, "error": str(e)}

    # Date range: last 7 days (for daily updates, we only need recent data)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    success_count = 0
    error_count = 0
    total_rows = 0
    batch_size = settings.daily_ohlcv_batch_size
    delay = settings.daily_ohlcv_delay

    # Process in batches
    for batch_idx in range(0, len(all_symbols), batch_size):
        batch = all_symbols[batch_idx : batch_idx + batch_size]
        batch_num = batch_idx // batch_size + 1
        total_batches = (len(all_symbols) + batch_size - 1) // batch_size

        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} symbols)")

        batch_data = []
        for symbol in batch:
            try:
                stock = Vnstock().stock(symbol=symbol, source="VCI")
                df = stock.quote.history(start=start_date, end=end_date, interval="1D")

                if df is not None and not df.empty:
                    df["symbol"] = symbol
                    batch_data.append(df)
                    success_count += 1
                    total_rows += len(df)
                else:
                    # Fallback to TCBS
                    try:
                        stock = Vnstock().stock(symbol=symbol, source="TCBS")
                        df = stock.quote.history(
                            start=start_date, end=end_date, interval="1D"
                        )
                        if df is not None and not df.empty:
                            df["symbol"] = symbol
                            batch_data.append(df)
                            success_count += 1
                            total_rows += len(df)
                        else:
                            error_count += 1
                    except Exception:
                        error_count += 1

                time.sleep(delay)

            except Exception as e:
                logger.debug(f"Error fetching {symbol}: {e}")
                error_count += 1
                time.sleep(delay)

        # Save batch to database
        if batch_data:
            _save_ohlcv_batch(batch_data)

        logger.info(
            f"Batch {batch_num} complete: {success_count} success, {error_count} errors"
        )

    elapsed = (datetime.now() - start_time).total_seconds() / 60
    logger.info(
        f"Daily OHLCV collection complete in {elapsed:.1f} min: "
        f"{success_count} success, {error_count} failed, {total_rows} rows"
    )

    return {
        "success": success_count,
        "failed": error_count,
        "total_rows": total_rows,
        "elapsed_minutes": round(elapsed, 1),
    }


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
