"""Trading domain schemas for money flow data."""

from datetime import date
from typing import Optional

from pydantic import BaseModel


# === Foreign Trading Schemas ===


class ForeignTradingItem(BaseModel):
    """Single day foreign trading data."""

    date: str
    net_volume: int = 0
    net_value: int = 0
    buy_volume: int = 0
    buy_value: int = 0
    sell_volume: int = 0
    sell_value: int = 0
    remaining_room: Optional[int] = None
    ownership_pct: Optional[float] = None


class ForeignTradingResponse(BaseModel):
    """Response for foreign trading endpoint."""

    symbol: str
    items: list[ForeignTradingItem]
    total_net_volume: int = 0
    total_net_value: int = 0


# === Proprietary Trading Schemas ===


class PropTradingItem(BaseModel):
    """Single day proprietary trading data."""

    date: str
    buy_volume: float = 0
    sell_volume: float = 0
    net_volume: float = 0
    net_value: float = 0


class PropTradingResponse(BaseModel):
    """Response for proprietary trading endpoint."""

    symbol: str
    items: list[PropTradingItem]
    total_net_volume: float = 0


# === Order Stats Schemas ===


class OrderStatsItem(BaseModel):
    """Single day order statistics."""

    date: str
    buy_orders: int = 0
    sell_orders: int = 0
    buy_volume: int = 0
    sell_volume: int = 0
    avg_buy_order: float = 0
    avg_sell_order: float = 0


class OrderStatsResponse(BaseModel):
    """Response for order stats endpoint."""

    symbol: str
    items: list[OrderStatsItem]


# === Intraday Order Stats Schemas (Real-time from quote.intraday) ===


class IntradayOrderStatsResponse(BaseModel):
    """Current-day order statistics from intraday tick data."""

    symbol: str
    date: str  # Current trading date (YYYY-MM-DD)
    buy_orders: int
    sell_orders: int
    buy_volume: int
    sell_volume: int
    net_volume: int
    ato_volume: int  # Auction at open
    atc_volume: int  # Auction at close
    last_updated: str  # ISO timestamp


# === Foreign Snapshot Schemas (from company.trading_stats) ===


class ForeignSnapshotResponse(BaseModel):
    """Snapshot of foreign investor activity from trading_stats."""

    symbol: str
    foreign_volume: int  # Today's foreign trading volume
    foreign_room: int  # Remaining foreign ownership room
    ownership_ratio: float | None  # Current foreign ownership (0-1)
    total_volume: int  # Today's total trading volume
    avg_volume_2w: float | None  # 2-week average volume
    foreign_pct_of_volume: float | None  # Foreign volume as % of total
    last_updated: str  # ISO timestamp
