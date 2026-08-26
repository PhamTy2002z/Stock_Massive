"""The measured session grid, pinned as a golden table.

The numbers here are not derived from exchange rules; they are what the provider
was observed to send (75 sessions of STB on HOSE, 70 of SHS on HNX, probed
2026-08-26). Where the two disagree the data wins, and the two places they
disagree are the whole reason this file exists — see ``session_window``'s
docstring for ``09:00`` and ``14:45``.
"""

from __future__ import annotations

from datetime import time

import pytest

from src.stocks.intraday import session_window

#: Every bucket start observed carrying volume, and the phase it belongs to.
GOLDEN = (
    ("09:00", "ato"),
    ("09:15", "am"),
    ("09:30", "am"),
    ("09:45", "am"),
    ("10:00", "am"),
    ("10:15", "am"),
    ("10:30", "am"),
    ("10:45", "am"),
    ("11:00", "am"),
    ("11:15", "am"),
    ("13:00", "pm"),
    ("13:15", "pm"),
    ("13:30", "pm"),
    ("13:45", "pm"),
    ("14:00", "pm"),
    ("14:15", "pm"),
    ("14:45", "atc"),
)


def as_time(label: str) -> time:
    hour, minute = label.split(":")
    return time(int(hour), int(minute))


def test_the_grid_is_exactly_the_seventeen_buckets_observed():
    assert session_window.SESSION_BUCKET_LABELS == tuple(
        label for label, _ in GOLDEN
    )


@pytest.mark.parametrize("label,phase", GOLDEN)
def test_each_observed_bucket_keeps_its_phase(label, phase):
    assert session_window.phase_of(as_time(label)) == phase


@pytest.mark.parametrize(
    "label,why",
    [
        ("00:00", "the middle of the night is padding on a 24-hour grid"),
        ("08:45", "before the opening auction"),
        ("11:30", "the morning bell — empty on every session observed"),
        ("12:00", "lunch"),
        ("12:45", "still lunch"),
        ("14:30", "the closing auction runs here but nothing matches until 14:45"),
        ("15:00", "after the close"),
        ("23:45", "padding"),
    ],
)
def test_padding_is_not_in_session(label, why):
    assert session_window.phase_of(as_time(label)) is None, why
    assert not session_window.in_session(as_time(label))


def test_the_closing_auction_is_at_1445_not_1430():
    """The correction this phase was written around.

    The auction period starts at 14:30, so a window written from the exchange
    clock would label that bucket ATC and stop there — discarding the largest
    single bucket of most sessions, which the provider stamps at 14:45.
    """
    assert session_window.phase_of(time(14, 30)) is None
    assert session_window.phase_of(time(14, 45)) == "atc"


def test_a_hose_symbol_has_no_ato_bucket_and_that_is_not_a_gap():
    """HOSE matches its opening auction into 09:15; HNX trades from 09:00.

    The grid is the union, so both exchanges fit one axis. A HOSE symbol simply
    never fills the first column.
    """
    assert session_window.phase_of(time(9, 0)) == "ato"
    assert session_window.phase_of(time(9, 15)) == "am"


def test_seconds_inside_a_bucket_start_do_not_lose_the_phase():
    assert session_window.phase_of(time(14, 45, 30)) == "atc"
