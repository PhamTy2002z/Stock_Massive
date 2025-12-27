"""Tests for advanced Deep Dive tab endpoints."""

import pytest

from src.stocks.service import StockService
from src.stocks.shared import StockServiceError


class TestAdvancedEndpointsRouter:
    """Test cases for advanced Deep Dive API endpoints."""

    def test_price_depth_success(self, client, valid_symbol):
        """Test GET /api/v1/stocks/{symbol}/price-depth with valid symbol."""
        response = client.get(f"/api/v1/stocks/{valid_symbol}/price-depth")

        # May return 502 if vnstock API unavailable during market close
        if response.status_code == 502:
            pytest.skip("Price depth API unavailable (possibly market closed)")

        assert response.status_code == 200
        data = response.json()
        assert "symbol" in data
        assert data["symbol"] == valid_symbol.upper()
        assert "bid_1" in data
        assert "ask_1" in data
        assert "spread" in data
        assert "spread_percent" in data
        assert "total_bid_volume" in data
        assert "total_ask_volume" in data

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

    def test_invalid_symbol_price_depth(self, client):
        """Test price-depth with invalid symbol returns error."""
        response = client.get("/api/v1/stocks/INVALID_SYMBOL_XYZ/price-depth")

        # Invalid symbol should return 502 (service error)
        assert response.status_code == 502

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


class TestAdvancedEndpointsService:
    """Test cases for advanced Deep Dive service layer."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return StockService(source="VCI")

    def test_service_price_depth(self, service):
        """Test PriceService.get_price_depth method."""
        try:
            result = service.get_price_depth("VCB")
            assert result.symbol == "VCB"
            assert result.bid_1 is not None
            assert result.ask_1 is not None
            assert result.spread is not None
        except StockServiceError:
            pytest.skip("Price depth unavailable from vnstock API")

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
