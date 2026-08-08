"""Price domain service for historical and real-time price data."""

import logging
from functools import lru_cache
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd
from vnstock import Quote, Trading

from ..schemas.price import (
    StockPrice,
    IntradayTick,
    PriceBoardItem,
    MarketIndexItem,
    PriceLevel,
    PriceDepthResponse,
)
from ..shared import StockServiceError, validate_symbol, safe_float

logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


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
                        accumulated_vol=int(row.get("accumulated_vol", 0)) if pd.notna(row.get("accumulated_vol")) else None,
                        accumulated_val=int(row.get("accumulated_val", 0)) if pd.notna(row.get("accumulated_val")) else None,
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

    def get_price_depth(self, symbol: str) -> PriceDepthResponse:
        """Get price depth (bid/ask levels) for a stock."""
        symbol = validate_symbol(symbol)
        try:
            quote = Quote(symbol=symbol, source=self.source)
            df = quote.price_depth()

            if df is None or (isinstance(df, pd.DataFrame) and df.empty):
                raise StockServiceError(f"No price depth data for {symbol}")

            # Parse DataFrame - handle both single row and multi-row cases
            if isinstance(df, pd.DataFrame) and len(df) > 0:
                row = df.iloc[0].to_dict()
            elif isinstance(df, dict):
                row = df
            else:
                raise StockServiceError(f"Invalid price depth format for {symbol}")

            # Try various column name patterns for bid levels
            bid_1 = PriceLevel(
                price=safe_float(row.get("bid_price_1") or row.get("bidPrice1") or row.get("bid1")) or 0,
                volume=int(row.get("bid_volume_1") or row.get("bidVolume1") or row.get("bidVol1") or 0)
            )
            bid_2_price = safe_float(row.get("bid_price_2") or row.get("bidPrice2") or row.get("bid2"))
            bid_2 = PriceLevel(
                price=bid_2_price or 0,
                volume=int(row.get("bid_volume_2") or row.get("bidVolume2") or row.get("bidVol2") or 0)
            ) if bid_2_price else None
            bid_3_price = safe_float(row.get("bid_price_3") or row.get("bidPrice3") or row.get("bid3"))
            bid_3 = PriceLevel(
                price=bid_3_price or 0,
                volume=int(row.get("bid_volume_3") or row.get("bidVolume3") or row.get("bidVol3") or 0)
            ) if bid_3_price else None

            # Try various column name patterns for ask levels
            ask_1 = PriceLevel(
                price=safe_float(row.get("ask_price_1") or row.get("askPrice1") or row.get("ask1")) or 0,
                volume=int(row.get("ask_volume_1") or row.get("askVolume1") or row.get("askVol1") or 0)
            )
            ask_2_price = safe_float(row.get("ask_price_2") or row.get("askPrice2") or row.get("ask2"))
            ask_2 = PriceLevel(
                price=ask_2_price or 0,
                volume=int(row.get("ask_volume_2") or row.get("askVolume2") or row.get("askVol2") or 0)
            ) if ask_2_price else None
            ask_3_price = safe_float(row.get("ask_price_3") or row.get("askPrice3") or row.get("ask3"))
            ask_3 = PriceLevel(
                price=ask_3_price or 0,
                volume=int(row.get("ask_volume_3") or row.get("askVolume3") or row.get("askVol3") or 0)
            ) if ask_3_price else None

            # Calculate totals and spread
            total_bid = bid_1.volume + (bid_2.volume if bid_2 else 0) + (bid_3.volume if bid_3 else 0)
            total_ask = ask_1.volume + (ask_2.volume if ask_2 else 0) + (ask_3.volume if ask_3 else 0)
            spread = ask_1.price - bid_1.price
            spread_pct = (spread / bid_1.price * 100) if bid_1.price > 0 else 0

            return PriceDepthResponse(
                symbol=symbol.upper(),
                bid_1=bid_1,
                bid_2=bid_2,
                bid_3=bid_3,
                ask_1=ask_1,
                ask_2=ask_2,
                ask_3=ask_3,
                total_bid_volume=total_bid,
                total_ask_volume=total_ask,
                spread=round(spread, 2),
                spread_percent=round(spread_pct, 4),
                timestamp=datetime.now(VN_TZ)
            )
        except StockServiceError:
            raise
        except Exception as e:
            logger.error(f"Error fetching price depth for {symbol}: {e}")
            raise StockServiceError(f"Failed to get price depth for {symbol}: {e}")


@lru_cache(maxsize=1)
def get_price_service(source: str = "VCI") -> PriceService:
    """Get or create price service instance (thread-safe singleton)."""
    return PriceService(source=source)
