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
    IncomeStatementRow,
    IncomeStatementResponse,
    BalanceSheetItem,
    BalanceSheetRow,
    BalanceSheetResponse,
    CashFlowRow,
    CashFlowResponse,
    PriceBoardItem,
    MarketIndexItem,
    StockDetail,
    ShareholderItem,
    ShareholdersResponse,
    OfficerItem,
    OfficersResponse,
    InsiderDealItem,
    InsiderDealsResponse,
    SectorPerformanceItem,
    SectorPerformanceResponse,
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

    def get_income_statement_detailed(
        self,
        symbol: str,
        period: str = "quarter",
        limit: int = 4,
    ) -> IncomeStatementResponse:
        """Get detailed income statement data for financial table display.

        Args:
            symbol: Stock symbol
            period: 'year' or 'quarter'
            limit: Number of periods to return (default 4)

        Returns:
            IncomeStatementResponse with rows and periods
        """
        symbol = validate_symbol(symbol)
        try:
            finance = Finance(symbol=symbol, source=self.source)
            df = finance.income_statement(period=period, lang="vi", dropna=True)

            if df is None or df.empty:
                return IncomeStatementResponse(symbol=symbol, periods=[], rows=[])

            return self._df_to_income_statement_response(df, symbol, period, limit)
        except Exception as e:
            logger.error(f"Error fetching detailed income statement for {symbol}: {e}")
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

    def get_balance_sheet_detailed(
        self,
        symbol: str,
        period: str = "quarter",
        limit: int = 4,
    ) -> BalanceSheetResponse:
        """Get detailed balance sheet data for financial table display.

        Args:
            symbol: Stock symbol
            period: 'year' or 'quarter'
            limit: Number of periods to return (default 4)

        Returns:
            BalanceSheetResponse with rows and periods
        """
        symbol = validate_symbol(symbol)
        try:
            finance = Finance(symbol=symbol, source=self.source)
            df = finance.balance_sheet(period=period, lang="vi", dropna=True)

            if df is None or df.empty:
                return BalanceSheetResponse(symbol=symbol, periods=[], rows=[])

            return self._df_to_balance_sheet_response(df, symbol, period, limit)
        except Exception as e:
            logger.error(f"Error fetching detailed balance sheet for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch balance sheet for {symbol}: {e}")

    def get_cash_flow_detailed(
        self,
        symbol: str,
        period: str = "quarter",
        limit: int = 4,
    ) -> CashFlowResponse:
        """Get detailed cash flow data for financial table display.

        Args:
            symbol: Stock symbol
            period: 'year' or 'quarter'
            limit: Number of periods to return (default 4)

        Returns:
            CashFlowResponse with rows and periods
        """
        symbol = validate_symbol(symbol)
        try:
            finance = Finance(symbol=symbol, source=self.source)
            df = finance.cash_flow(period=period, lang="vi", dropna=True)

            if df is None or df.empty:
                return CashFlowResponse(symbol=symbol, periods=[], rows=[])

            return self._df_to_cash_flow_response(df, symbol, period, limit)
        except Exception as e:
            logger.error(f"Error fetching detailed cash flow for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch cash flow for {symbol}: {e}")

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

        # 1. Get price board data (includes organ_name for company name)
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
                    "exchange": row.get("exchange"),
                })

                # Get company name from price_board (organ_name field)
                organ_name = row.get("organ_name")
                if organ_name and pd.notna(organ_name):
                    result["company_name"] = str(organ_name)

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

                # Only set company_name from overview if not already set from price_board
                if not result.get("company_name"):
                    company_name = row.get("organ_name") or row.get("short_name") or row.get("company_name")
                    if company_name:
                        result["company_name"] = company_name

                # Only set exchange if not already set
                if not result.get("exchange"):
                    result["exchange"] = row.get("exchange")

                result.update({
                    "industry": row.get("icb_name3") or row.get("icb_name2") or row.get("industry"),
                    "issue_share": self._safe_float(row.get("issue_share")),
                    # Fallback to issue_share if outstanding_share not available
                    "outstanding_shares": self._safe_float(row.get("outstanding_share")) or self._safe_float(row.get("issue_share")),
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

    def get_shareholders(self, symbol: str) -> ShareholdersResponse:
        """Get major shareholders for a stock.

        Args:
            symbol: Stock symbol

        Returns:
            ShareholdersResponse with list of major shareholders
        """
        symbol = validate_symbol(symbol)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            df = stock.company.shareholders()

            if df is None or df.empty:
                return ShareholdersResponse(symbol=symbol, shareholders=[], total_count=0)

            shareholders = []
            for _, row in df.iterrows():
                try:
                    # Handle update_date - convert to string if datetime
                    update_date = row.get("update_date")
                    if update_date is not None and pd.notna(update_date):
                        if hasattr(update_date, "strftime"):
                            update_date = update_date.strftime("%Y-%m-%d")
                        else:
                            update_date = str(update_date)
                    else:
                        update_date = None

                    shareholders.append(ShareholderItem(
                        id=str(row.get("id", "")),
                        name=str(row.get("share_holder", "")),
                        shares=float(row.get("quantity", 0)),
                        ownership_pct=float(row.get("share_own_percent", 0)) * 100,  # Convert to percentage
                        update_date=update_date,
                    ))
                except Exception as e:
                    logger.warning(f"Skipping shareholder row due to error: {e}")
                    continue

            return ShareholdersResponse(
                symbol=symbol,
                shareholders=shareholders,
                total_count=len(shareholders),
            )
        except Exception as e:
            logger.error(f"Error fetching shareholders for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch shareholders for {symbol}: {e}")

    def get_officers(
        self,
        symbol: str,
        filter_by: str = "working",
    ) -> OfficersResponse:
        """Get company officers/management for a stock.

        Args:
            symbol: Stock symbol
            filter_by: Filter by status ('working', 'resigned', 'all')

        Returns:
            OfficersResponse with list of officers
        """
        symbol = validate_symbol(symbol)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            df = stock.company.officers(filter_by=filter_by)

            if df is None or df.empty:
                return OfficersResponse(symbol=symbol, officers=[], total_count=0)

            officers = []
            for _, row in df.iterrows():
                try:
                    # Handle update_date
                    update_date = row.get("update_date")
                    if update_date is not None and pd.notna(update_date):
                        if hasattr(update_date, "strftime"):
                            update_date = update_date.strftime("%Y-%m-%d")
                        else:
                            update_date = str(update_date)
                    else:
                        update_date = None

                    officers.append(OfficerItem(
                        id=str(row.get("id", "")),
                        name=str(row.get("officer_name", "")),
                        position=str(row.get("officer_position", "")),
                        position_short=row.get("position_short_name"),
                        shares=self._safe_float(row.get("quantity")),
                        ownership_pct=self._safe_float(row.get("officer_own_percent")) * 100 if row.get("officer_own_percent") else None,
                        update_date=update_date,
                        status=row.get("type"),
                    ))
                except Exception as e:
                    logger.warning(f"Skipping officer row due to error: {e}")
                    continue

            return OfficersResponse(
                symbol=symbol,
                officers=officers,
                total_count=len(officers),
            )
        except Exception as e:
            logger.error(f"Error fetching officers for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch officers for {symbol}: {e}")

    def get_insider_deals(self, symbol: str) -> InsiderDealsResponse:
        """Get insider trading deals for a stock.

        Args:
            symbol: Stock symbol

        Returns:
            InsiderDealsResponse with list of insider deals
        """
        symbol = validate_symbol(symbol)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            df = stock.company.insider_deals()

            if df is None or df.empty:
                return InsiderDealsResponse(symbol=symbol, deals=[], total_count=0)

            deals = []
            for _, row in df.iterrows():
                try:
                    # Handle announce_date
                    announce_date = row.get("deal_announce_date")
                    if announce_date is not None and pd.notna(announce_date):
                        if hasattr(announce_date, "strftime"):
                            announce_date = announce_date.strftime("%Y-%m-%d")
                        else:
                            announce_date = str(announce_date)
                    else:
                        announce_date = ""

                    deals.append(InsiderDealItem(
                        announce_date=announce_date,
                        action=str(row.get("deal_action", "")),
                        quantity=float(row.get("deal_quantity", 0)),
                        price=self._safe_float(row.get("deal_price")),
                        ratio=self._safe_float(row.get("deal_ratio")),
                    ))
                except Exception as e:
                    logger.warning(f"Skipping insider deal row due to error: {e}")
                    continue

            return InsiderDealsResponse(
                symbol=symbol,
                deals=deals,
                total_count=len(deals),
            )
        except Exception as e:
            logger.error(f"Error fetching insider deals for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch insider deals for {symbol}: {e}")

    def get_sector_performance(self) -> SectorPerformanceResponse:
        """Get market-cap weighted sector performance.

        Uses ICB Level 2 classification (10 sectors).

        Returns:
            SectorPerformanceResponse with sector performance data
        """
        from datetime import datetime

        try:
            listing = Listing()
            trading = Trading()

            # Get industry classification
            industries_df = listing.symbols_by_industries()

            if industries_df is None or industries_df.empty:
                return SectorPerformanceResponse(
                    sectors=[],
                    generated_at=datetime.now(),
                    total_sectors=0
                )

            # Group by ICB Level 2
            # Expected columns: symbol, icb_code2, icb_name2, etc.
            icb_col = 'icb_code2' if 'icb_code2' in industries_df.columns else 'icb_code'
            name_col = 'icb_name2' if 'icb_name2' in industries_df.columns else 'icb_name'

            sectors = {}
            for icb_code in industries_df[icb_col].unique():
                if pd.isna(icb_code):
                    continue
                sector_df = industries_df[industries_df[icb_col] == icb_code]
                icb_name = sector_df[name_col].iloc[0] if name_col in sector_df.columns else str(icb_code)
                symbols = sector_df['symbol'].tolist()
                sectors[icb_code] = {
                    'name': icb_name,
                    'symbols': symbols[:100]  # Limit to avoid rate limits
                }

            results = []
            for icb_code, sector_data in sectors.items():
                symbols = sector_data['symbols']
                if not symbols:
                    continue

                try:
                    # Get price board for sector symbols
                    price_df = trading.price_board(
                        symbols_list=symbols,
                        flatten_columns=True,
                        drop_levels=[0]
                    )

                    if price_df is None or price_df.empty:
                        continue

                    # Calculate market cap weighted change
                    total_cap = 0.0
                    weighted_change = 0.0
                    stock_changes = []

                    for _, row in price_df.iterrows():
                        symbol = row.get('symbol', '')
                        change_pct = self._safe_float(row.get('change_pct')) or 0.0
                        # Market cap from accumulated_value or estimate
                        market_cap = self._safe_float(row.get('accumulated_value')) or 1.0

                        if market_cap > 0:
                            weighted_change += change_pct * market_cap
                            total_cap += market_cap
                            stock_changes.append((symbol, change_pct))

                    if total_cap > 0:
                        avg_change = weighted_change / total_cap
                    else:
                        avg_change = 0.0

                    # Sort for top gainers/losers
                    stock_changes.sort(key=lambda x: x[1], reverse=True)
                    top_gainers = [s[0] for s in stock_changes[:3]]
                    top_losers = [s[0] for s in stock_changes[-3:]]

                    results.append(SectorPerformanceItem(
                        icb_code=str(icb_code),
                        icb_name=sector_data['name'],
                        change_pct=round(avg_change, 2),
                        total_market_cap=round(total_cap / 1_000_000_000, 2),
                        stock_count=len(price_df),
                        top_gainers=top_gainers,
                        top_losers=top_losers,
                    ))
                except Exception as e:
                    logger.warning(f"Error processing sector {icb_code}: {e}")
                    continue

            # Sort by change_pct descending
            results.sort(key=lambda x: x.change_pct, reverse=True)

            return SectorPerformanceResponse(
                sectors=results,
                generated_at=datetime.now(),
                total_sectors=len(results),
            )

        except Exception as e:
            logger.error(f"Error fetching sector performance: {e}")
            raise StockServiceError(f"Failed to fetch sector performance: {e}")

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

    def _df_to_income_statement_response(
        self, df: pd.DataFrame, symbol: str, period: str, limit: int
    ) -> IncomeStatementResponse:
        """Convert vnstock income statement DataFrame to detailed response.

        Maps Vietnamese column names to structured rows for frontend display.
        Supports both regular companies and banks (different column structures).
        """
        # Limit to most recent periods
        df = df.head(limit)

        # Build period labels (e.g., "Q3/2025" or "2024")
        periods = []
        for _, row in df.iterrows():
            year = row.get("Năm", row.get("year", ""))
            if period == "quarter":
                quarter = row.get("Kỳ", row.get("quarter", ""))
                periods.append(f"Q{quarter}/{year}")
            else:
                periods.append(str(year))

        # Detect if this is a bank (has banking-specific columns)
        is_bank = "Thu nhập lãi thuần" in df.columns or "Thu nhập lãi và các khoản tương tự" in df.columns

        # Define row mappings based on company type
        # Format: (id, label, column_names_to_try, level, is_summary)
        if is_bank:
            row_mappings = [
                ("interest_income", "Thu nhập lãi và các khoản tương tự", ["Thu nhập lãi và các khoản tương tự", "Doanh thu (đồng)"], 0, True),
                ("interest_expense", "Chi phí lãi và các khoản tương tự", ["Chi phí lãi và các khoản tương tự"], 1, False),
                ("net_interest_income", "Thu nhập lãi thuần", ["Thu nhập lãi thuần"], 0, True),
                ("service_income", "Thu nhập từ hoạt động dịch vụ", ["Thu nhập từ hoạt động dịch vụ"], 1, False),
                ("service_expense", "Chi phí hoạt động dịch vụ", ["Chi phí hoạt động dịch vụ"], 1, False),
                ("net_service_income", "Lãi thuần từ hoạt động dịch vụ", ["Lãi thuần từ hoạt động dịch vụ"], 0, True),
                ("forex_gold", "Kinh doanh ngoại hối và vàng", ["Kinh doanh ngoại hối và vàng"], 1, False),
                ("trading_securities", "Chứng khoán kinh doanh", ["Chứng khoán kinh doanh"], 1, False),
                ("investment_securities", "Chứng khoán đầu tư", ["Chứng khoán đầu tư"], 1, False),
                ("other_income", "Hoạt động khác", ["Hoạt động khác"], 1, False),
                ("other_expense", "Chi phí hoạt động khác", ["Chi phí hoạt động khác"], 1, False),
                ("net_other", "Lãi/lỗ thuần từ hoạt động khác", ["Lãi/lỗ thuần từ hoạt động khác"], 1, False),
                ("dividend_received", "Cổ tức đã nhận", ["Cố tức đã nhận", "Cổ tức đã nhận"], 1, False),
                ("total_operating_income", "Tổng thu nhập hoạt động", ["Tổng thu nhập hoạt động"], 0, True),
                ("admin_exp", "Chi phí quản lý doanh nghiệp", ["Chi phí quản lý DN"], 1, False),
                ("operating_profit", "LN từ HĐKD trước CF dự phòng", ["LN từ HĐKD trước CF dự phòng"], 0, True),
                ("provision_expense", "Chi phí dự phòng rủi ro tín dụng", ["Chi phí dự phòng rủi ro tín dụng"], 1, False),
                ("ebt", "Lợi nhuận trước thuế", ["LN trước thuế"], 0, True),
                ("tax", "Thuế TNDN", ["Thuế TNDN"], 1, False),
                ("tax_current", "Chi phí thuế TNDN hiện hành", ["Chi phí thuế TNDN hiện hành"], 2, False),
                ("tax_deferred", "Chi phí thuế TNDN hoãn lại", ["Chi phí thuế TNDN hoãn lại"], 2, False),
                ("net_profit", "Lợi nhuận thuần", ["Lợi nhuận thuần"], 0, True),
                ("parent_profit", "Cổ đông của Công ty mẹ", ["Cổ đông của Công ty mẹ"], 1, False),
                ("minority_profit", "Cổ đông thiểu số", ["Cổ đông thiểu số"], 1, False),
                ("eps", "Lãi cơ bản trên cổ phiếu", ["Lãi cơ bản trên cổ phiếu"], 0, True),
            ]
        else:
            # Regular company mappings
            row_mappings = [
                ("revenue", "Doanh thu bán hàng và cung cấp dịch vụ", ["Doanh thu bán hàng và cung cấp dịch vụ", "Doanh thu (đồng)"], 0, True),
                ("deductions", "Các khoản giảm trừ doanh thu", ["Các khoản giảm trừ doanh thu"], 1, False),
                ("net_revenue", "Doanh thu thuần", ["Doanh thu thuần"], 0, True),
                ("cogs", "Giá vốn hàng bán", ["Giá vốn hàng bán"], 1, False),
                ("gross_profit", "Lãi gộp", ["Lãi gộp"], 0, True),
                ("finance_income", "Thu nhập tài chính", ["Thu nhập tài chính"], 1, False),
                ("finance_exp", "Chi phí tài chính", ["Chi phí tài chính"], 1, False),
                ("interest_exp", "Chi phí tiền lãi vay", ["Chi phí tiền lãi vay"], 2, False),
                ("selling_exp", "Chi phí bán hàng", ["Chi phí bán hàng"], 1, False),
                ("admin_exp", "Chi phí quản lý doanh nghiệp", ["Chi phí quản lý DN", "Chi phí quản lý doanh nghiệp"], 1, False),
                ("operating_profit", "Lãi/Lỗ từ hoạt động kinh doanh", ["Lãi/Lỗ từ hoạt động kinh doanh"], 0, True),
                ("other_income", "Thu nhập khác", ["Thu nhập khác"], 1, False),
                ("other_exp", "Chi phí khác", ["Thu nhập/Chi phí khác", "Chi phí khác"], 1, False),
                ("other_profit", "Lợi nhuận khác", ["Lợi nhuận khác"], 1, False),
                ("ebt", "Lợi nhuận trước thuế", ["LN trước thuế", "Lợi nhuận trước thuế"], 0, True),
                ("tax_current", "Chi phí thuế TNDN hiện hành", ["Chi phí thuế TNDN hiện hành"], 1, False),
                ("tax_deferred", "Chi phí thuế TNDN hoãn lại", ["Chi phí thuế TNDN hoãn lại"], 1, False),
                ("net_profit", "Lợi nhuận thuần", ["Lợi nhuận thuần"], 0, True),
                ("parent_profit", "Cổ đông của Công ty mẹ", ["Cổ đông của Công ty mẹ", "Lợi nhuận sau thuế của Cổ đông công ty mẹ (đồng)"], 1, False),
                ("minority_profit", "Cổ đông thiểu số", ["Cổ đông thiểu số"], 1, False),
                ("eps", "Lãi cơ bản trên cổ phiếu", ["Lãi cơ bản trên cổ phiếu"], 0, True),
            ]

        rows = []
        for row_id, label, col_names, level, is_summary in row_mappings:
            values = {}
            for i, period_label in enumerate(periods):
                if i < len(df):
                    row_data = df.iloc[i]
                    val = None
                    # Try each column name in order
                    for col_name in col_names:
                        if col_name in df.columns:
                            val = row_data.get(col_name)
                            if val is not None and not pd.isna(val):
                                break
                    # Convert to millions for display (except EPS which stays as-is)
                    if val is not None and not pd.isna(val):
                        if row_id == "eps":
                            values[period_label] = float(val)  # EPS in VND
                        else:
                            values[period_label] = float(val) / 1_000_000  # Convert to millions
                    else:
                        values[period_label] = None
                else:
                    values[period_label] = None

            # Only add row if it has at least one non-null value
            if any(v is not None for v in values.values()):
                rows.append(IncomeStatementRow(
                    id=row_id,
                    label=label,
                    values=values,
                    level=level,
                    is_header=False,
                    is_summary=is_summary,
                ))

        return IncomeStatementResponse(
            symbol=symbol,
            periods=periods,
            rows=rows,
            unit="Triệu VND",
        )

    def _df_to_balance_sheet_response(
        self,
        df: pd.DataFrame,
        symbol: str,
        period: str,
        limit: int,
    ) -> BalanceSheetResponse:
        """Convert balance sheet DataFrame to BalanceSheetResponse."""
        # Limit the data
        df = df.head(limit)

        # Generate period labels
        periods = []
        for i in range(len(df)):
            row = df.iloc[i]
            year = row.get("Năm") or row.get("year")
            quarter = row.get("Kỳ") or row.get("quarter")
            if period == "quarter" and quarter:
                periods.append(f"Q{int(quarter)}/{int(year)}")
            else:
                periods.append(str(int(year)))

        # Balance sheet row mappings: (id, label, [possible_column_names], level, is_summary)
        row_mappings = [
            ("current_assets", "TÀI SẢN NGẮN HẠN", ["TÀI SẢN NGẮN HẠN (đồng)", "TÀI SẢN NGẮN HẠN"], 0, True),
            ("cash", "Tiền và tương đương tiền", ["Tiền và tương đương tiền (đồng)", "Tiền và tương đương tiền"], 1, False),
            ("short_invest", "Giá trị thuần đầu tư ngắn hạn", ["Giá trị thuần đầu tư ngắn hạn (đồng)", "Giá trị thuần đầu tư ngắn hạn"], 1, False),
            ("receivables", "Các khoản phải thu ngắn hạn", ["Các khoản phải thu ngắn hạn (đồng)", "Các khoản phải thu ngắn hạn"], 1, False),
            ("inventory", "Hàng tồn kho ròng", ["Hàng tồn kho ròng", "Hàng tồn kho, ròng (đồng)"], 1, False),
            ("other_current", "Tài sản lưu động khác", ["Tài sản lưu động khác (đồng)", "Tài sản lưu động khác"], 1, False),
            ("long_assets", "TÀI SẢN DÀI HẠN", ["TÀI SẢN DÀI HẠN (đồng)", "TÀI SẢN DÀI HẠN"], 0, True),
            ("long_receivables", "Phải thu dài hạn", ["Phải thu dài hạn (đồng)", "Phải thu dài hạn"], 1, False),
            ("fixed_assets", "Tài sản cố định", ["Tài sản cố định (đồng)", "Tài sản cố định"], 1, False),
            ("long_invest", "Đầu tư dài hạn", ["Đầu tư dài hạn (đồng)", "Đầu tư dài hạn"], 1, False),
            ("goodwill", "Lợi thế thương mại", ["Lợi thế thương mại"], 1, False),
            ("other_long", "Tài sản dài hạn khác", ["Tài sản dài hạn khác (đồng)", "Tài sản dài hạn khác"], 1, False),
            ("total_assets", "TỔNG CỘNG TÀI SẢN", ["TỔNG CỘNG TÀI SẢN (đồng)", "TỔNG CỘNG TÀI SẢN"], 0, True),
            ("liabilities", "NỢ PHẢI TRẢ", ["NỢ PHẢI TRẢ (đồng)", "NỢ PHẢI TRẢ"], 0, True),
            ("short_debt", "Nợ ngắn hạn", ["Nợ ngắn hạn (đồng)", "Nợ ngắn hạn"], 1, False),
            ("long_debt", "Nợ dài hạn", ["Nợ dài hạn (đồng)", "Nợ dài hạn"], 1, False),
            ("equity", "VỐN CHỦ SỞ HỮU", ["VỐN CHỦ SỞ HỮU (đồng)", "VỐN CHỦ SỞ HỮU"], 0, True),
            ("capital_fund", "Vốn và các quỹ", ["Vốn và các quỹ (đồng)", "Vốn và các quỹ"], 1, False),
            ("owner_capital", "Vốn góp của chủ sở hữu", ["Vốn góp của chủ sở hữu (đồng)", "Vốn góp của chủ sở hữu"], 1, False),
            ("other_fund", "Các quỹ khác", ["Các quỹ khác"], 1, False),
            ("retained", "Lãi chưa phân phối", ["Lãi chưa phân phối (đồng)", "Lãi chưa phân phối"], 1, False),
            ("minority", "LỢI ÍCH CỦA CỔ ĐÔNG THIỂU SỐ", ["LỢI ÍCH CỦA CỔ ĐÔNG THIỂU SỐ", "Cổ đông thiểu số"], 0, True),
            ("total_capital", "TỔNG CỘNG NGUỒN VỐN", ["TỔNG CỘNG NGUỒN VỐN (đồng)", "TỔNG CỘNG NGUỒN VỐN"], 0, True),
        ]

        rows = []
        for row_id, label, col_names, level, is_summary in row_mappings:
            values = {}
            for i, period_label in enumerate(periods):
                if i < len(df):
                    row_data = df.iloc[i]
                    val = None
                    # Try each column name in order
                    for col_name in col_names:
                        if col_name in df.columns:
                            val = row_data.get(col_name)
                            if val is not None and not pd.isna(val):
                                break
                    # Convert to millions for display
                    if val is not None and not pd.isna(val):
                        values[period_label] = float(val) / 1_000_000  # Convert to millions
                    else:
                        values[period_label] = None
                else:
                    values[period_label] = None

            # Only add row if it has at least one non-null value
            if any(v is not None for v in values.values()):
                rows.append(BalanceSheetRow(
                    id=row_id,
                    label=label,
                    values=values,
                    level=level,
                    is_header=level == 0 and is_summary,
                    is_summary=is_summary,
                ))

        return BalanceSheetResponse(
            symbol=symbol,
            periods=periods,
            rows=rows,
            unit="Triệu VND",
        )

    def _df_to_cash_flow_response(
        self,
        df: pd.DataFrame,
        symbol: str,
        period: str,
        limit: int,
    ) -> CashFlowResponse:
        """Convert cash flow DataFrame to CashFlowResponse."""
        # Limit the data
        df = df.head(limit)

        # Generate period labels
        periods = []
        for i in range(len(df)):
            row = df.iloc[i]
            year = row.get("Năm") or row.get("year")
            quarter = row.get("Kỳ") or row.get("quarter")
            if period == "quarter" and quarter:
                periods.append(f"Q{int(quarter)}/{int(year)}")
            else:
                periods.append(str(int(year)))

        # Cash flow row mappings: (id, label, [possible_column_names], level, is_summary)
        row_mappings = [
            # Operating Activities
            ("ebt_cf", "Lãi/Lỗ ròng trước thuế", ["Lãi/Lỗ ròng trước thuế"], 0, True),
            ("depreciation", "Khấu hao TSCĐ", ["Khấu hao TSCĐ"], 1, False),
            ("provision", "Dự phòng RR tín dụng", ["Dự phòng RR tín dụng"], 1, False),
            ("asset_loss", "Lãi/Lỗ từ thanh lý tài sản cố định", ["Lãi/Lỗ từ thanh lý tài sản cố định"], 1, False),
            ("invest_loss", "Lãi/Lỗ từ hoạt động đầu tư", ["Lãi/Lỗ từ hoạt động đầu tư"], 1, False),
            ("interest_income", "Thu nhập lãi", ["Thu nhập lãi"], 1, False),
            ("dividend_income", "Thu lãi và cổ tức", ["Thu lãi và cổ tức"], 1, False),
            ("cfo_before_wc", "Lưu chuyển tiền thuần từ HĐKD trước thay đổi VLĐ", ["Lưu chuyển tiền thuần từ HĐKD trước thay đổi VLĐ"], 0, True),
            ("receivables_change", "Tăng/Giảm các khoản phải thu", ["Tăng/Giảm các khoản phải thu", "_Tăng/Giảm các khoản phải thu"], 1, False),
            ("inventory_change", "Tăng/Giảm hàng tồn kho", ["Tăng/Giảm hàng tồn kho"], 1, False),
            ("payables_change", "Tăng/Giảm các khoản phải trả", ["Tăng/Giảm các khoản phải trả", "_Tăng/Giảm các khoản phải trả"], 1, False),
            ("prepaid_change", "Tăng/Giảm chi phí trả trước", ["Tăng/Giảm chi phí trả trước"], 1, False),
            ("interest_paid", "Chi phí lãi vay đã trả", ["Chi phí lãi vay đã trả"], 1, False),
            ("tax_paid", "Tiền thu nhập doanh nghiệp đã trả", ["Tiền thu nhập doanh nghiệp đã trả"], 1, False),
            ("other_cfo_in", "Tiền thu khác từ các hoạt động kinh doanh", ["Tiền thu khác từ các hoạt động kinh doanh"], 1, False),
            ("other_cfo_out", "Tiền chi khác từ các hoạt động kinh doanh", ["Tiền chi khác từ các hoạt động kinh doanh"], 1, False),
            ("net_cfo", "Lưu chuyển tiền tệ ròng từ các hoạt động SXKD", ["Lưu chuyển tiền tệ ròng từ các hoạt động SXKD"], 0, True),
            # Investing Activities
            ("capex", "Mua sắm TSCĐ", ["Mua sắm TSCĐ"], 1, False),
            ("asset_sale", "Tiền thu được từ thanh lý tài sản cố định", ["Tiền thu được từ thanh lý tài sản cố định"], 1, False),
            ("loan_collect", "Tiền thu hồi cho vay, bán lại các công cụ nợ của đơn vị khác", ["Tiền thu hồi cho vay, bán lại các công cụ nợ của đơn vị khác (đồng)"], 1, False),
            ("invest_other", "Đầu tư vào các doanh nghiệp khác", ["Đầu tư vào các doanh nghiệp khác"], 1, False),
            ("invest_sale", "Tiền thu từ việc bán các khoản đầu tư vào doanh nghiệp khác", ["Tiền thu từ việc bán các khoản đầu tư vào doanh nghiệp khác"], 1, False),
            ("dividend_received", "Tiền thu cổ tức và lợi nhuận được chia", ["Tiền thu cổ tức và lợi nhuận được chia"], 1, False),
            ("net_cfi", "Lưu chuyển từ hoạt động đầu tư", ["Lưu chuyển từ hoạt động đầu tư"], 0, True),
            # Financing Activities
            ("equity_issue", "Tăng vốn cổ phần từ góp vốn và/hoặc phát hành cổ phiếu", ["Tăng vốn cổ phần từ góp vốn và/hoặc phát hành cổ phiếu"], 1, False),
            ("equity_buyback", "Chi trả cho việc mua lại, trả cổ phiếu", ["Chi trả cho việc mua lại, trả cổ phiếu"], 1, False),
            ("borrow_receive", "Tiền thu được các khoản đi vay", ["Tiền thu được các khoản đi vay"], 1, False),
            ("borrow_repay", "Tiền trả các khoản đi vay", ["Tiền trả các khoản đi vay"], 1, False),
            ("lease_payment", "Tiền thanh toán vốn gốc đi thuê tài chính", ["Tiền thanh toán vốn gốc đi thuê tài chính"], 1, False),
            ("dividend_paid", "Cổ tức đã trả", ["Cổ tức đã trả"], 1, False),
            ("net_cff", "Lưu chuyển tiền từ hoạt động tài chính", ["Lưu chuyển tiền từ hoạt động tài chính"], 0, True),
            # Summary
            ("net_change", "Lưu chuyển tiền thuần trong kỳ", ["Lưu chuyển tiền thuần trong kỳ"], 0, True),
            ("cash_begin", "Tiền và tương đương tiền", ["Tiền và tương đương tiền"], 1, False),
            ("fx_effect", "Ảnh hưởng của chênh lệch tỷ giá", ["Ảnh hưởng của chênh lệch tỷ giá"], 1, False),
            ("cash_end", "Tiền và tương đương tiền cuối kỳ", ["Tiền và tương đương tiền cuối kỳ"], 0, True),
        ]

        rows = []
        for row_id, label, col_names, level, is_summary in row_mappings:
            values = {}
            for i, period_label in enumerate(periods):
                if i < len(df):
                    row_data = df.iloc[i]
                    val = None
                    # Try each column name in order
                    for col_name in col_names:
                        if col_name in df.columns:
                            val = row_data.get(col_name)
                            if val is not None and not pd.isna(val):
                                break
                    # Convert to millions for display
                    if val is not None and not pd.isna(val):
                        values[period_label] = float(val) / 1_000_000  # Convert to millions
                    else:
                        values[period_label] = None
                else:
                    values[period_label] = None

            # Only add row if it has at least one non-null value
            if any(v is not None for v in values.values()):
                rows.append(CashFlowRow(
                    id=row_id,
                    label=label,
                    values=values,
                    level=level,
                    is_header=level == 0 and is_summary,
                    is_summary=is_summary,
                ))

        return CashFlowResponse(
            symbol=symbol,
            periods=periods,
            rows=rows,
            unit="Triệu VND",
        )

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
