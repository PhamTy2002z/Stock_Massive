"""Intraday data collection service for aggregating tick data to 5-minute bars."""
import logging
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.stocks.models import StockIntradayBar
from src.stocks.schemas import IntradayTick
from src.stocks.shared import StockServiceError, validate_symbol

logger = logging.getLogger(__name__)


class IntradayCollector:
    """Service for collecting and aggregating intraday tick data to OHLCV bars."""

    def __init__(self, db: AsyncSession):
        """Initialize collector with database session.

        Args:
            db: Async database session
        """
        self.db = db
        # Lazy import to avoid circular dependency
        from src.stocks.service import get_stock_service
        self.stock_service = get_stock_service()

    def aggregate_ticks_to_bars(
        self, ticks: list[IntradayTick], interval_minutes: int = 5
    ) -> list[dict]:
        """Aggregate tick data to OHLCV bars.

        Args:
            ticks: List of IntradayTick objects
            interval_minutes: Bar interval in minutes (default 5)

        Returns:
            List of bar dictionaries with OHLCV data
        """
        if not ticks:
            return []

        # Convert ticks to DataFrame
        df = pd.DataFrame([t.model_dump() for t in ticks])

        # Floor time to interval buckets
        df["bar_time"] = pd.to_datetime(df["time"]).dt.floor(f"{interval_minutes}min")

        # Aggregate to OHLCV bars
        bars = (
            df.groupby("bar_time")
            .agg(
                {
                    "price": ["first", "max", "min", "last"],
                    "volume": "sum",
                }
            )
            .reset_index()
        )

        # Flatten column names
        bars.columns = [
            "bar_time",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
        ]

        # Calculate trade value from accumulated_val difference per bar (if available)
        if "accumulated_val" in df.columns and df["accumulated_val"].notna().any():
            trade_values = df.groupby("bar_time").apply(
                lambda x: x["accumulated_val"].iloc[-1] - x["accumulated_val"].iloc[0]
                if len(x) > 1 and x["accumulated_val"].notna().all()
                else 0,
                include_groups=False,
            )
            bars["trade_value"] = trade_values.values
        else:
            bars["trade_value"] = 0

        # Count trades per bar
        bars["trade_count"] = df.groupby("bar_time").size().values

        # Convert bar_time to Python datetime
        bars["bar_time"] = bars["bar_time"].dt.to_pydatetime()

        return bars.to_dict("records")

    async def collect_symbol(self, symbol: str) -> list[dict]:
        """Collect and aggregate intraday data for a symbol.

        Args:
            symbol: Stock symbol (e.g., VCB, FPT)

        Returns:
            List of bar dictionaries ready for database insertion
        """
        symbol = validate_symbol(symbol)
        ticks = self.stock_service.get_intraday(symbol)
        bars = self.aggregate_ticks_to_bars(ticks)

        # Add symbol to each bar
        for bar in bars:
            bar["symbol"] = symbol.upper()

        return bars

    async def save_bars(self, bars: list[dict]) -> int:
        """Upsert bars to database.

        Uses PostgreSQL ON CONFLICT DO UPDATE for idempotent inserts.

        Args:
            bars: List of bar dictionaries

        Returns:
            Number of affected rows
        """
        if not bars:
            return 0

        stmt = insert(StockIntradayBar).values(bars)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "bar_time"],
            set_={
                "open_price": stmt.excluded.open_price,
                "high_price": stmt.excluded.high_price,
                "low_price": stmt.excluded.low_price,
                "close_price": stmt.excluded.close_price,
                "volume": stmt.excluded.volume,
                "trade_value": stmt.excluded.trade_value,
                "trade_count": stmt.excluded.trade_count,
            },
        )
        result = await self.db.execute(stmt)
        # Note: commit handled by get_db() dependency
        return result.rowcount

    async def collect_and_save(self, symbols: list[str]) -> dict:
        """Collect and save intraday data for multiple symbols.

        Args:
            symbols: List of stock symbols

        Returns:
            Dictionary with success/failed symbols and total bars count
        """
        results = {"success": [], "failed": [], "total_bars": 0}

        for symbol in symbols:
            try:
                bars = await self.collect_symbol(symbol)
                count = await self.save_bars(bars)
                results["success"].append(symbol)
                results["total_bars"] += count
                logger.info(f"Collected {count} bars for {symbol}")
            except StockServiceError as e:
                results["failed"].append({"symbol": symbol, "error": str(e)})
                logger.warning(f"Failed to collect {symbol}: {e}")
            except Exception as e:
                results["failed"].append({"symbol": symbol, "error": str(e)})
                logger.error(f"Unexpected error collecting {symbol}: {e}")

        return results

    async def analyze_volume(
        self, symbol: str, days: int = 10, top_n: int = 10
    ) -> dict:
        """Analyze volume patterns for a symbol over N days.

        Groups bars by time-of-day (hour + 5-min bucket) to identify
        peak trading periods within the 09:00-15:00 trading session.

        Args:
            symbol: Stock symbol (e.g., VCB, FPT)
            days: Number of days to analyze (default 10)
            top_n: Number of top periods to return (default 10)

        Returns:
            Dictionary with symbol, days_analyzed, peak_periods, generated_at
        """
        symbol = validate_symbol(symbol)
        cutoff_date = datetime.now() - timedelta(days=days)

        # Extract hour and minute bucket for grouping
        hour_expr = func.extract("hour", StockIntradayBar.bar_time)
        minute_expr = func.floor(
            func.extract("minute", StockIntradayBar.bar_time) / 5
        ) * 5

        stmt = (
            select(
                hour_expr.label("hour"),
                minute_expr.label("minute_bucket"),
                func.avg(StockIntradayBar.volume).label("avg_volume"),
                func.sum(StockIntradayBar.volume).label("total_volume"),
                func.count().label("sample_count"),
            )
            .where(StockIntradayBar.symbol == symbol.upper())
            .where(StockIntradayBar.bar_time >= cutoff_date)
            .where(hour_expr >= 9)
            .where(hour_expr < 15)
            .group_by(hour_expr, minute_expr)
            .order_by(func.avg(StockIntradayBar.volume).desc())
            .limit(top_n)
        )

        result = await self.db.execute(stmt)
        rows = result.fetchall()

        periods = []
        for row in rows:
            hour = int(row.hour)
            minute = int(row.minute_bucket)
            periods.append({
                "hour": hour,
                "minute_bucket": minute,
                "time_label": f"{hour:02d}:{minute:02d}",
                "avg_volume": float(row.avg_volume),
                "total_volume": int(row.total_volume),
                "sample_count": int(row.sample_count),
            })

        return {
            "symbol": symbol.upper(),
            "days_analyzed": days,
            "trading_session": "09:00-15:00",
            "peak_periods": periods,
            "generated_at": datetime.now(),
        }

    async def detect_volume_anomalies(self, symbol: str, days: int = 20) -> dict:
        """Detect volume anomalies across all 5-minute time slots.

        Compares latest day's volume against N-day average baseline.

        Args:
            symbol: Stock symbol (e.g., VCB, FPT)
            days: Number of days for baseline calculation (default 20)

        Returns:
            Dictionary with symbol, time_slots (72 bars), metadata
        """
        symbol = validate_symbol(symbol)
        cutoff_date = datetime.now() - timedelta(days=days)

        # Get latest trading date
        latest_stmt = (
            select(func.max(func.date(StockIntradayBar.bar_time)))
            .where(StockIntradayBar.symbol == symbol.upper())
        )
        latest_result = await self.db.execute(latest_stmt)
        latest_date = latest_result.scalar()

        if not latest_date:
            return {
                "symbol": symbol.upper(),
                "days_analyzed": days,
                "trading_session": "09:00-15:00",
                "time_slots": [],
                "generated_at": datetime.now(),
                "latest_date": None,
            }

        # Extract hour and minute for grouping
        hour_expr = func.extract("hour", StockIntradayBar.bar_time)
        minute_expr = func.floor(
            func.extract("minute", StockIntradayBar.bar_time) / 5
        ) * 5
        date_expr = func.date(StockIntradayBar.bar_time)

        # Get baseline averages (exclude latest day)
        baseline_stmt = (
            select(
                hour_expr.label("hour"),
                minute_expr.label("minute_bucket"),
                func.avg(StockIntradayBar.volume).label("avg_volume"),
                func.count().label("sample_count"),
            )
            .where(StockIntradayBar.symbol == symbol.upper())
            .where(StockIntradayBar.bar_time >= cutoff_date)
            .where(date_expr < latest_date)
            .where(hour_expr >= 9)
            .where(hour_expr < 15)
            .group_by(hour_expr, minute_expr)
        )
        baseline_result = await self.db.execute(baseline_stmt)
        baseline_rows = baseline_result.fetchall()

        # Build baseline lookup
        baseline_map = {}
        for row in baseline_rows:
            key = (int(row.hour), int(row.minute_bucket))
            baseline_map[key] = {
                "avg_volume": float(row.avg_volume),
                "sample_count": int(row.sample_count),
            }

        # Get latest day's volumes
        current_stmt = (
            select(
                hour_expr.label("hour"),
                minute_expr.label("minute_bucket"),
                StockIntradayBar.volume,
            )
            .where(StockIntradayBar.symbol == symbol.upper())
            .where(date_expr == latest_date)
            .where(hour_expr >= 9)
            .where(hour_expr < 15)
        )
        current_result = await self.db.execute(current_stmt)
        current_rows = current_result.fetchall()

        # Build current volume lookup
        current_map = {}
        for row in current_rows:
            key = (int(row.hour), int(row.minute_bucket))
            current_map[key] = int(row.volume)

        # Generate all 72 time slots (09:00-14:55)
        time_slots = []
        for hour in range(9, 15):
            for minute in range(0, 60, 5):
                if hour == 14 and minute > 55:
                    break  # Stop at 14:55

                key = (hour, minute)
                current_vol = current_map.get(key, 0)
                baseline = baseline_map.get(key, {"avg_volume": 0, "sample_count": 0})
                avg_vol = baseline["avg_volume"]

                # Calculate ratio and anomaly level
                if avg_vol > 0:
                    ratio = current_vol / avg_vol
                else:
                    ratio = 0.0

                # Determine anomaly level
                if ratio >= 3.0:
                    anomaly = "very_high"
                elif ratio >= 2.0:
                    anomaly = "high"
                elif ratio >= 1.5:
                    anomaly = "elevated"
                else:
                    anomaly = "normal"

                time_slots.append({
                    "hour": hour,
                    "minute_bucket": minute,
                    "time_label": f"{hour:02d}:{minute:02d}",
                    "current_volume": current_vol,
                    "avg_volume": avg_vol,
                    "volume_ratio": round(ratio, 2),
                    "anomaly_level": anomaly,
                    "sample_count": baseline["sample_count"],
                })

        return {
            "symbol": symbol.upper(),
            "days_analyzed": days,
            "trading_session": "09:00-15:00",
            "time_slots": time_slots,
            "generated_at": datetime.now(),
            "latest_date": latest_date,
        }
