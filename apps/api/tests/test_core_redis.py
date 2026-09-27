"""The Redis client singleton: bounded waits and no re-ping storm when Redis is down."""
from unittest.mock import Mock, patch

import pytest

from src.core import redis as redis_module
from src.core.config import Settings


@pytest.fixture(autouse=True)
def _fresh_client():
    redis_module.reset_redis_client()
    yield
    redis_module.reset_redis_client()


def _settings(**overrides):
    return Settings(cache_redis_url="redis://redis.invalid:6379/0", **overrides)


@patch("src.core.redis.get_settings")
@patch("src.core.redis.StandardRedis")
def test_the_client_has_small_socket_timeouts(mock_redis_cls, mock_settings):
    mock_settings.return_value = _settings()
    client = mock_redis_cls.from_url.return_value

    assert redis_module.get_redis() is client
    kwargs = mock_redis_cls.from_url.call_args.kwargs
    assert kwargs["socket_timeout"] == redis_module.SOCKET_TIMEOUT_SECONDS
    assert kwargs["socket_connect_timeout"] == redis_module.SOCKET_TIMEOUT_SECONDS
    assert redis_module.SOCKET_TIMEOUT_SECONDS <= 1
    # Cached: no second ping.
    assert redis_module.get_redis() is client
    client.ping.assert_called_once()


@patch("src.core.redis.get_settings")
@patch("src.core.redis.StandardRedis")
def test_a_failed_init_is_not_retried_until_the_backoff_passes(
    mock_redis_cls, mock_settings, monkeypatch
):
    mock_settings.return_value = _settings()
    client = mock_redis_cls.from_url.return_value
    client.ping.side_effect = ConnectionError("down")
    clock = [1000.0]
    monkeypatch.setattr(redis_module.time, "monotonic", lambda: clock[0])

    assert redis_module.get_redis() is None
    assert redis_module.get_redis() is None
    clock[0] += redis_module.RETRY_AFTER_FAILURE_SECONDS - 1
    assert redis_module.get_redis() is None
    assert client.ping.call_count == 1

    clock[0] += 2
    client.ping.side_effect = None
    assert redis_module.get_redis() is client
    assert client.ping.call_count == 2


@patch("src.core.redis.get_settings")
@patch("src.core.redis.UpstashRedis")
def test_the_upstash_path_still_initialises(mock_upstash_cls, mock_settings):
    mock_settings.return_value = Settings(
        upstash_redis_rest_url="https://example.upstash.io",
        upstash_redis_rest_token="token",
    )
    assert redis_module.get_redis() is mock_upstash_cls.return_value
    mock_upstash_cls.assert_called_once_with(
        url="https://example.upstash.io", token="token"
    )


@patch("src.core.redis.get_settings")
def test_unconfigured_is_none(mock_settings):
    mock_settings.return_value = Settings(
        cache_redis_url="", upstash_redis_rest_url="", upstash_redis_url=""
    )
    assert redis_module.get_redis() is None
