"""Service for market overview data aggregation."""

import asyncio
import logging
from datetime import date, datetime
from typing import Any

from vnstock import Listing, Trading

from .schemas import (
    ForeignFlowData,
    ForeignFlowItem,
    MarketBreadth,
    MarketOverviewResponse,
    TopMoverItem,
    TopVolumeItem,
)
from ..shared import safe_float

logger = logging.getLogger(__name__)

# 100ms delay between VCI calls to avoid rate limit
VCI_DELAY = 0.1


class MarketOverviewService:
    """Service for aggregating market overview data with rate limit protection."""

    def __init__(self, source: str = "VCI"):
        self.source = source

    async def get_market_overview(self) -> MarketOverviewResponse:
        """Aggregate all market overview data with sequential VCI calls.

        Returns partial data on individual failures (graceful degradation).
        """
        # Initialize with defaults for partial response
        breadth = MarketBreadth(advances=0, declines=0, unchanged=0, total=0)
        top_gainers: list[TopMoverItem] = []
        top_losers: list[TopMoverItem] = []
        foreign_flow = ForeignFlowData(net_buy=[], net_sell=[], total_net_value=0)
        top_volume: list[TopVolumeItem] = []

        try:
            from vnstock_data import Top
            top = Top(source=self.source)
            today = date.today().strftime("%Y-%m-%d")

            # 1. Top gainers
            try:
                gainers_df = top.gainer(index="VNINDEX", limit=5)
                top_gainers = self._parse_movers(gainers_df)
            except Exception as e:
                logger.warning(f"Failed to fetch top gainers: {e}")
            await asyncio.sleep(VCI_DELAY)

            # 2. Top losers
            try:
                losers_df = top.loser(index="VNINDEX", limit=5)
                top_losers = self._parse_movers(losers_df)
            except Exception as e:
                logger.warning(f"Failed to fetch top losers: {e}")
            await asyncio.sleep(VCI_DELAY)

            # 3. Foreign buy
            foreign_buy_df = None
            try:
                foreign_buy_df = top.foreign_buy(date=today)
            except Exception as e:
                logger.warning(f"Failed to fetch foreign buy: {e}")
            await asyncio.sleep(VCI_DELAY)

            # 4. Foreign sell
            foreign_sell_df = None
            try:
                foreign_sell_df = top.foreign_sell(date=today)
            except Exception as e:
                logger.warning(f"Failed to fetch foreign sell: {e}")
            await asyncio.sleep(VCI_DELAY)

            # Parse foreign flow
            foreign_flow = self._parse_foreign(foreign_buy_df, foreign_sell_df)

            # 5. Top volume
            try:
                volume_df = top.volume(index="VNINDEX", limit=5)
                top_volume = self._parse_volume(volume_df)
            except Exception as e:
                logger.warning(f"Failed to fetch top volume: {e}")
            await asyncio.sleep(VCI_DELAY)

            # 6. Market breadth from VN30 price board
            breadth = await self._calculate_breadth()

        except Exception as e:
            logger.error(f"Market overview error: {e}")
            # Return partial data already collected

        return MarketOverviewResponse(
            market_breadth=breadth,
            top_gainers=top_gainers,
            top_losers=top_losers,
            foreign_flow=foreign_flow,
            top_volume=top_volume,
            generated_at=datetime.now(),
        )

    async def _calculate_breadth(self) -> MarketBreadth:
        """Calculate market breadth from VN30 price board."""
        try:
            listing = Listing()
            trading = Trading()

            # Use VN30 for breadth calculation (smaller dataset, faster)
            symbols = listing.symbols_by_group("VN30")
            if symbols is None or (hasattr(symbols, "empty") and symbols.empty):
                return MarketBreadth(advances=0, declines=0, unchanged=0, total=0)

            symbols_list = symbols.tolist() if hasattr(symbols, "tolist") else list(symbols)

            df = trading.price_board(
                symbols_list=symbols_list,
                flatten_columns=True,
                drop_levels=[0],
            )

            if df is None or df.empty:
                return MarketBreadth(advances=0, declines=0, unchanged=0, total=0)

            # Calculate based on match_price vs ref_price
            advances = len(df[df["match_price"] > df["ref_price"]])
            declines = len(df[df["match_price"] < df["ref_price"]])
            unchanged = len(df[df["match_price"] == df["ref_price"]])

            return MarketBreadth(
                advances=advances,
                declines=declines,
                unchanged=unchanged,
                total=advances + declines + unchanged,
            )
        except Exception as e:
            logger.warning(f"Breadth calculation error: {e}")
            return MarketBreadth(advances=0, declines=0, unchanged=0, total=0)

    def _parse_movers(self, df: Any) -> list[TopMoverItem]:
        """Parse top gainers/losers DataFrame."""
        if df is None or (hasattr(df, "empty") and df.empty):
            return []

        items: list[TopMoverItem] = []
        for _, row in df.head(5).iterrows():
            symbol = str(row.get("symbol", ""))
            if not symbol:
                continue

            price = safe_float(row.get("last_price", 0))
            change_pct = safe_float(row.get("price_change_pct_1d", 0))
            volume = row.get("accumulated_volume")

            items.append(
                TopMoverItem(
                    symbol=symbol,
                    price=price or 0.0,
                    change_pct=change_pct or 0.0,
                    volume=int(volume) if volume else None,
                )
            )
        return items

    def _parse_foreign(
        self, buy_df: Any, sell_df: Any
    ) -> ForeignFlowData:
        """Parse foreign flow DataFrames."""
        net_buy: list[ForeignFlowItem] = []
        net_sell: list[ForeignFlowItem] = []
        total_buy = 0.0
        total_sell = 0.0

        if buy_df is not None and not (hasattr(buy_df, "empty") and buy_df.empty):
            for _, row in buy_df.head(5).iterrows():
                symbol = str(row.get("symbol", ""))
                if not symbol:
                    continue
                val = safe_float(row.get("net_value", 0)) or 0.0
                net_buy.append(ForeignFlowItem(symbol=symbol, net_value=val))
                total_buy += val

        if sell_df is not None and not (hasattr(sell_df, "empty") and sell_df.empty):
            for _, row in sell_df.head(5).iterrows():
                symbol = str(row.get("symbol", ""))
                if not symbol:
                    continue
                val = safe_float(row.get("net_value", 0)) or 0.0
                net_sell.append(ForeignFlowItem(symbol=symbol, net_value=val))
                total_sell += val

        return ForeignFlowData(
            net_buy=net_buy,
            net_sell=net_sell,
            # net_sell values are typically negative
            total_net_value=total_buy + total_sell,
        )

    def _parse_volume(self, df: Any) -> list[TopVolumeItem]:
        """Parse top volume DataFrame."""
        if df is None or (hasattr(df, "empty") and df.empty):
            return []

        items: list[TopVolumeItem] = []
        for _, row in df.head(5).iterrows():
            symbol = str(row.get("symbol", ""))
            if not symbol:
                continue

            price = safe_float(row.get("last_price", 0)) or 0.0
            volume = int(row.get("accumulated_volume", 0) or 0)
            value = safe_float(row.get("accumulated_value", 0)) or 0.0

            items.append(
                TopVolumeItem(
                    symbol=symbol,
                    price=price,
                    volume=volume,
                    value=value,
                )
            )
        return items
