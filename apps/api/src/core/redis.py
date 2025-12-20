"""Upstash Redis client setup."""
import logging
from typing import Optional

from upstash_redis import Redis

from src.core.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: Optional[Redis] = None


def get_redis() -> Optional[Redis]:
    """Get Upstash Redis client singleton.

    Returns None if not configured (graceful degradation).
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    settings = get_settings()

    if not settings.upstash_redis_url or not settings.upstash_redis_token:
        logger.warning("Upstash Redis not configured, caching disabled")
        return None

    try:
        _redis_client = Redis(
            url=settings.upstash_redis_url,
            token=settings.upstash_redis_token,
        )
        logger.info("Upstash Redis client initialized")
        return _redis_client
    except Exception as e:
        logger.error(f"Failed to initialize Upstash Redis: {e}")
        return None
