"""Tests for industry (ICB) classification normalisation.

These use stub frames rather than live vnstock. The bug this module exists to
prevent — vnstock 3.x -> 4.x renaming the industry columns — went unnoticed
precisely because every sector test hit the network and failed for what looked
like unrelated reasons.
"""
import pandas as pd
import pytest

from src.stocks.shared import StockServiceError, fetch_industry_mapping

# Shape returned by vnstock 4.x
V4_INDUSTRIES = pd.DataFrame(
    [
        {"symbol": "VNM", "industry_code": "19", "industry_name": "Thực phẩm - Đồ uống"},
        {"symbol": "VCB", "industry_code": "11", "industry_name": "Ngân hàng"},
        {"symbol": "CTG", "industry_code": "11", "industry_name": "Ngân hàng"},
    ]
)

V4_EXCHANGES = pd.DataFrame(
    [
        {"symbol": "VNM", "organ_name": "CTCP Sữa Việt Nam", "exchange": "HOSE"},
        {"symbol": "VCB", "organ_name": "Ngân hàng TMCP Ngoại thương", "exchange": "HOSE"},
        {"symbol": "CTG", "organ_name": "Ngân hàng TMCP Công thương", "exchange": "HOSE"},
    ]
)

# Shape returned by vnstock 3.x, which the app used to read
V3_INDUSTRIES = pd.DataFrame(
    [{"symbol": "VNM", "icb_code2": "8300", "icb_name2": "Food & Beverage"}]
)


class StubListing:
    """Minimal stand-in for vnstock's Listing."""

    def __init__(self, industries=None, exchanges=None, exchange_error=None):
        self._industries = V4_INDUSTRIES if industries is None else industries
        self._exchanges = V4_EXCHANGES if exchanges is None else exchanges
        self._exchange_error = exchange_error

    def symbols_by_industries(self):
        return self._industries

    def symbols_by_exchange(self):
        if self._exchange_error:
            raise self._exchange_error
        return self._exchanges


class TestFetchIndustryMapping:
    """Happy path against the vnstock 4.x schema."""

    def test_maps_industry_code_and_name(self):
        mapping = fetch_industry_mapping(StubListing())

        assert mapping["VNM"]["icb_code"] == "19"
        assert mapping["VNM"]["icb_name"] == "Thực phẩm - Đồ uống"

    def test_joins_company_name_and_exchange(self):
        mapping = fetch_industry_mapping(StubListing())

        assert mapping["VNM"]["company_name"] == "CTCP Sữa Việt Nam"
        assert mapping["VNM"]["exchange"] == "HOSE"

    def test_groups_peers_under_one_code(self):
        mapping = fetch_industry_mapping(StubListing())

        banks = [s for s, v in mapping.items() if v["icb_code"] == "11"]
        assert sorted(banks) == ["CTG", "VCB"]

    def test_skips_malformed_symbols(self):
        industries = pd.DataFrame(
            [
                {"symbol": "VNM", "industry_code": "19", "industry_name": "F&B"},
                {"symbol": "bad symbol!", "industry_code": "19", "industry_name": "F&B"},
                {"symbol": "", "industry_code": "19", "industry_name": "F&B"},
            ]
        )
        mapping = fetch_industry_mapping(StubListing(industries=industries))

        assert list(mapping) == ["VNM"]


class TestSchemaGuard:
    """The point of this module: a schema change must fail loudly."""

    def test_v3_schema_raises_instead_of_returning_blanks(self):
        """The regression that shipped: 3.x columns silently produced None."""
        with pytest.raises(StockServiceError) as exc:
            fetch_industry_mapping(StubListing(industries=V3_INDUSTRIES))

        assert "industry_code" in str(exc.value)

    def test_empty_frame_raises(self):
        with pytest.raises(StockServiceError):
            fetch_industry_mapping(StubListing(industries=pd.DataFrame()))

    def test_none_frame_raises(self):
        listing = StubListing()
        listing._industries = None  # upstream returned nothing at all

        with pytest.raises(StockServiceError):
            fetch_industry_mapping(listing)


class TestExchangeLookupIsBestEffort:
    """Industry data is what sector features need; profile data is a bonus."""

    def test_survives_exchange_lookup_failure(self):
        mapping = fetch_industry_mapping(
            StubListing(exchange_error=ConnectionError("upstream down"))
        )

        assert mapping["VNM"]["icb_code"] == "19"
        assert mapping["VNM"]["company_name"] is None
        assert mapping["VNM"]["exchange"] == ""

    def test_survives_exchange_schema_change(self):
        bad = pd.DataFrame([{"ticker": "VNM"}])  # 'symbol' column gone
        mapping = fetch_industry_mapping(StubListing(exchanges=bad))

        assert mapping["VNM"]["icb_code"] == "19"
        assert mapping["VNM"]["company_name"] is None

    def test_symbol_missing_from_exchange_feed(self):
        partial = pd.DataFrame([{"symbol": "VNM", "organ_name": "Vinamilk", "exchange": "HOSE"}])
        mapping = fetch_industry_mapping(StubListing(exchanges=partial))

        assert mapping["VCB"]["company_name"] is None
        assert mapping["VCB"]["icb_name"] == "Ngân hàng"


class TestTruncation:
    """Values land in bounded DB columns."""

    def test_long_values_are_truncated(self):
        industries = pd.DataFrame(
            [{"symbol": "VNM", "industry_code": "1" * 20, "industry_name": "x" * 400}]
        )
        mapping = fetch_industry_mapping(StubListing(industries=industries))

        assert len(mapping["VNM"]["icb_code"]) == 4
        assert len(mapping["VNM"]["icb_name"]) == 100

    def test_blank_values_become_none(self):
        industries = pd.DataFrame(
            [{"symbol": "VNM", "industry_code": "   ", "industry_name": None}]
        )
        mapping = fetch_industry_mapping(StubListing(industries=industries))

        assert mapping["VNM"]["icb_code"] is None
        assert mapping["VNM"]["icb_name"] is None
