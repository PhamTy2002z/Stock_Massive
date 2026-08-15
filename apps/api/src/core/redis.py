"""Redis client setup for local Redis or Upstash, and the scripts both speak.

Two client libraries are configured shapes here — a self-hosted Redis locally
and Upstash over REST — and they disagree about how a script is called. That
disagreement belongs in one place: a caller that gets it wrong does not fail
loudly, it falls into the ``except TypeError`` of whichever spelling it wrote
and looks fine until the other client is the one deployed.

The two lock scripts live here for the same reason. A Collector lease and a
cache-refresh lock are the same primitive, and two copies of "delete only if the
token is still mine" are two chances for one of them to become "delete".
"""
import logging
from typing import Any, Optional

from redis import Redis as StandardRedis
from upstash_redis import Redis as UpstashRedis

from src.core.config import get_settings

logger = logging.getLogger(__name__)

# Release only a lock this holder still owns. Deleting unconditionally lets a
# holder whose lease already expired delete its successor's.
RELEASE_IF_OWNED_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

# Extend only a lock this holder still owns, for the same reason.
RENEW_IF_OWNED_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('EXPIRE', KEYS[1], ARGV[2])
end
return 0
"""


def eval_script(redis: Any, script: str, keys: list[str], args: list[Any]) -> Any:
    """Run a script against either client this deployment might be using.

    redis-py takes the key count positionally and Upstash takes keyword lists.
    Both are configured, so both are spoken.
    """
    try:
        return redis.eval(script, keys=keys, args=args)
    except TypeError:
        return redis.eval(script, len(keys), *keys, *args)


_redis_client: Optional[Any] = None


def get_redis() -> Optional[Any]:
    """Get the configured Redis client singleton.

    Returns None if not configured (graceful degradation).
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    settings = get_settings()

    try:
        if settings.cache_redis_url:
            _redis_client = StandardRedis.from_url(
                settings.cache_redis_url,
                decode_responses=True,
            )
            _redis_client.ping()
            logger.info("Standard Redis client initialized")
        elif settings.redis_url and settings.redis_token:
            _redis_client = UpstashRedis(
                url=settings.redis_url,
                token=settings.redis_token,
            )
            logger.info("Upstash Redis client initialized")
        else:
            logger.warning("Redis not configured, caching disabled")
            return None
        return _redis_client
    except Exception as e:
        logger.error("Failed to initialize Redis: %s", e)
        _redis_client = None
        return None


def reset_redis_client() -> None:
    """Clear the singleton after configuration changes or in tests."""
    global _redis_client
    _redis_client = None
