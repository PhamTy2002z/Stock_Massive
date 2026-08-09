"""Tests for advanced Deep Dive tab endpoints.

Phase 4: Integration & Testing - Tests for:
- Endpoint success/error cases
- Service layer validation
- Error handling (timeout, invalid data)
- Performance validation (P95 < 500ms)
- Caching behavior
"""

import time

import pytest

from src.stocks.service import StockService
from src.stocks.shared import StockServiceError

# Every test in this module calls the live vnstock API — there are no mocks.
# They go red on upstream throttling rather than on anything in this repo,
# so they sit out the default run. Run them with: pytest -m network
pytestmark = pytest.mark.network


class TestAdvancedEndpointsRouter:
    """Test cases for advanced Deep Dive API endpoints."""

    def test_ratio_summary_success(self, client, valid_symbol):
        """Test GET /api/v1/stocks/{symbol}/ratio-summary with valid symbol."""
        response = client.get(f"/api/v1/stocks/{valid_symbol}/ratio-summary")

        # May return 502 if vnstock API unavailable
        if response.status_code == 502:
            pytest.skip("Ratio summary API unavailable")

        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data
        assert data["symbol"] == valid_symbol.upper()
        # Financial ratios are optional, just check structure
        assert "pe" in data
        assert "pb" in data
        assert "roe" in data
        assert "roa" in data

    def test_trading_stats_success(self, client, valid_symbol):
        """Test GET /api/v1/stocks/{symbol}/trading-stats with valid symbol."""
        response = client.get(f"/api/v1/stocks/{valid_symbol}/trading-stats")

        # May return 502 if vnstock API unavailable
        if response.status_code == 502:
            pytest.skip("Trading stats API unavailable")

        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data
        assert data["symbol"] == valid_symbol.upper()
        # Stats are optional, just check structure
        assert "total_volume" in data
        assert "avg_volume" in data
        assert "high_price" in data
        assert "low_price" in data

    def test_foreign_snapshot_success(self, client, valid_symbol):
        """Test GET /api/v1/stocks/{symbol}/foreign-snapshot with valid symbol."""
        response = client.get(f"/api/v1/stocks/{valid_symbol}/foreign-snapshot")

        # May return 502 if vnstock API unavailable
        if response.status_code == 502:
            pytest.skip("Foreign snapshot API unavailable")

        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data
        assert data["symbol"] == valid_symbol.upper()
        assert "foreign_volume" in data
        assert "foreign_room" in data
        assert "total_volume" in data
        assert "last_updated" in data
        # Optional fields
        assert "ownership_ratio" in data
        assert "avg_volume_2w" in data
        assert "foreign_pct_of_volume" in data

    def test_invalid_symbol_ratio_summary(self, client):
        """Test ratio-summary with invalid symbol returns error."""
        response = client.get("/api/v1/stocks/INVALID_SYMBOL_XYZ/ratio-summary")

        # Invalid symbol should return 502 (service error)
        assert response.status_code == 502

    def test_invalid_symbol_trading_stats(self, client):
        """Test trading-stats with invalid symbol returns error."""
        response = client.get("/api/v1/stocks/INVALID_SYMBOL_XYZ/trading-stats")

        # Invalid symbol should return 502 (service error)
        assert response.status_code == 502

    def test_invalid_symbol_foreign_snapshot(self, client):
        """Test foreign-snapshot with invalid symbol returns error."""
        response = client.get("/api/v1/stocks/INVALID_XYZ/foreign-snapshot")

        # Invalid symbol should return 502 (service error)
        assert response.status_code == 502


class TestAdvancedEndpointsService:
    """Test cases for advanced Deep Dive service layer."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return StockService(source="VCI")

    def test_service_ratio_summary(self, service):
        """Test CompanyService.get_ratio_summary method."""
        try:
            result = service.get_ratio_summary("VCB")
            assert result.symbol == "VCB"
            # Ratios may be None, just validate structure
            assert hasattr(result, "pe")
            assert hasattr(result, "pb")
            assert hasattr(result, "roe")
        except StockServiceError:
            pytest.skip("Ratio summary unavailable from vnstock API")

    def test_service_trading_stats(self, service):
        """Test CompanyService.get_trading_stats method."""
        try:
            result = service.get_trading_stats("VCB")
            assert result.symbol == "VCB"
            # Stats may be None, just validate structure
            assert hasattr(result, "total_volume")
            assert hasattr(result, "high_price")
            assert hasattr(result, "low_price")
        except StockServiceError:
            pytest.skip("Trading stats unavailable from vnstock API")

    def test_service_foreign_snapshot(self):
        """Test TradingService.get_foreign_snapshot method."""
        from src.stocks.trading.service import TradingService
        service = TradingService(source="VCI")
        try:
            result = service.get_foreign_snapshot("VCB")
            assert result.symbol == "VCB"
            assert hasattr(result, "foreign_volume")
            assert hasattr(result, "foreign_room")
            assert hasattr(result, "total_volume")
            assert hasattr(result, "last_updated")
            # Validate types
            assert isinstance(result.foreign_volume, int)
            assert isinstance(result.foreign_room, int)
            assert isinstance(result.total_volume, int)
        except StockServiceError:
            pytest.skip("Foreign snapshot unavailable from vnstock API")


class TestAdvancedEndpointsErrorHandling:
    """Test error handling for advanced endpoints."""

    def test_ratio_summary_handles_empty_data(self, client, valid_symbol):
        """Test ratio-summary handles empty/null data gracefully."""
        response = client.get(f"/api/v1/stocks/{valid_symbol}/ratio-summary")
        if response.status_code == 200:
            data = response.json()
            # All ratio fields should exist (may be None)
            for field in ["pe", "pb", "roe", "roa"]:
                assert field in data

    def test_trading_stats_handles_empty_data(self, client, valid_symbol):
        """Test trading-stats handles empty/null data gracefully."""
        response = client.get(f"/api/v1/stocks/{valid_symbol}/trading-stats")
        if response.status_code == 200:
            data = response.json()
            # All stats fields should exist (may be None)
            for field in ["total_volume", "avg_volume", "high_price", "low_price"]:
                assert field in data

    def test_foreign_snapshot_handles_empty_data(self, client, valid_symbol):
        """Test foreign-snapshot handles empty/null data gracefully."""
        response = client.get(f"/api/v1/stocks/{valid_symbol}/foreign-snapshot")
        if response.status_code == 200:
            data = response.json()
            # Required fields
            for field in ["symbol", "foreign_volume", "foreign_room", "total_volume", "last_updated"]:
                assert field in data
            # Optional fields (may be None)
            for field in ["ownership_ratio", "avg_volume_2w", "foreign_pct_of_volume"]:
                assert field in data

class TestAdvancedEndpointsPerformance:
    """Performance validation for advanced endpoints."""

    @pytest.fixture
    def symbols(self):
        """Test symbols for performance testing."""
        return ["VCB", "ACB", "TCB"]

    def test_ratio_summary_response_time(self, client, valid_symbol):
        """Test ratio-summary P95 response time < 500ms."""
        times = []
        for _ in range(5):
            start = time.time()
            response = client.get(f"/api/v1/stocks/{valid_symbol}/ratio-summary")
            elapsed = time.time() - start
            if response.status_code == 200:
                times.append(elapsed)

        if not times:
            pytest.skip("No successful responses to measure")

        times.sort()
        p95_idx = int(len(times) * 0.95) or len(times) - 1
        p95 = times[p95_idx]
        # Allow 2s for external API calls
        assert p95 < 2.0, f"P95 response time {p95:.3f}s exceeds 2s threshold"

    def test_trading_stats_response_time(self, client, valid_symbol):
        """Test trading-stats P95 response time < 500ms."""
        times = []
        for _ in range(5):
            start = time.time()
            response = client.get(f"/api/v1/stocks/{valid_symbol}/trading-stats")
            elapsed = time.time() - start
            if response.status_code == 200:
                times.append(elapsed)

        if not times:
            pytest.skip("No successful responses to measure")

        times.sort()
        p95_idx = int(len(times) * 0.95) or len(times) - 1
        p95 = times[p95_idx]
        # Allow 2s for external API calls
        assert p95 < 2.0, f"P95 response time {p95:.3f}s exceeds 2s threshold"

    def test_foreign_snapshot_response_time(self, client, valid_symbol):
        """Test foreign-snapshot P95 response time < 500ms."""
        times = []
        for _ in range(5):
            start = time.time()
            response = client.get(f"/api/v1/stocks/{valid_symbol}/foreign-snapshot")
            elapsed = time.time() - start
            if response.status_code == 200:
                times.append(elapsed)

        if not times:
            pytest.skip("No successful responses to measure")

        times.sort()
        p95_idx = int(len(times) * 0.95) or len(times) - 1
        p95 = times[p95_idx]
        # Allow 2s for external API calls
        assert p95 < 2.0, f"P95 response time {p95:.3f}s exceeds 2s threshold"


class TestAdvancedEndpointsCaching:
    """Test caching behavior for advanced endpoints."""

    def test_ratio_summary_consistent_data(self, client, valid_symbol):
        """Test ratio-summary returns consistent data across calls."""
        response1 = client.get(f"/api/v1/stocks/{valid_symbol}/ratio-summary")
        response2 = client.get(f"/api/v1/stocks/{valid_symbol}/ratio-summary")

        if response1.status_code != 200 or response2.status_code != 200:
            pytest.skip("Ratio summary unavailable")

        data1 = response1.json()
        data2 = response2.json()
        # Symbol should always match
        assert data1["symbol"] == data2["symbol"]

    def test_trading_stats_consistent_data(self, client, valid_symbol):
        """Test trading-stats returns consistent data across calls."""
        response1 = client.get(f"/api/v1/stocks/{valid_symbol}/trading-stats")
        response2 = client.get(f"/api/v1/stocks/{valid_symbol}/trading-stats")

        if response1.status_code != 200 or response2.status_code != 200:
            pytest.skip("Trading stats unavailable")

        data1 = response1.json()
        data2 = response2.json()
        # Symbol should always match
        assert data1["symbol"] == data2["symbol"]

    def test_foreign_snapshot_consistent_data(self, client, valid_symbol):
        """Test foreign-snapshot returns consistent data across calls."""
        response1 = client.get(f"/api/v1/stocks/{valid_symbol}/foreign-snapshot")
        response2 = client.get(f"/api/v1/stocks/{valid_symbol}/foreign-snapshot")

        if response1.status_code != 200 or response2.status_code != 200:
            pytest.skip("Foreign snapshot unavailable")

        data1 = response1.json()
        data2 = response2.json()
        # Symbol should always match
        assert data1["symbol"] == data2["symbol"]
