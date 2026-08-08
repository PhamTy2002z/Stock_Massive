"""Tests for FinancialService DataFrame parsers.

Pure conversion logic — no vnstock calls, so these run offline.
"""
import numpy as np
import pandas as pd
import pytest

from src.stocks.financial.service import FinancialService


@pytest.fixture
def service():
    return FinancialService(source="VCI")


class TestFlattenColumns:
    def test_keeps_second_level_of_multiindex(self, service):
        df = pd.DataFrame(
            [[2025, 21.5]],
            columns=pd.MultiIndex.from_tuples([("Meta", "yearReport"), ("Chỉ tiêu định giá", "ROE (%)")]),
        )

        flat = service._flatten_columns(df)

        assert list(flat.columns) == ["yearReport", "ROE (%)"]

    def test_leaves_flat_columns_untouched(self, service):
        df = pd.DataFrame([{"yearReport": 2025, "roe": 0.2}])

        assert list(service._flatten_columns(df).columns) == ["yearReport", "roe"]

    def test_passes_through_empty_and_none(self, service):
        empty = pd.DataFrame()
        assert service._flatten_columns(empty).empty
        assert service._flatten_columns(None) is None


class TestDfToFinancialRatios:
    def test_maps_camel_case_columns(self, service):
        df = pd.DataFrame([{
            "yearReport": 2025, "lengthReport": 3,
            "priceToEarning": 15.2, "priceToBook": 2.1, "roe": 0.21, "roa": 0.018,
            "debtOnEquity": 0.8, "debtOnAsset": 0.4, "grossProfitMargin": 0.35,
        }])

        ratio = service._df_to_financial_ratios(df, "quarter")[0]

        assert ratio.year == 2025
        assert ratio.quarter == 3
        assert ratio.pe == 15.2
        assert ratio.pb == 2.1
        assert ratio.debt_to_equity == 0.8
        assert ratio.debt_to_assets == 0.4
        assert ratio.gross_margin == 0.35

    def test_maps_display_name_columns(self, service):
        df = pd.DataFrame([{"year": 2025, "P/E": 11.0, "P/B": 1.5, "ROE": 0.18, "D/E": 0.5}])

        ratio = service._df_to_financial_ratios(df, "year")[0]

        assert ratio.year == 2025
        assert ratio.pe == 11.0
        assert ratio.pb == 1.5
        assert ratio.roe == 0.18
        assert ratio.debt_to_equity == 0.5

    def test_year_period_never_sets_quarter(self, service):
        df = pd.DataFrame([{"yearReport": 2025, "lengthReport": 3}])

        assert service._df_to_financial_ratios(df, "year")[0].quarter is None

    def test_nan_becomes_none(self, service):
        df = pd.DataFrame([{"yearReport": 2025, "priceToEarning": np.nan, "roe": None}])

        ratio = service._df_to_financial_ratios(df, "year")[0]

        assert ratio.pe is None
        assert ratio.roe is None

    def test_empty_frame_yields_no_rows(self, service):
        assert service._df_to_financial_ratios(pd.DataFrame(), "year") == []


class TestDfToIncomeStatements:
    def test_maps_camel_case_columns(self, service):
        df = pd.DataFrame([{
            "yearReport": 2025, "lengthReport": 2,
            "revenue": 1_000.0, "costOfGoodSold": 600.0, "grossProfit": 400.0,
            "operationProfit": 250.0, "preTaxProfit": 240.0, "postTaxProfit": 190.0,
            "earningPerShare": 3200,
        }])

        item = service._df_to_income_statements(df, "quarter")[0]

        assert (item.year, item.quarter) == (2025, 2)
        assert item.revenue == 1_000.0
        assert item.gross_profit == 400.0
        assert item.operating_profit == 250.0
        assert item.net_income == 190.0
        assert item.eps == 3200.0

    def test_maps_display_name_columns(self, service):
        df = pd.DataFrame([{"year": 2024, "Net Revenue": 900.0, "Net profit": 100.0}])

        item = service._df_to_income_statements(df, "year")[0]

        assert item.revenue == 900.0
        assert item.net_income == 100.0
        assert item.quarter is None


class TestDfToBalanceSheets:
    def test_maps_camel_case_columns(self, service):
        df = pd.DataFrame([{
            "yearReport": 2025, "lengthReport": 4,
            "asset": 2_000.0, "debt": 1_200.0, "equity": 800.0, "cash": 150.0,
        }])

        item = service._df_to_balance_sheets(df, "quarter")[0]

        assert (item.year, item.quarter) == (2025, 4)
        assert item.total_assets == 2_000.0
        assert item.total_liabilities == 1_200.0
        assert item.total_equity == 800.0
        assert item.cash == 150.0
        # Balance sheet identity holds for the mapped fields
        assert item.total_assets == item.total_liabilities + item.total_equity

    def test_maps_display_name_columns(self, service):
        df = pd.DataFrame([{"year": 2024, "Total assets": 500.0, "Total equity": 200.0}])

        item = service._df_to_balance_sheets(df, "year")[0]

        assert item.total_assets == 500.0
        assert item.total_equity == 200.0


class TestDfToIncomeStatementResponse:
    def test_builds_quarter_labels_and_scales_to_millions(self, service):
        df = pd.DataFrame([
            {"Năm": 2025, "Kỳ": 2, "Doanh thu thuần": 5_000_000_000.0, "Lãi gộp": 2_000_000_000.0},
            {"Năm": 2025, "Kỳ": 1, "Doanh thu thuần": 4_000_000_000.0, "Lãi gộp": 1_500_000_000.0},
        ])

        response = service._df_to_income_statement_response(df, "VCB", "quarter", limit=4)

        assert response.periods == ["Q2/2025", "Q1/2025"]
        assert response.unit == "Triệu VND"
        net_revenue = next(r for r in response.rows if r.id == "net_revenue")
        assert net_revenue.values["Q2/2025"] == 5_000.0
        assert net_revenue.values["Q1/2025"] == 4_000.0

    def test_year_period_labels_are_bare_years(self, service):
        df = pd.DataFrame([{"Năm": 2025, "Doanh thu thuần": 1_000_000.0}])

        response = service._df_to_income_statement_response(df, "VCB", "year", limit=4)

        assert response.periods == ["2025"]

    def test_limit_truncates_periods(self, service):
        df = pd.DataFrame([{"Năm": y, "Doanh thu thuần": 1_000_000.0} for y in (2025, 2024, 2023)])

        response = service._df_to_income_statement_response(df, "VCB", "year", limit=2)

        assert response.periods == ["2025", "2024"]

    def test_rows_with_no_data_are_dropped(self, service):
        df = pd.DataFrame([{"Năm": 2025, "Doanh thu thuần": 1_000_000.0}])

        response = service._df_to_income_statement_response(df, "VCB", "year", limit=4)

        assert {r.id for r in response.rows} == {"net_revenue"}

    def test_falls_back_to_alternate_column_label(self, service):
        df = pd.DataFrame([{"Năm": 2025, "Chi phí quản lý DN": 2_000_000.0}])

        response = service._df_to_income_statement_response(df, "VCB", "year", limit=4)

        admin = next(r for r in response.rows if r.id == "admin_expense")
        assert admin.values["2025"] == 2.0
