"""Regression tests for provider-backed response-cache boundaries."""

from unittest.mock import Mock, patch

from src.core.cache import CacheRefreshUnavailable
from src.stocks.analytics.router import get_sector_peers
from src.stocks.company.router import get_stock_detail
from src.stocks.financial.router import get_balance_sheet_detailed


def test_stock_detail_cache_hit_does_not_call_provider_service():
    service = Mock()
    cached = {"symbol": "VCB", "price": 59_700}

    with (
        patch("src.stocks.company.router.get_company_service", return_value=service),
        patch(
            "src.stocks.company.router.stock_detail_cache.get_or_load",
            return_value=cached,
        ) as get_or_load,
    ):
        result = get_stock_detail("vcb")

    assert result.symbol == "VCB"
    assert result.price == 59_700
    get_or_load.assert_called_once()
    service.get_stock_detail.assert_not_called()


def test_financial_cache_hit_does_not_call_provider_service():
    service = Mock()
    cached = {"symbol": "VCB", "periods": [], "rows": [], "unit": "VND"}

    with (
        patch("src.stocks.financial.router.get_financial_service", return_value=service),
        patch(
            "src.stocks.financial.router.financial_response_cache.get_or_load",
            return_value=cached,
        ) as get_or_load,
    ):
        result = get_balance_sheet_detailed("vcb", "quarter", 4)

    assert result.symbol == "VCB"
    assert result.rows == []
    get_or_load.assert_called_once()
    service.get_balance_sheet_detailed.assert_not_called()


def test_sector_peers_cache_hit_does_not_call_provider_service():
    service = Mock()
    cached = {
        "symbol": "VCB",
        "icb_code": "8300",
        "icb_name": "Banks",
        "peers": [],
    }

    with (
        patch("src.stocks.analytics.router.get_financial_service", return_value=service),
        patch(
            "src.stocks.analytics.router.sector_peers_response_cache.get_or_load",
            return_value=cached,
        ) as get_or_load,
    ):
        result = get_sector_peers("vcb", 10)

    assert result.symbol == "VCB"
    assert result.icb_code == "8300"
    get_or_load.assert_called_once()
    service.get_sector_peers.assert_not_called()


def test_recent_cold_miss_failure_maps_to_retryable_503(client):
    with patch(
        "src.stocks.company.router.stock_detail_cache.get_or_load",
        side_effect=CacheRefreshUnavailable("Data refresh temporarily unavailable"),
    ):
        response = client.get("/api/v1/stocks/VCB/detail")

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "15"
    assert response.json() == {"detail": "Data refresh temporarily unavailable"}


def test_invalid_symbol_status_is_stable_across_repeated_requests(client):
    first = client.get("/api/v1/stocks/BAD!/detail")
    second = client.get("/api/v1/stocks/BAD!/detail")

    assert first.status_code == second.status_code == 502
    assert first.json() == second.json()


def test_existing_query_validation_precedes_symbol_validation(client):
    officers = client.get("/api/v1/stocks/BAD!/officers?filter_by=nope")
    ratios = client.get("/api/v1/stocks/BAD!/financials/ratios?period=nope")

    assert officers.status_code == 400
    assert ratios.status_code == 400
