"""Price domain service for historical and real-time price data."""

import logging
from functools import lru_cache
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd
from src.core.vnstock_client import Quote, Trading
from src.core.vnstock_client import VnstockUnavailable, VnstockUnsupported

from ..schemas.price import (
    StockPrice,
    IntradayTick,
    PriceBoardItem,
    MarketIndexItem,
)
from ..shared import StockServiceError, validate_symbol, quote_price_vnd, safe_float

logger = logging.getLogger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# (symbol, display name). Shared with the router so it can tell a complete
# board from a partial one before caching.
MARKET_INDICES: list[tuple[str, str]] = [
    ("VNINDEX", "VN-INDEX"),
    ("VN30", "VN30"),
    ("HNXINDEX", "HNX-INDEX"),
    ("UPCOMINDEX", "UPCOM-INDEX"),
]


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
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
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
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching intraday for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch intraday for {symbol}: {e}")

    def get_price_board(self, symbols: list[str]) -> list[PriceBoardItem]:
        """Get real-time price board for multiple symbols."""
        try:
            # vnstock 4.x defaults Trading to KBS, whose price_board rejects
            # drop_levels; 3.x defaulted to VCI. Pass the configured source.
            trading = Trading(source=self.source)
            df = trading.price_board(
                symbols_list=[s.upper() for s in symbols],
                flatten_columns=True,
                drop_levels=[0],
            )

            if df is None or df.empty:
                return []

            return self._df_to_price_board(df)
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching price board: {e}")
            raise StockServiceError(f"Failed to fetch price board: {e}")

    def get_market_indices(self) -> list[MarketIndexItem]:
        """Get market indices data (VN-INDEX, VN30, HNX-INDEX, UPCOM-INDEX)."""
        indices = MARKET_INDICES

        # Only the last two closes are needed. The window used to start at
        # 2025-01-01, pulling ~18 months per index; that was slow enough that a
        # single index could time out and get dropped, silently returning 3 of 4.
        start = (date.today() - timedelta(days=30)).isoformat()

        results = []
        missing = []
        for symbol, name in indices:
            try:
                quote = Quote(symbol=symbol, source=self.source)
                df = quote.history(start=start, end=date.today().isoformat())

                if df is None or df.empty or len(df) < 1:
                    logger.warning(f"No data for index {symbol}")
                    missing.append(symbol)
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
            except (VnstockUnavailable, VnstockUnsupported):
                # Upstream quota/capability problems carry their own meaning;
                # don't flatten them into a generic service error.
                raise
            except Exception as e:
                logger.warning(f"Error fetching index {symbol}: {e}")
                missing.append(symbol)
                continue

        if missing:
            # Surfaced so a partial board is visible in logs and can be kept out
            # of the cache, rather than looking like the market only has 3 indices.
            logger.error(f"Market indices incomplete, missing: {missing}")

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
                        # Quote history arrives in thousands of VND; the rest of
                        # the API speaks plain VND.
                        open=quote_price_vnd(row.get("open")),
                        high=quote_price_vnd(row.get("high")),
                        low=quote_price_vnd(row.get("low")),
                        close=quote_price_vnd(row.get("close")),
                        volume=int(row.get("volume", 0)) if pd.notna(row.get("volume")) else None,
                    )
                )
            except (VnstockUnavailable, VnstockUnsupported):
                # Upstream quota/capability problems carry their own meaning;
                # don't flatten them into a generic service error.
                raise
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
                        price=quote_price_vnd(row.get("price")),
                        volume=int(row.get("volume", 0)) if pd.notna(row.get("volume")) else None,
                        accumulated_vol=int(row.get("accumulated_vol", 0)) if pd.notna(row.get("accumulated_vol")) else None,
                        accumulated_val=int(row.get("accumulated_val", 0)) if pd.notna(row.get("accumulated_val")) else None,
                        match_type=row.get("match_type") or row.get("type"),
                    )
                )
            except (VnstockUnavailable, VnstockUnsupported):
                # Upstream quota/capability problems carry their own meaning;
                # don't flatten them into a generic service error.
                raise
            except Exception as e:
                logger.warning(f"Skipping intraday tick due to error: {e}")
                continue
        return ticks

    def _df_to_price_board(self, df: pd.DataFrame) -> list[PriceBoardItem]:
        """Convert DataFrame to list of PriceBoardItem."""
        items = []
        for row in df.to_dict("records"):
            try:
                match_price = safe_float(row.get("match_price"))
                ref_price = safe_float(row.get("ref_price") or row.get("refPrice"))
                accumulated_volume = safe_float(row.get("accumulated_volume"))
                accumulated_value = safe_float(row.get("accumulated_value"))

                # vnstock 4.x stopped sending last_price/total_vol/total_val/
                # change/change_pct, so every field a consumer of the older
                # contract knew about came back null. They are all derivable
                # from what it does send — fill them rather than ship a 200 with
                # nothing usable in it.
                change = row.get("change")
                change = safe_float(change)
                if change is None and match_price is not None and ref_price is not None:
                    change = match_price - ref_price

                change_pct = safe_float(row.get("change_pct") or row.get("changePct"))
                if change_pct is None and change is not None and ref_price:
                    change_pct = round(change / ref_price * 100, 2)

                items.append(
                    PriceBoardItem(
                        symbol=str(row.get("symbol", row.get("ticker", ""))),
                        match_price=match_price,
                        highest=safe_float(row.get("highest")),
                        lowest=safe_float(row.get("lowest")),
                        accumulated_volume=int(accumulated_volume) if accumulated_volume is not None else None,
                        accumulated_value=accumulated_value,
                        ceiling=safe_float(row.get("ceiling")),
                        floor=safe_float(row.get("floor")),
                        ref_price=ref_price,
                        last_price=safe_float(row.get("last_price") or row.get("lastPrice")) or match_price,
                        last_vol=safe_float(row.get("last_vol") or row.get("lastVol")),
                        total_vol=safe_float(row.get("total_vol") or row.get("totalVol")) or accumulated_volume,
                        total_val=safe_float(row.get("total_val") or row.get("totalVal")) or accumulated_value,
                        change=change,
                        change_pct=change_pct,
                    )
                )
            except (VnstockUnavailable, VnstockUnsupported):
                # Upstream quota/capability problems carry their own meaning;
                # don't flatten them into a generic service error.
                raise
            except Exception as e:
                logger.warning(f"Skipping price board item due to error: {e}")
                continue
        return items

@lru_cache(maxsize=1)
def get_price_service(source: str = "VCI") -> PriceService:
    """Get or create price service instance (thread-safe singleton)."""
    return PriceService(source=source)
