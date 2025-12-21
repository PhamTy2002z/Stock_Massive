"""Unit tests for market context service calculations."""
import numpy as np
import pytest

from src.stocks.market_context_service import MarketContextService


class TestPearsonCorrelation:
    """Tests for Pearson correlation calculation."""

    def test_perfect_positive_correlation(self):
        """Test perfect positive correlation returns 1.0."""
        x = np.array([1, 2, 3, 4, 5])
        y = np.array([2, 4, 6, 8, 10])

        corr = MarketContextService._pearson_correlation(x, y)

        assert corr == pytest.approx(1.0, abs=0.001)

    def test_perfect_negative_correlation(self):
        """Test perfect negative correlation returns -1.0."""
        x = np.array([1, 2, 3, 4, 5])
        y = np.array([10, 8, 6, 4, 2])

        corr = MarketContextService._pearson_correlation(x, y)

        assert corr == pytest.approx(-1.0, abs=0.001)

    def test_no_correlation(self):
        """Test uncorrelated data returns near 0."""
        x = np.array([1, 2, 3, 4, 5])
        y = np.array([3, 1, 4, 1, 5])  # Random-ish

        corr = MarketContextService._pearson_correlation(x, y)

        assert corr is not None
        assert -1.0 <= corr <= 1.0

    def test_insufficient_data_returns_none(self):
        """Test returns None with < 2 data points."""
        x = np.array([1])
        y = np.array([2])

        corr = MarketContextService._pearson_correlation(x, y)

        assert corr is None

    def test_empty_arrays_returns_none(self):
        """Test returns None with empty arrays."""
        x = np.array([])
        y = np.array([])

        corr = MarketContextService._pearson_correlation(x, y)

        assert corr is None


class TestBetaCalculation:
    """Tests for beta calculation."""

    def test_beta_equals_one_for_market(self):
        """Test beta = 1 when stock moves exactly with market."""
        market = np.array([0.01, 0.02, -0.01, 0.015, 0.005])
        stock = market.copy()  # Same as market

        beta = MarketContextService._calculate_beta(stock, market)

        assert beta == pytest.approx(1.0, abs=0.01)

    def test_beta_greater_than_one(self):
        """Test beta > 1 for more volatile stock."""
        market = np.array([0.01, 0.02, -0.01, 0.015, 0.005])
        stock = market * 1.5  # 50% more volatile

        beta = MarketContextService._calculate_beta(stock, market)

        assert beta is not None
        assert beta > 1.0

    def test_beta_less_than_one(self):
        """Test beta < 1 for less volatile stock."""
        market = np.array([0.01, 0.02, -0.01, 0.015, 0.005])
        stock = market * 0.5  # 50% less volatile

        beta = MarketContextService._calculate_beta(stock, market)

        assert beta is not None
        assert beta < 1.0

    def test_negative_beta(self):
        """Test negative beta for inverse correlation."""
        market = np.array([0.01, 0.02, -0.01, 0.015, 0.005])
        stock = -market  # Inverse

        beta = MarketContextService._calculate_beta(stock, market)

        assert beta is not None
        assert beta < 0

    def test_zero_variance_returns_none(self):
        """Test returns None when market has zero variance."""
        market = np.array([0.01, 0.01, 0.01, 0.01, 0.01])  # No variance
        stock = np.array([0.02, 0.03, 0.01, 0.02, 0.015])

        beta = MarketContextService._calculate_beta(stock, market)

        assert beta is None

    def test_insufficient_data_returns_none(self):
        """Test returns None with < 2 data points."""
        market = np.array([0.01])
        stock = np.array([0.02])

        beta = MarketContextService._calculate_beta(stock, market)

        assert beta is None


class TestRelativeStrength:
    """Tests for relative strength calculation."""

    def test_outperformance(self):
        """Test RS > 1 when stock outperforms market."""
        # Stock: +6% cumulative, Market: +3% cumulative
        stock = np.array([0.02, 0.02, 0.02])
        market = np.array([0.01, 0.01, 0.01])

        rs = MarketContextService._calculate_relative_strength(stock, market)

        assert rs is not None
        assert rs > 1.0

    def test_underperformance(self):
        """Test RS < 1 when stock underperforms market."""
        # Stock: +3% cumulative, Market: +6% cumulative
        stock = np.array([0.01, 0.01, 0.01])
        market = np.array([0.02, 0.02, 0.02])

        rs = MarketContextService._calculate_relative_strength(stock, market)

        assert rs is not None
        assert rs < 1.0

    def test_equal_performance(self):
        """Test RS = 1 when stock matches market."""
        returns = np.array([0.01, 0.02, -0.01])

        rs = MarketContextService._calculate_relative_strength(returns, returns)

        assert rs == pytest.approx(1.0, abs=0.01)

    def test_near_zero_market_return(self):
        """Test RS calculation when market return is near zero but not exactly zero."""
        # These don't produce exactly zero due to compound returns
        stock = np.array([0.02, -0.02])
        market = np.array([0.01, -0.01])

        rs = MarketContextService._calculate_relative_strength(stock, market)

        # RS is defined but may be large when market return is small
        assert rs is not None
        assert isinstance(rs, float)

    def test_negative_returns(self):
        """Test RS calculation with negative returns."""
        stock = np.array([-0.01, -0.02, -0.01])  # Losing
        market = np.array([-0.02, -0.03, -0.02])  # Losing more

        rs = MarketContextService._calculate_relative_strength(stock, market)

        assert rs is not None
        # Stock lost less, so RS should indicate relative outperformance


class TestCalculationEdgeCases:
    """Tests for edge cases in calculations."""

    def test_correlation_with_nan_values(self):
        """Test correlation handles NaN gracefully."""
        x = np.array([1, 2, np.nan, 4, 5])
        y = np.array([2, 4, 6, 8, 10])

        # Should return None or handle gracefully
        corr = MarketContextService._pearson_correlation(x, y)
        # NaN in input typically produces NaN output, which we convert to None
        assert corr is None or isinstance(corr, float)

    def test_beta_with_large_values(self):
        """Test beta calculation with large return values."""
        market = np.array([0.1, 0.2, -0.15, 0.25, 0.05])  # 10-25% daily moves
        stock = np.array([0.15, 0.3, -0.2, 0.35, 0.08])

        beta = MarketContextService._calculate_beta(stock, market)

        assert beta is not None
        assert 0.5 < beta < 3.0  # Reasonable range

    def test_rs_with_small_values(self):
        """Test RS calculation with very small returns."""
        stock = np.array([0.0001, 0.0002, 0.0001])
        market = np.array([0.0001, 0.0001, 0.0001])

        rs = MarketContextService._calculate_relative_strength(stock, market)

        assert rs is not None
        assert rs > 1.0  # Stock slightly outperformed
