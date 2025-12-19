"""Tests for intraday data collection service."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.stocks.intraday_collector import IntradayCollector
from src.stocks.schemas import IntradayTick


class TestIntradayCollector:
    """Test cases for IntradayCollector."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def collector(self, mock_db):
        """Create collector instance with mocked dependencies."""
        with patch("src.stocks.service.get_stock_service"):
            return IntradayCollector(mock_db)

    @pytest.fixture
    def sample_ticks(self):
        """Create sample tick data for testing."""
        base_time = datetime(2025, 12, 18, 9, 0, 0)
        return [
            IntradayTick(
                time=datetime(2025, 12, 18, 9, 0, 0),
                price=100.0,
                volume=1000,
                accumulated_vol=1000,
                accumulated_val=100000,
                match_type="ATO",
            ),
            IntradayTick(
                time=datetime(2025, 12, 18, 9, 1, 30),
                price=101.0,
                volume=500,
                accumulated_vol=1500,
                accumulated_val=150500,
                match_type="LO",
            ),
            IntradayTick(
                time=datetime(2025, 12, 18, 9, 3, 45),
                price=99.5,
                volume=800,
                accumulated_vol=2300,
                accumulated_val=230100,
                match_type="LO",
            ),
            IntradayTick(
                time=datetime(2025, 12, 18, 9, 5, 10),
                price=102.0,
                volume=1200,
                accumulated_vol=3500,
                accumulated_val=352500,
                match_type="LO",
            ),
            IntradayTick(
                time=datetime(2025, 12, 18, 9, 7, 20),
                price=101.5,
                volume=600,
                accumulated_vol=4100,
                accumulated_val=413400,
                match_type="LO",
            ),
        ]

    def test_aggregate_ticks_to_bars_happy_path(self, collector, sample_ticks):
        """Test aggregation of tick data to 5-minute bars."""
        bars = collector.aggregate_ticks_to_bars(sample_ticks, interval_minutes=5)

        # Should create 2 bars: 09:00-09:05 and 09:05-09:10
        assert len(bars) == 2

        # First bar (09:00-09:05)
        bar1 = bars[0]
        assert bar1["bar_time"] == datetime(2025, 12, 18, 9, 0, 0)
        assert bar1["open_price"] == 100.0  # First price
        assert bar1["high_price"] == 101.0  # Max price
        assert bar1["low_price"] == 99.5  # Min price
        assert bar1["close_price"] == 99.5  # Last price
        assert bar1["volume"] == 2300  # Sum of volumes (1000 + 500 + 800)
        assert bar1["trade_count"] == 3  # Number of ticks

        # Second bar (09:05-09:10)
        bar2 = bars[1]
        assert bar2["bar_time"] == datetime(2025, 12, 18, 9, 5, 0)
        assert bar2["open_price"] == 102.0
        assert bar2["high_price"] == 102.0
        assert bar2["low_price"] == 101.5
        assert bar2["close_price"] == 101.5
        assert bar2["volume"] == 1800  # Sum of volumes (1200 + 600)
        assert bar2["trade_count"] == 2

    def test_aggregate_ticks_empty_list(self, collector):
        """Test aggregation with empty tick list."""
        bars = collector.aggregate_ticks_to_bars([])

        assert bars == []

    def test_aggregate_ticks_single_tick(self, collector):
        """Test aggregation with single tick."""
        single_tick = [
            IntradayTick(
                time=datetime(2025, 12, 18, 9, 2, 30),
                price=100.0,
                volume=1000,
                accumulated_vol=1000,
                accumulated_val=100000,
                match_type="LO",
            )
        ]

        bars = collector.aggregate_ticks_to_bars(single_tick)

        assert len(bars) == 1
        bar = bars[0]
        assert bar["bar_time"] == datetime(2025, 12, 18, 9, 0, 0)  # Floored to 09:00
        assert bar["open_price"] == 100.0
        assert bar["high_price"] == 100.0
        assert bar["low_price"] == 100.0
        assert bar["close_price"] == 100.0
        assert bar["volume"] == 1000
        assert bar["trade_count"] == 1
        assert bar["trade_value"] == 0  # Single tick has no accumulated_val difference

    def test_bar_time_flooring_to_5min_intervals(self, collector):
        """Test that bar times are correctly floored to 5-minute intervals."""
        ticks = [
            IntradayTick(
                time=datetime(2025, 12, 18, 9, 0, 0),
                price=100.0,
                volume=100,
                accumulated_vol=100,
                accumulated_val=10000,
                match_type="ATO",
            ),
            IntradayTick(
                time=datetime(2025, 12, 18, 9, 4, 59),
                price=101.0,
                volume=100,
                accumulated_vol=200,
                accumulated_val=20100,
                match_type="LO",
            ),
            IntradayTick(
                time=datetime(2025, 12, 18, 9, 5, 0),
                price=102.0,
                volume=100,
                accumulated_vol=300,
                accumulated_val=30300,
                match_type="LO",
            ),
            IntradayTick(
                time=datetime(2025, 12, 18, 9, 9, 59),
                price=103.0,
                volume=100,
                accumulated_vol=400,
                accumulated_val=40600,
                match_type="LO",
            ),
        ]

        bars = collector.aggregate_ticks_to_bars(ticks)

        assert len(bars) == 2
        # First bar should include 09:00:00 and 09:04:59
        assert bars[0]["bar_time"] == datetime(2025, 12, 18, 9, 0, 0)
        assert bars[0]["trade_count"] == 2
        # Second bar should include 09:05:00 and 09:09:59
        assert bars[1]["bar_time"] == datetime(2025, 12, 18, 9, 5, 0)
        assert bars[1]["trade_count"] == 2

    def test_trade_value_calculation(self, collector):
        """Test trade value calculation from accumulated_val differences."""
        ticks = [
            IntradayTick(
                time=datetime(2025, 12, 18, 9, 0, 0),
                price=100.0,
                volume=1000,
                accumulated_vol=1000,
                accumulated_val=100000,
                match_type="ATO",
            ),
            IntradayTick(
                time=datetime(2025, 12, 18, 9, 2, 0),
                price=101.0,
                volume=500,
                accumulated_vol=1500,
                accumulated_val=150500,
                match_type="LO",
            ),
            IntradayTick(
                time=datetime(2025, 12, 18, 9, 4, 0),
                price=102.0,
                volume=800,
                accumulated_vol=2300,
                accumulated_val=232100,
                match_type="LO",
            ),
        ]

        bars = collector.aggregate_ticks_to_bars(ticks)

        assert len(bars) == 1
        # Trade value should be last accumulated_val - first accumulated_val
        # 232100 - 100000 = 132100
        assert bars[0]["trade_value"] == 132100

    def test_aggregate_ticks_different_intervals(self, collector, sample_ticks):
        """Test aggregation with different interval sizes."""
        # Test 1-minute interval
        bars_1min = collector.aggregate_ticks_to_bars(sample_ticks, interval_minutes=1)
        assert len(bars_1min) >= 4  # Should have more bars with smaller interval

        # Test 10-minute interval
        bars_10min = collector.aggregate_ticks_to_bars(sample_ticks, interval_minutes=10)
        assert len(bars_10min) == 1  # All ticks should fit in one 10-minute bar

    def test_ohlc_logic_consistency(self, collector, sample_ticks):
        """Test that OHLC values follow logical constraints."""
        bars = collector.aggregate_ticks_to_bars(sample_ticks)

        for bar in bars:
            # High should be >= all other prices
            assert bar["high_price"] >= bar["open_price"]
            assert bar["high_price"] >= bar["close_price"]
            assert bar["high_price"] >= bar["low_price"]

            # Low should be <= all other prices
            assert bar["low_price"] <= bar["open_price"]
            assert bar["low_price"] <= bar["close_price"]
            assert bar["low_price"] <= bar["high_price"]

    @pytest.mark.asyncio
    async def test_collect_symbol_with_mock_service(self, collector, sample_ticks):
        """Test collect_symbol method with mocked stock service."""
        # Mock the stock service to return sample ticks
        collector.stock_service = MagicMock()
        collector.stock_service.get_intraday.return_value = sample_ticks

        bars = await collector.collect_symbol("VCB")

        # Verify stock service was called
        collector.stock_service.get_intraday.assert_called_once_with("VCB")

        # Verify bars were created and symbol was added
        assert len(bars) > 0
        for bar in bars:
            assert bar["symbol"] == "VCB"

    @pytest.mark.asyncio
    async def test_collect_symbol_empty_ticks(self, collector):
        """Test collect_symbol with no tick data."""
        collector.stock_service = MagicMock()
        collector.stock_service.get_intraday.return_value = []

        bars = await collector.collect_symbol("INVALID")

        assert bars == []

    def test_aggregate_ticks_preserves_datetime_type(self, collector, sample_ticks):
        """Test that bar_time is returned as datetime-compatible object."""
        bars = collector.aggregate_ticks_to_bars(sample_ticks)

        for bar in bars:
            # Should be datetime-compatible (either datetime or pandas Timestamp)
            assert hasattr(bar["bar_time"], "year")
            assert hasattr(bar["bar_time"], "month")
            assert hasattr(bar["bar_time"], "day")
            assert hasattr(bar["bar_time"], "hour")
            assert hasattr(bar["bar_time"], "minute")

    def test_aggregate_ticks_multiple_bars_same_interval(self, collector):
        """Test aggregation across multiple 5-minute intervals."""
        ticks = []
        base_time = datetime(2025, 12, 18, 9, 0, 0)

        # Create ticks spanning 30 minutes (6 bars)
        for i in range(30):
            ticks.append(
                IntradayTick(
                    time=datetime(2025, 12, 18, 9, i, 0),
                    price=100.0 + i * 0.1,
                    volume=100,
                    accumulated_vol=(i + 1) * 100,
                    accumulated_val=(i + 1) * 10000,
                    match_type="LO",
                )
            )

        bars = collector.aggregate_ticks_to_bars(ticks)

        # Should create 6 bars (09:00, 09:05, 09:10, 09:15, 09:20, 09:25)
        assert len(bars) == 6

        # Verify each bar has 5 ticks
        for bar in bars:
            assert bar["trade_count"] == 5
            assert bar["volume"] == 500  # 5 ticks * 100 volume each
