"""Unit tests for TradingHoursCache (generic and specific instances)."""
import json
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from src.core.cache import TradingHoursCache


class TestTradingHoursDetection:
    """Test trading hours detection logic."""

    @pytest.fixture
    def cache(self):
        """Create cache instance with default TTLs."""
        return TradingHoursCache(
            key_prefix="test:",
            ttl_trading=60,
            ttl_off_hours=3600,
        )

    def test_weekday_during_market_hours(self, cache):
        """Test trading hours detection during weekday market hours."""
        # Monday 10:00 VN time
        mock_time = datetime(2024, 1, 8, 10, 0, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch("src.core.cache.datetime") as mock_dt:
            mock_dt.now.return_value = mock_time
            assert cache._is_trading_hours() is True

    def test_weekday_before_market_open(self, cache):
        """Test trading hours detection before market opens."""
        # Monday 08:00 VN time
        mock_time = datetime(2024, 1, 8, 8, 0, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch("src.core.cache.datetime") as mock_dt:
            mock_dt.now.return_value = mock_time
            assert cache._is_trading_hours() is False

    def test_weekday_after_market_close(self, cache):
        """Test trading hours detection after market closes."""
        # Monday 16:00 VN time
        mock_time = datetime(2024, 1, 8, 16, 0, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch("src.core.cache.datetime") as mock_dt:
            mock_dt.now.return_value = mock_time
            assert cache._is_trading_hours() is False

    def test_weekend_saturday(self, cache):
        """Test trading hours detection on Saturday."""
        # Saturday 10:00 VN time
        mock_time = datetime(2024, 1, 13, 10, 0, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch("src.core.cache.datetime") as mock_dt:
            mock_dt.now.return_value = mock_time
            assert cache._is_trading_hours() is False

    def test_weekend_sunday(self, cache):
        """Test trading hours detection on Sunday."""
        # Sunday 10:00 VN time
        mock_time = datetime(2024, 1, 14, 10, 0, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch("src.core.cache.datetime") as mock_dt:
            mock_dt.now.return_value = mock_time
            assert cache._is_trading_hours() is False

    def test_market_open_boundary(self, cache):
        """Test trading hours at exact market open."""
        # Monday 09:00 VN time
        mock_time = datetime(2024, 1, 8, 9, 0, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch("src.core.cache.datetime") as mock_dt:
            mock_dt.now.return_value = mock_time
            assert cache._is_trading_hours() is True

    def test_market_close_boundary(self, cache):
        """Test trading hours at exact market close."""
        # Monday 15:00 VN time
        mock_time = datetime(2024, 1, 8, 15, 0, 0, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
        with patch("src.core.cache.datetime") as mock_dt:
            mock_dt.now.return_value = mock_time
            assert cache._is_trading_hours() is True


class TestTTLSelection:
    """Test TTL selection based on trading hours."""

    def test_ttl_during_trading_hours(self):
        """Test TTL is correct during trading hours."""
        cache = TradingHoursCache(key_prefix="test:", ttl_trading=30, ttl_off_hours=3600)
        with patch.object(cache, "_is_trading_hours", return_value=True):
            assert cache._get_ttl() == 30

    def test_ttl_off_trading_hours(self):
        """Test TTL is correct outside trading hours."""
        cache = TradingHoursCache(key_prefix="test:", ttl_trading=30, ttl_off_hours=3600)
        with patch.object(cache, "_is_trading_hours", return_value=False):
            assert cache._get_ttl() == 3600

    def test_custom_ttl_values(self):
        """Test custom TTL values are respected."""
        cache = TradingHoursCache(key_prefix="test:", ttl_trading=15, ttl_off_hours=86400)
        with patch.object(cache, "_is_trading_hours", return_value=True):
            assert cache._get_ttl() == 15
        with patch.object(cache, "_is_trading_hours", return_value=False):
            assert cache._get_ttl() == 86400


class TestGracefulDegradation:
    """Test graceful degradation when Redis not configured."""

    @pytest.fixture
    def cache(self):
        """Create cache instance."""
        return TradingHoursCache(key_prefix="test:", ttl_trading=60, ttl_off_hours=3600)

    def test_get_when_redis_unavailable(self, cache):
        """Test get returns None when Redis unavailable."""
        with patch("src.core.cache.get_redis", return_value=None):
            result = cache.get("test_key")
            assert result is None

    def test_set_when_redis_unavailable(self, cache):
        """Test set silently fails when Redis unavailable."""
        with patch("src.core.cache.get_redis", return_value=None):
            # Should not raise exception
            cache.set("test_key", {"data": "value"})

    def test_delete_when_redis_unavailable(self, cache):
        """Test delete silently fails when Redis unavailable."""
        with patch("src.core.cache.get_redis", return_value=None):
            # Should not raise exception
            cache.delete("test_key")

    def test_get_with_redis_exception(self, cache):
        """Test get handles Redis exceptions gracefully."""
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("Connection error")
        with patch("src.core.cache.get_redis", return_value=mock_redis):
            result = cache.get("test_key")
            assert result is None

    def test_set_with_redis_exception(self, cache):
        """Test set handles Redis exceptions gracefully."""
        mock_redis = MagicMock()
        mock_redis.set.side_effect = Exception("Connection error")
        with patch("src.core.cache.get_redis", return_value=mock_redis):
            # Should not raise exception
            cache.set("test_key", {"data": "value"})

    def test_delete_with_redis_exception(self, cache):
        """Test delete handles Redis exceptions gracefully."""
        mock_redis = MagicMock()
        mock_redis.delete.side_effect = Exception("Connection error")
        with patch("src.core.cache.get_redis", return_value=mock_redis):
            # Should not raise exception
            cache.delete("test_key")


class TestCacheOperations:
    """Test cache operations with Redis mocked."""

    @pytest.fixture
    def cache(self):
        """Create cache instance."""
        return TradingHoursCache(key_prefix="test:", ttl_trading=60, ttl_off_hours=3600)

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        return MagicMock()

    def test_get_success(self, cache, mock_redis):
        """Test successful get operation."""
        mock_redis.get.return_value = json.dumps({"data": "value"})
        with patch("src.core.cache.get_redis", return_value=mock_redis):
            result = cache.get("test_key")
            assert result == {"data": "value"}
            mock_redis.get.assert_called_once_with("test:test_key")

    def test_get_missing_key(self, cache, mock_redis):
        """Test get with missing key returns None."""
        mock_redis.get.return_value = None
        with patch("src.core.cache.get_redis", return_value=mock_redis):
            result = cache.get("missing_key")
            assert result is None

    def test_set_with_trading_ttl(self, cache, mock_redis):
        """Test set uses correct TTL during trading hours."""
        with patch("src.core.cache.get_redis", return_value=mock_redis):
            with patch.object(cache, "_is_trading_hours", return_value=True):
                test_data = {"symbol": "VNM", "data": [1, 2, 3]}
                cache.set("test_key", test_data)
                mock_redis.set.assert_called_once_with(
                    "test:test_key",
                    json.dumps(test_data, default=str),
                    ex=60,
                )

    def test_set_with_off_hours_ttl(self, cache, mock_redis):
        """Test set uses correct TTL outside trading hours."""
        with patch("src.core.cache.get_redis", return_value=mock_redis):
            with patch.object(cache, "_is_trading_hours", return_value=False):
                test_data = {"symbol": "VNM", "data": [1, 2, 3]}
                cache.set("test_key", test_data)
                mock_redis.set.assert_called_once_with(
                    "test:test_key",
                    json.dumps(test_data, default=str),
                    ex=3600,
                )

    def test_delete_success(self, cache, mock_redis):
        """Test successful delete operation."""
        with patch("src.core.cache.get_redis", return_value=mock_redis):
            cache.delete("test_key")
            mock_redis.delete.assert_called_once_with("test:test_key")

    def test_key_prefix_applied(self, cache, mock_redis):
        """Test key prefix is correctly applied."""
        with patch("src.core.cache.get_redis", return_value=mock_redis):
            cache.get("mykey")
            mock_redis.get.assert_called_with("test:mykey")

            cache.set("mykey", {"test": "data"})
            args = mock_redis.set.call_args[0]
            assert args[0] == "test:mykey"

            cache.delete("mykey")
            mock_redis.delete.assert_called_with("test:mykey")


class TestCacheInstances:
    """Test specific cache instances used in routers."""

    def test_volume_anomaly_cache_config(self):
        """Test volume anomaly cache has correct configuration."""
        from src.stocks.price.cache import volume_anomaly_cache

        assert volume_anomaly_cache.key_prefix == "stock:volume_anomaly:"
        assert volume_anomaly_cache.ttl_trading == 60
        assert volume_anomaly_cache.ttl_off_hours == 3600

    def test_market_indices_cache_config(self):
        """Test market indices cache has correct configuration."""
        from src.stocks.price.router import market_indices_cache

        assert market_indices_cache.key_prefix == "stock:indices:"
        assert market_indices_cache.ttl_trading == 30
        assert market_indices_cache.ttl_off_hours == 3600

    def test_price_board_cache_config(self):
        """Test price board cache has correct configuration."""
        from src.stocks.price.router import price_board_cache

        assert price_board_cache.key_prefix == "stock:price_board:"
        assert price_board_cache.ttl_trading == 15
        assert price_board_cache.ttl_off_hours == 3600

    def test_symbols_cache_config(self):
        """Test symbols cache has correct configuration."""
        from src.stocks.market.router import symbols_cache

        assert symbols_cache.key_prefix == "stock:symbols:"
        assert symbols_cache.ttl_trading == 3600
        assert symbols_cache.ttl_off_hours == 86400

    def test_sector_performance_cache_config(self):
        """Test sector performance cache has correct configuration."""
        from src.stocks.market.router import sector_performance_cache

        assert sector_performance_cache.key_prefix == "stock:sector:"
        assert sector_performance_cache.ttl_trading == 300
        assert sector_performance_cache.ttl_off_hours == 3600
