"""Trading domain module for foreign trading, proprietary trading, and order stats."""

from .service import TradingService, get_trading_service

__all__ = ["TradingService", "get_trading_service"]
