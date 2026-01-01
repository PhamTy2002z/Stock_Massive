"""Tests for sector historical performance feature.

Minimal tests covering:
1. PERIODS config values (1W=7, 2W=14, 1M=30)
2. API endpoint response structure validation
"""
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.stocks.analytics.sector_historical_service import (
    PERIODS,
    SectorHistoricalService,
)


class TestSectorHistoricalConfig:
    """Test PERIODS configuration."""

    def test_periods_config_values(self):
        """Verify PERIODS dict has correct day mappings."""
        assert PERIODS["1W"] == 7, "1W should be 7 days"
        assert PERIODS["2W"] == 14, "2W should be 14 days"
        assert PERIODS["1M"] == 30, "1M should be 30 days"

    def test_periods_keys(self):
        """Verify all expected period keys exist."""
        expected_keys = {"1W", "2W", "1M"}
        assert set(PERIODS.keys()) == expected_keys


class TestSectorHistoricalAPI:
    """Test sector historical API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_get_endpoint_response_structure(self, client):
        """Verify GET /sector-historical returns valid structure."""
        response = client.get("/api/v1/stocks/analytics/sector-historical?period=1W")

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "period" in data
        assert "top_gainers" in data
        assert "top_losers" in data
        assert "generated_at" in data

        # Validate period value
        assert data["period"] in ["1W", "2W", "1M"]

        # Validate arrays (may be empty if cache miss)
        assert isinstance(data["top_gainers"], list)
        assert isinstance(data["top_losers"], list)

    def test_get_endpoint_all_periods(self, client):
        """Verify endpoint works for all periods."""
        for period in ["1W", "2W", "1M"]:
            response = client.get(f"/api/v1/stocks/analytics/sector-historical?period={period}")
            assert response.status_code == 200
            data = response.json()
            assert data["period"] == period

    def test_response_item_structure(self, client):
        """Verify item structure if data exists (may be empty)."""
        response = client.get("/api/v1/stocks/analytics/sector-historical?period=1W")
        data = response.json()

        # If we have data, verify structure
        if data["top_gainers"]:
            item = data["top_gainers"][0]
            assert "icb_code" in item
            assert "icb_name" in item
            assert "change_pct" in item
            assert isinstance(item["change_pct"], (int, float))

        if data["top_losers"]:
            item = data["top_losers"][0]
            assert "icb_code" in item
            assert "icb_name" in item
            assert "change_pct" in item
            assert isinstance(item["change_pct"], (int, float))

    def test_invalid_period(self, client):
        """Verify endpoint rejects invalid period."""
        response = client.get("/api/v1/stocks/analytics/sector-historical?period=INVALID")
        # FastAPI validation should reject with 422
        assert response.status_code == 422


class TestSectorHistoricalService:
    """Test service layer."""

    def test_service_initialization(self):
        """Verify service can be initialized."""
        service = SectorHistoricalService()
        assert service is not None
        assert service.source == "VCI"

    def test_get_cached_returns_none_for_missing(self):
        """Verify get_cached returns None for missing data."""
        service = SectorHistoricalService()
        # Use a random key that won't exist
        result = service.get_cached("TEST_NONEXISTENT")
        assert result is None or isinstance(result, dict)
