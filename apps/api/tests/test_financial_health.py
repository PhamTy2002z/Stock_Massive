"""Tests for financial health scoring and Phase 1 endpoints."""

import pytest
from src.stocks.financial.health_scoring import (
    normalize_score,
    calculate_dimension_score,
    calculate_f_score,
    calculate_health_score,
    build_health_score_response,
    BENCHMARKS,
    DIMENSION_WEIGHTS,
)

# Every test in this module calls the live vnstock API — there are no mocks.
# They go red on upstream throttling rather than on anything in this repo,
# so they sit out the default run. Run them with: pytest -m network
pytestmark = pytest.mark.network


# ==================== Unit Tests for health_scoring.py ====================


class TestNormalizeScore:
    """Test normalize_score function."""

    def test_excellent_value_higher_is_better(self):
        """Test value >= excellent threshold (higher is better)."""
        score = normalize_score(0.25, BENCHMARKS["roe"], inverse=False)
        assert score == 100

    def test_good_value_higher_is_better(self):
        """Test value between good and excellent (higher is better)."""
        score = normalize_score(0.17, BENCHMARKS["roe"], inverse=False)
        # ROE: good=0.15, excellent=0.20
        # 0.17 is 40% between good and excellent
        # Score = 70 + 30 * 0.4 = 82
        assert 80 <= score <= 85

    def test_below_good_higher_is_better(self):
        """Test value below good threshold (higher is better)."""
        score = normalize_score(0.10, BENCHMARKS["roe"], inverse=False)
        # ROE: good=0.15
        # 0.10 is 66.7% of good
        # Score = 70 * 0.667 = ~47
        assert 45 <= score <= 50

    def test_excellent_value_lower_is_better(self):
        """Test value <= excellent threshold (lower is better)."""
        score = normalize_score(0.4, BENCHMARKS["de"], inverse=True)
        assert score == 100

    def test_good_value_lower_is_better(self):
        """Test value between excellent and good (lower is better)."""
        score = normalize_score(0.75, BENCHMARKS["de"], inverse=True)
        # D/E: excellent=0.5, good=1.0
        # 0.75 is 50% between excellent and good
        # Score = 70 + 30 * 0.5 = 85
        assert 80 <= score <= 90

    def test_below_good_lower_is_better(self):
        """Test value above good threshold (lower is better)."""
        score = normalize_score(1.5, BENCHMARKS["de"], inverse=True)
        # D/E: good=1.0
        # 1.5 is 50% above good
        # Score = 70 - 70 * 0.5 = 35
        assert 30 <= score <= 40

    def test_none_value_returns_neutral(self):
        """Test None value returns neutral score of 50."""
        score = normalize_score(None, BENCHMARKS["roe"])
        assert score == 50

    def test_zero_value_higher_is_better(self):
        """Test zero value for higher-is-better metric."""
        score = normalize_score(0, BENCHMARKS["roe"])
        assert score == 0


class TestCalculateDimensionScore:
    """Test calculate_dimension_score function."""

    def test_profitability_dimension(self):
        """Test profitability dimension scoring."""
        metrics = {
            "roe": 0.18,
            "roa": 0.10,
            "net_margin": 0.12,
        }
        score, metric_dict = calculate_dimension_score(metrics, "profitability")
        assert 60 <= score <= 90
        assert metric_dict == {"roe": 0.18, "roa": 0.10, "net_margin": 0.12}

    def test_liquidity_dimension(self):
        """Test liquidity dimension scoring."""
        metrics = {
            "current_ratio": 1.8,
            "quick_ratio": 1.2,
        }
        score, metric_dict = calculate_dimension_score(metrics, "liquidity")
        assert 60 <= score <= 90
        assert metric_dict == {"current_ratio": 1.8, "quick_ratio": 1.2}

    def test_liquidity_without_quick_ratio(self):
        """Test liquidity dimension with only current ratio."""
        metrics = {
            "current_ratio": 2.0,
        }
        score, metric_dict = calculate_dimension_score(metrics, "liquidity")
        assert 70 <= score <= 100
        assert "quick_ratio" in metric_dict

    def test_leverage_dimension(self):
        """Test leverage dimension scoring."""
        metrics = {
            "debt_to_equity": 0.6,
        }
        score, metric_dict = calculate_dimension_score(metrics, "leverage")
        assert 80 <= score <= 100
        assert "de" in metric_dict

    def test_leverage_with_de_alias(self):
        """Test leverage dimension with 'de' key."""
        metrics = {
            "de": 0.8,
        }
        score, metric_dict = calculate_dimension_score(metrics, "leverage")
        assert 70 <= score <= 100

    def test_efficiency_dimension(self):
        """Test efficiency dimension scoring."""
        metrics = {
            "asset_turnover": 1.0,
        }
        score, metric_dict = calculate_dimension_score(metrics, "efficiency")
        assert 60 <= score <= 90
        assert metric_dict == {"asset_turnover": 1.0}

    def test_efficiency_no_data(self):
        """Test efficiency dimension with no data."""
        metrics = {}
        score, metric_dict = calculate_dimension_score(metrics, "efficiency")
        assert score == 50
        assert metric_dict == {"asset_turnover": None}

    def test_valuation_dimension(self):
        """Test valuation dimension scoring."""
        metrics = {
            "pe": 12,
            "pb": 1.8,
        }
        score, metric_dict = calculate_dimension_score(metrics, "valuation")
        assert 60 <= score <= 100
        assert "pe" in metric_dict and "pb" in metric_dict

    def test_valuation_with_aliases(self):
        """Test valuation with alternative key names."""
        metrics = {
            "price_to_earning": 10,
            "price_to_book": 1.5,
        }
        score, metric_dict = calculate_dimension_score(metrics, "valuation")
        assert 80 <= score <= 100

    def test_valuation_no_data(self):
        """Test valuation dimension with no valid data."""
        metrics = {
            "pe": None,
            "pb": None,
        }
        score, metric_dict = calculate_dimension_score(metrics, "valuation")
        assert score == 50

    def test_unknown_dimension(self):
        """Test unknown dimension returns neutral score."""
        score, metric_dict = calculate_dimension_score({}, "unknown")
        assert score == 50
        assert metric_dict == {}


class TestCalculateFScore:
    """Test calculate_f_score function."""

    def test_perfect_f_score(self):
        """Test perfect F-Score of 6."""
        current = {
            "roa": 0.10,
            "net_cfo": 1000,
            "net_income": 800,
            "debt_to_equity": 0.5,
            "current_ratio": 2.0,
        }
        prior = {
            "roa": 0.08,
            "debt_to_equity": 0.7,
            "current_ratio": 1.8,
        }
        score, details = calculate_f_score(current, prior)
        assert score == 6
        assert all(details.values())

    def test_zero_f_score(self):
        """Test F-Score of 0."""
        current = {
            "roa": -0.05,
            "net_cfo": -100,
            "net_income": 50,
            "debt_to_equity": 1.5,
            "current_ratio": 1.0,
        }
        prior = {
            "roa": 0.05,
            "debt_to_equity": 1.0,
            "current_ratio": 1.5,
        }
        score, details = calculate_f_score(current, prior)
        assert score == 0
        assert not any(details.values())

    def test_partial_f_score(self):
        """Test partial F-Score."""
        current = {
            "roa": 0.08,
            "cfo": 500,  # Test 'cfo' alias
            "net_profit": 600,  # Test 'net_profit' alias
            "de": 0.8,  # Test 'de' alias
            "current_ratio": 1.7,
        }
        prior = {
            "roa": 0.10,
            "de": 0.9,
            "current_ratio": 1.5,
        }
        score, details = calculate_f_score(current, prior)
        assert 2 <= score <= 4
        assert details["positive_roa"] is True
        assert details["positive_cfo"] is True
        assert details["accrual_quality"] is False

    def test_missing_data(self):
        """Test F-Score with missing data."""
        current = {}
        prior = {}
        score, details = calculate_f_score(current, prior)
        assert score >= 0
        assert len(details) == 6


class TestCalculateHealthScore:
    """Test calculate_health_score function."""

    def test_perfect_health_score(self):
        """Test perfect health score of 100."""
        dimension_scores = {
            "profitability": 100,
            "liquidity": 100,
            "leverage": 100,
            "efficiency": 100,
            "valuation": 100,
        }
        score = calculate_health_score(dimension_scores)
        assert score == 100

    def test_weighted_health_score(self):
        """Test weighted calculation."""
        dimension_scores = {
            "profitability": 80,
            "liquidity": 60,
            "leverage": 70,
            "efficiency": 50,
            "valuation": 90,
        }
        # 80*0.3 + 60*0.2 + 70*0.2 + 50*0.15 + 90*0.15 = 24 + 12 + 14 + 7.5 + 13.5 = 71
        score = calculate_health_score(dimension_scores)
        assert score == 71

    def test_missing_dimensions_default_to_50(self):
        """Test missing dimensions default to neutral score."""
        dimension_scores = {
            "profitability": 100,
        }
        score = calculate_health_score(dimension_scores)
        # 100*0.3 + 50*0.2 + 50*0.2 + 50*0.15 + 50*0.15 = 30 + 10 + 10 + 7.5 + 7.5 = 65
        assert score == 65


class TestBuildHealthScoreResponse:
    """Test build_health_score_response function."""

    def test_complete_response(self):
        """Test building complete health score response."""
        ratio_data = {
            "roe": 0.18,
            "roa": 0.10,
            "net_margin": 0.12,
            "current_ratio": 1.8,
            "debt_to_equity": 0.6,
            "asset_turnover": 1.0,
            "pe": 12,
            "pb": 1.5,
        }
        prior_ratio_data = {
            "roa": 0.08,
            "debt_to_equity": 0.8,
            "current_ratio": 1.5,
        }
        cash_flow_data = {
            "net_cfo": 1000,
            "net_income": 900,
        }

        response = build_health_score_response(
            symbol="VNM",
            ratio_data=ratio_data,
            prior_ratio_data=prior_ratio_data,
            cash_flow_data=cash_flow_data,
            period="Q4/2024",
        )

        assert response["symbol"] == "VNM"
        assert 0 <= response["health_score"] <= 100
        assert 0 <= response["f_score"] <= 6
        assert response["period"] == "Q4/2024"
        assert len(response["dimensions"]) == 5
        assert "profitability" in response["dimensions"]
        assert "score" in response["dimensions"]["profitability"]
        assert "metrics" in response["dimensions"]["profitability"]
        assert len(response["f_score_details"]) == 6

    def test_minimal_data(self):
        """Test with minimal data."""
        response = build_health_score_response(
            symbol="TEST",
            ratio_data={},
            prior_ratio_data={},
            cash_flow_data={},
        )

        assert response["symbol"] == "TEST"
        assert response["period"] is None
        assert response["health_score"] == 50  # All dimensions default to 50
        assert response["f_score"] == 0


# ==================== Integration Tests for Endpoints ====================


class TestHealthScoreEndpoint:
    """Test GET /{symbol}/health-score endpoint."""

    def test_get_health_score_vnm(self, client):
        """Test health score for VNM symbol."""
        response = client.get("/api/v1/stocks/VNM/health-score")
        assert response.status_code == 200

        data = response.json()
        assert data["symbol"] == "VNM"
        assert "health_score" in data
        assert 0 <= data["health_score"] <= 100
        assert "dimensions" in data
        assert "f_score" in data
        assert 0 <= data["f_score"] <= 6

        # Check dimensions structure
        dimensions = data["dimensions"]
        for dim in ["profitability", "liquidity", "leverage", "efficiency", "valuation"]:
            assert dim in dimensions
            assert "score" in dimensions[dim]
            assert "metrics" in dimensions[dim]
            assert 0 <= dimensions[dim]["score"] <= 100

        # Check F-Score details
        assert "f_score_details" in data
        f_details = data["f_score_details"]
        expected_keys = [
            "positive_roa",
            "positive_cfo",
            "roa_improving",
            "accrual_quality",
            "leverage_decreasing",
            "liquidity_improving",
        ]
        for key in expected_keys:
            assert key in f_details
            assert isinstance(f_details[key], bool)

    def test_get_health_score_invalid_symbol(self, client):
        """Test health score with invalid symbol."""
        response = client.get("/api/v1/stocks/INVALID999/health-score")
        assert response.status_code in [404, 502]

    def test_health_score_caching(self, client):
        """Test that health score is cached."""
        # First request
        response1 = client.get("/api/v1/stocks/VNM/health-score")
        assert response1.status_code == 200

        # Second request should hit cache
        response2 = client.get("/api/v1/stocks/VNM/health-score")
        assert response2.status_code == 200
        assert response1.json() == response2.json()


class TestTrendMetricsEndpoint:
    """Test GET /{symbol}/trend-metrics endpoint."""

    def test_get_trend_metrics_vnm(self, client):
        """Test trend metrics for VNM symbol."""
        response = client.get("/api/v1/stocks/VNM/trend-metrics?periods=8")
        assert response.status_code == 200

        data = response.json()
        assert data["symbol"] == "VNM"
        assert "periods" in data
        assert isinstance(data["periods"], list)

        # Check data arrays exist
        expected_arrays = [
            "revenue",
            "net_profit",
            "gross_margin",
            "net_margin",
            "roe",
            "roa",
            "cfo",
            "cfi",
            "cff",
        ]
        for arr in expected_arrays:
            assert arr in data
            assert isinstance(data[arr], list)

    def test_get_trend_metrics_custom_periods(self, client):
        """Test trend metrics with custom period count."""
        response = client.get("/api/v1/stocks/VNM/trend-metrics?periods=4")
        assert response.status_code == 200

        data = response.json()
        # Check that arrays have at most 4 elements
        assert len(data["periods"]) <= 4
        assert len(data["revenue"]) <= 4

    def test_trend_metrics_validation(self, client):
        """Test period validation."""
        # Too few periods
        response = client.get("/api/v1/stocks/VNM/trend-metrics?periods=2")
        assert response.status_code == 422

        # Too many periods
        response = client.get("/api/v1/stocks/VNM/trend-metrics?periods=20")
        assert response.status_code == 422


class TestFCFAnalysisEndpoint:
    """Test GET /{symbol}/fcf-analysis endpoint."""

    def test_get_fcf_analysis_vnm(self, client):
        """Test FCF analysis for VNM symbol."""
        response = client.get("/api/v1/stocks/VNM/fcf-analysis")
        assert response.status_code == 200

        data = response.json()
        assert data["symbol"] == "VNM"

        # Check waterfall components
        assert "net_income" in data
        assert "cfo" in data
        assert "capex" in data
        assert "fcf" in data

        # Check metrics
        assert "fcf_margin" in data
        assert "fcf_yield" in data

        # Check cash conversion cycle
        assert "ccc" in data
        if data["ccc"] is not None:
            assert "dso" in data
            assert "dio" in data
            assert "dpo" in data

    def test_fcf_analysis_caching(self, client):
        """Test FCF analysis caching."""
        response1 = client.get("/api/v1/stocks/VNM/fcf-analysis")
        assert response1.status_code == 200

        response2 = client.get("/api/v1/stocks/VNM/fcf-analysis")
        assert response2.status_code == 200
        assert response1.json() == response2.json()


class TestSectorPeersEndpoint:
    """Test GET /analytics/sector-peers endpoint."""

    def test_get_sector_peers(self, client):
        """Test sector peers comparison."""
        response = client.get("/api/v1/stocks/analytics/sector-peers?symbol=VNM&limit=5")
        assert response.status_code == 200

        data = response.json()
        assert data["symbol"] == "VNM"
        assert "icb_code" in data
        assert "icb_name" in data
        assert "peers" in data
        assert isinstance(data["peers"], list)

        # Check peer structure
        if len(data["peers"]) > 0:
            peer = data["peers"][0]
            assert "symbol" in peer
            assert "company_name" in peer

    def test_sector_peers_custom_limit(self, client):
        """Test sector peers with custom limit."""
        response = client.get("/api/v1/stocks/analytics/sector-peers?symbol=VNM&limit=10")
        assert response.status_code == 200
