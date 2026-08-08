"""Stock service facade aggregating domain services."""

import logging
from datetime import date
from functools import lru_cache
from typing import Optional

from .price import PriceService
from .company import CompanyService
from .financial import FinancialService
from .market import MarketService
from .schemas.company import StockDetail
from .shared import StockServiceError  # noqa: F401  (re-exported for backward compatibility)

logger = logging.getLogger(__name__)


class StockService:
    """Facade service aggregating all domain services.

    Provides backward-compatible interface while delegating to domain services.
    """

    def __init__(self, source: str = "VCI"):
        """Initialize facade with domain services."""
        self.source = source
        self.price = PriceService(source)
        self.company = CompanyService(source)
        self.financial = FinancialService(source)
        self.market = MarketService(source)

    # === Price domain delegates ===

    def get_history(self, symbol: str, start: date, end: date, interval: str = "1D"):
        """Delegate to price service."""
        return self.price.get_history(symbol, start, end, interval)

    def get_intraday(self, symbol: str, page_size: int = 10000):
        """Delegate to price service."""
        return self.price.get_intraday(symbol, page_size)

    def get_price_board(self, symbols: list[str]):
        """Delegate to price service."""
        return self.price.get_price_board(symbols)

    def get_market_indices(self):
        """Delegate to price service."""
        return self.price.get_market_indices()

    # === Company domain delegates ===

    def get_company_overview(self, symbol: str):
        """Delegate to company service."""
        return self.company.get_company_overview(symbol)

    def get_shareholders(self, symbol: str):
        """Delegate to company service."""
        return self.company.get_shareholders(symbol)

    def get_officers(self, symbol: str, filter_by: str = "working"):
        """Delegate to company service."""
        return self.company.get_officers(symbol, filter_by)

    def get_insider_deals(self, symbol: str):
        """Delegate to company service."""
        return self.company.get_insider_deals(symbol)

    def get_ratio_summary(self, symbol: str):
        """Delegate to company service."""
        return self.company.get_ratio_summary(symbol)

    def get_trading_stats(self, symbol: str):
        """Delegate to company service."""
        return self.company.get_trading_stats(symbol)

    # === Price domain delegates (advanced) ===

    def get_price_depth(self, symbol: str):
        """Delegate to price service."""
        return self.price.get_price_depth(symbol)

    # === Financial domain delegates ===

    def get_financial_ratios(self, symbol: str, period: str = "year", lang: str = "en"):
        """Delegate to financial service."""
        return self.financial.get_financial_ratios(symbol, period, lang)

    def get_income_statement(self, symbol: str, period: str = "year", lang: str = "en"):
        """Delegate to financial service."""
        return self.financial.get_income_statement(symbol, period, lang)

    def get_income_statement_detailed(self, symbol: str, period: str = "quarter", limit: int = 4):
        """Delegate to financial service."""
        return self.financial.get_income_statement_detailed(symbol, period, limit)

    def get_balance_sheet(self, symbol: str, period: str = "year", lang: str = "en"):
        """Delegate to financial service."""
        return self.financial.get_balance_sheet(symbol, period, lang)

    def get_balance_sheet_detailed(self, symbol: str, period: str = "quarter", limit: int = 4):
        """Delegate to financial service."""
        return self.financial.get_balance_sheet_detailed(symbol, period, limit)

    def get_cash_flow_detailed(self, symbol: str, period: str = "quarter", limit: int = 4):
        """Delegate to financial service."""
        return self.financial.get_cash_flow_detailed(symbol, period, limit)

    def get_health_score(self, symbol: str):
        """Delegate to financial service - health score calculation."""
        return self.financial.get_health_score(symbol)

    def get_trend_metrics(self, symbol: str, periods: int = 8):
        """Delegate to financial service - trend metrics for charts."""
        return self.financial.get_trend_metrics(symbol, periods)

    def get_fcf_analysis(self, symbol: str):
        """Delegate to financial service - FCF analysis."""
        return self.financial.get_fcf_analysis(symbol)

    def get_sector_peers(self, symbol: str, limit: int = 5):
        """Delegate to financial service - sector peer comparison."""
        return self.financial.get_sector_peers(symbol, limit)

    # === Market domain delegates ===

    def list_symbols(self, exchange: Optional[str] = None):
        """Delegate to market service."""
        return self.market.list_symbols(exchange)

    def list_symbols_by_group(self, group: str):
        """Delegate to market service."""
        return self.market.list_symbols_by_group(group)

    def search_symbols(self, query: str, limit: int = 20):
        """Delegate to market service."""
        return self.market.search_symbols(query, limit)

    def get_sector_performance(self):
        """Delegate to market service."""
        return self.market.get_sector_performance()

    def get_fund_certificates(self, fund_type: Optional[str] = None):
        """Delegate to market service."""
        return self.market.get_fund_certificates(fund_type)

    def get_vn30_overview(self):
        """Delegate to market service."""
        return self.market.get_vn30_overview()

    # === Composite methods (cross-domain) ===

    def get_stock_detail(self, symbol: str) -> StockDetail:
        """Delegate to company service."""
        return self.company.get_stock_detail(symbol)


@lru_cache(maxsize=1)
def get_stock_service(source: str = "VCI") -> StockService:
    """Get or create stock service instance (thread-safe singleton)."""
    return StockService(source=source)
