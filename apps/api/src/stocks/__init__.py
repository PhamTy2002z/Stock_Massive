"""Stocks module with domain-based architecture.

Domain services:
- price: Historical prices, intraday, price board, market indices
- company: Company overview, shareholders, officers, insider deals
- financial: Financial ratios, income statement, balance sheet, cash flow
- market: Symbol listings, search, sector performance, fund certificates

The StockService facade provides backward-compatible access to all domains.
"""

from .service import StockService, get_stock_service
from .shared import StockServiceError

__all__ = [
    "StockService",
    "get_stock_service",
    "StockServiceError",
]
