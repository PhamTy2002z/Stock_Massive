"""The open-web provider has cache and allowance rules independent of vnstock."""

from __future__ import annotations

import json

from src.core.web_lane import SEARCH_FRESH_SECONDS, WebLane


class Redis:
    def __init__(self):
        self.values = {}
        self.counts = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, **options):
        if options.get("nx") and key in self.values:
            return False
        self.values[key] = value
        return True

    def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, _key, _seconds):
        return True

    def eval(self, _script, *, keys, args):
        if self.values.get(keys[0]) == args[0]:
            self.values.pop(keys[0], None)
            return 1
        return 0


def test_search_is_cached_for_thirty_minutes():
    redis = Redis()
    now = [1000.0]
    calls = []
    lane = WebLane(redis_factory=lambda: redis, clock=lambda: now[0])

    first = lane.read("search", "leadership", lambda: calls.append(1) or {"ok": 1})
    now[0] += SEARCH_FRESH_SECONDS - 1
    second = lane.read("search", "leadership", lambda: calls.append(2) or {"ok": 2})

    assert first.payload == second.payload == {"ok": 1}
    assert calls == [1]


def test_an_upstream_failure_serves_a_stale_value_with_a_label():
    redis = Redis()
    now = [1000.0]
    lane = WebLane(redis_factory=lambda: redis, clock=lambda: now[0])
    lane.read("search", "leadership", lambda: {"ok": 1})
    now[0] += SEARCH_FRESH_SECONDS + 1

    stale = lane.read(
        "search",
        "leadership",
        lambda: (_ for _ in ()).throw(RuntimeError("upstream down")),
    )

    assert stale.payload == {"ok": 1}
    assert stale.stale is True


def test_cache_keys_hash_queries_instead_of_exposing_them():
    redis = Redis()
    lane = WebLane(redis_factory=lambda: redis)
    lane.read("search", "a sensitive query", lambda: {"ok": 1})

    assert all("a sensitive query" not in key for key in redis.values)
    cached = [value for key, value in redis.values.items() if ":search:" in key]
    assert json.loads(cached[0])["payload"] == {"ok": 1}
