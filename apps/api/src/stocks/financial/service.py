"""Financial domain service for financial statements and ratios."""

import logging

import pandas as pd
from vnstock import Finance

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
)
from ..shared import StockServiceError, validate_symbol, safe_float

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
                        period_type=period,
                        price_to_earning=safe_float(row.get("priceToEarning") or row.get("P/E")),
                        price_to_book=safe_float(row.get("priceToBook") or row.get("P/B")),
                        roe=safe_float(row.get("roe") or row.get("ROE")),
                        roa=safe_float(row.get("roa") or row.get("ROA")),
                        eps=safe_float(row.get("earningPerShare") or row.get("EPS")),
                        book_value_per_share=safe_float(row.get("bookValuePerShare") or row.get("BVPS")),
                        dividend_yield=safe_float(row.get("dividend") or row.get("Dividend yield")),
                        current_ratio=safe_float(row.get("currentPayment") or row.get("Current ratio")),
                        quick_ratio=safe_float(row.get("quickPayment") or row.get("Quick ratio")),
                        debt_to_equity=safe_float(row.get("debtOnEquity") or row.get("D/E")),
                        debt_to_asset=safe_float(row.get("debtOnAsset") or row.get("D/A")),
                        gross_margin=safe_float(row.get("grossProfitMargin") or row.get("Gross margin")),
                        operating_margin=safe_float(row.get("operatingProfitMargin") or row.get("Operating margin")),
                        net_margin=safe_float(row.get("postTaxMargin") or row.get("Net margin")),
                        beta=safe_float(row.get("beta") or row.get("Beta")),
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
                        period_type=period,
                        revenue=safe_float(row.get("revenue") or row.get("Net Revenue")),
                        cost_of_goods_sold=safe_float(row.get("costOfGoodSold") or row.get("Cost of sales")),
                        gross_profit=safe_float(row.get("grossProfit") or row.get("Gross profit")),
                        operating_expense=safe_float(row.get("operationExpense")),
                        operating_profit=safe_float(row.get("operationProfit") or row.get("Operating profit")),
                        interest_expense=safe_float(row.get("interestExpense")),
                        pre_tax_profit=safe_float(row.get("preTaxProfit") or row.get("Profit before tax")),
                        net_profit=safe_float(row.get("postTaxProfit") or row.get("Net profit")),
                        eps=safe_float(row.get("earningPerShare") or row.get("EPS")),
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping income statement row due to error: {e}")
                continue
        return items

    def _df_to_income_statement_response(
        self, df: pd.DataFrame, symbol: str, period: str, limit: int
    ) -> IncomeStatementResponse:
        """Convert DataFrame to IncomeStatementResponse for detailed view."""
        df = df.head(limit)

        periods = []
        for _, row in df.iterrows():
            # Vietnamese columns first (lang="vi"), then English fallbacks
            year = row.get("Năm") or row.get("yearReport") or row.get("year")
            quarter = row.get("Kỳ") or row.get("lengthReport") or row.get("quarter")
            if period == "quarter" and quarter:
                periods.append(f"Q{int(quarter)}/{year}")
            else:
                periods.append(str(year))

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
                        period_type=period,
                        total_assets=safe_float(row.get("asset") or row.get("Total assets")),
                        current_assets=safe_float(row.get("shortAsset") or row.get("Current assets")),
                        fixed_assets=safe_float(row.get("fixedAsset") or row.get("Fixed assets")),
                        total_liabilities=safe_float(row.get("debt") or row.get("Total liabilities")),
                        current_liabilities=safe_float(row.get("shortDebt") or row.get("Current liabilities")),
                        long_term_liabilities=safe_float(row.get("longDebt") or row.get("Long-term liabilities")),
                        equity=safe_float(row.get("equity") or row.get("Total equity")),
                        charter_capital=safe_float(row.get("capital") or row.get("Charter capital")),
                        retained_earnings=safe_float(row.get("unDistributedIncome") or row.get("Retained earnings")),
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

        periods = []
        for _, row in df.iterrows():
            # Vietnamese columns first (lang="vi"), then English fallbacks
            year = row.get("Năm") or row.get("yearReport") or row.get("year")
            quarter = row.get("Kỳ") or row.get("lengthReport") or row.get("quarter")
            if period == "quarter" and quarter:
                periods.append(f"Q{int(quarter)}/{year}")
            else:
                periods.append(str(year))

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

        periods = []
        for _, row in df.iterrows():
            # Vietnamese columns first (lang="vi"), then English fallbacks
            year = row.get("Năm") or row.get("yearReport") or row.get("year")
            quarter = row.get("Kỳ") or row.get("lengthReport") or row.get("quarter")
            if period == "quarter" and quarter:
                periods.append(f"Q{int(quarter)}/{year}")
            else:
                periods.append(str(year))

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
