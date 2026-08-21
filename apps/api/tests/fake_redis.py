"""An in-process stand-in for Redis, faithful to the calls the arbiter makes.

The arbiter's reservation is a Lua script, and a fake cannot run Lua — so this
mirrors the four scripts in Python. That mirror is a real risk: a change to the
Lua that is not made here would leave the suite green over a bucket that no
longer spaces anything. Two things hold it down. The mirror lives beside the
scripts it copies, keyed by the script text itself, so an edited script that was
not mirrored raises ``UnknownScript`` rather than silently passing. And
``tests/test_vnstock_quota_redis.py`` runs the same assertions against a real
server whenever one is configured, which is what actually proves the Lua.

Thread-safe, because the spacing guarantee is only interesting under concurrent
callers.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from src.core.llm.breaker import OPEN_BREAKER_SCRIPT
from src.core.quota import RESERVE_SLOT_SCRIPT
from src.core.redis import RELEASE_IF_OWNED_SCRIPT, RENEW_IF_OWNED_SCRIPT


class UnknownScript(AssertionError):
    """A Lua script this fake has no mirror for."""


class FakeRedis:
    """Upstash-style client: ``eval(script, keys=[...], args=[...])``."""

    def __init__(self, clock=time.time) -> None:
        self._values: dict[str, str] = {}
        self._expiry: dict[str, float] = {}
        self._lock = threading.RLock()
        self._clock = clock
        self.calls: list[str] = []

    # -- plain commands ---------------------------------------------------

    def _live(self, key: str) -> bool:
        expires = self._expiry.get(key)
        if expires is not None and expires <= self._clock():
            self._values.pop(key, None)
            self._expiry.pop(key, None)
            return False
        return key in self._values

    def get(self, key: str) -> str | None:
        with self._lock:
            self.calls.append(f"get {key}")
            return self._values.get(key) if self._live(key) else None

    def set(
        self,
        key: str,
        value: Any,
        nx: bool = False,
        ex: int | None = None,
        px: int | None = None,
    ) -> bool | None:
        with self._lock:
            self.calls.append(f"set {key}")
            if nx and self._live(key):
                return None
            self._values[key] = str(value)
            if ex is not None:
                self._expiry[key] = self._clock() + ex
            elif px is not None:
                self._expiry[key] = self._clock() + px / 1000
            return True

    def delete(self, key: str) -> int:
        with self._lock:
            self._expiry.pop(key, None)
            return 1 if self._values.pop(key, None) is not None else 0

    def incr(self, key: str) -> int:
        with self._lock:
            current = int(self._values.get(key, "0")) if self._live(key) else 0
            current += 1
            self._values[key] = str(current)
            return current

    def decr(self, key: str) -> int:
        with self._lock:
            current = int(self._values.get(key, "0")) if self._live(key) else 0
            current -= 1
            self._values[key] = str(current)
            return current

    def expire(self, key: str, seconds: int) -> bool:
        with self._lock:
            if not self._live(key):
                return False
            self._expiry[key] = self._clock() + seconds
            return True

    # -- the mirrored scripts ---------------------------------------------

    def eval(self, script: str, keys: list[str], args: list[Any]) -> Any:
        with self._lock:
            if script == RESERVE_SLOT_SCRIPT:
                return self._reserve(keys[0], [float(arg) for arg in args])
            if script == RELEASE_IF_OWNED_SCRIPT:
                if self.get(keys[0]) == str(args[0]):
                    return self.delete(keys[0])
                return 0
            if script == RENEW_IF_OWNED_SCRIPT:
                if self.get(keys[0]) == str(args[0]):
                    return int(self.expire(keys[0], int(args[1])))
                return 0
            if script == OPEN_BREAKER_SCRIPT:
                return self._open_breaker(keys[0], [float(arg) for arg in args])
            raise UnknownScript(script)

    def _reserve(self, key: str, args: list[float]) -> int:
        now, spacing, max_wait, ttl = args
        stored = self.get(key)
        next_at = float(stored) if stored is not None else now
        if next_at < now:
            next_at = now
        wait = next_at - now
        if max_wait >= 0 and wait > max_wait:
            return -1
        self.set(key, int(next_at + spacing), px=int(ttl))
        return int(wait)

    def _open_breaker(self, key: str, args: list[float]) -> int:
        now, until_at = args
        held = self.get(key)
        if held is not None and float(held) > until_at:
            until_at = float(held)
        if until_at <= now:
            self.delete(key)
            return 0
        self.set(key, int(until_at), px=int(until_at - now))
        return int(until_at - now)


class PositionalFakeRedis(FakeRedis):
    """redis-py-style client: ``eval(script, numkeys, *keys, *args)``.

    Both signatures exist in this deployment — a self-hosted Redis locally and
    Upstash over REST — so the arbiter has to speak both, and one of them being
    untested is how that breaks in production only.
    """

    def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any:  # type: ignore[override]
        keys = list(keys_and_args[:numkeys])
        args = list(keys_and_args[numkeys:])
        return super().eval(script, keys=keys, args=args)
