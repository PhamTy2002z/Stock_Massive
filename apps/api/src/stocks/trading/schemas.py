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
