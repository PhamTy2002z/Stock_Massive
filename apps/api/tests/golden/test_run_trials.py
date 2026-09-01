"""Trials, the tape they share, and the retrieval time that travels with evidence.

The tape is what makes a second trial worth running. Without it, two trials of
one case differ by the model *and* by whatever the Internet did in between, and
a pass rate over three such trials measures nothing in particular. So the lane
records once and replays after — and that switch, plus the retrieval time the
tape is the only source of, is what this file pins down.
"""

from __future__ import annotations

from golden.run import ReplayLane, _retrieved_at


class Fixed:
    """A lane that always answers, and counts how often it was asked."""

    def __init__(self, payload="page", at=1_756_000_000.0):
        self.payload = payload
        self.at = at
        self.calls = 0

    def read(self, kind, key, fetch):
        from src.core.web_lane import WebRead

        self.calls += 1
        return WebRead(payload=self.payload, fetched_at=self.at, age_seconds=0.0, stale=False)


def test_the_first_trial_records_and_the_next_one_replays():
    inner = Fixed()
    lane = ReplayLane(inner, {}, replay=False)

    lane.read("search", "vn-index", lambda: None)
    assert inner.calls == 1 and lane.recorded == 1

    lane.start_replaying()
    lane.read("search", "vn-index", lambda: None)
    # The second read cost nothing and reached no network: same key, same page.
    assert inner.calls == 1
    assert lane.hits == 1
    assert lane.misses == []


def test_a_replay_that_misses_falls_through_and_is_counted():
    inner = Fixed()
    lane = ReplayLane(inner, {}, replay=True)
    lane.read("url", "https://a.vn/x", lambda: None)
    # It still finishes — a run has to produce an artifact — but the miss is on
    # the record, and the runner turns any miss at all into ``incomplete``.
    assert inner.calls == 1
    assert len(lane.misses) == 1


def test_retrieval_times_are_keyed_the_way_the_lane_keys_them():
    lane = ReplayLane(Fixed(at=1_756_000_000.0), {}, replay=False)
    lane.read("search", "vn-index\n", lambda: None)
    lane.read("url", "https://a.vn/x", lambda: None)
    times = lane.retrieval_times()
    assert times[("search", "vn-index\n")] == 1_756_000_000.0
    assert times[("url", "https://a.vn/x")] == 1_756_000_000.0


def test_a_search_call_takes_the_time_of_the_search_it_came_from():
    times = {("search", "vn-index\n"): 1_756_000_000.0}
    stamp = _retrieved_at({"name": "web_search", "arguments": {"query": "vn-index"}}, times)
    assert stamp is not None and stamp.startswith("2025-")


def test_a_search_with_a_recency_window_keys_on_the_window_too():
    times = {("search", "vn-index\n7"): 1_756_000_000.0}
    assert _retrieved_at(
        {"name": "web_search", "arguments": {"query": "vn-index", "recency_days": 7}}, times
    ) is not None
    # And the same query without the window is a different read, correctly.
    assert _retrieved_at({"name": "web_search", "arguments": {"query": "vn-index"}}, times) is None


def test_a_page_matches_even_after_the_url_was_normalised():
    times = {("url", "https://a.vn/x/"): 1_756_000_000.0}
    assert _retrieved_at({"name": "fetch_url", "arguments": {"url": "https://a.vn/x"}}, times)


def test_a_call_the_tape_never_saw_has_no_retrieval_time():
    assert _retrieved_at({"name": "fetch_url", "arguments": {"url": "https://b.vn/y"}}, {}) is None
    assert _retrieved_at({"name": "recall_facts", "arguments": {}}, {}) is None


def test_a_later_trial_asking_something_new_is_not_a_miss():
    """The model exploring differently is the measurement, not a broken tape.

    Trial one records what it searched for. Trial two searching for something
    else is exactly the variance a multi-trial baseline exists to see, so the
    read goes out live and joins the tape. Only a miss under an explicit
    ``--replay`` means the tape does not match its corpus, and only that ends
    the run incomplete.
    """
    inner = Fixed()
    lane = ReplayLane(inner, {}, replay=False)
    lane.read("search", "vn-index", lambda: None)

    lane.start_replaying()
    lane.read("search", "một câu hỏi khác", lambda: None)

    assert lane.misses == []
    assert len(lane.fresh_reads) == 1
    assert inner.calls == 2


def test_an_explicit_replay_still_treats_a_miss_as_one():
    lane = ReplayLane(Fixed(), {}, replay=True)
    lane.read("search", "vn-index", lambda: None)
    assert len(lane.misses) == 1
    assert lane.fresh_reads == []
