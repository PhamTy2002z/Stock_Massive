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


class TestStockDetail:
    @patch("src.stocks.company.service.Trading")
    def test_market_cap_uses_vnd_price_and_outstanding_shares(
        self, trading_cls, service
    ):
        """vnstock 4 price-board prices are VND, not thousands of VND."""
        trading_cls.return_value.price_board.return_value = pd.DataFrame(
            [
                {
                    "symbol": "VCB",
                    "match_price": 59_700.0,
                    "ref_price": 59_000.0,
                    "listed_share": 8_500_000_000,
                }
            ]
        )
        overview = pd.DataFrame(
            [
                {
                    "issue_share": 8_900_000_000,
                    "outstanding_share": 8_355_675_094,
                }
            ]
        )
        vnstock = _mock_company(
            overview=overview,
            ratio_summary=pd.DataFrame(),
        )

        with (
            patch("src.stocks.company.service.Vnstock", return_value=vnstock),
            patch.object(service, "_get_52_week_metrics", return_value={}),
            patch.object(service, "_get_vn30_rank", return_value=None),
        ):
            result = service.get_stock_detail("VCB")

        assert result.outstanding_shares == 8_355_675_094
        assert result.market_cap == round(
            59_700.0 * 8_355_675_094 / 1_000_000_000,
            2,
        )

    @patch("src.stocks.company.service.Trading")
    def test_market_cap_falls_back_to_listed_before_issued_shares(
        self, trading_cls, service
    ):
        trading_cls.return_value.price_board.return_value = pd.DataFrame(
            [
                {
                    "symbol": "AAA",
                    "match_price": 10_000.0,
                    "listed_share": 1_500_000_000,
                }
            ]
        )
        vnstock = _mock_company(
            overview=pd.DataFrame([{"issue_share": 2_000_000_000}]),
            ratio_summary=pd.DataFrame(),
        )

        with (
            patch("src.stocks.company.service.Vnstock", return_value=vnstock),
            patch.object(service, "_get_52_week_metrics", return_value={}),
            patch.object(service, "_get_vn30_rank", return_value=None),
        ):
            result = service.get_stock_detail("AAA")

        assert result.market_cap == 15_000.0


class TestFiftyTwoWeekMetrics:
    def test_uses_vnstock_4_ohlcv_daily_bars(self, service):
        frame = pd.DataFrame(
            {
                "open": [69.0, 77.0, 59.0],
                "high": [70.5, 78.2, 75.0],
                "low": [60.0, 62.5, 52.6],
                "volume": [1_000_000, 2_000_000, 3_000_001],
            }
        )
        market = MagicMock()
        equity = market.return_value.equity.return_value
        equity.ohlcv.return_value = frame

        with patch("src.stocks.company.service.Market", market):
            result = service._get_52_week_metrics("VCB")

        market.return_value.equity.assert_called_once_with("VCB")
        equity.ohlcv.assert_called_once_with(count=260, source="VCI")
        # OHLCV quotes thousands of VND; the price board in the same payload
        # quotes plain VND, so the range has to be scaled to match it.
        assert result == {
            "high_52_week": 78_200.0,
            "low_52_week": 52_600.0,
            "avg_volume_52_week": 2_000_000,
            "session_open": 59_000.0,
        }

    def test_empty_ohlcv_does_not_invent_zeroes(self, service):
        market = MagicMock()
        market.return_value.equity.return_value.ohlcv.return_value = pd.DataFrame()

        with patch("src.stocks.company.service.Market", market):
            assert service._get_52_week_metrics("VCB") == {}

    @patch("src.stocks.company.service.Trading")
    def test_daily_bar_supplies_the_open_the_price_board_omits(
        self, trading_cls, service
    ):
        """The price board has no open column, so the card had nothing to show."""
        trading_cls.return_value.price_board.return_value = pd.DataFrame(
            [{"symbol": "VCB", "match_price": 59_700.0, "ref_price": 59_000.0}]
        )
        vnstock = _mock_company(
            overview=pd.DataFrame(),
            ratio_summary=pd.DataFrame(),
        )
        metrics = {
            "high_52_week": 78_150.0,
            "low_52_week": 52_600.0,
            "avg_volume_52_week": 7_361_833,
            "session_open": 59_000.0,
        }

        with (
            patch("src.stocks.company.service.Vnstock", return_value=vnstock),
            patch.object(service, "_get_52_week_metrics", return_value=metrics),
            patch.object(service, "_get_vn30_rank", return_value=None),
        ):
            result = service.get_stock_detail("VCB")

        assert result.open_price == 59_000.0
        assert result.high_52_week == 78_150.0
        assert result.low_52_week == 52_600.0


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
