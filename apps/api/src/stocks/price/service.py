"""Price domain service for historical and real-time price data."""

import logging
from datetime import date
from typing import Optional

import pandas as pd
from vnstock import Quote, Trading

from ..schemas.price import (
    StockPrice,
    IntradayTick,
    PriceBoardItem,
    MarketIndexItem,
)
from ..shared import StockServiceError, validate_symbol, safe_float

logger = logging.getLogger(__name__)


class PriceService:
    """Service for price-related data: history, intraday, price board, indices."""

    def __init__(self, source: str = "VCI"):
        """Initialize price service with data source."""
        self.source = source

    def get_history(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1D",
    ) -> list[StockPrice]:
        """Get historical OHLCV data for a stock."""
        symbol = validate_symbol(symbol)
        try:
            quote = Quote(symbol=symbol, source=self.source)
            df = quote.history(
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                interval=interval,
            )

            if df is None or df.empty:
                return []

            return self._df_to_stock_prices(df)
        except Exception as e:
            logger.error(f"Error fetching history for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch history for {symbol}: {e}")

    def get_intraday(self, symbol: str, page_size: int = 10000) -> list[IntradayTick]:
        """Get intraday tick data for a stock."""
        symbol = validate_symbol(symbol)
        try:
            quote = Quote(symbol=symbol, source=self.source)
            df = quote.intraday(page_size=page_size, show_log=False)

            if df is None or df.empty:
                return []

            return self._df_to_intraday_ticks(df)
        except Exception as e:
            logger.error(f"Error fetching intraday for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch intraday for {symbol}: {e}")

    def get_price_board(self, symbols: list[str]) -> list[PriceBoardItem]:
        """Get real-time price board for multiple symbols."""
        try:
            trading = Trading()
            df = trading.price_board(
                symbols_list=[s.upper() for s in symbols],
                flatten_columns=True,
                drop_levels=[0],
            )

            if df is None or df.empty:
                return []

            return self._df_to_price_board(df)
        except Exception as e:
            logger.error(f"Error fetching price board: {e}")
            raise StockServiceError(f"Failed to fetch price board: {e}")

    def get_market_indices(self) -> list[MarketIndexItem]:
        """Get market indices data (VN-INDEX, VN30, HNX-INDEX, UPCOM-INDEX)."""
        indices = [
            ("VNINDEX", "VN-INDEX"),
            ("VN30", "VN30"),
            ("HNXINDEX", "HNX-INDEX"),
            ("UPCOMINDEX", "UPCOM-INDEX"),
        ]

        results = []
        for symbol, name in indices:
            try:
                quote = Quote(symbol=symbol, source="VCI")
                df = quote.history(start="2025-01-01", end=date.today().isoformat())

                if df is None or df.empty or len(df) < 1:
                    logger.warning(f"No data for index {symbol}")
                    continue

                latest = df.iloc[-1]
                current_value = float(latest["close"])

                if len(df) >= 2:
                    previous = df.iloc[-2]
                    prev_close = float(previous["close"])
                    change = current_value - prev_close
                    change_pct = (change / prev_close) * 100 if prev_close != 0 else 0
                else:
                    change = 0.0
                    change_pct = 0.0

                results.append(
                    MarketIndexItem(
                        symbol=symbol,
                        name=name,
                        value=round(current_value, 2),
                        change=round(change, 2),
                        change_pct=round(change_pct, 2),
                    )
                )
            except Exception as e:
                logger.warning(f"Error fetching index {symbol}: {e}")
                continue

        return results

    # --- Converter methods ---

    def _df_to_stock_prices(self, df: pd.DataFrame) -> list[StockPrice]:
        """Convert DataFrame to list of StockPrice."""
        prices = []
        for row in df.to_dict("records"):
            try:
                time_val = row.get("time")
                if hasattr(time_val, "strftime"):
                    time_str = time_val.strftime("%Y-%m-%d")
                else:
                    time_str = str(time_val) if time_val else None

                prices.append(
                    StockPrice(
                        time=time_str,
                        open=safe_float(row.get("open")),
                        high=safe_float(row.get("high")),
                        low=safe_float(row.get("low")),
                        close=safe_float(row.get("close")),
                        volume=int(row.get("volume", 0)) if pd.notna(row.get("volume")) else None,
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping price row due to error: {e}")
                continue
        return prices

    def _df_to_intraday_ticks(self, df: pd.DataFrame) -> list[IntradayTick]:
        """Convert DataFrame to list of IntradayTick."""
        ticks = []
        for row in df.to_dict("records"):
            try:
                time_val = row.get("time")
                if hasattr(time_val, "strftime"):
                    time_str = time_val.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    time_str = str(time_val) if time_val else None

                ticks.append(
                    IntradayTick(
                        time=time_str,
                        price=safe_float(row.get("price")),
                        volume=int(row.get("volume", 0)) if pd.notna(row.get("volume")) else None,
                        match_type=row.get("match_type") or row.get("type"),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping intraday tick due to error: {e}")
                continue
        return ticks

    def _df_to_price_board(self, df: pd.DataFrame) -> list[PriceBoardItem]:
        """Convert DataFrame to list of PriceBoardItem."""
        items = []
        for row in df.to_dict("records"):
            try:
                items.append(
                    PriceBoardItem(
                        symbol=str(row.get("symbol", row.get("ticker", ""))),
                        match_price=safe_float(row.get("match_price")),
                        highest=safe_float(row.get("highest")),
                        lowest=safe_float(row.get("lowest")),
                        accumulated_volume=int(row.get("accumulated_volume", 0)) if pd.notna(row.get("accumulated_volume")) else None,
                        accumulated_value=safe_float(row.get("accumulated_value")),
                        ceiling=safe_float(row.get("ceiling")),
                        floor=safe_float(row.get("floor")),
                        ref_price=safe_float(row.get("ref_price") or row.get("refPrice")),
                        last_price=safe_float(row.get("last_price") or row.get("lastPrice")),
                        last_vol=safe_float(row.get("last_vol") or row.get("lastVol")),
                        total_vol=safe_float(row.get("total_vol") or row.get("totalVol")),
                        total_val=safe_float(row.get("total_val") or row.get("totalVal")),
                        change=safe_float(row.get("change")),
                        change_pct=safe_float(row.get("change_pct") or row.get("changePct")),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping price board item due to error: {e}")
                continue
        return items
