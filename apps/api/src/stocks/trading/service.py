"""Trading analytics backed by the supported vnstock 4 Market API."""

import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from src.core.vnstock_client import Market, VnstockUnavailable, VnstockUnsupported

from ..shared import StockServiceError, validate_symbol
from .schemas import IntradayOrderStatsResponse

logger = logging.getLogger(__name__)
_INTRADAY_SOURCE = "KBS"


class TradingService:
    """Aggregate the latest complete trading session into order statistics."""

    def get_intraday_order_stats(self, symbol: str) -> IntradayOrderStatsResponse:
        """Aggregate the latest session from vnstock 4 KBS ``Market.trades``."""
        symbol = validate_symbol(symbol)
        try:
            df = Market().equity(symbol).trades(
                source=_INTRADAY_SOURCE,
                page_size=10_000,
            )

            if df is None or df.empty:
                return self._empty_intraday_response(symbol)

            match_types = df["match_type"].astype(str).str.lower()
            session_times = pd.to_datetime(df["time"], errors="coerce").dropna()
            if session_times.empty:
                raise ValueError("vnstock trades response has no valid session time")
            session_date = session_times.max().date().isoformat()
            buy_mask = match_types == "buy"
            sell_mask = match_types == "sell"
            ato_mask = match_types == "ato"
            atc_mask = match_types == "atc"

            buy_volume = int(df.loc[buy_mask, "volume"].sum()) if buy_mask.any() else 0
            sell_volume = (
                int(df.loc[sell_mask, "volume"].sum()) if sell_mask.any() else 0
            )

            return IntradayOrderStatsResponse(
                symbol=symbol,
                date=session_date,
                buy_orders=int(buy_mask.sum()),
                sell_orders=int(sell_mask.sum()),
                buy_volume=buy_volume,
                sell_volume=sell_volume,
                net_volume=buy_volume - sell_volume,
                ato_volume=int(df.loc[ato_mask, "volume"].sum()) if ato_mask.any() else 0,
                atc_volume=int(df.loc[atc_mask, "volume"].sum()) if atc_mask.any() else 0,
                last_updated=datetime.now().isoformat(),
            )
        except (VnstockUnavailable, VnstockUnsupported):
            raise
        except Exception as exc:
            logger.error("Error fetching intraday order stats for %s: %s", symbol, exc)
            raise StockServiceError(f"Failed to fetch intraday order stats: {exc}") from exc

    @staticmethod
    def _empty_intraday_response(symbol: str) -> IntradayOrderStatsResponse:
        return IntradayOrderStatsResponse(
            symbol=symbol,
            date=None,
            buy_orders=0,
            sell_orders=0,
            buy_volume=0,
            sell_volume=0,
            net_volume=0,
            ato_volume=0,
            atc_volume=0,
            last_updated=datetime.now().isoformat(),
        )


_trading_service: Optional[TradingService] = None


def get_trading_service() -> TradingService:
    """Return the process-wide trading service."""
    global _trading_service
    if _trading_service is None:
        _trading_service = TradingService()
    return _trading_service
