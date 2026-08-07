"""Stock service facade aggregating domain services."""

import logging
from datetime import date
from typing import Optional

import pandas as pd
from src.core.vnstock_client import Vnstock, Finance, Trading
from src.core.vnstock_client import VnstockUnavailable, VnstockUnsupported

from .price import PriceService
from .company import CompanyService
from .financial import FinancialService
from .market import MarketService
from .schemas.company import StockDetail
from .shared import StockServiceError, validate_symbol, safe_float

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
        """Get comprehensive stock detail data.

        Combines price board, company overview, and financial ratios.
        This is a composite method that orchestrates multiple domain services.
        """
        symbol = validate_symbol(symbol)
        result: dict = {"symbol": symbol.upper()}

        # 1. Get price board data
        try:
            # vnstock 4.x defaults Trading to KBS, whose price_board rejects
            # drop_levels; 3.x defaulted to VCI. Pass the configured source.
            trading = Trading(source=self.source)
            price_df = trading.price_board(
                symbols_list=[symbol],
                flatten_columns=True,
                drop_levels=[0],
            )

            if price_df is not None and not price_df.empty:
                row = price_df.iloc[0]
                result.update({
                    "price": safe_float(row.get("match_price")),
                    "ceiling": safe_float(row.get("ceiling")),
                    "floor": safe_float(row.get("floor")),
                    "ref_price": safe_float(row.get("ref_price")),
                    "high_price": safe_float(row.get("highest")),
                    "low_price": safe_float(row.get("lowest")),
                    "volume": int(row.get("accumulated_volume", 0)) if pd.notna(row.get("accumulated_volume")) else None,
                    "trading_value": safe_float(row.get("accumulated_value")),
                    "exchange": row.get("exchange"),
                })

                organ_name = row.get("organ_name")
                if organ_name and pd.notna(organ_name):
                    result["company_name"] = str(organ_name)

                if result.get("price") and result.get("ref_price"):
                    change = result["price"] - result["ref_price"]
                    change_pct = (change / result["ref_price"]) * 100
                    result["change"] = round(change, 2)
                    result["change_pct"] = round(change_pct, 2)

        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.warning(f"Error fetching price board for {symbol}: {e}")

        # 2. Get company overview
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            overview = stock.company.overview()

            if overview is not None and not (isinstance(overview, pd.DataFrame) and overview.empty):
                if isinstance(overview, pd.DataFrame):
                    row = overview.iloc[0].to_dict() if len(overview) > 0 else {}
                else:
                    row = overview if isinstance(overview, dict) else {}

                if not result.get("company_name"):
                    company_name = row.get("organ_name") or row.get("short_name") or row.get("company_name")
                    if company_name:
                        result["company_name"] = company_name

                if not result.get("exchange"):
                    result["exchange"] = row.get("exchange")

                result.update({
                    "industry": row.get("icb_name3") or row.get("icb_name2") or row.get("industry"),
                    "issue_share": safe_float(row.get("issue_share")),
                    "outstanding_shares": safe_float(row.get("outstanding_share")) or safe_float(row.get("issue_share")),
                    "description": row.get("company_profile") or row.get("description"),
                    "website": row.get("website"),
                    "employees": row.get("no_employees"),
                    "established_year": row.get("established_year"),
                })

                if result.get("price") and result.get("issue_share"):
                    market_cap = (result["price"] * 1000 * result["issue_share"]) / 1_000_000_000
                    result["market_cap"] = round(market_cap, 2)

        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.warning(f"Error fetching company overview for {symbol}: {e}")

        # 3. Get financial ratios (summary)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            ratios = stock.company.ratio_summary()

            if ratios is not None and not (isinstance(ratios, pd.DataFrame) and ratios.empty):
                if isinstance(ratios, pd.DataFrame):
                    row = ratios.iloc[0].to_dict() if len(ratios) > 0 else {}
                else:
                    row = ratios if isinstance(ratios, dict) else {}

                result.update({
                    "eps": safe_float(row.get("eps") or row.get("eps_ttm")),
                    "pe": safe_float(row.get("pe") or row.get("price_to_earning")),
                    "pb": safe_float(row.get("pb") or row.get("price_to_book")),
                    "roe": safe_float(row.get("roe")),
                    "roa": safe_float(row.get("roa")),
                })
                # Dividend yield from ratio_summary (decimal -> percentage)
                div_val = safe_float(row.get("dividend"))
                if div_val is not None:
                    result["dividend_yield"] = div_val * 100

        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.warning(f"Error fetching financial ratios for {symbol}: {e}")

        # 4. Get 52-week high/low from trading_stats
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            trading_stats = stock.company.trading_stats()

            if trading_stats is not None and not (isinstance(trading_stats, pd.DataFrame) and trading_stats.empty):
                if isinstance(trading_stats, pd.DataFrame):
                    row = trading_stats.iloc[0].to_dict() if len(trading_stats) > 0 else {}
                else:
                    row = trading_stats if isinstance(trading_stats, dict) else {}

                # high_price_1y and low_price_1y are in VND (not thousands)
                high_1y = safe_float(row.get("high_price_1y"))
                low_1y = safe_float(row.get("low_price_1y"))

                # Convert from VND to thousands (matching price display format)
                if high_1y:
                    result["high_52_week"] = high_1y / 1000
                if low_1y:
                    result["low_52_week"] = low_1y / 1000

                # avg_match_volume_2w as proxy for avg volume
                avg_vol = row.get("avg_match_volume_2w")
                if avg_vol and pd.notna(avg_vol):
                    result["avg_volume_52_week"] = int(avg_vol)

        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.warning(f"Error fetching trading stats for {symbol}: {e}")

        # 5. Calculate VN30 rank by market cap
        try:
            result["vn30_rank"] = self._get_vn30_rank(symbol, result.get("market_cap"))
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.warning(f"Error calculating VN30 rank for {symbol}: {e}")

        return StockDetail(**result)

    def _get_vn30_rank(self, symbol: str, current_market_cap: Optional[float] = None) -> Optional[int]:
        """Calculate VN30 rank by market cap for a symbol.

        Returns rank (1-30) if symbol is in VN30, None otherwise.
        """
        symbol = symbol.upper()

        # Get VN30 symbols list
        vn30_symbols = self.market.list_symbols_by_group("VN30")
        if not vn30_symbols or symbol not in vn30_symbols:
            return None

        # Get price board for all VN30 symbols to calculate market caps
        try:
            # vnstock 4.x defaults Trading to KBS, whose price_board rejects
            # drop_levels; 3.x defaulted to VCI. Pass the configured source.
            trading = Trading(source=self.source)
            price_df = trading.price_board(
                symbols_list=vn30_symbols,
                flatten_columns=True,
                drop_levels=[0],
            )

            if price_df is None or price_df.empty:
                return None

            # Calculate market cap for each VN30 stock
            # market_cap = match_price * listed_share / 1e9 (billion VND)
            market_caps = []
            for _, row in price_df.iterrows():
                sym = row.get("symbol", "").upper()
                price = safe_float(row.get("match_price"))
                listed_share = safe_float(row.get("listed_share"))

                if price and listed_share:
                    cap = (price * listed_share) / 1e9
                else:
                    cap = 0

                market_caps.append({"symbol": sym, "market_cap": cap})

            # Sort by market cap descending
            market_caps.sort(key=lambda x: x["market_cap"], reverse=True)

            # Find rank for the requested symbol
            for rank, item in enumerate(market_caps, start=1):
                if item["symbol"] == symbol:
                    return rank

            return None
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.warning(f"Error fetching VN30 price board: {e}")
            return None


from functools import lru_cache


@lru_cache(maxsize=1)
def get_stock_service(source: str = "VCI") -> StockService:
    """Get or create stock service instance (thread-safe singleton)."""
    return StockService(source=source)
