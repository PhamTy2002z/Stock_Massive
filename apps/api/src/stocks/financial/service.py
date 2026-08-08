"""Financial domain service for financial statements and ratios."""

import logging
from functools import lru_cache
import statistics
from typing import Optional

import pandas as pd
from vnstock import Finance, Listing

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
from ..shared import StockServiceError, validate_symbol, safe_float
from .health_scoring import build_health_score_response
from .cache import sector_peers_cache

logger = logging.getLogger(__name__)


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

                ratios.append(
                    FinancialRatio(
                        year=int(year_report) if year_report else None,
                        quarter=int(length_report) if length_report and period == "quarter" else None,
                        roe=safe_float(row.get("roe") or row.get("ROE")),
                        roa=safe_float(row.get("roa") or row.get("ROA")),
                        gross_margin=safe_float(row.get("grossProfitMargin") or row.get("Gross margin")),
                        net_margin=safe_float(row.get("postTaxMargin") or row.get("Net margin")),
                        pe=safe_float(row.get("priceToEarning") or row.get("P/E")),
                        pb=safe_float(row.get("priceToBook") or row.get("P/B")),
                        ps=safe_float(row.get("priceToSale") or row.get("P/S")),
                        current_ratio=safe_float(row.get("currentPayment") or row.get("Current ratio")),
                        quick_ratio=safe_float(row.get("quickPayment") or row.get("Quick ratio")),
                        debt_to_equity=safe_float(row.get("debtOnEquity") or row.get("D/E")),
                        debt_to_assets=safe_float(row.get("debtOnAsset") or row.get("D/A")),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping ratio row due to error: {e}")
                continue
        return ratios

    def _df_to_income_statements(self, df: pd.DataFrame, period: str) -> list[IncomeStatementItem]:
        """Convert DataFrame to list of IncomeStatementItem."""
        items = []
        for row in df.to_dict("records"):
            try:
                year_report = row.get("yearReport") or row.get("year")
                length_report = row.get("lengthReport") or row.get("quarter")

                items.append(
                    IncomeStatementItem(
                        year=int(year_report) if year_report else None,
                        quarter=int(length_report) if length_report and period == "quarter" else None,
                        revenue=safe_float(row.get("revenue") or row.get("Net Revenue")),
                        gross_profit=safe_float(row.get("grossProfit") or row.get("Gross profit")),
                        operating_profit=safe_float(row.get("operationProfit") or row.get("Operating profit")),
                        net_income=safe_float(row.get("postTaxProfit") or row.get("Net profit")),
                        eps=safe_float(row.get("earningPerShare") or row.get("EPS")),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping income statement row due to error: {e}")
                continue
        return items

    def _period_labels(self, df: pd.DataFrame, period: str) -> list[str]:
        """Build period labels ("Q2/2025" or "2025") for statement tables.

        iterrows() coerces an all-numeric row to float, so year/quarter are cast
        back to int — otherwise labels render as "Q2/2025.0".
        """
        labels = []
        for _, row in df.iterrows():
            # Vietnamese columns first (lang="vi"), then English fallbacks
            year = row.get("Năm") or row.get("yearReport") or row.get("year")
            quarter = row.get("Kỳ") or row.get("lengthReport") or row.get("quarter")
            try:
                year_label = str(int(year))
            except (TypeError, ValueError):
                year_label = str(year)
            if period == "quarter" and quarter:
                labels.append(f"Q{int(quarter)}/{year_label}")
            else:
                labels.append(year_label)
        return labels

    def _df_to_income_statement_response(
        self, df: pd.DataFrame, symbol: str, period: str, limit: int
    ) -> IncomeStatementResponse:
        """Convert DataFrame to IncomeStatementResponse for detailed view."""
        df = df.head(limit)

        periods = self._period_labels(df, period)

        # row_mappings: (id, label, column_names, level, is_summary)
        # level: 0=root, 1=child, 2=sub-child
        # column_names: vnstock Vietnamese column names (exact match required)
        row_mappings = [
            ("gross_revenue", "Doanh thu bán hàng và cung cấp dịch vụ", ["Doanh thu bán hàng và cung cấp dịch vụ"], 0, True),
            ("revenue_deductions", "Các khoản giảm trừ doanh thu", ["Các khoản giảm trừ doanh thu"], 1, False),
            ("net_revenue", "Doanh thu thuần", ["Doanh thu thuần"], 0, True),
            ("cogs", "Giá vốn hàng bán", ["Giá vốn hàng bán"], 1, False),
            ("gross_profit", "Lãi gộp", ["Lãi gộp"], 0, True),
            ("selling_expense", "Chi phí bán hàng", ["Chi phí bán hàng"], 1, False),
            ("admin_expense", "Chi phí quản lý doanh nghiệp", ["Chi phí quản lý DN", "Chi phí quản lý doanh nghiệp"], 1, False),
            ("financial_income", "Thu nhập tài chính", ["Thu nhập tài chính"], 1, False),
            ("financial_expense", "Chi phí tài chính", ["Chi phí tài chính"], 1, False),
            ("interest_expense", "Chi phí tiền lãi vay", ["Chi phí tiền lãi vay"], 2, False),
            ("operating_profit", "Lãi/Lỗ từ hoạt động kinh doanh", ["Lãi/Lỗ từ hoạt động kinh doanh"], 0, True),
            ("other_income", "Thu nhập khác", ["Thu nhập khác"], 1, False),
            ("other_expense", "Thu nhập/Chi phí khác", ["Thu nhập/Chi phí khác"], 1, False),
            ("other_profit", "Lợi nhuận khác", ["Lợi nhuận khác"], 1, False),
            ("pre_tax_profit", "Lợi nhuận trước thuế", ["LN trước thuế", "Lợi nhuận trước thuế"], 0, True),
            ("tax_expense", "Chi phí thuế TNDN", ["Chi phí thuế TNDN hiện hành", "Chi phí thuế TNDN"], 1, False),
            ("net_profit", "Lợi nhuận thuần", ["Lợi nhuận thuần"], 0, True),
            ("parent_profit", "Cổ đông của Công ty mẹ", ["Cổ đông của Công ty mẹ"], 1, False),
            ("minority_profit", "Cổ đông thiểu số", ["Cổ đông thiểu số"], 1, False),
        ]

        rows = []
        for row_id, label, col_names, level, is_summary in row_mappings:
            values = {}
            for i, period_label in enumerate(periods):
                if i < len(df):
                    row_data = df.iloc[i]
                    val = None
                    for col_name in col_names:
                        if col_name in df.columns:
                            val = row_data.get(col_name)
                            if val is not None and not pd.isna(val):
                                break
                    if val is not None and not pd.isna(val):
                        values[period_label] = float(val) / 1_000_000
                    else:
                        values[period_label] = None
                else:
                    values[period_label] = None

            if any(v is not None for v in values.values()):
                rows.append(IncomeStatementRow(
                    id=row_id,
                    label=label,
                    values=values,
                    level=level,
                    is_header=level == 0 and is_summary,
                    is_summary=is_summary,
                ))

        return IncomeStatementResponse(
            symbol=symbol,
            periods=periods,
            rows=rows,
            unit="Triệu VND",
        )

    def _df_to_balance_sheets(self, df: pd.DataFrame, period: str) -> list[BalanceSheetItem]:
        """Convert DataFrame to list of BalanceSheetItem."""
        items = []
        for row in df.to_dict("records"):
            try:
                year_report = row.get("yearReport") or row.get("year")
                length_report = row.get("lengthReport") or row.get("quarter")

                items.append(
                    BalanceSheetItem(
                        year=int(year_report) if year_report else None,
                        quarter=int(length_report) if length_report and period == "quarter" else None,
                        total_assets=safe_float(row.get("asset") or row.get("Total assets")),
                        total_liabilities=safe_float(row.get("debt") or row.get("Total liabilities")),
                        total_equity=safe_float(row.get("equity") or row.get("Total equity")),
                        cash=safe_float(row.get("cash") or row.get("Cash and cash equivalents")),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping balance sheet row due to error: {e}")
                continue
        return items

    def _df_to_balance_sheet_response(
        self, df: pd.DataFrame, symbol: str, period: str, limit: int
    ) -> BalanceSheetResponse:
        """Convert DataFrame to BalanceSheetResponse for detailed view."""
        df = df.head(limit)

        periods = self._period_labels(df, period)

        # row_mappings: (id, label, column_names, level, is_summary)
        # column_names: vnstock Vietnamese column names (exact match required)
        row_mappings = [
            ("current_assets", "TÀI SẢN NGẮN HẠN", ["TÀI SẢN NGẮN HẠN (đồng)", "Tài sản ngắn hạn"], 0, True),
            ("cash", "Tiền và tương đương tiền", ["Tiền và tương đương tiền (đồng)", "Tiền và các khoản tương đương tiền"], 1, False),
            ("short_invest", "Giá trị thuần đầu tư ngắn hạn", ["Giá trị thuần đầu tư ngắn hạn (đồng)", "Đầu tư tài chính ngắn hạn"], 1, False),
            ("receivables", "Các khoản phải thu ngắn hạn", ["Các khoản phải thu ngắn hạn (đồng)"], 1, False),
            ("inventory", "Hàng tồn kho ròng", ["Hàng tồn kho ròng", "Hàng tồn kho, ròng (đồng)"], 1, False),
            ("other_current", "Tài sản lưu động khác", ["Tài sản lưu động khác", "Tài sản lưu động khác (đồng)"], 1, False),
            ("long_assets", "TÀI SẢN DÀI HẠN", ["TÀI SẢN DÀI HẠN (đồng)", "Tài sản dài hạn"], 0, True),
            ("long_receivables", "Phải thu về cho vay dài hạn", ["Phải thu về cho vay dài hạn (đồng)", "Phải thu dài hạn (đồng)"], 1, False),
            ("fixed_assets", "Tài sản cố định", ["Tài sản cố định (đồng)"], 1, False),
            ("invest_assets", "Giá trị ròng tài sản đầu tư", ["Giá trị ròng tài sản đầu tư"], 1, False),
            ("long_invest", "Đầu tư dài hạn", ["Đầu tư dài hạn (đồng)"], 1, False),
            ("goodwill", "Lợi thế thương mại", ["Lợi thế thương mại", "Lợi thế thương mại (đồng)"], 1, False),
            ("other_long", "Tài sản dài hạn khác", ["Tài sản dài hạn khác", "Tài sản dài hạn khác (đồng)"], 1, False),
            ("total_assets", "TỔNG CỘNG TÀI SẢN", ["TỔNG CỘNG TÀI SẢN (đồng)"], 0, True),
            ("liabilities", "NỢ PHẢI TRẢ", ["NỢ PHẢI TRẢ (đồng)", "Nợ phải trả"], 0, True),
            ("short_debt", "Nợ ngắn hạn", ["Nợ ngắn hạn (đồng)"], 1, False),
            ("long_debt", "Nợ dài hạn", ["Nợ dài hạn (đồng)"], 1, False),
            ("equity", "VỐN CHỦ SỞ HỮU", ["VỐN CHỦ SỞ HỮU (đồng)", "Vốn chủ sở hữu"], 0, True),
            ("capital_fund", "Vốn và các quỹ", ["Vốn và các quỹ (đồng)"], 1, False),
            ("owner_capital", "Vốn góp của chủ sở hữu", ["Vốn góp của chủ sở hữu (đồng)"], 1, False),
            ("retained", "Lãi chưa phân phối", ["Lãi chưa phân phối (đồng)"], 1, False),
            ("state_fund", "Vốn Ngân sách nhà nước và quỹ khác", ["Vốn Ngân sách nhà nước và quỹ khác"], 1, False),
            ("minority", "LỢI ÍCH CỦA CỔ ĐÔNG THIỂU SỐ", ["LỢI ÍCH CỦA CỔ ĐÔNG THIỂU SỐ"], 0, True),
            ("total_capital", "TỔNG CỘNG NGUỒN VỐN", ["TỔNG CỘNG NGUỒN VỐN (đồng)"], 0, True),
        ]

        rows = []
        for row_id, label, col_names, level, is_summary in row_mappings:
            values = {}
            for i, period_label in enumerate(periods):
                if i < len(df):
                    row_data = df.iloc[i]
                    val = None
                    for col_name in col_names:
                        if col_name in df.columns:
                            val = row_data.get(col_name)
                            if val is not None and not pd.isna(val):
                                break
                    if val is not None and not pd.isna(val):
                        values[period_label] = float(val) / 1_000_000
                    else:
                        values[period_label] = None
                else:
                    values[period_label] = None

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
        self, df: pd.DataFrame, symbol: str, period: str, limit: int
    ) -> CashFlowResponse:
        """Convert DataFrame to CashFlowResponse for detailed view."""
        df = df.head(limit)

        periods = self._period_labels(df, period)

        row_mappings = [
            ("net_profit", "Lợi nhuận trước thuế", ["Lợi nhuận trước thuế"], 0, True),
            ("depreciation", "Khấu hao TSCĐ", ["Khấu hao TSCĐ"], 1, False),
            ("provisions", "Các khoản dự phòng", ["Các khoản dự phòng"], 1, False),
            ("fx_gain_loss", "Lãi/lỗ chênh lệch tỷ giá", ["Lãi/lỗ chênh lệch tỷ giá hối đoái chưa thực hiện"], 1, False),
            ("interest_income", "Lãi/lỗ từ hoạt động đầu tư", ["Lãi/lỗ từ hoạt động đầu tư"], 1, False),
            ("interest_expense", "Chi phí lãi vay", ["Chi phí lãi vay"], 1, False),
            ("receivables_change", "Tăng/giảm các khoản phải thu", ["Tăng/giảm các khoản phải thu"], 1, False),
            ("inventory_change", "Tăng/giảm hàng tồn kho", ["Tăng/giảm hàng tồn kho"], 1, False),
            ("payables_change", "Tăng/giảm các khoản phải trả", ["Tăng/giảm các khoản phải trả"], 1, False),
            ("prepaid_change", "Tăng/giảm chi phí trả trước", ["Tăng/giảm chi phí trả trước"], 1, False),
            ("interest_paid", "Tiền lãi vay đã trả", ["Tiền lãi vay đã trả"], 1, False),
            ("tax_paid", "Tiền thu nhập doanh nghiệp đã trả", ["Tiền thu nhập doanh nghiệp đã trả"], 1, False),
            ("other_cfo_in", "Tiền thu khác từ các hoạt động kinh doanh", ["Tiền thu khác từ các hoạt động kinh doanh"], 1, False),
            ("other_cfo_out", "Tiền chi khác từ các hoạt động kinh doanh", ["Tiền chi khác từ các hoạt động kinh doanh"], 1, False),
            ("net_cfo", "Lưu chuyển tiền tệ ròng từ các hoạt động SXKD", ["Lưu chuyển tiền tệ ròng từ các hoạt động SXKD"], 0, True),
            ("capex", "Mua sắm TSCĐ", ["Mua sắm TSCĐ"], 1, False),
            ("asset_sale", "Tiền thu được từ thanh lý tài sản cố định", ["Tiền thu được từ thanh lý tài sản cố định"], 1, False),
            ("loan_collect", "Tiền thu hồi cho vay", ["Tiền thu hồi cho vay, bán lại các công cụ nợ của đơn vị khác (đồng)"], 1, False),
            ("invest_other", "Đầu tư vào các doanh nghiệp khác", ["Đầu tư vào các doanh nghiệp khác"], 1, False),
            ("invest_sale", "Tiền thu từ việc bán các khoản đầu tư", ["Tiền thu từ việc bán các khoản đầu tư vào doanh nghiệp khác"], 1, False),
            ("dividend_received", "Tiền thu cổ tức và lợi nhuận được chia", ["Tiền thu cổ tức và lợi nhuận được chia"], 1, False),
            ("net_cfi", "Lưu chuyển từ hoạt động đầu tư", ["Lưu chuyển từ hoạt động đầu tư"], 0, True),
            ("equity_issue", "Tăng vốn cổ phần", ["Tăng vốn cổ phần từ góp vốn và/hoặc phát hành cổ phiếu"], 1, False),
            ("equity_buyback", "Chi trả cho việc mua lại cổ phiếu", ["Chi trả cho việc mua lại, trả cổ phiếu"], 1, False),
            ("borrow_receive", "Tiền thu được các khoản đi vay", ["Tiền thu được các khoản đi vay"], 1, False),
            ("borrow_repay", "Tiền trả các khoản đi vay", ["Tiền trả các khoản đi vay"], 1, False),
            ("lease_payment", "Tiền thanh toán vốn gốc đi thuê tài chính", ["Tiền thanh toán vốn gốc đi thuê tài chính"], 1, False),
            ("dividend_paid", "Cổ tức đã trả", ["Cổ tức đã trả"], 1, False),
            ("net_cff", "Lưu chuyển tiền từ hoạt động tài chính", ["Lưu chuyển tiền từ hoạt động tài chính"], 0, True),
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
                    for col_name in col_names:
                        if col_name in df.columns:
                            val = row_data.get(col_name)
                            if val is not None and not pd.isna(val):
                                break
                    if val is not None and not pd.isna(val):
                        values[period_label] = float(val) / 1_000_000
                    else:
                        values[period_label] = None
                else:
                    values[period_label] = None

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

    # ==================== New Methods for Health Score & Trends ====================

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
            List of ratio dicts ordered by most recent first
        """
        symbol = validate_symbol(symbol)
        try:
            finance = Finance(symbol=symbol, source=self.source)
            df = finance.ratio(period="quarter", lang="en", dropna=True)

            if df is None or df.empty:
                return []

            # Flatten MultiIndex columns
            df = self._flatten_columns(df)

            # Take the most recent N periods
            df = df.head(periods)
            return df.to_dict("records")
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
            gross_margin = [safe_float(r.get("Gross Profit Margin (%)")) for r in ratio_history]
            net_margin = [safe_float(r.get("Net Profit Margin (%)")) for r in ratio_history]
            roe = [safe_float(r.get("ROE (%)")) for r in ratio_history]
            roa = [safe_float(r.get("ROA (%)")) for r in ratio_history]

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
            listing = Listing()

            # Get symbols with industry data (symbols_by_industries has ICB codes)
            symbols_df = listing.symbols_by_industries()
            if symbols_df is None or symbols_df.empty:
                raise StockServiceError("Could not fetch symbol list")

            # Find target stock's ICB code (column is 'symbol', not 'ticker')
            target_row = symbols_df[symbols_df["symbol"] == symbol]
            if target_row.empty:
                raise StockServiceError(f"Symbol {symbol} not found")

            # Column names: icb_code3, icb_name3
            icb_code = str(target_row.iloc[0].get("icb_code3") or "")
            icb_name = str(target_row.iloc[0].get("icb_name3") or "Unknown")

            if not icb_code:
                raise StockServiceError(f"No ICB code found for {symbol}")

            # Find peers in same sector
            sector_stocks = symbols_df[symbols_df["icb_code3"] == icb_code].copy()

            # Sort alphabetically since no market cap in this API
            # Take top N including target
            top_symbols = sector_stocks.head(limit + 5)["symbol"].tolist()
            if symbol not in top_symbols:
                top_symbols = [symbol] + top_symbols[:limit]
            else:
                # Ensure target is first
                top_symbols.remove(symbol)
                top_symbols = [symbol] + top_symbols[:limit]

            # Get ratio data for each peer
            peers_data = []
            for peer_symbol in top_symbols[: limit + 1]:
                try:
                    ratio_history = self.get_ratio_history(peer_symbol, periods=1)
                    ratios = ratio_history[0] if ratio_history else {}

                    peer_row = symbols_df[symbols_df["symbol"] == peer_symbol]
                    company_name = (
                        peer_row.iloc[0].get("organ_name")
                        if not peer_row.empty
                        else None
                    )

                    # Get market cap from ratio data
                    market_cap = safe_float(ratios.get("Market Capital (Bn. VND)"))

                    peers_data.append(
                        {
                            "symbol": peer_symbol,
                            "company_name": company_name,
                            "roe": safe_float(ratios.get("ROE (%)") or ratios.get("roe")),
                            "roa": safe_float(ratios.get("ROA (%)") or ratios.get("roa")),
                            "pe": safe_float(
                                ratios.get("P/E") or ratios.get("priceToEarning")
                            ),
                            "pb": safe_float(
                                ratios.get("P/B") or ratios.get("priceToBook")
                            ),
                            "market_cap": market_cap,
                        }
                    )
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
            sector_peers_cache.set(cache_key, response.model_dump())

            return response
        except StockServiceError:
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
        metrics = ["pe", "pb", "roe", "roa", "market_cap"]
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
        """Normalize ratio data to consistent keys (after MultiIndex flattening)."""
        return {
            "roe": safe_float(data.get("ROE (%)") or data.get("roe")),
            "roa": safe_float(data.get("ROA (%)") or data.get("roa")),
            "net_margin": safe_float(data.get("Net Profit Margin (%)") or data.get("postTaxMargin")),
            "gross_margin": safe_float(data.get("Gross Profit Margin (%)") or data.get("grossProfitMargin")),
            "current_ratio": safe_float(data.get("Current Ratio") or data.get("currentPayment")),
            "quick_ratio": safe_float(data.get("Quick Ratio") or data.get("quickPayment")),
            "debt_to_equity": safe_float(data.get("Debt/Equity") or data.get("debtOnEquity")),
            "pe": safe_float(data.get("P/E") or data.get("priceToEarning")),
            "pb": safe_float(data.get("P/B") or data.get("priceToBook")),
            "asset_turnover": safe_float(data.get("Asset Turnover") or data.get("assetTurnover")),
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
