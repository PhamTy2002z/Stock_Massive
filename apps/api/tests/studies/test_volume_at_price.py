"""The study, against bars whose ladder can be worked out by hand.

Two buckets, three quoting steps between them, and a total that divides evenly:
everything asserted below is arithmetic on the fixture rather than a number that
merely looks plausible. The point of building it this small is that a change in
how volume is spread across a bar's range shows up as a wrong answer to a
question with a right one.
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
from src.studies.contracts import StudyContext, StudyRefused
from src.studies.volume_at_price import (
    BINS_CEILING,
    NAME,
    SESSIONS_CEILING,
    SESSIONS_FLOOR,
    VolumeAtPriceParams,
    compute as _compute,
)

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


def at(day: date, hour: int = 16, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=VN_TZ)


def compute(params: dict, when: datetime, universe: tuple[str, ...] = (SYMBOL,)):
    with get_sync_db() as session:
        return _compute(
            StudyContext(
                params=VolumeAtPriceParams.model_validate(params),
                session=session,
                as_of=when,
                universe=universe,
            )
        )


class _AUniverseOf:
    def __init__(self, symbols: tuple[str, ...]) -> None:
        self.symbols = symbols


# -- the arithmetic --------------------------------------------------------


def test_a_bars_volume_is_spread_evenly_over_the_steps_its_range_covers(window):
    result = compute({"symbol": SYMBOL}, at(SESSION))
    ladder = {row[0]: row[1] for row in result.frames["ladder"].rows}

    # Three steps in the wide bar, so a hundred each; the narrow bar sits whole
    # on the middle one.
    assert ladder == {74_000.0: 100.0, 74_100.0: 600.0, 74_200.0: 100.0}
    assert result.headline["totalVolume"] == TOTAL_VOLUME


def test_the_busiest_step_is_the_level_the_headline_names(window):
    result = compute({"symbol": SYMBOL}, at(SESSION))

    assert result.headline["peakPrice"] == PEAK_PRICE
    assert result.headline["peakVolume"] == PEAK_VOLUME
    assert result.headline["peakShare"] == pytest.approx(PEAK_VOLUME / TOTAL_VOLUME)
    assert result.headline["grouped"] is False
    assert result.headline["peakZone"] is None


def test_the_ladder_marks_the_busiest_level_once_and_says_so(window):
    result = compute({"symbol": SYMBOL}, at(SESSION))
    frame = result.frames["ladder"]
    peak_row = [row[0] for row in frame.rows].index(PEAK_PRICE)

    assert frame.point_roles[peak_row] == "focus"
    assert frame.point_roles.count("focus") == 1
    assert set(frame.point_roles) == {"focus", "series"}
    # Price order, not volume order: the shape is the point of the picture.
    assert [row[0] for row in frame.rows] == sorted(row[0] for row in frame.rows)


def test_the_steps_follow_the_boards_own_ladder_rather_than_a_flat_grid():
    """HOSE quotes in 50s below 50,000 and 100s above, and a bar can straddle it."""
    from src.stocks.providers import Exchange
    from src.studies.volume_at_price import _steps

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


def test_a_ladder_longer_than_the_bins_is_folded_into_even_zones():
    """A penny name's session covers more steps than a chart can hold."""
    from src.studies.volume_at_price import _fold

    ladder = {Decimal(9_000 + 10 * step): 1.0 for step in range(100)}
    ladder[Decimal(9_500)] = 50.0

    rungs = _fold(ladder, BINS_CEILING)

    assert len(rungs) == BINS_CEILING
    assert sum(rung.volume for rung in rungs) == pytest.approx(sum(ladder.values()))
    # A folded rung is labelled with the busiest step inside it, so the price the
    # answer names is a price the market quotes.
    heaviest = max(rungs, key=lambda rung: rung.volume)
    assert heaviest.price == Decimal(9_500)
    assert heaviest.folded is True
    assert heaviest.low <= Decimal(9_500) <= heaviest.high


def test_a_folded_answer_says_it_is_a_zone_rather_than_a_price():
    store(
        [
            (SESSION, 9, 30, Decimal(9_000), Decimal(9_990), 1_000),
            (SESSION, 13, 30, Decimal(9_500), Decimal(9_500), 5_000),
        ]
    )
    try:
        result = compute({"symbol": SYMBOL}, at(SESSION))
    finally:
        clear()

    assert result.headline["grouped"] is True
    assert " – " in result.headline["peakZone"]
    assert len(result.frames["ladder"].rows) <= BINS_CEILING


# -- which session the answer is about -------------------------------------


def test_a_session_the_store_does_not_hold_is_refused_rather_than_renamed(window):
    """The day after, on a weekday, with only the day before in the store."""
    after = SESSION + timedelta(days=1)
    assert after.weekday() < 5

    with pytest.raises(StudyRefused) as refusal:
        compute({"symbol": SYMBOL}, at(after, hour=11))

    assert refusal.value.issue is SignalIssue.SESSION_NOT_INGESTED
    assert str(after) in refusal.value.detail


def test_before_the_first_bucket_could_print_the_answer_is_the_session_stored(window):
    """At nine in the morning nothing of today exists yet, and that is not a gap."""
    after = SESSION + timedelta(days=1)

    result = compute({"symbol": SYMBOL}, at(after, hour=9, minute=5))

    assert result.headline["session"] == SESSION.isoformat()
    assert result.provenance.health == "normal"


def test_a_weekend_question_answers_from_the_last_session_stored(window):
    saturday = SESSION + timedelta(days=(5 - SESSION.weekday()) % 7)
    assert saturday.weekday() == 5

    result = compute({"symbol": SYMBOL}, at(saturday, hour=11))

    assert result.headline["session"] == SESSION.isoformat()


def test_a_session_still_running_is_served_and_says_how_far_it_got(window):
    result = compute({"symbol": SYMBOL}, at(SESSION, hour=13, minute=50))

    assert result.headline["sessionUnderway"] is True
    assert result.provenance.health == "degraded"
    # The last bucket starts at 13:30 and covers the quarter hour after it, so
    # the numbers run to 13:45. Naming its start would hand back a quarter hour
    # that was counted.
    assert result.provenance.reason == "Phiên chưa đóng, tính tới 13:45"


def test_the_running_session_is_counted_up_to_the_end_of_its_last_bucket():
    """The sentence names a clock time, and it is the one the numbers reach.

    The closing auction bucket is stamped 14:45 and stands for the quarter hour
    to 15:00, which is the same moment the rest of ``studies`` treats a session
    as settled. A reason built from bucket starts would say 14:45 and read as if
    the auction were still to come.
    """
    low, high, volume = WIDE_BAR
    store([(SESSION, 14, 45, low, high, volume)])
    try:
        result = compute({"symbol": SYMBOL}, at(SESSION, hour=14, minute=55))
    finally:
        clear()

    assert result.headline["sessionUnderway"] is True
    assert result.provenance.reason == "Phiên chưa đóng, tính tới 15:00"


def test_a_shorter_window_than_asked_for_says_so_without_refusing():
    low, high, volume = WIDE_BAR
    store([(SESSION, 9, 30, low, high, volume)])
    try:
        result = compute({"symbol": SYMBOL, "price_sessions": 3}, at(SESSION))
    finally:
        clear()

    assert result.headline["sessionsUsed"] == 1
    assert result.provenance.health == "degraded"
    assert result.provenance.reason == "chỉ đọc được 1/3 phiên gần nhất"


def test_two_sessions_are_read_newest_first_and_counted_as_two():
    low, high, volume = WIDE_BAR
    store(
        [
            (EARLIER, 9, 30, low, high, volume),
            (SESSION, 9, 30, low, high, volume),
        ]
    )
    try:
        result = compute({"symbol": SYMBOL, "price_sessions": 2}, at(SESSION))
    finally:
        clear()

    assert result.headline["sessionsUsed"] == 2
    assert result.headline["session"] == SESSION.isoformat()
    assert result.headline["totalVolume"] == 600.0


# -- the refusals ----------------------------------------------------------


def test_a_symbol_outside_the_universe_is_refused_before_any_read():
    with pytest.raises(StudyRefused) as refusal:
        compute({"symbol": OUTSIDE}, at(SESSION))

    assert refusal.value.issue is SignalIssue.MISSING_TARGET_SESSION


def test_an_empty_store_refuses_with_the_same_code_as_a_missing_session():
    clear()

    with pytest.raises(StudyRefused) as refusal:
        compute({"symbol": SYMBOL}, at(SESSION, hour=7))

    assert refusal.value.issue is SignalIssue.SESSION_NOT_INGESTED


def test_a_symbol_with_no_stored_board_is_refused_rather_than_given_a_guess():
    low, high, volume = WIDE_BAR
    store([(SESSION, 9, 30, low, high, volume)], exchange="")
    try:
        with pytest.raises(StudyRefused) as refusal:
            compute({"symbol": SYMBOL}, at(SESSION))
    finally:
        clear()

    assert refusal.value.issue is SignalIssue.EXCHANGE_UNKNOWN


def test_a_session_where_nothing_traded_has_no_level_to_report():
    low, high, _ = WIDE_BAR
    store([(SESSION, 9, 30, low, high, 0)])
    try:
        with pytest.raises(StudyRefused) as refusal:
            compute({"symbol": SYMBOL}, at(SESSION))
    finally:
        clear()

    assert refusal.value.issue is SignalIssue.NO_TRADED_SESSIONS


# -- what the model and the reader are handed ------------------------------


def test_the_headline_says_traded_rather_than_bought(window):
    result = compute({"symbol": SYMBOL}, at(SESSION))

    assert "giao dịch nhiều nhất" in result.headline["caveat"]
    assert "không phải mức được mua nhiều nhất" in result.headline["caveat"]


def test_the_method_notes_name_both_limits_of_the_estimate(window):
    result = compute({"symbol": SYMBOL}, at(SESSION))
    notes = " ".join(result.provenance.method_notes)

    assert "rải đều" in notes
    assert "không ghi bên mua hay bên bán" in notes


def test_the_headline_stays_inside_the_budget_the_model_pays_for(window):
    import json

    result = compute({"symbol": SYMBOL}, at(SESSION))

    assert len(json.dumps(result.headline, ensure_ascii=False)) < 1_500


def test_the_tiles_lead_with_the_level_and_mark_it_once(window):
    result = compute({"symbol": SYMBOL}, at(SESSION))
    tiles = result.frames["tiles"]

    assert tiles.rows[0] == ("Mức giá giao dịch nhiều nhất", PEAK_PRICE, "đồng")
    assert tiles.rows[1][1] == pytest.approx(75.0)
    assert tiles.point_roles == ("focus", None, None, None)


def test_the_signal_desk_draws_two_blocks_over_frames_the_study_produced(window):
    definition = registry.study(NAME)
    result = compute({"symbol": SYMBOL}, at(SESSION))
    spec = definition.view(result)

    assert [block.widget for block in spec.blocks] == ["stat_tiles", "bar_series"]
    assert {block.frame for block in spec.blocks} <= set(result.frames)
    assert set(definition.frames) == set(result.frames)


def test_the_whole_run_path_persists_an_artifact(monkeypatch):
    """The runner freezes its own as-of, so the fixture is stamped for now."""
    today = datetime.now(VN_TZ).date()
    low, high, volume = WIDE_BAR
    narrow_low, narrow_high, narrow_volume = NARROW_BAR
    store(
        [
            (today, 9, 30, low, high, volume),
            (today, 13, 30, narrow_low, narrow_high, narrow_volume),
        ]
    )
    monkeypatch.setattr(
        runner, "build_universe", lambda session: _AUniverseOf((SYMBOL,))
    )
    try:
        with get_sync_db() as session:
            stored = runner.run(NAME, {"symbol": SYMBOL}, session=session, warm=None)
            session.rollback()
    finally:
        clear()

    assert stored.study_name == NAME
    assert stored.headline["peakPrice"] == PEAK_PRICE
    assert stored.signal_desk_spec.title.endswith(SYMBOL)


# -- the declaration -------------------------------------------------------


def test_a_session_count_out_of_range_is_clamped_rather_than_refused():
    assert (
        VolumeAtPriceParams.model_validate({"symbol": "zzvap", "price_sessions": 900}).price_sessions
        == SESSIONS_CEILING
    )
    assert (
        VolumeAtPriceParams.model_validate({"symbol": "zzvap", "price_sessions": 0}).price_sessions
        == SESSIONS_FLOOR
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
