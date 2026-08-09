"""Response schemas for supported intraday trading analytics."""

from pydantic import BaseModel


class IntradayOrderStatsResponse(BaseModel):
    """Latest-session statistics aggregated from supported intraday trades."""

    symbol: str
    date: str | None
    buy_orders: int
    sell_orders: int
    buy_volume: int
    sell_volume: int
    net_volume: int
    ato_volume: int
    atc_volume: int
    last_updated: str
