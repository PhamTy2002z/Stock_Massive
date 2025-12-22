"""Tests for Analytics API endpoints."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from src.stocks.schemas.analytics import TopPerformerItem, TopPerformersResponse


class TestTopPerformersAPI:
    """Test cases for GET /api/v1/stocks/analytics/top-performers endpoint."""

    def test_get_top_performers_default_params(self, client):
        """Test GET /analytics/top-performers with default parameters."""
        # Mock the service to return a valid response
        mock_response = TopPerformersResponse(
            period="Q4-2024",
            updated_at=datetime(2024, 12, 22, 10, 0, 0),
            total=100,
            data=[
                TopPerformerItem(
                    rank=1,
                    symbol="VCB",
                    company_name="Vietcombank",
                    exchange="HOSE",
                    net_profit=15000000000000,
                    revenue=50000000000000,
                    profit_margin=30.0,
                    eps=15000.0,
                    year=2024,
                    quarter=4,
                ),
                TopPerformerItem(
                    rank=2,
                    symbol="FPT",
                    company_name="FPT Corp",
                    exchange="HOSE",
                    net_profit=10000000000000,
                    revenue=40000000000000,
                    profit_margin=25.0,
                    eps=12000.0,
                    year=2024,
                    quarter=4,
                ),
            ],
        )

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_top_performers.return_value = mock_response
            mock_service_class.return_value = mock_service

            # Clear cache to avoid interference
            with patch("src.stocks.analytics.router.top_performers_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.top_performers_cache.set"):
                    response = client.get("/api/v1/stocks/analytics/top-performers")

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "period" in data
        assert "updated_at" in data
        assert "total" in data
        assert "data" in data

        # Validate data
        assert data["period"] == "Q4-2024"
        assert data["total"] == 100
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 2

        # Validate first item
        assert data["data"][0]["rank"] == 1
        assert data["data"][0]["symbol"] == "VCB"
        assert data["data"][0]["company_name"] == "Vietcombank"
        assert data["data"][0]["exchange"] == "HOSE"
        assert data["data"][0]["net_profit"] == 15000000000000
        assert data["data"][0]["year"] == 2024
        assert data["data"][0]["quarter"] == 4

    def test_get_top_performers_with_limit(self, client):
        """Test GET /analytics/top-performers with custom limit."""
        mock_response = TopPerformersResponse(
            period="Q4-2024",
            updated_at=datetime(2024, 12, 22, 10, 0, 0),
            total=100,
            data=[
                TopPerformerItem(
                    rank=i,
                    symbol=f"SYM{i}",
                    company_name=f"Company {i}",
                    exchange="HOSE",
                    net_profit=1000000000000 * (11 - i),
                    revenue=5000000000000,
                    profit_margin=20.0,
                    eps=1000.0,
                    year=2024,
                    quarter=4,
                )
                for i in range(1, 11)
            ],
        )

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_top_performers.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.top_performers_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.top_performers_cache.set"):
                    response = client.get("/api/v1/stocks/analytics/top-performers?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 10

        # Verify service was called with correct limit
        mock_service.get_top_performers.assert_called_once()
        call_kwargs = mock_service.get_top_performers.call_args[1]
        assert call_kwargs["limit"] == 10

    def test_get_top_performers_with_exchange_filter(self, client):
        """Test GET /analytics/top-performers with exchange filter."""
        mock_response = TopPerformersResponse(
            period="Q4-2024",
            updated_at=datetime(2024, 12, 22, 10, 0, 0),
            total=50,
            data=[
                TopPerformerItem(
                    rank=1,
                    symbol="FPT",
                    company_name="FPT Corp",
                    exchange="HOSE",
                    net_profit=10000000000000,
                    revenue=40000000000000,
                    profit_margin=25.0,
                    eps=12000.0,
                    year=2024,
                    quarter=4,
                ),
            ],
        )

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_top_performers.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.top_performers_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.top_performers_cache.set"):
                    response = client.get("/api/v1/stocks/analytics/top-performers?exchange=HOSE")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 50

        # Verify all returned items are from HOSE
        for item in data["data"]:
            assert item["exchange"] == "HOSE"

        # Verify service was called with exchange filter
        call_kwargs = mock_service.get_top_performers.call_args[1]
        assert call_kwargs["exchange"] == "HOSE"

    def test_get_top_performers_with_period_filter(self, client):
        """Test GET /analytics/top-performers with year and quarter filters."""
        mock_response = TopPerformersResponse(
            period="Q3-2024",
            updated_at=datetime(2024, 9, 30, 10, 0, 0),
            total=80,
            data=[
                TopPerformerItem(
                    rank=1,
                    symbol="VCB",
                    company_name="Vietcombank",
                    exchange="HOSE",
                    net_profit=14000000000000,
                    revenue=48000000000000,
                    profit_margin=29.17,
                    eps=14500.0,
                    year=2024,
                    quarter=3,
                ),
            ],
        )

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_top_performers.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.top_performers_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.top_performers_cache.set"):
                    response = client.get("/api/v1/stocks/analytics/top-performers?year=2024&quarter=3")

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "Q3-2024"

        # Verify all items are from Q3-2024
        for item in data["data"]:
            assert item["year"] == 2024
            assert item["quarter"] == 3

        # Verify service was called with correct params
        call_kwargs = mock_service.get_top_performers.call_args[1]
        assert call_kwargs["year"] == 2024
        assert call_kwargs["quarter"] == 3

    def test_get_top_performers_empty_database(self, client):
        """Test GET /analytics/top-performers when database is empty."""
        mock_response = TopPerformersResponse(
            period="N/A",
            updated_at=None,
            total=0,
            data=[],
        )

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_top_performers.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.top_performers_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.top_performers_cache.set"):
                    response = client.get("/api/v1/stocks/analytics/top-performers")

        assert response.status_code == 200
        data = response.json()

        # Validate empty response structure
        assert data["period"] == "N/A"
        assert data["updated_at"] is None
        assert data["total"] == 0
        assert data["data"] == []

    def test_get_top_performers_limit_validation(self, client):
        """Test GET /analytics/top-performers with invalid limit values."""
        # Test limit < 1
        response = client.get("/api/v1/stocks/analytics/top-performers?limit=0")
        assert response.status_code == 422  # Validation error

        # Test limit > 100
        response = client.get("/api/v1/stocks/analytics/top-performers?limit=101")
        assert response.status_code == 422  # Validation error

    def test_get_top_performers_year_validation(self, client):
        """Test GET /analytics/top-performers with invalid year values."""
        # Test year < 2020
        response = client.get("/api/v1/stocks/analytics/top-performers?year=2019")
        assert response.status_code == 422  # Validation error

        # Test year > 2030
        response = client.get("/api/v1/stocks/analytics/top-performers?year=2031")
        assert response.status_code == 422  # Validation error

    def test_get_top_performers_quarter_validation(self, client):
        """Test GET /analytics/top-performers with invalid quarter values."""
        # Test quarter < 1
        response = client.get("/api/v1/stocks/analytics/top-performers?quarter=0")
        assert response.status_code == 422  # Validation error

        # Test quarter > 4
        response = client.get("/api/v1/stocks/analytics/top-performers?quarter=5")
        assert response.status_code == 422  # Validation error

    def test_get_top_performers_combined_filters(self, client):
        """Test GET /analytics/top-performers with multiple filters."""
        mock_response = TopPerformersResponse(
            period="Q2-2024",
            updated_at=datetime(2024, 6, 30, 10, 0, 0),
            total=25,
            data=[
                TopPerformerItem(
                    rank=1,
                    symbol="FPT",
                    company_name="FPT Corp",
                    exchange="HNX",
                    net_profit=9000000000000,
                    revenue=36000000000000,
                    profit_margin=25.0,
                    eps=11000.0,
                    year=2024,
                    quarter=2,
                ),
            ],
        )

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_top_performers.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.top_performers_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.top_performers_cache.set"):
                    response = client.get(
                        "/api/v1/stocks/analytics/top-performers"
                        "?limit=20&exchange=HNX&year=2024&quarter=2"
                    )

        assert response.status_code == 200
        data = response.json()

        # Verify service called with all params
        call_kwargs = mock_service.get_top_performers.call_args[1]
        assert call_kwargs["limit"] == 20
        assert call_kwargs["exchange"] == "HNX"
        assert call_kwargs["year"] == 2024
        assert call_kwargs["quarter"] == 2

    def test_get_top_performers_uses_cache(self, client):
        """Test that endpoint uses cache when available."""
        cached_data = {
            "period": "Q4-2024",
            "updated_at": "2024-12-22T10:00:00",
            "total": 100,
            "data": [
                {
                    "rank": 1,
                    "symbol": "CACHED",
                    "company_name": "Cached Company",
                    "exchange": "HOSE",
                    "net_profit": 99999999999999,
                    "revenue": 99999999999999,
                    "profit_margin": 99.9,
                    "eps": 99999.0,
                    "year": 2024,
                    "quarter": 4,
                }
            ],
        }

        with patch("src.stocks.analytics.router.top_performers_cache.get", return_value=cached_data):
            with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service

                response = client.get("/api/v1/stocks/analytics/top-performers")

        assert response.status_code == 200
        data = response.json()

        # Should return cached data
        assert data["data"][0]["symbol"] == "CACHED"

        # Service should NOT be called
        mock_service.get_top_performers.assert_not_called()

    def test_get_top_performers_caches_result(self, client):
        """Test that endpoint caches the result."""
        mock_response = TopPerformersResponse(
            period="Q4-2024",
            updated_at=datetime(2024, 12, 22, 10, 0, 0),
            total=50,
            data=[
                TopPerformerItem(
                    rank=1,
                    symbol="VCB",
                    company_name="Vietcombank",
                    exchange="HOSE",
                    net_profit=15000000000000,
                    revenue=50000000000000,
                    profit_margin=30.0,
                    eps=15000.0,
                    year=2024,
                    quarter=4,
                ),
            ],
        )

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_top_performers.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.top_performers_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.top_performers_cache.set") as mock_cache_set:
                    response = client.get("/api/v1/stocks/analytics/top-performers")

        assert response.status_code == 200

        # Verify cache.set was called
        mock_cache_set.assert_called_once()

        # Verify cached data matches response
        cached_data = mock_cache_set.call_args[0][1]
        assert cached_data["period"] == "Q4-2024"
        assert cached_data["total"] == 50

    def test_get_top_performers_cache_key_construction(self, client):
        """Test that cache key is built correctly with different params."""
        mock_response = TopPerformersResponse(
            period="Q4-2024",
            updated_at=None,
            total=0,
            data=[],
        )

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_top_performers.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.top_performers_cache.get", return_value=None) as mock_cache_get:
                with patch("src.stocks.analytics.router.top_performers_cache.set"):
                    # Test with all params
                    client.get("/api/v1/stocks/analytics/top-performers?limit=25&exchange=HOSE&year=2024&quarter=3")

                    # Verify cache key construction
                    cache_key = mock_cache_get.call_args[0][0]
                    assert "25" in cache_key
                    assert "HOSE" in cache_key
                    assert "2024" in cache_key
                    assert "3" in cache_key

    def test_get_top_performers_response_schema(self, client):
        """Test that response matches expected schema exactly."""
        mock_response = TopPerformersResponse(
            period="Q4-2024",
            updated_at=datetime(2024, 12, 22, 10, 0, 0),
            total=1,
            data=[
                TopPerformerItem(
                    rank=1,
                    symbol="VCB",
                    company_name="Vietcombank",
                    exchange="HOSE",
                    net_profit=15000000000000,
                    revenue=50000000000000,
                    profit_margin=30.0,
                    eps=15000.0,
                    year=2024,
                    quarter=4,
                ),
            ],
        )

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_top_performers.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.top_performers_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.top_performers_cache.set"):
                    response = client.get("/api/v1/stocks/analytics/top-performers")

        assert response.status_code == 200
        data = response.json()

        # Validate top-level schema
        required_keys = {"period", "updated_at", "total", "data"}
        assert set(data.keys()) == required_keys

        # Validate item schema
        item = data["data"][0]
        required_item_keys = {
            "rank", "symbol", "company_name", "exchange",
            "net_profit", "revenue", "profit_margin", "eps",
            "year", "quarter"
        }
        assert set(item.keys()) == required_item_keys

        # Validate types
        assert isinstance(data["period"], str)
        assert isinstance(data["total"], int)
        assert isinstance(data["data"], list)
        assert isinstance(item["rank"], int)
        assert isinstance(item["symbol"], str)
        assert isinstance(item["net_profit"], int)
        assert isinstance(item["profit_margin"], float)
