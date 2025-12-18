"""Stock data service wrapping vnstock library."""
import logging
import re
from datetime import date
from typing import Optional

import pandas as pd
from vnstock import Vnstock, Listing, Quote, Finance, Trading

from src.stocks.schemas import (
    StockPrice,
    IntradayTick,
    CompanyOverview,
    StockSymbol,
    FinancialRatio,
    IncomeStatementItem,
    BalanceSheetItem,
    PriceBoardItem,
    MarketIndexItem,
    StockDetail,
)

logger = logging.getLogger(__name__)


class StockServiceError(Exception):
    """Custom exception for stock service errors."""

    pass


# Symbol validation pattern: 1-10 uppercase alphanumeric characters
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{1,10}$")


def validate_symbol(symbol: str) -> str:
    """Validate and normalize stock symbol.

    Args:
        symbol: Stock symbol to validate

    Returns:
        Normalized uppercase symbol

    Raises:
        StockServiceError: If symbol is invalid
    """
    normalized = symbol.strip().upper()
    if not SYMBOL_PATTERN.match(normalized):
        raise StockServiceError(f"Invalid symbol format: {symbol}")
    return normalized


class StockService:
    """Service for fetching Vietnamese stock market data via vnstock."""

    def __init__(self, source: str = "VCI"):
        """Initialize service with data source.

        Args:
            source: Data source (VCI, TCBS, SSI). VCI is recommended.
        """
        self.source = source

    def get_history(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1D",
    ) -> list[StockPrice]:
        """Get historical OHLCV data for a stock.

        Args:
            symbol: Stock symbol (e.g., VCB, ACB)
            start: Start date
            end: End date
            interval: Time interval (1D, 1W, 1M)

        Returns:
            List of StockPrice objects
        """
        symbol = validate_symbol(symbol)
        try:
            quote = Quote(symbol=symbol, source=self.source)
            df = quote.history(
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                interval=interval,
            )

            if df is None or df.empty:
                return []

            return self._df_to_stock_prices(df)
        except Exception as e:
            logger.error(f"Error fetching history for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch history for {symbol}: {e}")

    def get_intraday(self, symbol: str, page_size: int = 10000) -> list[IntradayTick]:
        """Get intraday tick data for a stock.

        Args:
            symbol: Stock symbol
            page_size: Number of ticks to fetch

        Returns:
            List of IntradayTick objects
        """
        symbol = validate_symbol(symbol)
        try:
            quote = Quote(symbol=symbol, source=self.source)
            df = quote.intraday(page_size=page_size, show_log=False)

            if df is None or df.empty:
                return []

            return self._df_to_intraday_ticks(df)
        except Exception as e:
            logger.error(f"Error fetching intraday for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch intraday for {symbol}: {e}")

    def get_company_overview(self, symbol: str) -> CompanyOverview:
        """Get company overview information.

        Args:
            symbol: Stock symbol

        Returns:
            CompanyOverview object
        """
        symbol = validate_symbol(symbol)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            overview = stock.company.overview()

            if overview is None or (isinstance(overview, pd.DataFrame) and overview.empty):
                return CompanyOverview(symbol=symbol.upper())

            return self._to_company_overview(symbol, overview)
        except Exception as e:
            logger.error(f"Error fetching company overview for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch company overview for {symbol}: {e}")

    def get_financial_ratios(
        self,
        symbol: str,
        period: str = "year",
        lang: str = "en",
    ) -> list[FinancialRatio]:
        """Get financial ratios for a stock.

        Args:
            symbol: Stock symbol
            period: 'year' or 'quarter'
            lang: Language ('en' or 'vi')

        Returns:
            List of FinancialRatio objects
        """
        symbol = validate_symbol(symbol)
        try:
            finance = Finance(symbol=symbol, source=self.source)
            df = finance.ratio(period=period, lang=lang, dropna=True)

            if df is None or df.empty:
                return []

            return self._df_to_financial_ratios(df, period)
        except Exception as e:
            logger.error(f"Error fetching ratios for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch ratios for {symbol}: {e}")

    def get_income_statement(
        self,
        symbol: str,
        period: str = "year",
        lang: str = "en",
    ) -> list[IncomeStatementItem]:
        """Get income statement data.

        Args:
            symbol: Stock symbol
            period: 'year' or 'quarter'
            lang: Language

        Returns:
            List of IncomeStatementItem objects
        """
        symbol = validate_symbol(symbol)
        try:
            finance = Finance(symbol=symbol, source=self.source)
            df = finance.income_statement(period=period, lang=lang, dropna=True)

            if df is None or df.empty:
                return []

            return self._df_to_income_statements(df, period)
        except Exception as e:
            logger.error(f"Error fetching income statement for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch income statement for {symbol}: {e}")

    def get_balance_sheet(
        self,
        symbol: str,
        period: str = "year",
        lang: str = "en",
    ) -> list[BalanceSheetItem]:
        """Get balance sheet data.

        Args:
            symbol: Stock symbol
            period: 'year' or 'quarter'
            lang: Language

        Returns:
            List of BalanceSheetItem objects
        """
        symbol = validate_symbol(symbol)
        try:
            finance = Finance(symbol=symbol, source=self.source)
            df = finance.balance_sheet(period=period, lang=lang, dropna=True)

            if df is None or df.empty:
                return []

            return self._df_to_balance_sheets(df, period)
        except Exception as e:
            logger.error(f"Error fetching balance sheet for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch balance sheet for {symbol}: {e}")

    def list_symbols(self, exchange: Optional[str] = None) -> list[StockSymbol]:
        """List all stock symbols.

        Args:
            exchange: Filter by exchange (HOSE, HNX, UPCOM). If provided, uses
                     symbols_by_exchange method instead of all_symbols.

        Returns:
            List of StockSymbol objects
        """
        try:
            listing = Listing()

            if exchange:
                # Use dedicated method for exchange filtering
                symbols_series = listing.symbols_by_exchange(exchange.upper())
                if symbols_series is None or (hasattr(symbols_series, "empty") and symbols_series.empty):
                    return []
                # Convert Series to list of StockSymbol
                symbols_list = symbols_series.tolist() if hasattr(symbols_series, "tolist") else list(symbols_series)
                return [StockSymbol(symbol=s, exchange=exchange.upper()) for s in symbols_list]

            # Get all symbols (no exchange column available)
            df = listing.all_symbols()

            if df is None or df.empty:
                return []

            return self._df_to_stock_symbols(df)
        except Exception as e:
            logger.error(f"Error fetching symbols: {e}")
            raise StockServiceError(f"Failed to fetch symbols: {e}")

    def list_symbols_by_group(self, group: str) -> list[str]:
        """List symbols by group (e.g., VN30, HNX30).

        Args:
            group: Group name

        Returns:
            List of symbol strings
        """
        try:
            listing = Listing()
            symbols = listing.symbols_by_group(group.upper())

            if symbols is None:
                return []

            return symbols.tolist() if hasattr(symbols, "tolist") else list(symbols)
        except Exception as e:
            logger.error(f"Error fetching symbols for group {group}: {e}")
            raise StockServiceError(f"Failed to fetch symbols for group {group}: {e}")

    def search_symbols(self, query: str, limit: int = 20) -> list[StockSymbol]:
        """Search stock symbols by ticker or company name.

        Args:
            query: Search query (matches symbol or company name)
            limit: Maximum results to return

        Returns:
            List of matching StockSymbol objects
        """
        if not query or len(query.strip()) < 1:
            return []

        query = query.strip().upper()

        try:
            listing = Listing()
            df = listing.all_symbols()

            if df is None or df.empty:
                return []

            # Filter by symbol or organ_name (case-insensitive)
            mask = df["symbol"].str.upper().str.contains(query, na=False)
            if "organ_name" in df.columns:
                mask |= df["organ_name"].str.upper().str.contains(query, na=False)

            filtered = df[mask].head(limit)

            return self._df_to_stock_symbols(filtered)
        except Exception as e:
            logger.error(f"Error searching symbols for '{query}': {e}")
            raise StockServiceError(f"Failed to search symbols: {e}")

    def get_price_board(self, symbols: list[str]) -> list[PriceBoardItem]:
        """Get real-time price board for multiple symbols.

        Args:
            symbols: List of stock symbols

        Returns:
            List of PriceBoardItem objects
        """
        try:
            trading = Trading()
            df = trading.price_board(
                symbols_list=[s.upper() for s in symbols],
                flatten_columns=True,
                drop_levels=[0],
            )

            if df is None or df.empty:
                return []

            return self._df_to_price_board(df)
        except Exception as e:
            logger.error(f"Error fetching price board: {e}")
            raise StockServiceError(f"Failed to fetch price board: {e}")

    def get_market_indices(self) -> list[MarketIndexItem]:
        """Get market indices data (VN-INDEX, VN30, HNX-INDEX, UPCOM-INDEX).

        Uses Quote.history to get latest closing prices and calculate changes.

        Returns:
            List of MarketIndexItem objects
        """
        # Index symbols and display names
        indices = [
            ("VNINDEX", "VN-INDEX"),
            ("VN30", "VN30"),
            ("HNXINDEX", "HNX-INDEX"),
            ("UPCOMINDEX", "UPCOM-INDEX"),
        ]

        results = []
        for symbol, name in indices:
            try:
                quote = Quote(symbol=symbol, source="VCI")
                # Get last 2 trading days to calculate change
                df = quote.history(start="2025-01-01", end=date.today().isoformat())

                if df is None or df.empty or len(df) < 1:
                    logger.warning(f"No data for index {symbol}")
                    continue

                # Get latest and previous day data
                latest = df.iloc[-1]
                current_value = float(latest["close"])

                if len(df) >= 2:
                    previous = df.iloc[-2]
                    prev_close = float(previous["close"])
                    change = current_value - prev_close
                    change_pct = (change / prev_close) * 100 if prev_close != 0 else 0
                else:
                    change = 0.0
                    change_pct = 0.0

                results.append(
                    MarketIndexItem(
                        symbol=symbol,
                        name=name,
                        value=round(current_value, 2),
                        change=round(change, 2),
                        change_pct=round(change_pct, 2),
                    )
                )
            except Exception as e:
                logger.warning(f"Error fetching index {symbol}: {e}")
                continue

        return results

    def get_stock_detail(self, symbol: str) -> StockDetail:
        """Get comprehensive stock detail data.

        Combines price board, company overview, and financial ratios.

        Args:
            symbol: Stock symbol

        Returns:
            StockDetail object with all available data
        """
        symbol = validate_symbol(symbol)
        result: dict = {"symbol": symbol.upper()}

        # 1. Get price board data
        try:
            trading = Trading()
            price_df = trading.price_board(
                symbols_list=[symbol],
                flatten_columns=True,
                drop_levels=[0],
            )

            if price_df is not None and not price_df.empty:
                row = price_df.iloc[0]
                result.update({
                    "price": self._safe_float(row.get("match_price")),
                    "ceiling": self._safe_float(row.get("ceiling")),
                    "floor": self._safe_float(row.get("floor")),
                    "ref_price": self._safe_float(row.get("ref_price")),
                    "high_price": self._safe_float(row.get("highest")),
                    "low_price": self._safe_float(row.get("lowest")),
                    "volume": int(row.get("accumulated_volume", 0)) if pd.notna(row.get("accumulated_volume")) else None,
                    "trading_value": self._safe_float(row.get("accumulated_value")),
                })

                # Calculate change if we have price and ref_price
                if result.get("price") and result.get("ref_price"):
                    change = result["price"] - result["ref_price"]
                    change_pct = (change / result["ref_price"]) * 100
                    result["change"] = round(change, 2)
                    result["change_pct"] = round(change_pct, 2)

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

                result.update({
                    "company_name": row.get("organ_name") or row.get("short_name") or row.get("company_name"),
                    "exchange": row.get("exchange"),
                    "industry": row.get("icb_name3") or row.get("icb_name2") or row.get("industry"),
                    "issue_share": self._safe_float(row.get("issue_share")),
                    "outstanding_shares": self._safe_float(row.get("outstanding_share")),
                    "description": row.get("company_profile") or row.get("description"),
                    "website": row.get("website"),
                    "employees": row.get("no_employees"),
                    "established_year": row.get("established_year"),
                })

                # Calculate market cap if we have price and issue_share
                if result.get("price") and result.get("issue_share"):
                    market_cap = (result["price"] * 1000 * result["issue_share"]) / 1_000_000_000
                    result["market_cap"] = round(market_cap, 2)

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
                    "eps": self._safe_float(row.get("eps") or row.get("eps_ttm")),
                    "pe": self._safe_float(row.get("pe") or row.get("price_to_earning")),
                    "pb": self._safe_float(row.get("pb") or row.get("price_to_book")),
                    "roe": self._safe_float(row.get("roe")),
                    "roa": self._safe_float(row.get("roa")),
                })

        except Exception as e:
            logger.warning(f"Error fetching financial ratios for {symbol}: {e}")

        # 4. Try to get Beta from Vietnamese ratio data
        try:
            finance = Finance(symbol=symbol, source=self.source)
            ratio_df = finance.ratio(period="year", lang="vi", dropna=True)
            if ratio_df is not None and not ratio_df.empty and "Beta" in ratio_df.columns:
                beta_val = ratio_df["Beta"].iloc[0] if len(ratio_df) > 0 else None
                result["beta"] = self._safe_float(beta_val)
        except Exception:
            pass

        return StockDetail(**result)

    # === Private conversion methods ===

    def _df_to_stock_prices(self, df: pd.DataFrame) -> list[StockPrice]:
        """Convert DataFrame to list of StockPrice."""
        prices = []
        for row in df.to_dict("records"):
            try:
                time_val = row.get("time")
                if isinstance(time_val, pd.Timestamp):
                    time_val = time_val.date()
                elif isinstance(time_val, str):
                    time_val = pd.to_datetime(time_val).date()

                prices.append(
                    StockPrice(
                        time=time_val,
                        open=float(row.get("open", 0)),
                        high=float(row.get("high", 0)),
                        low=float(row.get("low", 0)),
                        close=float(row.get("close", 0)),
                        volume=int(row.get("volume", 0)),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping row due to error: {e}")
                continue
        return prices

    def _df_to_intraday_ticks(self, df: pd.DataFrame) -> list[IntradayTick]:
        """Convert DataFrame to list of IntradayTick."""
        ticks = []
        for row in df.to_dict("records"):
            try:
                ticks.append(
                    IntradayTick(
                        time=pd.to_datetime(row.get("time")),
                        price=float(row.get("price", 0)),
                        volume=int(row.get("volume", 0)),
                        accumulated_vol=int(row.get("accumulated_vol", 0)),
                        accumulated_val=int(row.get("accumulated_val", 0)),
                        match_type=str(row.get("match_type", "")),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping tick due to error: {e}")
                continue
        return ticks

    def _to_company_overview(self, symbol: str, data) -> CompanyOverview:
        """Convert overview data to CompanyOverview."""
        if isinstance(data, pd.DataFrame):
            if data.empty:
                return CompanyOverview(symbol=symbol.upper())
            # DataFrame row - access by column name
            row = data.iloc[0] if len(data) > 0 else {}
            # Convert Series to dict for easier access
            if hasattr(row, "to_dict"):
                row = row.to_dict()
        else:
            row = data if isinstance(data, dict) else {}

        # Handle vnstock column names: company_profile, icb_name3 (industry)
        return CompanyOverview(
            symbol=symbol.upper(),
            company_name=row.get("organ_name") or row.get("company_name") or row.get("organName"),
            exchange=row.get("exchange"),
            industry=row.get("icb_name3") or row.get("icb_name2") or row.get("industry") or row.get("industryName"),
            established_year=row.get("established_year"),
            employees=row.get("employees") or row.get("noEmployees"),
            website=row.get("website"),
            description=row.get("company_profile") or row.get("description") or row.get("companyProfile"),
        )

    def _df_to_stock_symbols(self, df: pd.DataFrame) -> list[StockSymbol]:
        """Convert DataFrame to list of StockSymbol."""
        symbols = []
        for row in df.to_dict("records"):
            try:
                symbols.append(
                    StockSymbol(
                        symbol=str(row.get("symbol", row.get("ticker", ""))),
                        organ_name=row.get("organ_name") or row.get("organName"),
                        exchange=row.get("exchange"),
                        organ_type_code=row.get("organ_type_code"),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping symbol due to error: {e}")
                continue
        return symbols

    def _df_to_financial_ratios(self, df: pd.DataFrame, period: str) -> list[FinancialRatio]:
        """Convert DataFrame to list of FinancialRatio."""
        ratios = []
        for row in df.to_dict("records"):
            try:
                ratios.append(
                    FinancialRatio(
                        year=row.get("year"),
                        quarter=row.get("quarter") if period == "quarter" else None,
                        ticker=row.get("ticker"),
                        roe=row.get("roe") or row.get("ROE"),
                        roa=row.get("roa") or row.get("ROA"),
                        gross_margin=row.get("gross_margin") or row.get("grossMargin"),
                        net_margin=row.get("net_margin") or row.get("netMargin"),
                        pe=row.get("pe") or row.get("PE"),
                        pb=row.get("pb") or row.get("PB"),
                        ps=row.get("ps") or row.get("PS"),
                        current_ratio=row.get("current_ratio") or row.get("currentRatio"),
                        quick_ratio=row.get("quick_ratio") or row.get("quickRatio"),
                        debt_to_equity=row.get("debt_to_equity") or row.get("debtToEquity"),
                        debt_to_assets=row.get("debt_to_assets") or row.get("debtToAssets"),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping ratio due to error: {e}")
                continue
        return ratios

    def _df_to_income_statements(self, df: pd.DataFrame, period: str) -> list[IncomeStatementItem]:
        """Convert DataFrame to list of IncomeStatementItem."""
        items = []
        for row in df.to_dict("records"):
            try:
                items.append(
                    IncomeStatementItem(
                        year=row.get("year"),
                        quarter=row.get("quarter") if period == "quarter" else None,
                        revenue=row.get("revenue") or row.get("netRevenue"),
                        gross_profit=row.get("gross_profit") or row.get("grossProfit"),
                        operating_profit=row.get("operating_profit") or row.get("operatingProfit"),
                        net_income=row.get("net_income") or row.get("netIncome"),
                        eps=row.get("eps") or row.get("EPS"),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping income statement item due to error: {e}")
                continue
        return items

    def _df_to_balance_sheets(self, df: pd.DataFrame, period: str) -> list[BalanceSheetItem]:
        """Convert DataFrame to list of BalanceSheetItem."""
        items = []
        for row in df.to_dict("records"):
            try:
                items.append(
                    BalanceSheetItem(
                        year=row.get("year"),
                        quarter=row.get("quarter") if period == "quarter" else None,
                        total_assets=row.get("total_assets") or row.get("totalAssets"),
                        total_liabilities=row.get("total_liabilities") or row.get("totalLiabilities"),
                        total_equity=row.get("total_equity") or row.get("totalEquity"),
                        cash=row.get("cash") or row.get("cashAndCashEquivalents"),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping balance sheet item due to error: {e}")
                continue
        return items

    def _safe_float(self, value) -> float | None:
        """Convert value to float, returning None for NaN/invalid values."""
        if value is None:
            return None
        if pd.isna(value):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _df_to_price_board(self, df: pd.DataFrame) -> list[PriceBoardItem]:
        """Convert DataFrame to list of PriceBoardItem."""
        items = []
        for row in df.to_dict("records"):
            try:
                items.append(
                    PriceBoardItem(
                        symbol=str(row.get("symbol", row.get("ticker", ""))),
                        # New fields
                        match_price=self._safe_float(row.get("match_price")),
                        highest=self._safe_float(row.get("highest")),
                        lowest=self._safe_float(row.get("lowest")),
                        accumulated_volume=int(row.get("accumulated_volume", 0)) if pd.notna(row.get("accumulated_volume")) else None,
                        accumulated_value=self._safe_float(row.get("accumulated_value")),
                        # Existing fields
                        ceiling=self._safe_float(row.get("ceiling")),
                        floor=self._safe_float(row.get("floor")),
                        ref_price=self._safe_float(row.get("ref_price") or row.get("refPrice")),
                        last_price=self._safe_float(row.get("last_price") or row.get("lastPrice")),
                        last_vol=self._safe_float(row.get("last_vol") or row.get("lastVol")),
                        total_vol=self._safe_float(row.get("total_vol") or row.get("totalVol")),
                        total_val=self._safe_float(row.get("total_val") or row.get("totalVal")),
                        change=self._safe_float(row.get("change")),
                        change_pct=self._safe_float(row.get("change_pct") or row.get("changePct")),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping price board item due to error: {e}")
                continue
        return items


# Singleton instance
_stock_service: Optional[StockService] = None


def get_stock_service(source: str = "VCI") -> StockService:
    """Get or create stock service instance."""
    global _stock_service
    if _stock_service is None:
        _stock_service = StockService(source=source)
    return _stock_service
