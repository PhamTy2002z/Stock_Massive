"""Tests for rate limiting implementation."""
import threading

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import Request, Response, HTTPException

from src.core.ratelimit import (
    InProcessSlidingWindowLimiter,
    RateLimiter,
    RedisFixedWindowLimiter,
    credential_rate_limit,
    heavy_rate_limit,
    standard_rate_limit,
)
from src.core.config import Settings


class TestRateLimiterInitialization:
    """Test RateLimiter class initialization."""

    def test_init_with_valid_params(self):
        """Test initialization with valid parameters."""
        limiter = RateLimiter(max_requests=100, window=60, prefix="test")
        assert limiter.max_requests == 100
        assert limiter.window == 60
        assert limiter.prefix == "test"
        assert limiter._limiter is None

    def test_init_with_different_values(self):
        """Test initialization with different values."""
        limiter = RateLimiter(max_requests=20, window=30, prefix="heavy")
        assert limiter.max_requests == 20
        assert limiter.window == 30
        assert limiter.prefix == "heavy"


class TestRateLimiterConfigSettings:
    """Test rate limiter config settings."""

    @patch("src.core.ratelimit.get_settings")
    def test_standard_rate_limit_config(self, mock_settings):
        """Test standard rate limit uses correct config values."""
        mock_settings.return_value = Settings(
            rate_limit_standard_max=100,
            rate_limit_standard_window=60,
        )
        # Import after mocking
        from src.core.ratelimit import standard_rate_limit

        assert standard_rate_limit.max_requests == 100
        assert standard_rate_limit.window == 60
        assert standard_rate_limit.prefix == "standard"

    @patch("src.core.ratelimit.get_settings")
    def test_heavy_rate_limit_config(self, mock_settings):
        """Test heavy rate limit uses correct config values."""
        mock_settings.return_value = Settings(
            rate_limit_heavy_max=20,
            rate_limit_heavy_window=60,
        )
        # Import after mocking
        from src.core.ratelimit import heavy_rate_limit

        assert heavy_rate_limit.max_requests == 20
        assert heavy_rate_limit.window == 60
        assert heavy_rate_limit.prefix == "heavy"


class TestRateLimiterRedisIntegration:
    """Test RateLimiter Redis integration and graceful degradation."""

    @patch("src.core.ratelimit.get_settings")
    @patch("src.core.ratelimit.get_redis")
    def test_get_limiter_when_rate_limiting_disabled(
        self, mock_redis, mock_settings
    ):
        """Test graceful degradation when rate limiting is disabled."""
        mock_settings.return_value = Settings(rate_limit_enabled=False)
        limiter = RateLimiter(max_requests=100, window=60, prefix="test")

        result = limiter._get_limiter()

        assert result is None
        mock_redis.assert_not_called()

    @patch("src.core.ratelimit.get_settings")
    @patch("src.core.ratelimit.get_redis")
    def test_get_limiter_when_redis_unavailable(
        self, mock_redis, mock_settings
    ):
        """Test graceful degradation when Redis is unavailable."""
        mock_settings.return_value = Settings(rate_limit_enabled=True)
        mock_redis.return_value = None

        limiter = RateLimiter(max_requests=100, window=60, prefix="test")
        result = limiter._get_limiter()

        assert result is None

    @patch("src.core.ratelimit.get_settings")
    @patch("src.core.ratelimit.get_redis")
    def test_get_limiter_successful_initialization(
        self, mock_redis, mock_settings
    ):
        """A configured Redis client enables rate limiting."""
        mock_settings.return_value = Settings(rate_limit_enabled=True)
        mock_redis_instance = Mock()
        mock_redis.return_value = mock_redis_instance

        limiter = RateLimiter(max_requests=100, window=60, prefix="test")
        result = limiter._get_limiter()

        assert isinstance(result, RedisFixedWindowLimiter)

    @patch("src.core.ratelimit.get_settings")
    @patch("src.core.ratelimit.get_redis")
    def test_get_limiter_caching(
        self, mock_redis, mock_settings
    ):
        """Test that limiter instance is cached."""
        mock_settings.return_value = Settings(rate_limit_enabled=True)
        mock_redis.return_value = Mock()

        limiter = RateLimiter(max_requests=100, window=60, prefix="test")

        # First call
        result1 = limiter._get_limiter()
        # Second call
        result2 = limiter._get_limiter()

        assert result1 is result2

    @patch("src.core.ratelimit.get_settings")
    @patch("src.core.ratelimit.get_redis")
    @patch("src.core.ratelimit.RedisFixedWindowLimiter")
    def test_get_limiter_handles_initialization_error(
        self, mock_limiter_class, mock_redis, mock_settings
    ):
        """Test graceful handling of rate limiter initialization errors."""
        mock_settings.return_value = Settings(rate_limit_enabled=True)
        mock_redis.return_value = Mock()
        mock_limiter_class.side_effect = Exception("Redis connection failed")

        limiter = RateLimiter(max_requests=100, window=60, prefix="test")
        result = limiter._get_limiter()

        assert result is None


def _request(peer, forwarded=None):
    """A request from direct peer ``peer`` carrying an optional XFF header."""
    request = Mock(spec=Request)
    request.headers = {"X-Forwarded-For": forwarded} if forwarded is not None else {}
    request.client = Mock(host=peer) if peer is not None else None
    request.url.path = "/auth/login"
    return request


class TestIPExtraction:
    """The address a request is charged to, and whose word it takes for it."""

    def _identify(self, peer, forwarded=None):
        limiter = RateLimiter(max_requests=100, window=60, prefix="test")
        return limiter._get_identifier(_request(peer, forwarded))

    def test_a_public_peer_cannot_choose_its_own_address(self):
        """Spoofing XFF from the internet changes nothing: the peer is charged."""
        assert self._identify("198.51.100.7", "203.0.113.1") == "198.51.100.7"
        assert self._identify("2001:db8::7", "203.0.113.1") == "2001:db8::7"

    def test_a_trusted_proxy_forwards_the_client_it_saw(self):
        assert self._identify("172.18.0.3", "203.0.113.1") == "203.0.113.1"
        assert self._identify("127.0.0.1", "203.0.113.1") == "203.0.113.1"
        assert self._identify("::1", "2001:db8::1") == "2001:db8::1"

    def test_an_ipv4_mapped_peer_is_matched_as_ipv4(self):
        assert self._identify("::ffff:10.0.0.5", "203.0.113.1") == "203.0.113.1"

    def test_the_right_most_untrusted_hop_wins_over_client_written_entries(self):
        """Left of the last proxy-appended entry is whatever the client sent."""
        forwarded = "1.1.1.1, 203.0.113.9, 10.0.0.2, 172.18.0.4"
        assert self._identify("172.18.0.3", forwarded) == "203.0.113.9"

    def test_a_chain_of_only_proxies_is_charged_to_the_peer(self):
        assert self._identify("172.18.0.3", "10.0.0.2, 192.168.1.4") == "172.18.0.3"

    def test_a_malformed_entry_ends_the_walk(self):
        assert self._identify("172.18.0.3", "203.0.113.1, not-an-ip") == "172.18.0.3"
        assert self._identify("172.18.0.3", "not-an-ip, also-invalid") == "172.18.0.3"
        # Proxy-written hops to the right of the garbage are still honoured.
        assert self._identify("172.18.0.3", "garbage, 203.0.113.5") == "203.0.113.5"
        assert self._identify("172.18.0.3", "") == "172.18.0.3"

    def test_a_trusted_peer_without_the_header_is_charged_itself(self):
        assert self._identify("192.168.1.1") == "192.168.1.1"

    def test_a_non_ip_peer_is_used_verbatim(self):
        assert self._identify("testclient", "203.0.113.1") == "testclient"

    def test_get_identifier_without_client(self):
        assert self._identify(None, "203.0.113.1") == "unknown"

    @patch("src.core.ratelimit.get_settings")
    def test_the_trusted_networks_come_from_settings(self, mock_settings):
        mock_settings.return_value = Settings(trusted_proxy_cidrs="198.51.100.0/24")
        assert self._identify("198.51.100.7", "203.0.113.1") == "203.0.113.1"
        assert self._identify("172.18.0.3", "203.0.113.1") == "172.18.0.3"

    def test_an_invalid_cidr_is_refused_at_settings_load(self):
        with pytest.raises(ValueError):
            Settings(trusted_proxy_cidrs="10.0.0.0/8,not-a-network")

    def test_is_valid_ip_with_ipv4(self):
        """Test valid IPv4 address."""
        limiter = RateLimiter(max_requests=100, window=60, prefix="test")
        assert limiter._is_valid_ip("192.168.1.1") is True
        assert limiter._is_valid_ip("10.0.0.1") is True
        assert limiter._is_valid_ip("203.0.113.1") is True

    def test_is_valid_ip_with_ipv6(self):
        """Test valid IPv6 address."""
        limiter = RateLimiter(max_requests=100, window=60, prefix="test")
        assert limiter._is_valid_ip("::1") is True
        assert limiter._is_valid_ip("2001:db8::1") is True

    def test_is_valid_ip_with_invalid_values(self):
        """Test invalid IP addresses."""
        limiter = RateLimiter(max_requests=100, window=60, prefix="test")
        assert limiter._is_valid_ip("not-an-ip") is False
        assert limiter._is_valid_ip("256.256.256.256") is False
        assert limiter._is_valid_ip("") is False
        assert limiter._is_valid_ip("malicious<script>") is False


class TestRateLimitingBehavior:
    """Test rate limiting behavior in request handling."""

    @pytest.mark.asyncio
    @patch("src.core.ratelimit.get_settings")
    @patch("src.core.ratelimit.get_redis")
    async def test_call_allows_request_when_redis_unavailable(
        self, mock_redis, mock_settings
    ):
        """Test that requests are allowed when Redis is unavailable."""
        mock_settings.return_value = Settings(rate_limit_enabled=True)
        mock_redis.return_value = None

        request = Mock(spec=Request)
        request.headers.get.return_value = None
        request.client = Mock(host="192.168.1.1")
        response = Mock(spec=Response)
        response.headers = {}

        limiter = RateLimiter(max_requests=100, window=60, prefix="test")
        # Should not raise exception
        await limiter(request, response)

    @pytest.mark.asyncio
    @patch("src.core.ratelimit.get_settings")
    @patch("src.core.ratelimit.get_redis")
    async def test_call_allows_request_within_limit(
        self, mock_redis, mock_settings
    ):
        """Test that requests inside the fixed window are allowed."""
        mock_settings.return_value = Settings(rate_limit_enabled=True)
        redis = Mock()
        redis.incr.return_value = 1
        mock_redis.return_value = redis

        request = Mock(spec=Request)
        request.headers.get.return_value = None
        request.client = Mock(host="192.168.1.1")
        request.url.path = "/api/stocks"
        response = Mock(spec=Response)
        response.headers = {}

        limiter = RateLimiter(max_requests=100, window=60, prefix="test")
        await limiter(request, response)
        assert response.headers["X-RateLimit-Remaining"] == "99"
        redis.expire.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.core.ratelimit.get_settings")
    @patch("src.core.ratelimit.get_redis")
    async def test_call_blocks_request_when_limit_exceeded(
        self, mock_redis, mock_settings
    ):
        """Test requests over the fixed-window limit are blocked."""
        mock_settings.return_value = Settings(rate_limit_enabled=True)
        redis = Mock()
        redis.incr.return_value = 101
        mock_redis.return_value = redis

        request = Mock(spec=Request)
        request.headers.get.return_value = None
        request.client = Mock(host="192.168.1.1")
        request.url.path = "/api/stocks"
        response = Mock(spec=Response)
        response.headers = {}

        limiter = RateLimiter(max_requests=100, window=60, prefix="test")

        with pytest.raises(HTTPException) as exc_info:
            await limiter(request, response)
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    @patch("src.core.ratelimit.get_settings")
    @patch("src.core.ratelimit.get_redis")
    async def test_call_handles_rate_limit_check_error(
        self, mock_redis, mock_settings
    ):
        """Test graceful handling of rate limit check errors."""
        mock_settings.return_value = Settings(rate_limit_enabled=True)
        redis = Mock()
        redis.incr.side_effect = Exception("Redis timeout")
        mock_redis.return_value = redis

        request = Mock(spec=Request)
        request.headers.get.return_value = None
        request.client = Mock(host="192.168.1.1")
        response = Mock(spec=Response)
        response.headers = {}

        limiter = RateLimiter(max_requests=100, window=60, prefix="test")
        # Should not raise exception (graceful degradation)
        await limiter(request, response)


class TestGlobalRateLimiters:
    """Test global rate limiter instances."""

    def test_standard_rate_limit_exists(self):
        """Test standard rate limiter is created."""
        assert standard_rate_limit is not None
        assert standard_rate_limit.prefix == "standard"

    def test_heavy_rate_limit_exists(self):
        """Test heavy rate limiter is created."""
        assert heavy_rate_limit is not None
        assert heavy_rate_limit.prefix == "heavy"


class TestInProcessFallback:
    """The limit a fail-closed scope keeps without Redis."""

    def test_allows_up_to_the_limit_then_refuses(self):
        limiter = InProcessSlidingWindowLimiter(max_requests=3, window=60)
        results = [limiter.limit("a") for _ in range(4)]
        assert [r.allowed for r in results] == [True, True, True, False]
        assert results[2].remaining == 0
        # Another address has its own window.
        assert limiter.limit("b").allowed is True

    def test_the_window_slides(self, monkeypatch):
        clock = [1000.0]
        monkeypatch.setattr("src.core.ratelimit.time.monotonic", lambda: clock[0])
        limiter = InProcessSlidingWindowLimiter(max_requests=2, window=60)
        assert limiter.limit("a").allowed and limiter.limit("a").allowed
        assert limiter.limit("a").allowed is False
        clock[0] += 61
        assert limiter.limit("a").allowed is True

    def test_memory_is_bounded(self, monkeypatch):
        clock = [1000.0]
        monkeypatch.setattr("src.core.ratelimit.time.monotonic", lambda: clock[0])
        limiter = InProcessSlidingWindowLimiter(max_requests=5, window=60, max_keys=3)
        for key in ("a", "b", "c"):
            limiter.limit(key)
        clock[0] += 61  # all three expire, so pruning makes room without eviction
        limiter.limit("d")
        assert set(limiter._hits) == {"d"}
        for key in ("e", "f", "g"):
            limiter.limit(key)  # every key live: the oldest is evicted
        assert len(limiter._hits) == 3


class TestFailClosed:
    """Credential scopes keep limiting when Redis is gone; others let through."""

    @staticmethod
    async def _hit(limiter, times):
        statuses = []
        for _ in range(times):
            response = Mock(spec=Response)
            response.headers = {}
            try:
                await limiter(_request("198.51.100.7"), response)
                statuses.append(200)
            except HTTPException as exc:
                statuses.append(exc.status_code)
        return statuses

    @pytest.mark.asyncio
    @patch("src.core.ratelimit.get_settings")
    @patch("src.core.ratelimit.get_redis")
    async def test_no_redis_falls_back_to_the_in_process_window(self, mock_redis, mock_settings):
        mock_settings.return_value = Settings(rate_limit_enabled=True)
        mock_redis.return_value = None
        limiter = RateLimiter(max_requests=2, window=60, prefix="t", fail_closed=True)
        assert await self._hit(limiter, 3) == [200, 200, 429]

    @pytest.mark.asyncio
    @patch("src.core.ratelimit.get_settings")
    @patch("src.core.ratelimit.get_redis")
    async def test_a_redis_error_falls_back_too(self, mock_redis, mock_settings):
        mock_settings.return_value = Settings(rate_limit_enabled=True)
        redis = Mock()
        redis.incr.side_effect = ConnectionError("Redis timeout")
        mock_redis.return_value = redis
        limiter = RateLimiter(max_requests=2, window=60, prefix="t", fail_closed=True)
        assert await self._hit(limiter, 3) == [200, 200, 429]

    @pytest.mark.asyncio
    @patch("src.core.ratelimit.get_settings")
    @patch("src.core.ratelimit.get_redis")
    async def test_a_fail_open_scope_still_lets_everything_through(self, mock_redis, mock_settings):
        mock_settings.return_value = Settings(rate_limit_enabled=True)
        mock_redis.return_value = None
        limiter = RateLimiter(max_requests=2, window=60, prefix="t")
        assert await self._hit(limiter, 5) == [200] * 5

    @pytest.mark.asyncio
    @patch("src.core.ratelimit.get_settings")
    @patch("src.core.ratelimit.get_redis")
    async def test_disabled_means_disabled_even_when_fail_closed(self, mock_redis, mock_settings):
        mock_settings.return_value = Settings(rate_limit_enabled=False)
        limiter = RateLimiter(max_requests=1, window=60, prefix="t", fail_closed=True)
        assert await self._hit(limiter, 3) == [200] * 3
        mock_redis.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.core.ratelimit.get_settings")
    @patch("src.core.ratelimit.get_redis")
    async def test_redis_is_counted_off_the_event_loop(self, mock_redis, mock_settings):
        mock_settings.return_value = Settings(rate_limit_enabled=True)
        threads = []

        def incr(key):
            threads.append(threading.get_ident())
            return 1

        redis = Mock()
        redis.incr.side_effect = incr
        mock_redis.return_value = redis
        limiter = RateLimiter(max_requests=2, window=60, prefix="t")
        assert await self._hit(limiter, 1) == [200]
        assert threads and threading.get_ident() not in threads

    def test_credential_endpoints_have_a_fail_closed_limiter(self):
        assert credential_rate_limit.fail_closed is True
        assert credential_rate_limit.prefix == "credential"
        assert heavy_rate_limit.fail_closed is False
        assert standard_rate_limit.fail_closed is False
