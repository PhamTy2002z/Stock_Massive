"""Tests for Analytics API endpoints."""
import pytest
from datetime import datetime, date
from unittest.mock import AsyncMock, patch, MagicMock

from src.stocks.schemas.analytics import (
    VolumeSpikeItem,
    IndustryVolumeSpikeGroup,
    VolumeSpikeMetadata,
    VolumeSpikeResponse,
)
from src.stocks.schemas.price import VolumeAnomalyLevel


class TestVolumeSpikeAPI:
    """Test cases for GET /api/v1/stocks/analytics/volume-spikes endpoint."""

    def _create_mock_response(
        self,
        trade_date: date = None,
        total_spikes: int = 5,
        num_industries: int = 2,
    ) -> VolumeSpikeResponse:
        """Helper to create mock volume spike response."""
        if trade_date is None:
            trade_date = date(2024, 12, 20)

        industries = []
        for i in range(num_industries):
            stocks = [
                VolumeSpikeItem(
                    symbol=f"SYM{i}{j}",
                    company_name=f"Company {i}{j}",
                    exchange="HOSE",
                    current_volume=1000000 * (j + 1),
                    avg_volume_20d=500000,
                    spike_ratio=2.0 + j * 0.5,
                    price_change_pct=1.5,
                    close_price=25.5,
                    anomaly_level=VolumeAnomalyLevel.HIGH,
                    icb_code=f"100{i}",
                    icb_name=f"Industry {i}",
                )
                for j in range(3)
            ]
            industries.append(
                IndustryVolumeSpikeGroup(
                    icb_code=f"100{i}",
                    icb_name=f"Industry {i}",
                    spike_count=3,
                    avg_spike_ratio=2.5,
                    stocks=stocks,
                )
            )

        return VolumeSpikeResponse(
            trade_date=trade_date,
            total_spikes=total_spikes,
            industries=industries,
            metadata=VolumeSpikeMetadata(
                calculation_time_ms=150,
                cache_hit=False,
                symbols_processed=100,
                symbols_with_spikes=total_spikes,
            ),
        )

    def test_get_volume_spikes_default_params(self, client):
        """Test GET /analytics/volume-spikes with default parameters."""
        mock_response = self._create_mock_response()

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_volume_spikes.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.volume_spikes_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.volume_spikes_cache.set"):
                    response = client.get("/api/v1/stocks/analytics/volume-spikes")

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "trade_date" in data
        assert "total_spikes" in data
        assert "industries" in data
        assert "metadata" in data

        # Validate data
        assert data["total_spikes"] == 5
        assert len(data["industries"]) == 2
        assert data["metadata"]["cache_hit"] is False

    def test_get_volume_spikes_with_min_ratio(self, client):
        """Test GET /analytics/volume-spikes with custom min_ratio."""
        mock_response = self._create_mock_response(total_spikes=3)

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_volume_spikes.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.volume_spikes_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.volume_spikes_cache.set"):
                    response = client.get("/api/v1/stocks/analytics/volume-spikes?min_ratio=2.0")

        assert response.status_code == 200

        # Verify service was called with correct min_ratio
        call_kwargs = mock_service.get_volume_spikes.call_args[1]
        assert call_kwargs["min_ratio"] == 2.0

    def test_get_volume_spikes_with_exchange_filter(self, client):
        """Test GET /analytics/volume-spikes with exchange filter."""
        mock_response = self._create_mock_response()

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_volume_spikes.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.volume_spikes_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.volume_spikes_cache.set"):
                    response = client.get("/api/v1/stocks/analytics/volume-spikes?exchange=HOSE")

        assert response.status_code == 200

        # Verify service was called with exchange filter
        call_kwargs = mock_service.get_volume_spikes.call_args[1]
        assert call_kwargs["exchange"] == "HOSE"

    def test_get_volume_spikes_with_date(self, client):
        """Test GET /analytics/volume-spikes with specific date."""
        mock_response = self._create_mock_response(trade_date=date(2024, 12, 19))

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_volume_spikes.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.volume_spikes_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.volume_spikes_cache.set"):
                    response = client.get("/api/v1/stocks/analytics/volume-spikes?target_date=2024-12-19")

        assert response.status_code == 200
        data = response.json()
        assert data["trade_date"] == "2024-12-19"

        # Verify service was called with correct date
        call_kwargs = mock_service.get_volume_spikes.call_args[1]
        assert call_kwargs["target_date"] == date(2024, 12, 19)

    def test_get_volume_spikes_include_upcom(self, client):
        """Test GET /analytics/volume-spikes with include_upcom=true."""
        mock_response = self._create_mock_response()

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_volume_spikes.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.volume_spikes_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.volume_spikes_cache.set"):
                    response = client.get("/api/v1/stocks/analytics/volume-spikes?include_upcom=true")

        assert response.status_code == 200

        # Verify service was called with include_upcom=True
        call_kwargs = mock_service.get_volume_spikes.call_args[1]
        assert call_kwargs["include_upcom"] is True

    def test_get_volume_spikes_empty_result(self, client):
        """Test GET /analytics/volume-spikes when no spikes found."""
        mock_response = VolumeSpikeResponse(
            trade_date=date(2024, 12, 20),
            total_spikes=0,
            industries=[],
            metadata=VolumeSpikeMetadata(
                calculation_time_ms=50,
                cache_hit=False,
                symbols_processed=100,
                symbols_with_spikes=0,
            ),
        )

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_volume_spikes.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.volume_spikes_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.volume_spikes_cache.set"):
                    response = client.get("/api/v1/stocks/analytics/volume-spikes")

        assert response.status_code == 200
        data = response.json()

        assert data["total_spikes"] == 0
        assert data["industries"] == []

    def test_get_volume_spikes_min_ratio_validation(self, client):
        """Test GET /analytics/volume-spikes with invalid min_ratio values."""
        # Test min_ratio < 1.0
        response = client.get("/api/v1/stocks/analytics/volume-spikes?min_ratio=0.5")
        assert response.status_code == 422

        # Test min_ratio > 5.0
        response = client.get("/api/v1/stocks/analytics/volume-spikes?min_ratio=6.0")
        assert response.status_code == 422

    def test_get_volume_spikes_limit_validation(self, client):
        """Test GET /analytics/volume-spikes with invalid limit values."""
        # Test limit < 10
        response = client.get("/api/v1/stocks/analytics/volume-spikes?limit=5")
        assert response.status_code == 422

        # Test limit > 200
        response = client.get("/api/v1/stocks/analytics/volume-spikes?limit=250")
        assert response.status_code == 422

    def test_get_volume_spikes_exchange_validation(self, client):
        """Test GET /analytics/volume-spikes with invalid exchange value."""
        response = client.get("/api/v1/stocks/analytics/volume-spikes?exchange=INVALID")
        assert response.status_code == 422

    def test_get_volume_spikes_uses_cache(self, client):
        """Test that endpoint uses cache when available."""
        cached_data = {
            "trade_date": "2024-12-20",
            "total_spikes": 10,
            "industries": [],
            "metadata": {
                "calculation_time_ms": 100,
                "cache_hit": False,
                "symbols_processed": 50,
                "symbols_with_spikes": 10,
            },
        }

        with patch("src.stocks.analytics.router.volume_spikes_cache.get", return_value=cached_data):
            with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
                mock_service = AsyncMock()
                mock_service_class.return_value = mock_service

                response = client.get("/api/v1/stocks/analytics/volume-spikes")

        assert response.status_code == 200
        data = response.json()

        # Should return cached data with cache_hit=True
        assert data["total_spikes"] == 10
        assert data["metadata"]["cache_hit"] is True

        # Service should NOT be called
        mock_service.get_volume_spikes.assert_not_called()

    def test_get_volume_spikes_caches_result(self, client):
        """Test that endpoint caches the result."""
        mock_response = self._create_mock_response()

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_volume_spikes.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.volume_spikes_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.volume_spikes_cache.set") as mock_cache_set:
                    response = client.get("/api/v1/stocks/analytics/volume-spikes")

        assert response.status_code == 200

        # Verify cache.set was called
        mock_cache_set.assert_called_once()

    def test_get_volume_spikes_response_schema(self, client):
        """Test that response matches expected schema exactly."""
        mock_response = self._create_mock_response(num_industries=1)

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_volume_spikes.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.volume_spikes_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.volume_spikes_cache.set"):
                    response = client.get("/api/v1/stocks/analytics/volume-spikes")

        assert response.status_code == 200
        data = response.json()

        # Validate top-level schema
        required_keys = {"trade_date", "total_spikes", "industries", "metadata"}
        assert set(data.keys()) == required_keys

        # Validate metadata schema
        metadata_keys = {"calculation_time_ms", "cache_hit", "symbols_processed", "symbols_with_spikes"}
        assert set(data["metadata"].keys()) == metadata_keys

        # Validate industry group schema
        industry = data["industries"][0]
        industry_keys = {"icb_code", "icb_name", "spike_count", "avg_spike_ratio", "stocks"}
        assert set(industry.keys()) == industry_keys

        # Validate stock item schema
        stock = industry["stocks"][0]
        stock_keys = {
            "symbol", "company_name", "exchange", "current_volume",
            "avg_volume_20d", "spike_ratio", "price_change_pct",
            "close_price", "anomaly_level", "icb_code", "icb_name"
        }
        assert set(stock.keys()) == stock_keys

    def test_get_volume_spikes_combined_filters(self, client):
        """Test GET /analytics/volume-spikes with multiple filters."""
        mock_response = self._create_mock_response()

        with patch("src.stocks.analytics.router.AnalyticsService") as mock_service_class:
            mock_service = AsyncMock()
            mock_service.get_volume_spikes.return_value = mock_response
            mock_service_class.return_value = mock_service

            with patch("src.stocks.analytics.router.volume_spikes_cache.get", return_value=None):
                with patch("src.stocks.analytics.router.volume_spikes_cache.set"):
                    response = client.get(
                        "/api/v1/stocks/analytics/volume-spikes"
                        "?target_date=2024-12-19&min_ratio=2.5&exchange=HNX&include_upcom=false&limit=30"
                    )

        assert response.status_code == 200

        # Verify service called with all params
        call_kwargs = mock_service.get_volume_spikes.call_args[1]
        assert call_kwargs["target_date"] == date(2024, 12, 19)
        assert call_kwargs["min_ratio"] == 2.5
        assert call_kwargs["exchange"] == "HNX"
        assert call_kwargs["include_upcom"] is False
        assert call_kwargs["limit"] == 30
