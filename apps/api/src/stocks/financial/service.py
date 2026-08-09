"""Financial domain service for financial statements and ratios."""

import logging
import re
from functools import lru_cache
import statistics
from typing import Optional

import pandas as pd
from src.core.vnstock_client import Finance, Listing
from src.core.vnstock_client import VnstockUnavailable, VnstockUnsupported

from ..schemas.financial import (
    FinancialRatio,
    IncomeStatementItem,
    IncomeStatementRow,
    IncomeStatementResponse,
    BalanceSheetItem,
    BalanceSheetRow,
    BalanceSheetResponse,
    CashFlowRow,
    CashFlowResponse,
    HealthScoreResponse,
    TrendMetricsResponse,
    FCFAnalysisResponse,
    SectorPeersResponse,
    SectorMedian,
    PeerMetrics,
)
from ..shared import (
    safe_float_millions,
    StockServiceError,
    fetch_industry_mapping,
    safe_float,
    validate_symbol,
)
from .health_scoring import build_health_score_response
from .ratio_frame import is_wide_ratio_frame, wide_ratio_frame_to_records
from .cache import (
    RATIO_HISTORY_EMPTY_TTL,
    SECTOR_PEERS_PARTIAL_TTL,
    ratio_history_cache,
    sector_peers_cache,
)

logger = logging.getLogger(__name__)

# Target plus at least two peers, so a sector median describes the sector rather
# than the target itself.
MIN_PEERS_FOR_MEDIAN = 3

# The default VCI feed still answers ratio queries with 2018 quarters; KBS is
# the source that returns the current reporting period.
RATIO_SOURCE = "KBS"


class FinancialService:
    """Service for financial data: ratios, income, balance sheet, cash flow."""

    def __init__(self, source: str = "VCI"):
        """Initialize financial service with data source."""
        self.source = source

    def get_financial_ratios(
        self,
        symbol: str,
        period: str = "year",
        lang: str = "en",
    ) -> list[FinancialRatio]:
        """Get financial ratios for a stock."""
        symbol = validate_symbol(symbol)
        try:
            finance = Finance(symbol=symbol, source=self.source)
            df = finance.ratio(period=period, lang=lang, dropna=True)

            if df is None or df.empty:
                return []

            return self._df_to_financial_ratios(df, period)
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching ratios for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch ratios for {symbol}: {e}")

    def get_income_statement(
        self,
        symbol: str,
        period: str = "year",
        lang: str = "en",
    ) -> list[IncomeStatementItem]:
        """Get income statement data (simplified)."""
        symbol = validate_symbol(symbol)
        try:
            finance = Finance(symbol=symbol, source=self.source)
            df = finance.income_statement(period=period, lang=lang, dropna=True)

            if df is None or df.empty:
                return []

            return self._df_to_income_statements(df, period)
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching income statement for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch income statement for {symbol}: {e}")

    def get_income_statement_detailed(
        self,
        symbol: str,
        period: str = "quarter",
        limit: int = 4,
    ) -> IncomeStatementResponse:
        """Get detailed income statement data for financial table display."""
        symbol = validate_symbol(symbol)
        try:
            finance = Finance(symbol=symbol, source=self.source)
            df = finance.income_statement(period=period, lang="vi", dropna=True)

            if df is None or df.empty:
                return IncomeStatementResponse(symbol=symbol, periods=[], rows=[])

            return self._df_to_income_statement_response(df, symbol, period, limit)
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching detailed income statement for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch income statement for {symbol}: {e}")

    def get_balance_sheet(
        self,
        symbol: str,
        period: str = "year",
        lang: str = "en",
    ) -> list[BalanceSheetItem]:
        """Get balance sheet data (simplified)."""
        symbol = validate_symbol(symbol)
        try:
            finance = Finance(symbol=symbol, source=self.source)
            df = finance.balance_sheet(period=period, lang=lang, dropna=True)

            if df is None or df.empty:
                return []

            return self._df_to_balance_sheets(df, period)
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching balance sheet for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch balance sheet for {symbol}: {e}")

    def get_balance_sheet_detailed(
        self,
        symbol: str,
        period: str = "quarter",
        limit: int = 4,
    ) -> BalanceSheetResponse:
        """Get detailed balance sheet data for financial table display."""
        symbol = validate_symbol(symbol)
        try:
            finance = Finance(symbol=symbol, source=self.source)
            df = finance.balance_sheet(period=period, lang="vi", dropna=True)

            if df is None or df.empty:
                return BalanceSheetResponse(symbol=symbol, periods=[], rows=[])

            return self._df_to_balance_sheet_response(df, symbol, period, limit)
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching detailed balance sheet for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch balance sheet for {symbol}: {e}")

    def get_cash_flow_detailed(
        self,
        symbol: str,
        period: str = "quarter",
        limit: int = 4,
    ) -> CashFlowResponse:
        """Get detailed cash flow data for financial table display."""
        symbol = validate_symbol(symbol)
        try:
            finance = Finance(symbol=symbol, source=self.source)
            df = finance.cash_flow(period=period, lang="vi", dropna=True)

            if df is None or df.empty:
                return CashFlowResponse(symbol=symbol, periods=[], rows=[])

            return self._df_to_cash_flow_response(df, symbol, period, limit)
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching detailed cash flow for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch cash flow for {symbol}: {e}")

    # --- Converter methods ---

    def _df_to_financial_ratios(self, df: pd.DataFrame, period: str) -> list[FinancialRatio]:
        """Convert DataFrame to list of FinancialRatio."""
        ratios = []
        for row in df.to_dict("records"):
            try:
                year_report = row.get("yearReport") or row.get("year")
                length_report = row.get("lengthReport") or (4 if period == "year" else row.get("quarter"))

                # Keyword names must match FinancialRatio exactly: pydantic drops
                # unknown keywords without complaining, so a near-miss like
                # `price_to_earning` for `pe` serves null for every ratio while
                # the endpoint still answers 200.
                ratios.append(
                    FinancialRatio(
                        year=int(year_report) if year_report else None,
                        quarter=int(length_report) if length_report and period == "quarter" else None,
                        pe=safe_float(row.get("priceToEarning") or row.get("P/E")),
                        pb=safe_float(row.get("priceToBook") or row.get("P/B")),
                        roe=safe_float(row.get("roe") or row.get("ROE")),
                        roa=safe_float(row.get("roa") or row.get("ROA")),
                        current_ratio=safe_float(row.get("currentPayment") or row.get("Current ratio")),
                        quick_ratio=safe_float(row.get("quickPayment") or row.get("Quick ratio")),
                        debt_to_equity=safe_float(row.get("debtOnEquity") or row.get("D/E")),
                        debt_to_assets=safe_float(row.get("debtOnAsset") or row.get("D/A")),
                        gross_margin=safe_float(row.get("grossProfitMargin") or row.get("Gross margin")),
                        net_margin=safe_float(row.get("postTaxMargin") or row.get("Net margin")),
                    )
                )
            except (VnstockUnavailable, VnstockUnsupported):
                # Upstream quota/capability problems carry their own meaning;
                # don't flatten them into a generic service error.
                raise
            except Exception as e:
                logger.warning(f"Skipping ratio row due to error: {e}")
                continue
        return ratios

    # --- vnstock 4.x statement layout ---
    #
    # 3.x returned one row per period with line items as columns; 4.x returns one
    # row per line item (`item`, `item_en`, `item_id`) with periods as columns
    # ("2026-Q2", "2025-Q4", ...). Every converter below reads that layout.

    _PERIOD_COLUMN = re.compile(r"^(?P<year>\d{4})(?:-Q(?P<quarter>[1-4]))?$")
    _META_COLUMNS = ("item", "item_en", "item_id")

    # The two summary converters below used to read the 3.x column names, so
    # they returned one object per *line item* with every field None — 25 rows
    # of nulls that still answered 200, so nothing flagged them.

    def _pivot_by_period(self, df: pd.DataFrame) -> list[tuple[str, Optional[int], Optional[int], dict]]:
        """Regroup an item-per-row frame into one (column, year, quarter, {item_id: value}) per period."""
        periods = []
        for col in df.columns:
            match = self._PERIOD_COLUMN.match(str(col))
            if not match:
                continue
            year = int(match.group("year"))
            quarter = int(match.group("quarter")) if match.group("quarter") else None
            periods.append((col, year, quarter))

        records = df.to_dict("records")
        result = []
        for col, year, quarter in periods:
            values = {
                str(record.get("item_id")): record.get(col)
                for record in records
                if record.get("item_id")
            }
            result.append((col, year, quarter, values))
        return result

    def _df_to_income_statements(self, df: pd.DataFrame, period: str) -> list[IncomeStatementItem]:
        """Convert DataFrame to list of IncomeStatementItem, one per period."""
        items = []
        for _, year, quarter, values in self._pivot_by_period(df):
            items.append(
                IncomeStatementItem(
                    year=year,
                    quarter=quarter if period == "quarter" else None,
                    revenue=safe_float(values.get("net_sales")),
                    gross_profit=safe_float(values.get("gross_profit")),
                    operating_profit=safe_float(values.get("operating_profit_loss")),
                    net_income=safe_float(values.get("net_profit_loss_after_tax")),
                    eps=safe_float(values.get("eps_basic_vnd")),
                )
            )
        return items

    def _df_to_balance_sheets(self, df: pd.DataFrame, period: str) -> list[BalanceSheetItem]:
        """Convert DataFrame to list of BalanceSheetItem, one per period."""
        items = []
        for _, year, quarter, values in self._pivot_by_period(df):
            items.append(
                BalanceSheetItem(
                    year=year,
                    quarter=quarter if period == "quarter" else None,
                    total_assets=safe_float(values.get("total_assets")),
                    total_liabilities=safe_float(values.get("liabilities")),
                    total_equity=safe_float(values.get("owners_equity")),
                    cash=safe_float(values.get("cash_and_cash_equivalents")),
                )
            )
        return items


    def _period_columns(self, df: pd.DataFrame, limit: int) -> list[tuple[str, str]]:
        """Return [(column, display label)] for the newest `limit` periods."""
        found = []
        for col in df.columns:
            match = self._PERIOD_COLUMN.match(str(col))
            if not match:
                continue
            year, quarter = match.group("year"), match.group("quarter")
            found.append((col, f"Q{quarter}/{year}" if quarter else year))
        return found[:limit]

    def _statement_rows(self, df: pd.DataFrame, columns: list[tuple[str, str]]) -> list[dict]:
        """Build one row dict per line item, values in millions of VND."""
        rows = []
        seen_ids: dict[str, int] = {}

        for record in df.to_dict("records"):
            label = str(record.get("item") or record.get("item_en") or "").strip()
            if not label:
                continue

            # Balance sheets repeat some item_ids (e.g. short_term_investments
            # appears at two depths), so disambiguate rather than collide.
            base_id = str(record.get("item_id") or label)
            seen_ids[base_id] = seen_ids.get(base_id, 0) + 1
            row_id = base_id if seen_ids[base_id] == 1 else f"{base_id}_{seen_ids[base_id]}"

            values: dict[str, Optional[float]] = {}
            for col, period_label in columns:
                values[period_label] = safe_float_millions(record.get(col))

            if any(v is not None for v in values.values()):
                rows.append({"id": row_id, "label": label, "values": values})

        return rows

    def _df_to_income_statement_response(
        self, df: pd.DataFrame, symbol: str, period: str, limit: int
    ) -> IncomeStatementResponse:
        """Convert DataFrame to IncomeStatementResponse for detailed view."""
        columns = self._period_columns(df, limit)
        rows = self._statement_rows(df, columns)
        return IncomeStatementResponse(
            symbol=symbol,
            periods=[label for _, label in columns],
            rows=[IncomeStatementRow(**row) for row in rows],
            unit="Triệu VND",
        )

    def _df_to_balance_sheet_response(
        self, df: pd.DataFrame, symbol: str, period: str, limit: int
    ) -> BalanceSheetResponse:
        """Convert DataFrame to BalanceSheetResponse for detailed view."""
        columns = self._period_columns(df, limit)
        rows = self._statement_rows(df, columns)
        return BalanceSheetResponse(
            symbol=symbol,
            periods=[label for _, label in columns],
            rows=[BalanceSheetRow(**row) for row in rows],
            unit="Triệu VND",
        )

    def _df_to_cash_flow_response(
        self, df: pd.DataFrame, symbol: str, period: str, limit: int
    ) -> CashFlowResponse:
        """Convert DataFrame to CashFlowResponse for detailed view."""
        columns = self._period_columns(df, limit)
        rows = self._statement_rows(df, columns)
        return CashFlowResponse(
            symbol=symbol,
            periods=[label for _, label in columns],
            rows=[CashFlowRow(**row) for row in rows],
            unit="Triệu VND",
        )


    def _flatten_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Flatten MultiIndex columns from vnstock API.

        Converts ('Meta', 'yearReport') -> 'yearReport'
        Converts ('Chỉ tiêu...', 'ROE (%)') -> 'ROE (%)'
        """
        if df is None or df.empty:
            return df

        if isinstance(df.columns, pd.MultiIndex):
            # Use the second level (actual field name)
            df.columns = [col[1] if isinstance(col, tuple) else col for col in df.columns]
        return df

    def get_ratio_history(
        self,
        symbol: str,
        periods: int = 8,
    ) -> list[dict]:
        """Get historical ratio data for trend analysis.

        Args:
            symbol: Stock symbol
            periods: Number of quarters to fetch (default: 8)

        Returns:
            List of ratio dicts ordered by most recent first, each keyed by the
            provider's metric ids (`pe_ratio`, `roe_trailling`, ...).
        """
        symbol = validate_symbol(symbol)
        cache_key = f"{symbol}:{periods}"
        cached = ratio_history_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            finance = Finance(symbol=symbol, source=RATIO_SOURCE)
            df = finance.ratio(period="quarter", lang="en", dropna=True)

            if df is None or df.empty:
                ratio_history_cache.set(cache_key, [], ttl=RATIO_HISTORY_EMPTY_TTL)
                return []

            # Flatten MultiIndex columns
            df = self._flatten_columns(df)

            if is_wide_ratio_frame(df):
                records = wide_ratio_frame_to_records(df, periods)
            else:
                # A period-per-row frame is already in the shape callers want.
                records = df.head(periods).to_dict("records")

            if not records:
                ratio_history_cache.set(cache_key, [], ttl=RATIO_HISTORY_EMPTY_TTL)
                return []

            ratio_history_cache.set(cache_key, records)
            return records
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching ratio history for {symbol}: {e}")
            return []

    def get_income_history(
        self,
        symbol: str,
        periods: int = 8,
    ) -> list[dict]:
        """Get historical income statement data.

        Args:
            symbol: Stock symbol
            periods: Number of quarters to fetch (default: 8)

        Returns:
            List of income statement dicts ordered by most recent first
        """
        symbol = validate_symbol(symbol)
        try:
            finance = Finance(symbol=symbol, source=self.source)
            df = finance.income_statement(period="quarter", lang="en", dropna=True)

            if df is None or df.empty:
                return []

            df = self._flatten_columns(df)
            df = df.head(periods)
            return df.to_dict("records")
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching income history for {symbol}: {e}")
            return []

    def get_cash_flow_history(
        self,
        symbol: str,
        periods: int = 8,
    ) -> list[dict]:
        """Get historical cash flow data.

        Args:
            symbol: Stock symbol
            periods: Number of quarters to fetch (default: 8)

        Returns:
            List of cash flow dicts ordered by most recent first
        """
        symbol = validate_symbol(symbol)
        try:
            finance = Finance(symbol=symbol, source=self.source)
            df = finance.cash_flow(period="quarter", lang="en", dropna=True)

            if df is None or df.empty:
                return []

            df = self._flatten_columns(df)
            df = df.head(periods)
            return df.to_dict("records")
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching cash flow history for {symbol}: {e}")
            return []

    def get_health_score(self, symbol: str) -> HealthScoreResponse:
        """Calculate financial health score for a stock.

        Args:
            symbol: Stock symbol

        Returns:
            HealthScoreResponse with scores and F-Score
        """
        symbol = validate_symbol(symbol)
        try:
            # Get ratio data (need at least 2 periods for F-Score)
            ratio_history = self.get_ratio_history(symbol, periods=2)
            if not ratio_history:
                raise StockServiceError(f"No ratio data available for {symbol}")

            current_ratio = self._normalize_ratio_data(ratio_history[0])
            prior_ratio = self._normalize_ratio_data(ratio_history[1]) if len(ratio_history) > 1 else {}

            # Get cash flow data for CFO
            cf_history = self.get_cash_flow_history(symbol, periods=1)
            cash_flow_data = self._normalize_cash_flow_data(cf_history[0]) if cf_history else {}

            # Build period label
            year = ratio_history[0].get("yearReport") or ratio_history[0].get("year")
            quarter = ratio_history[0].get("lengthReport") or ratio_history[0].get("quarter")
            period = f"Q{quarter}/{year}" if year and quarter else None

            # Calculate health score
            result = build_health_score_response(
                symbol=symbol,
                ratio_data=current_ratio,
                prior_ratio_data=prior_ratio,
                cash_flow_data=cash_flow_data,
                period=period,
            )

            return HealthScoreResponse(**result)
        except StockServiceError:
            raise
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error calculating health score for {symbol}: {e}")
            raise StockServiceError(f"Failed to calculate health score for {symbol}: {e}")

    def get_trend_metrics(
        self,
        symbol: str,
        periods: int = 8,
    ) -> TrendMetricsResponse:
        """Get trend metrics for chart visualization.

        Args:
            symbol: Stock symbol
            periods: Number of quarters (default: 8)

        Returns:
            TrendMetricsResponse with arrays of metrics
        """
        symbol = validate_symbol(symbol)
        try:
            # Get historical data
            ratio_history = self.get_ratio_history(symbol, periods)
            income_history = self.get_income_history(symbol, periods)
            cf_history = self.get_cash_flow_history(symbol, periods)

            # Reverse to show oldest first for charts
            ratio_history = list(reversed(ratio_history))
            income_history = list(reversed(income_history))
            cf_history = list(reversed(cf_history))

            # Build period labels
            period_labels = []
            for r in ratio_history:
                year = r.get("yearReport") or r.get("year")
                quarter = r.get("lengthReport") or r.get("quarter")
                if year and quarter:
                    period_labels.append(f"Q{int(quarter)}/{year}")
                else:
                    period_labels.append(str(year))

            # Extract metrics (using exact vnstock English column names)
            revenue = [safe_float(i.get("Net Sales") or i.get("Revenue (Bn. VND)")) for i in income_history]
            net_profit = [safe_float(i.get("Net Profit For the Year") or i.get("Attributable to parent company")) for i in income_history]
            gross_profit = [safe_float(i.get("Gross Profit")) for i in income_history]
            gross_margin = [self._normalize_ratio_data(r)["gross_margin"] for r in ratio_history]
            net_margin = [self._normalize_ratio_data(r)["net_margin"] for r in ratio_history]
            roe = [self._normalize_ratio_data(r)["roe"] for r in ratio_history]
            roa = [self._normalize_ratio_data(r)["roa"] for r in ratio_history]

            # Cash flow metrics (exact vnstock English column names)
            cfo = [safe_float(c.get("Net cash inflows/outflows from operating activities")) for c in cf_history]
            cfi = [safe_float(c.get("Net Cash Flows from Investing Activities")) for c in cf_history]
            cff = [safe_float(c.get("Cash flows from financial activities")) for c in cf_history]

            return TrendMetricsResponse(
                symbol=symbol,
                periods=period_labels,
                revenue=revenue,
                net_profit=net_profit,
                gross_profit=gross_profit,
                gross_margin=gross_margin,
                net_margin=net_margin,
                roe=roe,
                roa=roa,
                cfo=cfo,
                cfi=cfi,
                cff=cff,
            )
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching trend metrics for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch trend metrics for {symbol}: {e}")

    def get_fcf_analysis(self, symbol: str) -> FCFAnalysisResponse:
        """Calculate Free Cash Flow analysis.

        Args:
            symbol: Stock symbol

        Returns:
            FCFAnalysisResponse with FCF, margins, and CCC
        """
        symbol = validate_symbol(symbol)
        try:
            # Get latest cash flow and income data
            cf_history = self.get_cash_flow_history(symbol, periods=1)
            income_history = self.get_income_history(symbol, periods=1)
            ratio_history = self.get_ratio_history(symbol, periods=1)

            if not cf_history:
                raise StockServiceError(f"No cash flow data available for {symbol}")

            cf = cf_history[0]
            income = income_history[0] if income_history else {}
            ratios = ratio_history[0] if ratio_history else {}

            # Build period label
            year = cf.get("yearReport")
            quarter = cf.get("lengthReport")
            period = f"Q{int(quarter)}/{year}" if year and quarter else str(year)

            # Extract values (using exact vnstock English column names)
            net_income = safe_float(income.get("Net Profit For the Year") or income.get("Attributable to parent company"))
            cfo = safe_float(cf.get("Net cash inflows/outflows from operating activities"))
            capex = safe_float(cf.get("Purchase of fixed assets"))
            if capex and capex > 0:
                capex = -capex  # CapEx should be negative

            # Calculate FCF
            fcf = None
            if cfo is not None and capex is not None:
                fcf = cfo + capex  # capex is negative

            # FCF margin
            revenue = safe_float(income.get("Net Sales") or income.get("Revenue (Bn. VND)"))
            fcf_margin = None
            if fcf is not None and revenue and revenue > 0:
                fcf_margin = fcf / revenue

            # Get market cap from ratio data (already has it)
            market_cap = safe_float(ratios.get("Market Capital (Bn. VND)"))
            fcf_yield = None
            if market_cap and fcf:
                fcf_yield = fcf / market_cap

            # CCC components (may be null for banks) - exact column names
            dso = safe_float(ratios.get("Days Sales Outstanding"))
            dio = safe_float(ratios.get("Days Inventory Outstanding"))
            dpo = safe_float(ratios.get("Days Payable Outstanding"))
            ccc = None
            if dso is not None and dio is not None and dpo is not None:
                ccc = dso + dio - dpo

            return FCFAnalysisResponse(
                symbol=symbol,
                period=period,
                net_income=net_income,
                cfo=cfo,
                capex=capex,
                fcf=fcf,
                fcf_margin=fcf_margin,
                ccc=ccc,
                dso=dso,
                dio=dio,
                dpo=dpo,
                market_cap=market_cap,
                fcf_yield=fcf_yield,
            )
        except StockServiceError:
            raise
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error calculating FCF analysis for {symbol}: {e}")
            raise StockServiceError(f"Failed to calculate FCF analysis for {symbol}: {e}")

    def get_sector_peers(
        self,
        symbol: str,
        limit: int = 10,
    ) -> SectorPeersResponse:
        """Get sector peer companies for comparison with median and premium/discount.

        Args:
            symbol: Target stock symbol
            limit: Maximum number of peers to return (default: 10)

        Returns:
            SectorPeersResponse with peer metrics, sector median, and premium/discount
        """
        symbol = validate_symbol(symbol)

        # Check cache first
        cache_key = f"{symbol}:{limit}"
        cached = sector_peers_cache.get(cache_key)
        if cached:
            return SectorPeersResponse(**cached)

        try:
            # vnstock 4.x exposes a single industry level (~25 sectors); the
            # icb_code3 / icb_name3 columns this used to read no longer exist.
            industry_map = fetch_industry_mapping(Listing())

            target = industry_map.get(symbol)
            if target is None:
                raise StockServiceError(f"Symbol {symbol} not found")

            icb_code = target["icb_code"] or ""
            icb_name = target["icb_name"] or "Unknown"

            if not icb_code:
                raise StockServiceError(f"No ICB code found for {symbol}")

            # Peers in the same sector, alphabetical (this feed carries no market cap)
            peers = sorted(
                s
                for s, info in industry_map.items()
                if info["icb_code"] == icb_code and s != symbol
            )
            top_symbols = [symbol] + peers[:limit]

            # Get ratio data for each peer
            peers_data = []
            exhausted_upstream = False
            for peer_symbol in top_symbols[: limit + 1]:
                try:
                    ratio_history = self.get_ratio_history(peer_symbol, periods=1)
                    ratios = ratio_history[0] if ratio_history else {}

                    company_name = industry_map.get(peer_symbol, {}).get("company_name")
                    normalized = self._normalize_ratio_data(ratios)

                    peers_data.append(
                        {
                            "symbol": peer_symbol,
                            "company_name": company_name,
                            "roe": normalized["roe"],
                            "roa": normalized["roa"],
                            "pe": normalized["pe"],
                            "pb": normalized["pb"],
                            "ps": normalized["ps"],
                            # The ratio feed carries no market cap; the field
                            # stays in the contract but is only filled when a
                            # source that reports it is wired in.
                            "market_cap": safe_float(
                                ratios.get("Market Capital (Bn. VND)")
                            ),
                        }
                    )
                except (VnstockUnavailable, VnstockUnsupported):
                    # The target symbol has no substitute, so its failure is the
                    # whole request's failure. A peer is different: comparing
                    # against fewer peers still answers the question, and
                    # aborting here would discard every symbol already fetched
                    # and send the next request back through the same fan-out.
                    #
                    # A median needs peers to mean anything: with the target
                    # alone it would equal the target and report a 0% premium
                    # against itself, so too small a sample still fails.
                    if peer_symbol == symbol or len(peers_data) < MIN_PEERS_FOR_MEDIAN:
                        raise
                    logger.warning(
                        "Upstream exhausted at peer %s; building %s sector "
                        "comparison from %d symbol(s)",
                        peer_symbol,
                        symbol,
                        len(peers_data),
                    )
                    exhausted_upstream = True
                    break
                except Exception as e:
                    logger.warning(f"Could not fetch data for peer {peer_symbol}: {e}")
                    continue

            # Calculate sector median
            sector_median = self._calculate_sector_median(peers_data)

            # Add premium/discount to each peer
            for peer in peers_data:
                peer["premium_pe"] = self._calculate_premium(
                    peer.get("pe"), sector_median.pe
                )
                peer["premium_pb"] = self._calculate_premium(
                    peer.get("pb"), sector_median.pb
                )
                peer["premium_ps"] = self._calculate_premium(
                    peer.get("ps"), sector_median.ps
                )
                peer["premium_roe"] = self._calculate_premium(
                    peer.get("roe"), sector_median.roe
                )
                peer["premium_roa"] = self._calculate_premium(
                    peer.get("roa"), sector_median.roa
                )

            # Find target stock and its premium
            target = next((p for p in peers_data if p["symbol"] == symbol), None)
            target_premium = {
                "pe": target.get("premium_pe") if target else None,
                "pb": target.get("premium_pb") if target else None,
                "ps": target.get("premium_ps") if target else None,
                "roe": target.get("premium_roe") if target else None,
                "roa": target.get("premium_roa") if target else None,
            }

            # Build response
            peers = [PeerMetrics(**p) for p in peers_data]
            response = SectorPeersResponse(
                symbol=symbol,
                icb_code=icb_code,
                icb_name=icb_name,
                peers=peers,
                sector_median=sector_median,
                target_premium=target_premium,
            )

            # Cache response
            sector_peers_cache.set(
                cache_key,
                response.model_dump(),
                ttl=SECTOR_PEERS_PARTIAL_TTL if exhausted_upstream else None,
            )

            return response
        except StockServiceError:
            raise
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching sector peers for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch sector peers for {symbol}: {e}")

    def _calculate_sector_median(self, peers: list[dict]) -> SectorMedian:
        """Calculate median values for sector metrics.

        Args:
            peers: List of peer data dicts with pe, pb, roe, roa, market_cap

        Returns:
            SectorMedian with median values (None if insufficient data)
        """
        metrics = ["pe", "pb", "ps", "roe", "roa", "market_cap"]
        medians = {}
        for metric in metrics:
            values = [p.get(metric) for p in peers if p.get(metric) is not None]
            # Need at least 3 values for meaningful median
            medians[metric] = statistics.median(values) if len(values) >= 3 else None
        return SectorMedian(**medians)

    def _calculate_premium(
        self, value: Optional[float], median: Optional[float]
    ) -> Optional[float]:
        """Calculate premium/discount as percentage vs median.

        Args:
            value: The stock's metric value
            median: The sector median value

        Returns:
            Percentage deviation from median (positive = premium, negative = discount)
        """
        if value is None or median is None or median == 0:
            return None
        return ((value - median) / abs(median)) * 100

    def _normalize_ratio_data(self, data: dict) -> dict:
        """Normalize one ratio record to consistent keys.

        Each metric lists the provider metric ids first, then the older display
        labels, so a record from either frame shape resolves the same way.
        """
        def pick(*keys: str) -> Optional[float]:
            for key in keys:
                value = safe_float(data.get(key))
                if value is not None:
                    return value
            return None

        return {
            # The trailing figures cover four quarters; a single quarter's ROE
            # would read as roughly a quarter of the company's real return.
            "roe": pick("roe_trailling", "ROE (%)", "roe"),
            "roa": pick("roa_trailling", "ROA (%)", "roa"),
            "net_margin": pick(
                "net_margin", "Net Profit Margin (%)", "postTaxMargin"
            ),
            "gross_margin": pick(
                "gross_margin", "Gross Profit Margin (%)", "grossProfitMargin"
            ),
            "current_ratio": pick(
                "short_term_ratio", "Current Ratio", "currentPayment"
            ),
            "quick_ratio": pick("quick_ratio", "Quick Ratio", "quickPayment"),
            "debt_to_equity": pick(
                "debt_to_equity", "Debt/Equity", "debtOnEquity"
            ),
            "pe": pick("pe_ratio", "P/E", "priceToEarning"),
            "pb": pick("pb_ratio", "P/B", "priceToBook"),
            "ps": pick("ps_ratio", "P/S", "priceToSales"),
            "asset_turnover": pick(
                "total_asset_turnover", "Asset Turnover", "assetTurnover"
            ),
        }

    def _normalize_cash_flow_data(self, data: dict) -> dict:
        """Normalize cash flow data to consistent keys (using exact vnstock column names)."""
        cfo = safe_float(data.get("Net cash inflows/outflows from operating activities"))
        return {
            "cfo": cfo,
            "net_cfo": cfo,
        }


@lru_cache(maxsize=1)
def get_financial_service(source: str = "VCI") -> FinancialService:
    """Get or create financial service instance (thread-safe singleton)."""
    return FinancialService(source=source)
