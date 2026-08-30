"""The template, against bars whose ladder can be worked out by hand.

Two buckets, three quoting steps between them, and a total that divides evenly:
everything asserted below is arithmetic on the fixture rather than a number that
merely looks plausible. The point of building it this small is that a change in
how volume is spread across a bar's range shows up as a wrong answer to a
question with a right one.

**Asserted through the engine rather than against a function.** The Study is a
plan now: the fold, the shares and the mark on the busiest level live in the
sandbox, and there is no ``compute`` and no ``view`` to call. So every test here
runs the plan and reads the frames back off the rows it wrote, which is also the
honest subject — what a reader sees comes out of those rows and out of nothing
else. The two invariants that used to be checked against ``_fold`` directly are
checked against a planted window built to expose them.

**The clock is the other half of every question here.** *Mức giá giao dịch nhiều
nhất hôm nay* is a question about a session that may still be running, so the
same store is a healthy answer at four in the afternoon, a degraded one at half
past one, and a refusal at eleven the next morning. ``run_template`` runs the
plan the way production does and takes no as-of, so the instant the runner reads
is replaced per test rather than the window being rebuilt against whatever today
happens to be.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import delete

from src.core.database import Base, get_sync_db, sync_engine
from src.stocks.models import BarIntraday15m, ListingRoster
from src.stocks.providers.normalize import VN_TZ
from src.stocks.signals.issues import SignalIssue
from src.studies import registry, runner
from src.studies.contracts import StudyRefused
from src.studies.templates.params import (
    BINS_CEILING,
    LADDER_SESSIONS_CEILING,
    LADDER_SESSIONS_FLOOR,
    VolumeAtPriceParams,
)
from src.studies.templates.volume_at_price import NAME

from .template_run import run_template

#: Synthetic on purpose. The suite writes a listing row and deletes it again,
#: and a real ticker would mean deleting a row somebody's store actually needs.
SYMBOL = "ZZVAP"
OUTSIDE = "NOTINUNIV"

#: A Thursday, so a weekday question about it is a question about a session the
#: store is expected to hold.
SESSION = date(2026, 8, 20)
EARLIER = date(2026, 8, 19)

#: Above 50,000, so HOSE quotes this name in steps of 100.
TICK = Decimal(100)

#: Bucket one spans three steps and carries 300; bucket two sits on one step and
#: carries 500. So the ladder is 74,000 → 100, 74,100 → 600, 74,200 → 100.
WIDE_BAR = (Decimal(74_000), Decimal(74_200), 300)
NARROW_BAR = (Decimal(74_100), Decimal(74_100), 500)
PEAK_PRICE = 74_100.0
PEAK_VOLUME = 600.0
TOTAL_VOLUME = 800.0

#: A penny name's session: a hundred quoting steps of ten dong, which is more
#: rungs than the picture may carry, plus one step carrying most of the day.
#: 9,510 rather than the bottom of its zone, so "labelled with the busiest step
#: inside it" is a claim this window can actually falsify.
WIDE_RANGE = (Decimal(9_000), Decimal(9_990), 1_000)
HEAVY_STEP = (Decimal(9_510), Decimal(9_510), 5_000)
HEAVY_PRICE = 9_510.0
HEAVY_ZONE = (9_500.0, 9_530.0)
HEAVY_ZONE_VOLUME = 5_040.0
RANGE_TOTAL_VOLUME = 6_000.0


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


def bucket(day: date, hour: int, minute: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=VN_TZ)


def store(rows, *, exchange: str = "HOSE") -> None:
    """Put a listing and a set of buckets in the store for this symbol."""
    with get_sync_db() as session:
        session.execute(delete(BarIntraday15m).where(BarIntraday15m.symbol == SYMBOL))
        session.execute(delete(ListingRoster).where(ListingRoster.symbol == SYMBOL))
        if exchange:
            session.add(
                ListingRoster(
                    symbol=SYMBOL,
                    exchange=exchange,
                    is_listed=True,
                    source="test",
                    observed_at=bucket(SESSION, 15, 0),
                )
            )
        for day, hour, minute, low, high, volume in rows:
            session.add(
                BarIntraday15m(
                    symbol=SYMBOL,
                    bucket_start=bucket(day, hour, minute),
                    trading_day=day,
                    phase="pm" if hour >= 13 else "am",
                    open=low,
                    high=high,
                    low=low,
                    close=high,
                    volume=volume,
                    source="test",
                    observed_at=bucket(day, 15, 0),
                )
            )
        session.commit()


def clear() -> None:
    with get_sync_db() as session:
        session.execute(delete(BarIntraday15m).where(BarIntraday15m.symbol == SYMBOL))
        session.execute(delete(ListingRoster).where(ListingRoster.symbol == SYMBOL))
        session.commit()


@pytest.fixture
def window():
    """One session of two buckets, removed again afterwards."""
    low, high, volume = WIDE_BAR
    narrow_low, narrow_high, narrow_volume = NARROW_BAR
    store(
        [
            (SESSION, 9, 30, low, high, volume),
            (SESSION, 13, 30, narrow_low, narrow_high, narrow_volume),
        ]
    )
    yield SESSION
    clear()


@pytest.fixture
def penny_window():
    """A session covering a hundred steps, so the ladder has to be folded."""
    low, high, volume = WIDE_RANGE
    step_low, step_high, step_volume = HEAVY_STEP
    store(
        [
            (SESSION, 9, 30, low, high, volume),
            (SESSION, 13, 30, step_low, step_high, step_volume),
        ]
    )
    yield SESSION
    clear()


def at(day: date, hour: int = 16, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=VN_TZ)


class _FrozenClock:
    """The instant the runner freezes its as-of at, chosen by the test.

    Stands in for the ``datetime`` the runner reads the wall clock through. Not
    a convenience: which session this Study answers about, whether that session
    is still running, and how far its numbers reach are all read off that one
    instant, so a test that could not move it could only assert about whatever
    day the suite happened to run on.
    """

    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self, tz=None) -> datetime:
        return self._moment if tz is None else self._moment.astimezone(tz)


def run(
    params: dict,
    when: datetime,
    monkeypatch,
    *,
    universe: tuple[str, ...] = (SYMBOL,),
):
    monkeypatch.setattr(runner, "datetime", _FrozenClock(when))
    return run_template(NAME, params, universe=universe, monkeypatch=monkeypatch)


# -- the arithmetic --------------------------------------------------------


def test_a_bars_volume_is_spread_evenly_over_the_steps_its_range_covers(
    window, monkeypatch
):
    result = run({"symbol": SYMBOL}, at(SESSION), monkeypatch)
    ladder = result.frames["ladder"]
    volumes = dict(zip(ladder.column("price"), ladder.column("volume")))

    # Three steps in the wide bar, so a hundred each; the narrow bar sits whole
    # on the middle one.
    assert volumes == {74_000.0: 100.0, 74_100.0: 600.0, 74_200.0: 100.0}
    assert result.headline["totalVolume"] == TOTAL_VOLUME


def test_the_busiest_step_is_the_level_the_headline_names(window, monkeypatch):
    result = run({"symbol": SYMBOL}, at(SESSION), monkeypatch)

    assert result.headline["peakPrice"] == PEAK_PRICE
    assert result.headline["peakVolume"] == PEAK_VOLUME
    assert result.headline["peakShare"] == pytest.approx(PEAK_VOLUME / TOTAL_VOLUME)
    assert result.headline["grouped"] is False
    assert result.headline["peakZone"] is None


def test_the_ladder_marks_the_busiest_level_once_and_says_so(window, monkeypatch):
    frame = run({"symbol": SYMBOL}, at(SESSION), monkeypatch).frames["ladder"]
    prices = frame.column("price")
    peak_row = prices.index(PEAK_PRICE)

    assert frame.point_roles[peak_row] == "focus"
    assert frame.point_roles.count("focus") == 1
    assert set(frame.point_roles) == {"focus", "series"}
    # Price order, not volume order: the shape is the point of the picture.
    assert prices == sorted(prices)


def test_the_steps_follow_the_boards_own_ladder_rather_than_a_flat_grid():
    """HOSE quotes in 50s below 50,000 and 100s above, and a bar can straddle it.

    Still a function call rather than a planted window, because the grid stayed
    a *read*: which prices exist on this board is a fact about the exchange, and
    it is the one thing in this Study no arithmetic over the bars recovers.
    """
    from src.stocks.providers import Exchange
    from src.studies.templates.volume_at_price import _steps

    below = _steps(Exchange.HOSE, Decimal(49_800), Decimal(49_900))
    across = _steps(Exchange.HOSE, Decimal(49_900), Decimal(50_100))

    assert below == (Decimal(49_800), Decimal(49_850), Decimal(49_900))
    # 49,950 is quotable, 50,000 is the boundary, and above it the step widens.
    assert across == (
        Decimal(49_900),
        Decimal(49_950),
        Decimal(50_000),
        Decimal(50_100),
    )


def test_a_ladder_longer_than_the_bins_is_folded_into_even_zones(
    penny_window, monkeypatch
):
    """A penny name's session covers more steps than a chart can hold.

    A hundred quoting steps of ten dong, folded into twenty-four even zones. The
    heavy step sits at 9,510 — inside its zone rather than at the bottom of it —
    so "a folded rung is labelled with the busiest step inside it" is a claim
    that fails here if the label were taken from the zone's edge or its middle.
    """
    folded = run({"symbol": SYMBOL}, at(SESSION), monkeypatch).frames["folded"]

    assert len(folded.rows) == BINS_CEILING
    assert sum(folded.column("volume")) == pytest.approx(RANGE_TOTAL_VOLUME)

    rows = [dict(zip(folded.columns, row)) for row in folded.rows]
    heaviest = max(rows, key=lambda rung: rung["volume"])

    assert heaviest["volume"] == HEAVY_ZONE_VOLUME
    # A price the market quotes, not the arithmetic middle of a range.
    assert heaviest["price"] == HEAVY_PRICE
    assert (heaviest["zone_low"], heaviest["zone_high"]) == HEAVY_ZONE
    assert heaviest["zone_low"] < heaviest["price"] < heaviest["zone_high"]


def test_a_folded_answer_says_it_is_a_zone_rather_than_a_price(
    penny_window, monkeypatch
):
    result = run({"symbol": SYMBOL}, at(SESSION), monkeypatch)

    assert result.headline["grouped"] is True
    assert result.headline["peakPrice"] == HEAVY_PRICE
    assert " – " in result.headline["peakZone"]
    assert len(result.frames["ladder"].rows) <= BINS_CEILING


# -- which session the answer is about -------------------------------------


def test_a_session_the_store_does_not_hold_is_refused_rather_than_renamed(
    window, monkeypatch
):
    """The day after, on a weekday, with only the day before in the store."""
    after = SESSION + timedelta(days=1)
    assert after.weekday() < 5

    with pytest.raises(StudyRefused) as refusal:
        run({"symbol": SYMBOL}, at(after, hour=11), monkeypatch)

    assert refusal.value.issue is SignalIssue.SESSION_NOT_INGESTED
    assert str(after) in refusal.value.detail


def test_before_the_first_bucket_could_print_the_answer_is_the_session_stored(
    window, monkeypatch
):
    """At nine in the morning nothing of today exists yet, and that is not a gap."""
    after = SESSION + timedelta(days=1)

    result = run({"symbol": SYMBOL}, at(after, hour=9, minute=5), monkeypatch)

    assert result.headline["session"] == SESSION.isoformat()
    assert result.artifact.provenance.health == "normal"


def test_a_weekend_question_answers_from_the_last_session_stored(window, monkeypatch):
    saturday = SESSION + timedelta(days=(5 - SESSION.weekday()) % 7)
    assert saturday.weekday() == 5

    result = run({"symbol": SYMBOL}, at(saturday, hour=11), monkeypatch)

    assert result.headline["session"] == SESSION.isoformat()


def test_a_session_still_running_is_served_and_says_how_far_it_got(
    window, monkeypatch
):
    result = run({"symbol": SYMBOL}, at(SESSION, hour=13, minute=50), monkeypatch)

    assert result.headline["sessionUnderway"] is True
    assert result.artifact.provenance.health == "degraded"
    # The last bucket starts at 13:30 and covers the quarter hour after it, so
    # the numbers run to 13:45. Naming its start would hand back a quarter hour
    # that was counted.
    assert result.artifact.provenance.reason == "Phiên chưa đóng, tính tới 13:45"


def test_the_running_session_is_counted_up_to_the_end_of_its_last_bucket(monkeypatch):
    """The sentence names a clock time, and it is the one the numbers reach.

    The closing auction bucket is stamped 14:45 and stands for the quarter hour
    to 15:00, which is the same moment the rest of ``studies`` treats a session
    as settled. A reason built from bucket starts would say 14:45 and read as if
    the auction were still to come.
    """
    low, high, volume = WIDE_BAR
    store([(SESSION, 14, 45, low, high, volume)])
    try:
        result = run({"symbol": SYMBOL}, at(SESSION, hour=14, minute=55), monkeypatch)
    finally:
        clear()

    assert result.headline["sessionUnderway"] is True
    assert result.artifact.provenance.reason == "Phiên chưa đóng, tính tới 15:00"


def test_a_shorter_window_than_asked_for_says_so_without_refusing(monkeypatch):
    low, high, volume = WIDE_BAR
    store([(SESSION, 9, 30, low, high, volume)])
    try:
        result = run({"symbol": SYMBOL, "price_sessions": 3}, at(SESSION), monkeypatch)
    finally:
        clear()

    assert result.headline["sessionsUsed"] == 1
    assert result.artifact.provenance.health == "degraded"
    assert result.artifact.provenance.reason == "chỉ đọc được 1/3 phiên gần nhất"
    # The strip's own count, which is a number of sessions and not a row count:
    # the ladder underneath it holds three rungs and the reads hold one session.
    assert result.artifact.provenance.sessions_used == 1


def test_two_sessions_are_read_newest_first_and_counted_as_two(monkeypatch):
    low, high, volume = WIDE_BAR
    store(
        [
            (EARLIER, 9, 30, low, high, volume),
            (SESSION, 9, 30, low, high, volume),
        ]
    )
    try:
        result = run({"symbol": SYMBOL, "price_sessions": 2}, at(SESSION), monkeypatch)
    finally:
        clear()

    assert result.headline["sessionsUsed"] == 2
    assert result.headline["session"] == SESSION.isoformat()
    assert result.headline["totalVolume"] == 600.0
    assert result.artifact.provenance.sessions_used == 2


# -- the refusals ----------------------------------------------------------


def test_a_symbol_outside_the_universe_is_refused_before_any_read(monkeypatch):
    with pytest.raises(StudyRefused) as refusal:
        run({"symbol": OUTSIDE}, at(SESSION), monkeypatch)

    assert refusal.value.issue is SignalIssue.MISSING_TARGET_SESSION


def test_an_empty_store_refuses_with_the_same_code_as_a_missing_session(monkeypatch):
    clear()

    with pytest.raises(StudyRefused) as refusal:
        run({"symbol": SYMBOL}, at(SESSION, hour=7), monkeypatch)

    assert refusal.value.issue is SignalIssue.SESSION_NOT_INGESTED


def test_a_symbol_with_no_stored_board_is_refused_rather_than_given_a_guess(
    monkeypatch,
):
    low, high, volume = WIDE_BAR
    store([(SESSION, 9, 30, low, high, volume)], exchange="")
    try:
        with pytest.raises(StudyRefused) as refusal:
            run({"symbol": SYMBOL}, at(SESSION), monkeypatch)
    finally:
        clear()

    assert refusal.value.issue is SignalIssue.EXCHANGE_UNKNOWN


def test_a_session_where_nothing_traded_has_no_level_to_report(monkeypatch):
    low, high, _ = WIDE_BAR
    store([(SESSION, 9, 30, low, high, 0)])
    try:
        with pytest.raises(StudyRefused) as refusal:
            run({"symbol": SYMBOL}, at(SESSION), monkeypatch)
    finally:
        clear()

    assert refusal.value.issue is SignalIssue.NO_TRADED_SESSIONS


# -- what the model and the reader are handed ------------------------------


def test_the_headline_says_traded_rather_than_bought(window, monkeypatch):
    result = run({"symbol": SYMBOL}, at(SESSION), monkeypatch)

    assert "giao dịch nhiều nhất" in result.headline["caveat"]
    assert "không phải mức được mua nhiều nhất" in result.headline["caveat"]


def test_the_method_notes_name_both_limits_of_the_estimate(window, monkeypatch):
    """The template's own limitations lead the strip, ahead of the engine's.

    Both survive the merge of six steps' notes, which is the thing worth holding:
    a cap that dropped them would leave a reader the calculation's code digest
    and none of what the numbers mean.
    """
    result = run({"symbol": SYMBOL}, at(SESSION), monkeypatch)
    notes = " ".join(result.artifact.provenance.method_notes)

    assert "rải đều" in notes
    assert "không ghi bên mua hay bên bán" in notes


def test_the_headline_stays_inside_the_budget_the_model_pays_for(window, monkeypatch):
    import json

    result = run({"symbol": SYMBOL}, at(SESSION), monkeypatch)

    assert len(json.dumps(result.headline, ensure_ascii=False)) < 1_500


def test_the_strip_leads_with_the_level_and_carries_what_the_tiles_did(
    window, monkeypatch
):
    """The four figures the dropped ``tiles`` frame held, as resolved cells.

    ``tiles`` existed to feed a v1 ``stat_tiles`` block; the KPI strip is that
    block's replacement, so the test that held the tiles now holds the strip. The
    share reads as a percentage because it is quoted off a frame whose unit says
    so — off the ladder it would print ``0,75`` where a reader is owed ``75,0%``.
    """
    result = run({"symbol": SYMBOL}, at(SESSION), monkeypatch)
    board = result.board

    peak = result.kpi("Mức giá giao dịch nhiều nhất")
    assert peak.value.raw == PEAK_PRICE
    assert peak.role == "focus"
    assert [cell.role for cell in board.kpis].count("focus") == 1

    share = result.kpi("Tỷ trọng khối lượng tại mức đó")
    assert share.value.raw == pytest.approx(75.0)
    assert share.value.text.endswith("%")

    assert result.kpi("Giá đóng cửa gần nhất").value.raw == PEAK_PRICE
    assert result.kpi("Số phiên tính").value.raw == 1
    # Every figure on the strip is a cell of a frame this run wrote.
    assert all(cell.value.frame.startswith("f") for cell in board.kpis)


def test_the_board_draws_the_ladder_over_frames_the_plan_produced(window, monkeypatch):
    """One picture, and it is the ladder rather than either quoted frame.

    The composer files frames under ``f0``, ``f1``… so the board's vocabulary is
    not the plan's. What is checked is that the drawn frame is neither of the two
    the strip quotes, and that its axes are the ladder's own columns — price
    along the bottom, volume as the bar.
    """
    result = run({"symbol": SYMBOL}, at(SESSION), monkeypatch)
    board = result.board
    definition = registry.study(NAME)

    visuals = [
        block
        for section in board.sections
        for block in section.blocks
        if hasattr(block, "widget")
    ]
    assert len(visuals) == 1
    drawn = visuals[0]

    assert board.archetype == definition.archetype == "decompose"
    assert board.title.endswith(SYMBOL)
    assert drawn.widget == "bar_series"
    assert drawn.options == {"x": "price", "y": "volume"}
    assert drawn.frame not in {cell.value.frame for cell in board.kpis}
    assert set(result.frames) == set(definition.step_names)


def test_a_run_persists_a_frame_per_step_and_never_the_headline(window, monkeypatch):
    result = run({"symbol": SYMBOL}, at(SESSION), monkeypatch)

    assert result.artifact.study_name == NAME
    assert result.headline["peakPrice"] == PEAK_PRICE
    # Every step is addressable, which is what lets a model re-mix one.
    assert set(result.artifact.steps) == set(result.frames)
    assert all("#" in reference for reference in result.artifact.steps.values())


# -- the declaration -------------------------------------------------------


def test_a_session_count_out_of_range_is_clamped_rather_than_refused():
    assert (
        VolumeAtPriceParams.model_validate(
            {"symbol": "zzvap", "price_sessions": 900}
        ).price_sessions
        == LADDER_SESSIONS_CEILING
    )
    assert (
        VolumeAtPriceParams.model_validate(
            {"symbol": "zzvap", "price_sessions": 0}
        ).price_sessions
        == LADDER_SESSIONS_FLOOR
    )
    assert VolumeAtPriceParams.model_validate({"symbol": "zzvap"}).price_sessions == 1
    assert VolumeAtPriceParams.model_validate({"symbol": " zzvap "}).symbol == SYMBOL


def test_the_question_reaches_the_wordings_a_reader_actually_uses():
    question = registry.study(NAME).question

    for phrasing in ("mức giá mua nhiều nhất", "vùng giá tập trung", "hôm nay"):
        assert phrasing in question


def test_every_signal_issue_has_a_sentence_for_the_model():
    """The web app's half is held by ``signal-issues.test.ts``; this is ours."""
    from src.alpha.reasons import SIGNAL_ISSUE_SENTENCES

    missing = [issue for issue in SignalIssue if issue not in SIGNAL_ISSUE_SENTENCES]

    assert missing == []
