"""Stocks module — post-rip-out.

The domain services (price/company/financial/market/monitor/news/analytics)
were removed with the market surfaces. Only the store-side pieces the chat
lane reads survive here: signal fields, the universe, the trading-day helpers,
and shared exceptions/validators.
"""

from .shared import StockServiceError

__all__ = ["StockServiceError"]
