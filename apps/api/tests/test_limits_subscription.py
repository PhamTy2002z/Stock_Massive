"""The subscription limiter's async entry points count off the event loop."""
import threading
from unittest.mock import Mock, patch

import pytest

from src.agent.limits import SubscriptionLimiter, SubscriptionThrottled
from src.core.config import Settings


def _redis(counts):
    threads = []

    def incr(key):
        threads.append(threading.get_ident())
        counts[key] = counts.get(key, 0) + 1
        return counts[key]

    redis = Mock()
    redis.incr.side_effect = incr
    return redis, threads


@pytest.mark.asyncio
@patch("src.agent.limits.get_settings")
@patch("src.agent.limits.get_redis")
async def test_async_checks_run_in_a_worker_thread_and_still_refuse(mock_redis, mock_settings):
    mock_settings.return_value = Settings(rate_limit_enabled=True)
    redis, threads = _redis({})
    mock_redis.return_value = redis
    limiter = SubscriptionLimiter(per_user=1, per_turn=1, window=60)

    await limiter.acheck_user(7)
    with pytest.raises(SubscriptionThrottled):
        await limiter.acheck_user(7)
    await limiter.acheck_turn("turn-1")
    with pytest.raises(SubscriptionThrottled):
        await limiter.acheck_turn("turn-1")

    assert len(threads) == 4
    assert threading.get_ident() not in threads


@pytest.mark.asyncio
@patch("src.agent.limits.get_settings")
@patch("src.agent.limits.get_redis")
async def test_a_failing_redis_still_degrades_open(mock_redis, mock_settings):
    mock_settings.return_value = Settings(rate_limit_enabled=True)
    redis = Mock()
    redis.incr.side_effect = ConnectionError("Redis timeout")
    mock_redis.return_value = redis
    limiter = SubscriptionLimiter(per_user=1, per_turn=1, window=60)

    for _ in range(3):
        await limiter.acheck_user(7)
        await limiter.acheck_turn("turn-1")
