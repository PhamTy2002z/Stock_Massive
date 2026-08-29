"""The tape. Without it, two artifacts weeks apart are not comparable.

``WebLane`` serves a search fresh for thirty minutes and a page for a day, so the
difference between a run today and a run after phase 08 would be code plus the
Internet plus sampling — three terms and one measurement. Recording at the lane
seam removes the middle one, and these tests hold the two properties that makes
possible: a replay returns exactly what was recorded, and a replay that misses
says so instead of quietly serving something else.
"""

from __future__ import annotations

import pytest

from golden.run import ReplayLane


class Inner:
    """A lane that always calls through, and counts how often it did."""

    def __init__(self) -> None:
        self.calls = 0

    def read(self, _kind, _key, fetch):
        from src.core.web_lane import WebRead

        self.calls += 1
        return WebRead(fetch(), 111.0, 0.0, False)


def test_recording_then_replaying_returns_the_same_payload_without_fetching():
    inner = Inner()
    tape: dict = {}
    recorder = ReplayLane(inner, tape, replay=False)

    first = recorder.read("search", "vn-index", lambda: [{"url": "https://a.example"}])

    assert inner.calls == 1
    assert recorder.recorded == 1

    replayed = ReplayLane(Inner(), tape, replay=True)
    again = replayed.read("search", "vn-index", lambda: pytest.fail("must not fetch"))

    assert again.payload == first.payload
    assert replayed.hits == 1
    assert replayed.misses == []


def test_a_replay_miss_is_recorded_rather_than_silently_served_live():
    """A partly replayed artifact is not comparable with the one it replayed.

    So the miss falls through to the live lane — the run still finishes and its
    numbers are still worth reading — and it is counted, because the run status
    turns on whether any miss happened at all.
    """
    inner = Inner()
    lane = ReplayLane(inner, {}, replay=True)

    lane.read("url", "https://b.example", lambda: {"content": "text"})

    assert lane.misses == ["url:https://b.example"]
    assert inner.calls == 1


def test_the_tape_is_keyed_the_way_the_real_lane_keys_its_cache():
    """Kind and key together, so a search and a page read cannot collide."""
    tape: dict = {}
    lane = ReplayLane(Inner(), tape, replay=False)

    lane.read("search", "same", lambda: "from search")
    lane.read("url", "same", lambda: "from url")

    assert len(tape) == 2
    assert {entry["payload"] for entry in tape.values()} == {"from search", "from url"}


def test_whitespace_around_a_key_does_not_make_a_second_tape_entry():
    tape: dict = {}
    recorder = ReplayLane(Inner(), tape, replay=False)
    recorder.read("search", "vn-index", lambda: "payload")

    replayed = ReplayLane(Inner(), tape, replay=True)
    replayed.read("search", "  vn-index  ", lambda: pytest.fail("must not fetch"))

    assert replayed.hits == 1
