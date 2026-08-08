"""Tests for CompanyService mapping logic.

All vnstock access is mocked — these tests are offline and deterministic.
"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.stocks.company.service import CompanyService
from src.stocks.shared import StockServiceError


@pytest.fixture
def service():
    return CompanyService(source="VCI")


def _mock_company(**frames):
    """Build a Vnstock() mock whose stock().company exposes the given frames."""
    company = MagicMock()
    for name, value in frames.items():
        getattr(company, name).return_value = value
    stock = MagicMock()
    stock.company = company
    vnstock = MagicMock()
    vnstock.stock.return_value = stock
    return vnstock


class TestSymbolValidation:
    """Invalid symbols must be rejected before any network call."""

    @pytest.mark.parametrize(
        "method, args",
        [
            ("get_company_overview", ()),
            ("get_shareholders", ()),
            ("get_officers", ()),
            ("get_ratio_summary", ()),
            ("get_trading_stats", ()),
        ],
    )
    def test_invalid_symbol_raises(self, service, method, args):
        with patch("src.stocks.company.service.Vnstock") as vnstock:
            with pytest.raises(StockServiceError, match="Invalid symbol format"):
                getattr(service, method)("VCB!", *args)
            vnstock.assert_not_called()

    def test_symbol_is_normalized(self, service):
        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(overview=pd.DataFrame())):
            result = service.get_company_overview(" vcb ")
        assert result.symbol == "VCB"


class TestCompanyOverview:
    def test_maps_dataframe_row(self, service):
        df = pd.DataFrame([{
            "organ_name": "Ngân hàng TMCP Ngoại thương Việt Nam",
            "short_name": "Vietcombank",
            "exchange": "HOSE",
            "icb_name3": "Ngân hàng",
            "icb_name2": "Tài chính",
            "issue_share": 5_589_000_000,
            "outstanding_share": 5_589_000_000,
            "company_profile": "Profile text",
            "website": "https://vietcombank.com.vn",
            "no_employees": 23000,
            "established_year": "1963",
        }])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(overview=df)):
            result = service.get_company_overview("VCB")

        assert result.symbol == "VCB"
        assert result.company_name == "Ngân hàng TMCP Ngoại thương Việt Nam"
        assert result.exchange == "HOSE"
        assert result.industry == "Ngân hàng"  # icb_name3 wins over icb_name2
        assert result.website == "https://vietcombank.com.vn"
        assert result.employees == 23000
        assert result.established_year == 1963
        # NOTE: the service also passes short_name/issue_share/outstanding_share,
        # but CompanyOverview declares no such fields so pydantic drops them.
        assert not hasattr(result, "issue_share")

    def test_falls_back_to_short_name_and_icb2(self, service):
        df = pd.DataFrame([{"short_name": "ACB", "icb_name2": "Tài chính"}])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(overview=df)):
            result = service.get_company_overview("ACB")

        assert result.company_name == "ACB"
        assert result.industry == "Tài chính"

    def test_empty_frame_returns_symbol_only(self, service):
        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(overview=pd.DataFrame())):
            result = service.get_company_overview("VCB")

        assert result.symbol == "VCB"
        assert result.company_name is None

    def test_none_payload_returns_symbol_only(self, service):
        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(overview=None)):
            result = service.get_company_overview("VCB")

        assert result.symbol == "VCB"
        assert result.company_name is None

    def test_upstream_failure_becomes_service_error(self, service):
        vnstock = _mock_company()
        vnstock.stock.side_effect = RuntimeError("upstream down")

        with patch("src.stocks.company.service.Vnstock", return_value=vnstock):
            with pytest.raises(StockServiceError, match="Failed to fetch company overview"):
                service.get_company_overview("VCB")


class TestShareholders:
    def test_maps_rows_and_scales_ownership_to_percent(self, service):
        df = pd.DataFrame([
            {"id": 1, "share_holder": "SBV", "quantity": 1000, "share_own_percent": 0.7451,
             "update_date": pd.Timestamp("2026-01-15")},
            {"id": 2, "share_holder": "Mizuho", "quantity": 500, "share_own_percent": 0.15},
        ])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(shareholders=df)):
            result = service.get_shareholders("VCB")

        assert result.total_count == 2
        first, second = result.shareholders
        assert first.name == "SBV"
        assert first.shares == 1000.0
        assert first.ownership_pct == pytest.approx(74.51)
        assert first.update_date == "2026-01-15"
        assert second.update_date is None

    def test_skips_unparsable_rows_instead_of_failing(self, service):
        df = pd.DataFrame([
            {"id": 1, "share_holder": "SBV", "quantity": "not-a-number", "share_own_percent": 0.7},
            {"id": 2, "share_holder": "Mizuho", "quantity": 500, "share_own_percent": 0.15},
        ])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(shareholders=df)):
            result = service.get_shareholders("VCB")

        assert result.total_count == 1
        assert result.shareholders[0].name == "Mizuho"

    def test_empty_frame_returns_empty_response(self, service):
        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(shareholders=pd.DataFrame())):
            result = service.get_shareholders("VCB")

        assert result.shareholders == []
        assert result.total_count == 0


class TestOfficers:
    def test_maps_rows_and_passes_filter_through(self, service):
        df = pd.DataFrame([
            {"id": 10, "officer_name": "Nguyễn Văn A", "officer_position": "Chủ tịch HĐQT",
             "position_short_name": "CT", "quantity": 12000, "officer_own_percent": 0.0012,
             "update_date": "2026-02-01", "type": "working"},
        ])
        vnstock = _mock_company(officers=df)

        with patch("src.stocks.company.service.Vnstock", return_value=vnstock):
            result = service.get_officers("VCB", filter_by="resigned")

        vnstock.stock.return_value.company.officers.assert_called_once_with(filter_by="resigned")
        officer = result.officers[0]
        assert officer.name == "Nguyễn Văn A"
        assert officer.position == "Chủ tịch HĐQT"
        assert officer.ownership_pct == pytest.approx(0.12)
        assert officer.status == "working"

    def test_missing_ownership_stays_none(self, service):
        df = pd.DataFrame([{"id": 11, "officer_name": "B", "officer_position": "TGĐ"}])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(officers=df)):
            result = service.get_officers("VCB")

        assert result.officers[0].ownership_pct is None


class TestRatioSummary:
    def test_maps_primary_field_names(self, service):
        df = pd.DataFrame([{"pe": 15.2, "pb": 2.1, "ps": 3.3, "roe": 0.21, "roa": 0.018,
                            "roic": 0.15, "current_ratio": 1.4, "debt_to_equity": 0.8}])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(ratio_summary=df)):
            result = service.get_ratio_summary("VCB")

        assert result.pe == 15.2
        assert result.pb == 2.1
        assert result.debt_to_equity == 0.8

    def test_falls_back_to_alias_field_names(self, service):
        df = pd.DataFrame([{"price_to_earning": 11.0, "price_to_book": 1.5, "de": 0.6}])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(ratio_summary=df)):
            result = service.get_ratio_summary("VCB")

        assert result.pe == 11.0
        assert result.pb == 1.5
        assert result.debt_to_equity == 0.6

    def test_empty_frame_returns_symbol_only(self, service):
        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(ratio_summary=pd.DataFrame())):
            result = service.get_ratio_summary("VCB")

        assert result.symbol == "VCB"
        assert result.pe is None


class TestTradingStats:
    def test_converts_yearly_high_low_to_thousands(self, service):
        df = pd.DataFrame([{"total_volume": 1_500_000, "avg_volume": 900_000.5,
                            "total_value": 3.2e11, "avg_value": 1.1e10,
                            "high_price_1y": 98_500, "low_price_1y": 74_000}])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(trading_stats=df)):
            result = service.get_trading_stats("VCB")

        assert result.total_volume == 1_500_000
        assert result.high_price == pytest.approx(98.5)
        assert result.low_price == pytest.approx(74.0)

    def test_falls_back_to_match_field_names(self, service):
        df = pd.DataFrame([{"total_match_volume": 2_000_000, "avg_match_volume_2w": 1_000_000,
                            "total_match_value": 5.0e11}])

        with patch("src.stocks.company.service.Vnstock", return_value=_mock_company(trading_stats=df)):
            result = service.get_trading_stats("VCB")

        assert result.total_volume == 2_000_000
        assert result.avg_volume == 1_000_000.0
        assert result.total_value == 5.0e11
        assert result.high_price is None
