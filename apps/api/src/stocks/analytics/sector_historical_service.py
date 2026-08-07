"""Sector historical performance calculator.

Calculates top 5 gaining and top 5 losing sectors over 1W/2W/1M periods
based on VN100 stock performance. Data is cached to Redis with 24h TTL.
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from src.core.vnstock_client import Listing, Vnstock
from src.core.vnstock_client import VnstockUnavailable, VnstockUnsupported

from src.core.cache import TradingHoursCache
from src.core.config import get_settings
from src.stocks.shared import StockServiceError, fetch_industry_mapping

logger = logging.getLogger(__name__)
settings = get_settings()

# Redis cache with 24h TTL (historical data, calculated after market close)
sector_historical_cache = TradingHoursCache(
    key_prefix="stock:sector_hist:",
    ttl_trading=86400,   # 24h during trading (use cached)
    ttl_off_hours=86400, # 24h off-hours
)

PERIODS = {
    "1W": 7,
    "2W": 14,
    "1M": 30,
}


class SectorHistoricalService:
    """Calculate sector performance over 1W/2W/1M periods."""

    def __init__(self, source: str = "VCI"):
        self.source = source
        self.delay = settings.sector_historical_delay  # 1.2s between requests

    def calculate_all_periods(self) -> dict:
        """Calculate sector performance for all periods and cache results.

        Returns:
            Dict with results for each period (1W, 2W, 1M)
        """
        # Get VN100 symbols
        listing = Listing()
        vn100_symbols = listing.symbols_by_group("VN100")
        if vn100_symbols is None:
            logger.error("Failed to get VN100 symbols")
            return {"error": "Failed to get VN100 symbols"}

        symbols = vn100_symbols.tolist() if hasattr(vn100_symbols, "tolist") else list(vn100_symbols)
        logger.info(f"Processing {len(symbols)} VN100 symbols")

        # Get ICB mapping, narrowed to the symbols we are about to price
        try:
            full_map = fetch_industry_mapping(listing)
        except StockServiceError as exc:
            logger.error(f"Failed to build ICB mapping: {exc}")
            return {"error": "Industry classification data unavailable"}

        wanted = set(symbols)
        icb_map = {
            s: {"icb_code": v["icb_code"] or "", "icb_name": v["icb_name"] or ""}
            for s, v in full_map.items()
            if s in wanted
        }

        logger.info(f"ICB mapping available for {len(icb_map)} symbols")

        # Fetch historical prices for each symbol
        today = datetime.now().date()
        max_days = max(PERIODS.values())
        start_date = (today - timedelta(days=max_days + 10)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        stock_data = {}
        for symbol in symbols:
            try:
                stock = Vnstock().stock(symbol=symbol, source=self.source)
                df = stock.quote.history(start=start_date, end=end_date, interval="1D")
                if df is not None and not df.empty:
                    stock_data[symbol] = df
                time.sleep(self.delay)
            except (VnstockUnavailable, VnstockUnsupported):
                # Upstream quota/capability problems carry their own meaning;
                # don't flatten them into a generic service error.
                raise
            except Exception as e:
                logger.debug(f"Error fetching {symbol}: {e}")

        logger.info(f"Fetched data for {len(stock_data)} symbols")

        # Calculate performance for each period
        results = {}
        for period_name, days in PERIODS.items():
            results[period_name] = self._calculate_period(
                stock_data, icb_map, days, today
            )
            # Cache result
            sector_historical_cache.set(period_name, results[period_name])

        return results

    def _calculate_period(
        self,
        stock_data: dict,
        icb_map: dict,
        days: int,
        today
    ) -> dict:
        """Calculate sector performance for a single period.

        Args:
            stock_data: Dict of symbol -> DataFrame with historical prices
            icb_map: Dict of symbol -> {icb_code, icb_name}
            days: Number of days for the period
            today: Today's date

        Returns:
            Dict with top_gainers, top_losers, generated_at
        """
        target_date = today - timedelta(days=days)

        # Calculate % change per stock
        stock_changes = []
        for symbol, df in stock_data.items():
            if symbol not in icb_map:
                continue

            # Ensure date column exists
            if "time" in df.columns:
                df = df.copy()
                df["date"] = pd.to_datetime(df["time"]).dt.date
            elif "date" not in df.columns:
                continue

            # Get closest dates (handle weekends/holidays)
            start_row = df[df["date"] <= target_date].tail(1)
            end_row = df[df["date"] == today]
            if end_row.empty:
                end_row = df.tail(1)

            if start_row.empty or end_row.empty:
                continue

            start_price = float(start_row["close"].iloc[0])
            end_price = float(end_row["close"].iloc[0])

            if start_price > 0:
                pct_change = ((end_price - start_price) / start_price) * 100
                stock_changes.append({
                    "symbol": symbol,
                    "icb_code": icb_map[symbol]["icb_code"],
                    "icb_name": icb_map[symbol]["icb_name"],
                    "change_pct": pct_change,
                })

        if not stock_changes:
            return {"top_gainers": [], "top_losers": [], "generated_at": str(datetime.now())}

        # Group by sector, calculate average
        changes_df = pd.DataFrame(stock_changes)
        sector_perf = changes_df.groupby(["icb_code", "icb_name"])["change_pct"].mean().reset_index()
        sector_perf = sector_perf.sort_values("change_pct", ascending=False)

        # Top 5 gainers and losers
        top_gainers = [
            {"icb_code": r["icb_code"], "icb_name": r["icb_name"], "change_pct": round(r["change_pct"], 2)}
            for _, r in sector_perf.head(5).iterrows()
        ]
        top_losers = [
            {"icb_code": r["icb_code"], "icb_name": r["icb_name"], "change_pct": round(r["change_pct"], 2)}
            for _, r in sector_perf.tail(5).iloc[::-1].iterrows()
        ]

        return {
            "top_gainers": top_gainers,
            "top_losers": top_losers,
            "generated_at": str(datetime.now()),
        }

    def get_cached(self, period: str) -> Optional[dict]:
        """Get cached result for a period.

        Args:
            period: One of 1W, 2W, 1M

        Returns:
            Cached data or None
        """
        return sector_historical_cache.get(period)
