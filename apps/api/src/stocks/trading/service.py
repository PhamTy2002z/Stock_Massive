"""Trading domain service for foreign trading, proprietary trading, and order stats."""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
from vnstock import Trading, Vnstock

from ..shared import StockServiceError, validate_symbol, safe_float
from .schemas import (
    ForeignTradingItem,
    ForeignTradingResponse,
    PropTradingItem,
    PropTradingResponse,
    OrderStatsItem,
    OrderStatsResponse,
    IntradayOrderStatsResponse,
    ForeignSnapshotResponse,
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

            trading = Trading(symbol=symbol, source=self.source)
            try:
                df = trading.foreign_trade(
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d"),
                )
            except (NotImplementedError, Exception) as e:
                # vnstock Trading class may not support this method
                logger.warning(f"foreign_trade not available for {symbol}: {e}")
                return ForeignTradingResponse(
                    symbol=symbol, items=[], total_net_volume=0, total_net_value=0
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

            trading = Trading(symbol=symbol, source=self.source)
            try:
                df = trading.prop_trade(
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d"),
                )
            except (NotImplementedError, Exception) as e:
                # vnstock Trading class may not support this method
                logger.warning(f"prop_trade not available for {symbol}: {e}")
                return PropTradingResponse(symbol=symbol, items=[], total_net_volume=0)

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

            trading = Trading(symbol=symbol, source=self.source)
            try:
                df = trading.order_stats(
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d"),
                )
            except (NotImplementedError, Exception) as e:
                # vnstock Trading class may not support this method
                logger.warning(f"order_stats not available for {symbol}: {e}")
                return OrderStatsResponse(symbol=symbol, items=[])

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

    def get_intraday_order_stats(self, symbol: str) -> IntradayOrderStatsResponse:
        """Get current-day order stats from intraday tick data.

        Uses quote.intraday() to aggregate buy/sell orders for today.
        Only available during and after trading hours.
        """
        symbol = validate_symbol(symbol)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            df = stock.quote.intraday(page_size=10000)

            if df is None or df.empty:
                return IntradayOrderStatsResponse(
                    symbol=symbol,
                    date=date.today().isoformat(),
                    buy_orders=0,
                    sell_orders=0,
                    buy_volume=0,
                    sell_volume=0,
                    net_volume=0,
                    ato_volume=0,
                    atc_volume=0,
                    last_updated=datetime.now().isoformat(),
                )

            # Aggregate by match_type
            # match_type column contains: 'ATO', 'Buy', 'Sell', 'ATC'
            buy_mask = df["match_type"] == "Buy"
            sell_mask = df["match_type"] == "Sell"
            ato_mask = df["match_type"] == "ATO"
            atc_mask = df["match_type"] == "ATC"

            buy_orders = int(buy_mask.sum())
            sell_orders = int(sell_mask.sum())
            buy_volume = int(df.loc[buy_mask, "volume"].sum()) if buy_mask.any() else 0
            sell_volume = (
                int(df.loc[sell_mask, "volume"].sum()) if sell_mask.any() else 0
            )
            ato_volume = int(df.loc[ato_mask, "volume"].sum()) if ato_mask.any() else 0
            atc_volume = int(df.loc[atc_mask, "volume"].sum()) if atc_mask.any() else 0

            return IntradayOrderStatsResponse(
                symbol=symbol,
                date=date.today().isoformat(),
                buy_orders=buy_orders,
                sell_orders=sell_orders,
                buy_volume=buy_volume,
                sell_volume=sell_volume,
                net_volume=buy_volume - sell_volume,
                ato_volume=ato_volume,
                atc_volume=atc_volume,
                last_updated=datetime.now().isoformat(),
            )
        except Exception as e:
            logger.error(f"Error fetching intraday order stats for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch intraday order stats: {e}")

    def get_foreign_snapshot(self, symbol: str) -> ForeignSnapshotResponse:
        """Get current foreign investor snapshot from trading_stats.

        Uses company.trading_stats() to get foreign volume, room, ownership.
        This is a snapshot (not historical data).
        """
        symbol = validate_symbol(symbol)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            df = stock.company.trading_stats()

            if df is None or df.empty:
                return ForeignSnapshotResponse(
                    symbol=symbol,
                    foreign_volume=0,
                    foreign_room=0,
                    ownership_ratio=None,
                    total_volume=0,
                    avg_volume_2w=None,
                    foreign_pct_of_volume=None,
                    last_updated=datetime.now().isoformat(),
                )

            # Extract first row (should be single row)
            row = df.iloc[0] if len(df) > 0 else {}

            foreign_vol = int(row.get("foreign_volume", 0) or 0)
            total_vol = int(row.get("total_volume", 0) or 0)

            # Calculate foreign % of total volume
            foreign_pct = (foreign_vol / total_vol * 100) if total_vol > 0 else None

            return ForeignSnapshotResponse(
                symbol=symbol,
                foreign_volume=foreign_vol,
                foreign_room=int(row.get("foreign_room", 0) or 0),
                ownership_ratio=safe_float(row.get("current_holding_ratio")),
                total_volume=total_vol,
                avg_volume_2w=safe_float(row.get("avg_match_volume_2w")),
                foreign_pct_of_volume=foreign_pct,
                last_updated=datetime.now().isoformat(),
            )
        except Exception as e:
            logger.error(f"Error fetching foreign snapshot for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch foreign snapshot: {e}")


# Singleton instance
_trading_service: Optional[TradingService] = None


def get_trading_service() -> TradingService:
    """Get or create TradingService singleton."""
    global _trading_service
    if _trading_service is None:
        _trading_service = TradingService()
    return _trading_service
