"""The limiter subscription gets instead of the IP-based one (#85).

The reason is architectural rather than a tuning preference: **behind the Next proxy every user shares one IP.**
The existing ``heavy`` limiter identifies a caller by address, so the first
reconnect burst after a dropped network would rate-limit everybody at once —
one user's flaky connection taking the surface away from the rest.

So subscription and reconnection are counted per user and per Turn, and they are
**not charged as a Turn start**: the start allowance is consumed at dispatch,
and reattaching to a Turn that is already running dispatches nothing.
A reader who reloads twenty times has spent no model budget at all, and a
limiter that said otherwise would make a reload cost the same as a question.

Redis is the counter, and its absence is not a refusal. The limiter degrades to
open exactly as the app's other one does — a subscription is a read of work
already paid for, and failing it closed because a cache is down would take the
answer away from the user who is already owed it.
"""

from __future__ import annotations

import logging
import uuid

from src.alpha.refusals import AlphaRefusal
from src.core.config import get_settings
from src.core.ratelimit import RedisFixedWindowLimiter
from src.core.redis import get_redis

logger = logging.getLogger(__name__)


class SubscriptionThrottled(AlphaRefusal):
    """Too many subscribe or reconnect attempts, for this user or this Turn.

    429 and an :class:`AlphaRefusal`, so it arrives in the same
    ``{reason, message}`` shape as an admission refusal — but under its own
    reason, because the two mean opposite things to a client: a throttled
    subscribe should be retried later on a Turn that is still running, where an
    exhausted allowance means there is no Turn to come back to.
    """

    def __init__(self, scope: str) -> None:
        super().__init__(
            reason="turn_subscribe_throttled",
            message="Too many reconnections in a short window. Wait a moment and reopen.",
            status_code=429,
        )
        self.scope = scope


class SubscriptionLimiter:
    """A fixed window per user and a fixed window per Turn."""

    def __init__(
        self,
        *,
        per_user: int | None = None,
        per_turn: int | None = None,
        window: int | None = None,
    ) -> None:
        settings = get_settings()
        self._per_user = (
            settings.alpha_turn_subscribe_user_max if per_user is None else per_user
        )
        self._per_turn = (
            settings.alpha_turn_subscribe_turn_max if per_turn is None else per_turn
        )
        self._window = (
            settings.alpha_turn_subscribe_window if window is None else window
        )

    def check_user(self, user_id: int) -> None:
        """Count this attempt against the caller's own window, or refuse it.

        Asked first, and before any database work: it is the only window a
        caller can be held to before anything is known about what they asked
        for, so it is what bounds the cost of an unknown Turn id.
        """
        redis = self._redis()
        if redis is None:
            return
        if self._limit(redis, "user", str(user_id), self._per_user) is False:
            logger.warning("Subscription limit reached for user %s", user_id)
            raise SubscriptionThrottled("user")

    def check_turn(self, turn_id: uuid.UUID | str) -> None:
        """Count this attempt against the Turn's window, or refuse it.

        **Asked only once the Turn is known to be the caller's.** The window is
        keyed by Turn rather than by user, so counting it before ownership was
        resolved would let any signed-in account spend a stranger's budget by
        naming their Turn id — the same "one connection taking the surface away
        from the rest" this module exists to prevent, reintroduced through the
        limiter itself.
        """
        redis = self._redis()
        if redis is None:
            return
        if self._limit(redis, "turn", str(turn_id), self._per_turn) is False:
            logger.warning("Subscription limit reached for Turn %s", turn_id)
            raise SubscriptionThrottled("turn")

    def _limit(self, redis, scope: str, identifier: str, maximum: int) -> bool | None:
        """Whether this attempt is allowed, or ``None`` when nothing counted."""
        try:
            limiter = RedisFixedWindowLimiter(
                redis=redis,
                max_requests=maximum,
                window=self._window,
                prefix=f"stock_massive:ratelimit:turn-subscribe:{scope}",
            )
            return limiter.limit(identifier).allowed
        except Exception as exc:  # noqa: BLE001 - degrade open, as the app's own limiter does
            logger.warning("Subscription limit check failed for %s: %s", identifier, exc)
            return None

    @staticmethod
    def _redis():
        if not get_settings().rate_limit_enabled:
            return None
        try:
            return get_redis()
        except Exception as exc:  # noqa: BLE001 - the counter is not the gate
            logger.warning("Subscription limiter has no Redis: %s", exc)
            return None


__all__ = ["SubscriptionLimiter", "SubscriptionThrottled"]
