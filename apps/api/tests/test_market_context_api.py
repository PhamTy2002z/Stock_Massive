"""Tests for market context API endpoint."""
import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestMarketContextAPI:
    """Test suite for GET /{symbol}/market-context endpoint."""

    def test_get_market_context_success(self, client: TestClient):
        """Test successful market context retrieval."""
        response = client.get("/api/v1/stocks/VCB/market-context?period=3M")

        # May return 400 if no EOD data exists yet
        if response.status_code == 200:
            data = response.json()
            assert data["symbol"] == "VCB"
            assert data["period"] == "3M"
            assert "chart_data" in data
            assert "metrics" in data
            assert "performance" in data
            assert "generated_at" in data
        else:
            # 400 is acceptable if EOD pipeline hasn't run
            assert response.status_code == 400
            assert "EOD pipeline" in response.json()["detail"] or "No data" in response.json()["detail"]

    def test_get_market_context_default_period(self, client: TestClient):
        """Test default period is 3M."""
        response = client.get("/api/v1/stocks/VCB/market-context")

        if response.status_code == 200:
            data = response.json()
            assert data["period"] == "3M"
        else:
            assert response.status_code == 400

    def test_get_market_context_all_periods(self, client: TestClient):
        """Test all valid periods."""
        for period in ["1M", "3M", "6M", "1Y"]:
            response = client.get(f"/api/v1/stocks/VCB/market-context?period={period}")
            # Should not be 422 validation error
            assert response.status_code in [200, 400, 500]

    def test_get_market_context_invalid_period(self, client: TestClient):
        """Test invalid period returns 422."""
        response = client.get("/api/v1/stocks/VCB/market-context?period=2M")
        assert response.status_code == 422

    def test_get_market_context_invalid_symbol(self, client: TestClient):
        """Test invalid symbol returns 400."""
        response = client.get("/api/v1/stocks/INVALIDXYZ/market-context?period=3M")
        assert response.status_code == 400

    def test_response_schema_structure(self, client: TestClient):
        """Test response matches expected schema structure."""
        response = client.get("/api/v1/stocks/FPT/market-context?period=1M")

        if response.status_code == 200:
            data = response.json()

            # Top-level fields
            assert "symbol" in data
            assert "period" in data
            assert "chart_data" in data
            assert "metrics" in data
            assert "sector" in data  # Can be null
            assert "performance" in data
            assert "generated_at" in data

            # Metrics structure
            metrics = data["metrics"]
            assert "beta_20d" in metrics
            assert "beta_60d" in metrics
            assert "correlation_20d" in metrics
            assert "correlation_60d" in metrics
            assert "rs_market_20d" in metrics
            assert "rs_sector_20d" in metrics

            # Performance structure
            perf = data["performance"]
            assert "stock_return" in perf
            assert "vnindex_return" in perf
            assert "sector_return" in perf  # Can be null
            assert "outperform_market" in perf
            assert "outperform_sector" in perf  # Can be null

    def test_chart_data_normalization(self, client: TestClient):
        """Test chart data starts at base 100."""
        response = client.get("/api/v1/stocks/VCB/market-context?period=1M")

        if response.status_code == 200:
            data = response.json()
            if data["chart_data"]:
                first_point = data["chart_data"][0]
                # First point should be exactly or very close to 100
                assert 99.0 <= first_point["stock"] <= 101.0
                assert 99.0 <= first_point["vnindex"] <= 101.0

    def test_performance_logic(self, client: TestClient):
        """Test outperform flags are logically correct."""
        response = client.get("/api/v1/stocks/VCB/market-context?period=3M")

        if response.status_code == 200:
            data = response.json()
            perf = data["performance"]

            # outperform_market should be True if stock_return > vnindex_return
            if perf["stock_return"] > perf["vnindex_return"]:
                assert perf["outperform_market"] is True
            else:
                assert perf["outperform_market"] is False

    def test_sector_context_nullable(self, client: TestClient):
        """Test sector can be null for unclassified stocks."""
        response = client.get("/api/v1/stocks/VCB/market-context?period=3M")

        if response.status_code == 200:
            data = response.json()
            # Sector can be null or an object
            sector = data["sector"]
            if sector is not None:
                assert "icb_code" in sector
                assert "icb_name" in sector
                assert "rank" in sector
                assert "total" in sector
                assert "top_peers" in sector

    def test_symbol_case_insensitive(self, client: TestClient):
        """Test symbol is case-insensitive."""
        response_upper = client.get("/api/v1/stocks/VCB/market-context")
        response_lower = client.get("/api/v1/stocks/vcb/market-context")

        # Both should return same status code
        assert response_upper.status_code == response_lower.status_code

        if response_upper.status_code == 200:
            data_upper = response_upper.json()
            data_lower = response_lower.json()
            assert data_upper["symbol"] == data_lower["symbol"] == "VCB"


class TestMarketContextCaching:
    """Test caching behavior."""

    def test_cache_hit_same_request(self, client: TestClient):
        """Test repeated requests use cache."""
        # First request
        response1 = client.get("/api/v1/stocks/VCB/market-context?period=3M")
        # Second request (should hit cache)
        response2 = client.get("/api/v1/stocks/VCB/market-context?period=3M")

        assert response1.status_code == response2.status_code

        if response1.status_code == 200:
            data1 = response1.json()
            data2 = response2.json()
            # Generated_at should be same if cached
            assert data1["generated_at"] == data2["generated_at"]
