"""Redis client setup for local Redis or Upstash."""
import logging
from typing import Any, Optional

from redis import Redis as StandardRedis
from upstash_redis import Redis as UpstashRedis

from src.core.config import get_settings

logger = logging.getLogger(__name__)

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
