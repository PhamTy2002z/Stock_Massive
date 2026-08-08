"""Tests for Phase 1 Sector Peers Enhancement.

Tests cover:
- SectorMedian schema serialization
- Premium/discount calculation
- Cache behavior
- Limit parameter validation (5-20)
"""
import pytest
from fastapi.testclient import TestClient
from src.main import app

# Every test in this module calls the live vnstock API — there are no mocks.
# They go red on upstream throttling rather than on anything in this repo,
# so they sit out the default run. Run them with: pytest -m network
pytestmark = pytest.mark.network

client = TestClient(app)


class TestSectorPeersEnhancement:
    """Phase 1: Test sector peers endpoint enhancement."""

    def test_get_sector_peers_basic(self):
        """Test basic sector peers retrieval with new schema."""
        response = client.get("/api/v1/stocks/analytics/sector-peers?symbol=VNM&limit=10")
        assert response.status_code == 200

        data = response.json()
        assert data["symbol"] == "VNM"
        assert "icb_code" in data
        assert "icb_name" in data
        assert "peers" in data
        assert isinstance(data["peers"], list)

        # Check SectorMedian schema
        assert "sector_median" in data
        if data["sector_median"]:
            median = data["sector_median"]
            assert "pe" in median
            assert "pb" in median
            assert "roe" in median
            assert "roa" in median
            assert "market_cap" in median

        # Check target premium
        assert "target_premium" in data
        if data["target_premium"]:
            premium = data["target_premium"]
            assert "pe" in premium
            assert "pb" in premium
            assert "roe" in premium
            assert "roa" in premium

    def test_peer_metrics_schema(self):
        """Test PeerMetrics schema with premium/discount fields."""
        response = client.get("/api/v1/stocks/analytics/sector-peers?symbol=VCB&limit=5")
        assert response.status_code == 200

        data = response.json()
        peers = data["peers"]
        assert len(peers) > 0

        # Check first peer has all required fields
        peer = peers[0]
        assert "symbol" in peer
        assert "company_name" in peer
        assert "roe" in peer
        assert "roa" in peer
        assert "pe" in peer
        assert "pb" in peer
        assert "market_cap" in peer

        # Check premium/discount fields
        assert "premium_pe" in peer
        assert "premium_pb" in peer
        assert "premium_roe" in peer
        assert "premium_roa" in peer

    def test_limit_validation_minimum(self):
        """Test minimum limit validation (5)."""
        # Valid: limit=5
        response = client.get("/api/v1/stocks/analytics/sector-peers?symbol=HPG&limit=5")
        assert response.status_code == 200

        # Invalid: limit=4
        response = client.get("/api/v1/stocks/analytics/sector-peers?symbol=HPG&limit=4")
        assert response.status_code == 422

    def test_limit_validation_maximum(self):
        """Test maximum limit validation (20)."""
        # Valid: limit=20
        response = client.get("/api/v1/stocks/analytics/sector-peers?symbol=HPG&limit=20")
        assert response.status_code == 200

        # Invalid: limit=21
        response = client.get("/api/v1/stocks/analytics/sector-peers?symbol=HPG&limit=21")
        assert response.status_code == 422

    def test_limit_default_value(self):
        """Test default limit value (10)."""
        response = client.get("/api/v1/stocks/analytics/sector-peers?symbol=VNM")
        assert response.status_code == 200

        data = response.json()
        # Should return up to 11 peers (10 + target if not in top 10)
        assert len(data["peers"]) <= 11

    def test_cache_behavior(self):
        """Test caching by calling same endpoint twice."""
        # First call
        response1 = client.get("/api/v1/stocks/analytics/sector-peers?symbol=VNM&limit=8")
        assert response1.status_code == 200

        # Second call (should hit cache)
        response2 = client.get("/api/v1/stocks/analytics/sector-peers?symbol=VNM&limit=8")
        assert response2.status_code == 200

        # Results should be identical
        assert response1.json() == response2.json()

    def test_invalid_symbol(self):
        """Test invalid symbol returns 502 (external service error)."""
        response = client.get("/api/v1/stocks/analytics/sector-peers?symbol=INVALID999")
        assert response.status_code == 502

    def test_premium_calculation_logic(self):
        """Test premium/discount calculation accuracy."""
        response = client.get("/api/v1/stocks/analytics/sector-peers?symbol=VNM&limit=10")
        assert response.status_code == 200

        data = response.json()
        median = data.get("sector_median")
        if not median:
            pytest.skip("No sector median available")

        # Find target in peers
        target = next((p for p in data["peers"] if p["symbol"] == "VNM"), None)
        if not target:
            pytest.skip("Target not in peers")

        # Verify premium calculation formula: ((value - median) / median) * 100
        if target.get("pe") and median.get("pe"):
            expected_premium = ((target["pe"] - median["pe"]) / abs(median["pe"])) * 100
            assert abs(target["premium_pe"] - expected_premium) < 0.01  # Allow small float diff

        if target.get("pb") and median.get("pb"):
            expected_premium = ((target["pb"] - median["pb"]) / abs(median["pb"])) * 100
            assert abs(target["premium_pb"] - expected_premium) < 0.01
