"""Trading domain service for foreign trading, proprietary trading, and order stats."""

import logging
from datetime import date, timedelta
from typing import Optional

import pandas as pd
from vnstock import Vnstock

from ..shared import StockServiceError, validate_symbol, safe_float
from .schemas import (
    ForeignTradingItem,
    ForeignTradingResponse,
    PropTradingItem,
    PropTradingResponse,
    OrderStatsItem,
    OrderStatsResponse,
)

logger = logging.getLogger(__name__)


class TradingService:
    """Service for trading data: foreign trade, proprietary trade, order stats."""

    def __init__(self, source: str = "VCI"):
        """Initialize trading service with data source."""
        self.source = source

    def get_foreign_trading(
        self, symbol: str, days: int = 30
    ) -> ForeignTradingResponse:
        """Get foreign investor trading data for last N days."""
        symbol = validate_symbol(symbol)
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            stock = Vnstock().stock(symbol=symbol, source=self.source)
            df = stock.trading.foreign_trade(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
            )

            if df is None or df.empty:
                return ForeignTradingResponse(
                    symbol=symbol, items=[], total_net_volume=0, total_net_value=0
                )

            items = []
            total_net_volume = 0
            total_net_value = 0

            for idx, row in df.iterrows():
                try:
                    # Parse date from index
                    if hasattr(idx, "strftime"):
                        date_str = idx.strftime("%Y-%m-%d")
                    else:
                        date_str = str(idx)

                    net_vol = int(row.get("fr_net_volume", 0) or 0)
                    net_val = int(row.get("fr_net_value", 0) or 0)

                    items.append(
                        ForeignTradingItem(
                            date=date_str,
                            net_volume=net_vol,
                            net_value=net_val,
                            buy_volume=int(row.get("fr_buy_volume", 0) or 0),
                            buy_value=int(row.get("fr_buy_value", 0) or 0),
                            sell_volume=int(row.get("fr_sell_volume", 0) or 0),
                            sell_value=int(row.get("fr_sell_value", 0) or 0),
                            remaining_room=int(row.get("fr_remaining_room", 0) or 0)
                            if row.get("fr_remaining_room")
                            else None,
                            ownership_pct=safe_float(row.get("fr_ownership")),
                        )
                    )
                    total_net_volume += net_vol
                    total_net_value += net_val
                except Exception as e:
                    logger.warning(f"Skipping foreign trading row due to error: {e}")
                    continue

            return ForeignTradingResponse(
                symbol=symbol,
                items=items,
                total_net_volume=total_net_volume,
                total_net_value=total_net_value,
            )
        except Exception as e:
            logger.error(f"Error fetching foreign trading for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch foreign trading for {symbol}: {e}")

    def get_prop_trading(self, symbol: str, days: int = 30) -> PropTradingResponse:
        """Get proprietary trading data for last N days."""
        symbol = validate_symbol(symbol)
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            stock = Vnstock().stock(symbol=symbol, source=self.source)
            df = stock.trading.prop_trade(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                resolution="1D",
            )

            if df is None or df.empty:
                return PropTradingResponse(symbol=symbol, items=[], total_net_volume=0)

            items = []
            total_net_volume = 0.0

            for _, row in df.iterrows():
                try:
                    # Get date from trading_date column
                    trading_date = row.get("trading_date")
                    if trading_date is not None and pd.notna(trading_date):
                        if hasattr(trading_date, "strftime"):
                            date_str = trading_date.strftime("%Y-%m-%d")
                        else:
                            date_str = str(trading_date)[:10]
                    else:
                        continue

                    net_vol = safe_float(row.get("total_trade_net_volume")) or 0
                    net_val = safe_float(row.get("total_trade_net_value")) or 0

                    items.append(
                        PropTradingItem(
                            date=date_str,
                            buy_volume=safe_float(row.get("total_buy_trade_volume"))
                            or 0,
                            sell_volume=safe_float(row.get("total_sell_trade_volume"))
                            or 0,
                            net_volume=net_vol,
                            net_value=net_val,
                        )
                    )
                    total_net_volume += net_vol
                except Exception as e:
                    logger.warning(f"Skipping prop trading row due to error: {e}")
                    continue

            return PropTradingResponse(
                symbol=symbol,
                items=items,
                total_net_volume=total_net_volume,
            )
        except Exception as e:
            logger.error(f"Error fetching prop trading for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch prop trading for {symbol}: {e}")

    def get_order_stats(self, symbol: str, days: int = 30) -> OrderStatsResponse:
        """Get order flow statistics for last N days."""
        symbol = validate_symbol(symbol)
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            stock = Vnstock().stock(symbol=symbol, source=self.source)
            df = stock.trading.order_stats(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
            )

            if df is None or df.empty:
                return OrderStatsResponse(symbol=symbol, items=[])

            items = []
            for idx, row in df.iterrows():
                try:
                    # Parse date from index
                    if hasattr(idx, "strftime"):
                        date_str = idx.strftime("%Y-%m-%d")
                    else:
                        date_str = str(idx)

                    items.append(
                        OrderStatsItem(
                            date=date_str,
                            buy_orders=int(row.get("buy_orders", 0) or 0),
                            sell_orders=int(row.get("sell_orders", 0) or 0),
                            buy_volume=int(row.get("buy_volume", 0) or 0),
                            sell_volume=int(row.get("sell_volume", 0) or 0),
                            avg_buy_order=safe_float(row.get("avg_buy_order_volume"))
                            or 0,
                            avg_sell_order=safe_float(row.get("avg_sell_order_volume"))
                            or 0,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Skipping order stats row due to error: {e}")
                    continue

            return OrderStatsResponse(symbol=symbol, items=items)
        except Exception as e:
            logger.error(f"Error fetching order stats for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch order stats for {symbol}: {e}")


# Singleton instance
_trading_service: Optional[TradingService] = None


def get_trading_service() -> TradingService:
    """Get or create TradingService singleton."""
    global _trading_service
    if _trading_service is None:
        _trading_service = TradingService()
    return _trading_service
