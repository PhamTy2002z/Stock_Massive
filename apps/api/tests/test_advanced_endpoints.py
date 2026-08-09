"""Live checks for the supported advanced stock endpoint."""

import time

import pytest

from src.core.vnstock_client import VnstockUnavailable
from src.stocks.service import StockService
from src.stocks.shared import StockServiceError

# Every test in this module calls the live vnstock API — there are no mocks.
pytestmark = pytest.mark.network


class TestRatioSummaryEndpoint:
    """Contract checks for the retained ratio summary endpoint."""

    def test_success(self, client, valid_symbol):
        response = client.get(f"/api/v1/stocks/{valid_symbol}/ratio-summary")
        if response.status_code == 503:
            pytest.skip("Ratio summary temporarily unavailable upstream")

        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == valid_symbol.upper()
        for field in ["pe", "pb", "roe", "roa"]:
            assert field in data

    def test_invalid_symbol(self, client):
        response = client.get("/api/v1/stocks/INVALID_SYMBOL_XYZ/ratio-summary")
        assert response.status_code == 502

    def test_response_time(self, client, valid_symbol):
        times = []
        for _ in range(5):
            start = time.time()
            response = client.get(f"/api/v1/stocks/{valid_symbol}/ratio-summary")
            if response.status_code == 200:
                times.append(time.time() - start)

        if not times:
            pytest.skip("No successful responses to measure")

        times.sort()
        p95_idx = int(len(times) * 0.95) or len(times) - 1
        assert times[p95_idx] < 2.0

    def test_consistent_symbol(self, client, valid_symbol):
        response1 = client.get(f"/api/v1/stocks/{valid_symbol}/ratio-summary")
        response2 = client.get(f"/api/v1/stocks/{valid_symbol}/ratio-summary")
        if response1.status_code != 200 or response2.status_code != 200:
            pytest.skip("Ratio summary unavailable")

        assert response1.json()["symbol"] == response2.json()["symbol"]


def test_ratio_summary_service():
    """The facade retains the supported ratio summary service."""
    service = StockService(source="VCI")
    try:
        result = service.get_ratio_summary("VCB")
        assert result.symbol == "VCB"
        assert hasattr(result, "pe")
        assert hasattr(result, "pb")
        assert hasattr(result, "roe")
    except VnstockUnavailable:
        pytest.skip("Ratio summary temporarily unavailable upstream")
    except StockServiceError:
        pytest.skip("Ratio summary unavailable from vnstock API")
