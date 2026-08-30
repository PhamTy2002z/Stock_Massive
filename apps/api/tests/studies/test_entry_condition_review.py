"""The condition review, against a window whose every answer is known.

The fixture (``condition_fixture.py``) plants a plateau, a decline, a ramp and a
sixty-session cluster, so each number asserted here is derivable from that
construction rather than copied from a run: the 52-week band is the close series
plus a constant wick, the twelve-month return is the last close over the first,
and the accumulation zone is the pair of histogram bins the cluster was built to
fill. A change in the arithmetic therefore shows up as a wrong answer to a
question with a right one.

**Asserted through the engine rather than against a function.** The Study is a
plan now: its arithmetic lives in the sandbox and there is no ``compute`` to
call, so every test here runs the plan and reads the frames back off the rows it
wrote. That is also the honest subject — what a reader sees comes out of those
rows and out of nothing else. The three invariants that used to be checked
against ``_rsi`` and ``_concentration_zone`` directly are checked against planted
windows built to expose them, and each planted window still has an answer that
can be derived by hand.

**The window needs a calendar as well as bars.** The store's own daily reader
walks the Trading Day spine — the index series — and reads each symbol against
it, so a symbol's rows alone are a window nothing can look up. The spine is
planted here beside the fixture's bars, under a ticker of this file's own: a
test that skipped it would be testing a store that cannot exist, and one that
planted the real index would be deleting sessions somebody collected when it
cleaned up.

Two properties are checked here that are not about arithmetic at all, and both
are promises this Study makes to a reader:

**The frames never reach the model.** Asserted off the messages a Turn would
send, not off the payload, because a clean payload and a clean transcript are
two different claims and only the second one is the rule.

**The headline has no imperative in it.** A regex, because the failure mode is a
later edit adding one word — a Study that told a reader what to do would be
doing it in the only field the model actually reads.
"""

from __future__ import annotations

import json
import re
import uuid

import pytest
from sqlalchemy import delete

from src.agent.messages import (
    ContextBudget,
    ToolCallStatus,
    Transcript,
    TranscriptTurn,
    TurnToolCall,
    build_messages,
)
from src.agent.registry import ToolContext
from src.agent.tools import studies as study_tools
from src.alpha.models import AgentArtifact
from src.core.database import Base, get_sync_db, sync_engine
from src.stocks.models import BarDaily
from src.stocks.signals.issues import SignalIssue
from src.studies import registry
from src.studies.contracts import StudyRefused
from src.studies.reads_daily import SERIES_INDEX
from src.studies.templates.entry_condition_review import (
    CHECKLIST_NOTE,
    CONDITION_EVIDENCE,
    LABEL_IN_ZONE,
    LABEL_OFF_HIGH,
    LABEL_PROFIT_IMPROVED,
    LABEL_PROFIT_POSITIVE,
    LABEL_RETURN_12M,
    LABEL_RSI,
    MIN_SESSIONS,
    NAME,
    RSI_PERIOD,
    RSI_WINDOW_SESSIONS,
    ZONE_SESSIONS,
)
from src.studies.templates.params import (
    HORIZON_CEILING,
    HORIZON_FLOOR,
    ConditionReviewParams,
)

from . import condition_fixture as fixture
from .template_run import run_template

SYMBOL = fixture.SYMBOL

#: Wilder's RSI over the fixture's last hundred closes. Not hand-derived — the
#: recursion has no closed form — so the smoothing step is pinned analytically by
#: the three planted windows below and this is the value it produces for this
#: window. Well clear of the overbought threshold, so the status it decides does
#: not turn on the last decimal.
FIXTURE_RSI = 51.19

#: What the fixture makes of the six conditions: five hold, the twelve-month
#: return does not, and nothing is unknown because the quarters are stored.
EXPECTED_STATUSES = {
    LABEL_OFF_HIGH: "Đạt",
    LABEL_IN_ZONE: "Đạt",
    LABEL_RETURN_12M: "Chưa đạt",
    LABEL_RSI: "Đạt",
    LABEL_PROFIT_POSITIVE: "Đạt",
    LABEL_PROFIT_IMPROVED: "Đạt",
}

#: The vocabulary a condition review may never speak, in the field the model
#: reads. Case-insensitive, because the failure is the word and not its casing.
IMPERATIVE = re.compile(r"nên mua|mua ngay|bán ngay|WAIT|BUY|SELL", re.IGNORECASE)

#: This Study reads no membership rule: the four axes it measures come from the
#: store's own rows, and a symbol the backfill has not reached refuses for want
#: of sessions rather than for want of a declaration.
NO_UNIVERSE: tuple[str, ...] = ()


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


#: The ticker the spine is planted under. Not the real index, for the reason
#: ``condition_fixture`` does not use a real equity ticker either: the calendar
#: is read off the *series* (``stocks/trading_day.py::CALENDAR_SERIES``) and not
#: off a name, so a synthetic ticker is a valid spine — while planting and
#: clearing the real one would be a suite deleting sessions somebody collected.
CALENDAR_SYMBOL = "TSTZIDX"


@pytest.fixture(scope="module", autouse=True)
def calendar():
    """The Trading Day spine the store's daily reader walks, for these sessions.

    A symbol's own rows are a window nothing can look up: the store's daily
    reader resolves the sessions off the spine first and reads each symbol
    against them, so a fixture that planted bars and no calendar would be
    testing a store that cannot exist.
    """
    with get_sync_db() as session:
        _clear_calendar(session)
        session.add_all(
            BarDaily(
                symbol=CALENDAR_SYMBOL,
                trading_day=day,
                series=SERIES_INDEX,
                open=1_000.0,
                high=1_000.0,
                low=1_000.0,
                close=1_000.0,
                volume=0,
                price_basis=fixture.PRICE_BASIS,
                source=fixture.SOURCE,
                observed_at=fixture.AS_OF,
            )
            for day in fixture.sessions()
        )

    yield

    with get_sync_db() as session:
        _clear_calendar(session)


def _clear_calendar(session) -> None:
    session.execute(delete(BarDaily).where(BarDaily.symbol == CALENDAR_SYMBOL))


@pytest.fixture
def window():
    """The planted year and its eight quarters, committed, then removed again."""
    with get_sync_db() as session:
        fixture.load_bars(session)
        fixture.load_quarters(session)

    yield

    with get_sync_db() as session:
        fixture.clear_bars(session)
        fixture.clear_quarters(session)


def run(monkeypatch, params: dict | None = None):
    """One run of the plan, with its frames read back off the rows it wrote."""
    return run_template(
        NAME,
        {"symbol": SYMBOL, **(params or {})},
        universe=NO_UNIVERSE,
        monkeypatch=monkeypatch,
    )


def statuses(result) -> dict[str, str]:
    """The checklist as ``{condition: status}``, in the words it is sent in.

    Vietnamese rather than tokens: the frame is also what the disclosure under
    the block prints, so the status travels as the word a reader reads.
    """
    return {row[0]: row[1] for row in result.frames["conditions"].rows}


def visuals(board) -> list:
    return [
        block
        for section in board.sections
        for block in section.blocks
        if hasattr(block, "widget")
    ]


def captions(board) -> list[str]:
    return [
        block.text
        for section in board.sections
        for block in section.blocks
        if not hasattr(block, "widget")
    ]


# -- the four axes, against the construction -------------------------------


def test_the_band_and_the_position_are_the_ones_the_fixture_built(window, monkeypatch):
    position = run(monkeypatch).headline["pricePosition"]

    assert position["last"] == fixture.LAST_CLOSE
    assert position["high52w"] == fixture.HIGH_52W
    assert position["low52w"] == fixture.LOW_52W
    # (71.350 - 67.900) / (80.100 - 67.900), to the two decimals a rate earns.
    assert position["percentile"] == pytest.approx(28.28, abs=0.01)
    assert position["offHighPct"] == pytest.approx(-10.92, abs=0.01)
    # The last close over the first of the 250 sessions, and nothing else.
    assert position["return12mPct"] == pytest.approx(-10.81, abs=0.01)
    assert position["rsi14"] == pytest.approx(FIXTURE_RSI, abs=0.01)


def test_the_accumulation_zone_is_the_pair_of_bins_the_cluster_filled(
    window, monkeypatch
):
    cluster = run(monkeypatch).headline["pricePosition"]["closeCluster"]

    # The last sixty closes span 68.000–74.000, so the twenty bins are 300đ
    # wide and the cluster sits in the eleventh and twelfth of them.
    assert cluster["low"] == fixture.ZONE_LOW
    assert cluster["high"] == fixture.ZONE_HIGH
    assert cluster["sessions"] == f"{fixture.ZONE_SESSIONS_IN}/{ZONE_SESSIONS}"


def test_the_zone_is_recomputed_from_its_own_window_and_never_the_horizon(
    window, monkeypatch
):
    """The same store, a wider horizon, the same sixty-session zone.

    The zone's window is fixed in the Study rather than following the parameter
    the model passed, so a reader cannot change what "vùng tích luỹ" means by
    asking for a longer line. The frame says so itself: ``zone_window`` is sixty
    while the line beside it draws every session the horizon reached.
    """
    narrow = run(monkeypatch)
    wide = run(monkeypatch, {"horizon_sessions": HORIZON_CEILING})

    assert (
        narrow.headline["pricePosition"]["closeCluster"]
        == wide.headline["pricePosition"]["closeCluster"]
    )
    for result in (narrow, wide):
        assert result.frames["readings"].column("zone_window")[0] == ZONE_SESSIONS
        assert len(result.frames["price_context"].rows) == fixture.TOTAL_SESSIONS


def test_the_earnings_axis_reads_the_eight_stored_quarters(window, monkeypatch):
    result = run(monkeypatch)
    quarters = result.frames["earnings_quarters"].rows

    assert len(quarters) == len(fixture.QUARTER_PROFITS_VND)
    assert [row[1] for row in quarters] == list(fixture.QUARTER_PROFITS_VND)
    # Year-on-year on the four most recent only: the four before them are the
    # comparison, not a reading of their own.
    assert [row[2] for row in quarters[:4]] == [None] * 4
    # 1.800 against 1.300, four quarters earlier.
    assert quarters[-1][2] == pytest.approx(38.46, abs=0.01)
    assert result.headline["earningsTrend"] == "improving"
    assert result.headline["latestQuarter"]["period"] == "Q2/2026"


# -- the checklist ---------------------------------------------------------


def test_the_checklist_statuses_are_the_ones_the_fixture_determines(
    window, monkeypatch
):
    result = run(monkeypatch)

    assert statuses(result) == EXPECTED_STATUSES
    assert result.headline["conditions"]["met"] == 5
    assert result.headline["conditions"]["notMet"] == 1
    assert result.headline["conditions"]["unknown"] == 0
    # The labels the model narrates are the labels the Signal Desk draws — one text,
    # written here, never composed by a model.
    assert [item["label"] for item in result.headline["conditions"]["items"]] == [
        row[0] for row in result.frames["conditions"].rows
    ]


def test_a_row_points_at_a_picture_in_words_a_reader_can_follow(window, monkeypatch):
    """The pointer is printed into a tooltip, so it is Vietnamese and not a key.

    The case: the browser rendered "Số liệu trong khối price_context" over a row
    about the twelve-month return.

    The vocabulary is fixed in the template, so nothing a model writes can
    re-point a row; and both kinds of pointer land on something this board shows
    — four of them name a block, and "Các số dẫn dắt" names the strip.
    """
    result = run(monkeypatch)
    named = [row[4] for row in result.frames["conditions"].rows]

    # Written out here rather than compared against the template's own tuple.
    # The column is *filled from* that tuple, so asserting the two match is
    # asserting a copy against itself — it would follow any edit silently,
    # including one that put a column name back in front of a reader.
    assert named == [
        "Dải giá 52 tuần",
        "Dải giá 52 tuần",
        "Đường giá",
        "Các số dẫn dắt",
        "Lợi nhuận theo quý",
        "Lợi nhuận theo quý",
    ]
    assert named == list(CONDITION_EVIDENCE)
    for pointer in named:
        assert "_" not in pointer, pointer
    assert len(visuals(result.board)) >= 4
    assert len(result.board.kpis) >= 3


def test_every_condition_shows_the_number_the_picture_beside_it_shows(
    window, monkeypatch
):
    """A row's measurement is a cell of a frame the board draws, not a re-derivation.

    The checklist compares the raw measurement and prints the rounded one, and
    the rounding happens once — so a row and the picture it points at can never
    disagree by a đồng.
    """
    result = run(monkeypatch)
    measured = [row[2] for row in result.frames["conditions"].rows]
    readings = result.frames["readings"]
    reading = {name: readings.column(name)[0] for name in readings.columns}
    earnings = result.frames["earnings"]
    latest = dict(zip(earnings.columns, earnings.rows[-1]))

    assert measured[0] == reading["off_high_pct"]
    assert measured[1] == reading["last"]
    assert measured[2] == reading["return_12m_pct"]
    assert measured[3] == reading["rsi_14"]
    assert measured[4] == latest["net_profit_vnd"]
    assert measured[5] == latest["yoy_pct"]


def test_a_symbol_with_no_quarters_still_answers_with_an_unknown_earnings_axis(
    window, monkeypatch
):
    with get_sync_db() as session:
        fixture.clear_quarters(session)

    result = run(monkeypatch)

    assert result.headline["earningsTrend"] == "unknown"
    assert result.headline["latestQuarter"] is None
    # The two earnings conditions are unknown rather than failed: a company that
    # has not filed is not a company whose profit fell.
    assert statuses(result)[LABEL_PROFIT_POSITIVE] == "Chưa rõ"
    assert statuses(result)[LABEL_PROFIT_IMPROVED] == "Chưa rõ"
    assert result.headline["conditions"]["unknown"] == 2
    # And the price axes still answer, which is the whole point of not refusing.
    assert result.headline["pricePosition"]["last"] == fixture.LAST_CLOSE
    assert result.frames["earnings_quarters"].rows == ()
    # The strip says the panel is thinner than a whole review, in the terms the
    # reader is shown.
    assert result.artifact.provenance.health == "degraded"
    assert "quý lợi nhuận" in (result.artifact.provenance.reason or "")
    assert "0/8" in (result.artifact.provenance.reason or "")


def test_fewer_than_eight_quarters_is_still_an_unknown_trend(window, monkeypatch):
    with get_sync_db() as session:
        fixture.load_quarters(session, profits=(1_000e9, 1_100e9, 1_200e9))

    result = run(monkeypatch)

    # Three quarters is no year-on-year pair at all, and a partial trend read as
    # a trend would be a different claim from the one the data supports.
    assert result.headline["earningsTrend"] == "unknown"
    assert statuses(result)[LABEL_PROFIT_POSITIVE] == "Đạt"
    assert statuses(result)[LABEL_PROFIT_IMPROVED] == "Chưa rõ"


def test_a_loss_making_base_quarter_gets_no_percentage(window, monkeypatch):
    """A percentage change from a loss is a number nobody can use.

    The direction is still knowable, so the condition is answered from the sign
    of the change while the frame's percentage stays absent.
    """
    with get_sync_db() as session:
        fixture.load_quarters(
            session,
            profits=(-500e9, 100e9, 100e9, 100e9, 200e9, 200e9, 200e9, 200e9),
        )

    result = run(monkeypatch)
    quarters = result.frames["earnings_quarters"].rows

    # Q3/2025 against a negative Q3/2024: no percentage, but it did improve.
    assert quarters[4][2] is None
    assert result.headline["earningsTrend"] == "improving"


# -- refusal, clamping, and the shape of the answer ------------------------


def test_a_window_shorter_than_a_year_refuses_and_names_the_store(
    window, monkeypatch
):
    with get_sync_db() as session:
        fixture.load_bars(session, keep=MIN_SESSIONS - 1)

    with pytest.raises(StudyRefused) as refusal:
        run(monkeypatch)

    assert refusal.value.issue is SignalIssue.INSUFFICIENT_SESSIONS
    # The refusal is about the store rather than about the company, and it says
    # so with both numbers in it.
    assert f"{MIN_SESSIONS} needed" in refusal.value.detail
    assert str(MIN_SESSIONS - 1) in refusal.value.detail


def test_a_horizon_out_of_range_is_clamped_rather_than_refused():
    assert (
        ConditionReviewParams.model_validate(
            {"symbol": "tstz", "horizon_sessions": 5_000}
        ).horizon_sessions
        == HORIZON_CEILING
    )
    assert (
        ConditionReviewParams.model_validate(
            {"symbol": "tstz", "horizon_sessions": 5}
        ).horizon_sessions
        == HORIZON_FLOOR
    )
    assert ConditionReviewParams.model_validate({"symbol": " tstz "}).symbol == "TSTZ"


def test_the_headline_says_which_session_it_is_true_of(window, monkeypatch):
    headline = run(monkeypatch).headline

    assert headline["asOfSession"] == fixture.LAST_SESSION.isoformat()
    assert headline["sessionsUsed"] == fixture.TOTAL_SESSIONS


def test_the_headline_holds_no_imperative_language(window, monkeypatch):
    serialized = json.dumps(run(monkeypatch).headline, ensure_ascii=False)

    assert IMPERATIVE.search(serialized) is None, serialized


def test_the_headline_stays_inside_the_budget_the_model_pays_for(window, monkeypatch):
    serialized = json.dumps(run(monkeypatch).headline, ensure_ascii=False)

    # Roughly three hundred tokens. The six condition labels are the bulk of it
    # and they are the part the model cannot be given any other way.
    assert len(serialized) < 1_800, len(serialized)


# -- the board -------------------------------------------------------------


def test_the_board_draws_the_frames_the_plan_produced(window, monkeypatch):
    """Every picture on the board comes out of a step, and the strip out of cells.

    The frames the board carries are filed under ``f0``, ``f1``… by the composer,
    so what is checked here is that each one is a frame this run produced rather
    than that it is called what the plan called it — the step names are the
    plan's vocabulary and the keys are the board's.

    The checklist is last on purpose, and the assertion says so: it is the block
    a reader looks at first and the one that means least without the
    measurements above it.
    """
    result = run(monkeypatch)
    board = result.board
    definition = registry.study(NAME)

    drawn = [block.widget for block in visuals(board)]
    assert board.archetype == definition.archetype
    assert SYMBOL in board.title
    assert len(drawn) >= 4
    assert len(set(drawn)) >= 2
    assert drawn[-1] == "condition_checklist"
    # The band is a ruler with a mark on it rather than a strip of tiles, and
    # eight quarters are groups being compared rather than a path.
    assert "range_strip" in drawn
    assert "bar_series" in drawn


def test_the_kpi_strip_carries_the_figures_the_dropped_tiles_frame_did(
    window, monkeypatch
):
    """Five figures, resolved out of cells, at the width a reader is shown them.

    The v1 board opened with a ``stat_tiles`` block over a ``tiles`` frame; the
    strip is that block's replacement, so its five figures have to be the five
    the tiles carried — and each has to print in its own unit, which is why the
    three percentages are read out of a frame whose unit is ``%`` rather than out
    of the band, whose unit is đồng.
    """
    result = run(monkeypatch)
    position = result.headline["pricePosition"]

    assert result.kpi("Giá đóng cửa gần nhất").value.raw == position["last"]
    assert result.kpi("Vị thế trong dải 52 tuần").value.raw == position["percentile"]
    assert result.kpi("Lợi nhuận 12 tháng").value.raw == position["return12mPct"]
    assert result.kpi("Cách đỉnh 52 tuần").value.raw == position["offHighPct"]
    assert result.kpi("RSI 14 phiên").value.raw == position["rsi14"]

    for label in ("Vị thế trong dải 52 tuần", "Lợi nhuận 12 tháng", "Cách đỉnh 52 tuần"):
        assert result.kpi(label).value.text.endswith("%"), label
    # A price is money, so it is grouped and carries no percent sign.
    assert result.kpi("Giá đóng cửa gần nhất").value.text == "71.350"
    # Every figure on the strip is a resolved cell rather than a number typed
    # into the board.
    assert all(cell.value.frame.startswith("f") for cell in result.board.kpis)


def test_the_disclosure_travels_with_the_board_and_orders_nobody_about(
    window, monkeypatch
):
    """The fixed note is a caption now, under the block it discloses.

    Under v1 it was an option on the checklist widget. Either way it is written
    here rather than composed in the browser, and it does not tell the reader to
    do anything.
    """
    note = captions(run(monkeypatch).board)

    assert note == [CHECKLIST_NOTE]
    assert IMPERATIVE.search(note[0]) is None
    assert "nên" not in note[0] and "hãy" not in note[0]


def test_a_run_persists_a_frame_per_step_and_freezes_the_as_of(window, monkeypatch):
    result = run(monkeypatch)

    assert result.artifact.study_name == NAME
    assert set(result.frames) == set(registry.study(NAME).step_names)
    # Every step is addressable, which is what lets a model re-mix one.
    assert set(result.artifact.steps) == set(result.frames)
    assert all("#" in reference for reference in result.artifact.steps.values())
    # Read off the persisted payload: the checklist opens on the price axis.
    assert result.frames["conditions"].rows[0][0] == LABEL_OFF_HIGH
    assert result.artifact.provenance.as_of is not None
    # Nothing was warmed: this Study declares no inputs a provider has to fetch,
    # which is what lets it answer inside one round.
    assert registry.study(NAME).requires == ()


# -- the law: frames never reach a message --------------------------------


def test_the_frames_are_absent_from_the_messages_a_turn_would_send(window):
    """The whole rule, read off the transcript rather than off the payload.

    Every number checked here is one a reader sees on the Signal Desk and the model
    must not: a close from the price series, the zone bounds, a quarter's
    profit. The headline's own figures are exempt by design — they are what the
    model is given — so the assertions name cells that live only in frames.

    ``frames`` is on the payload now and holds a handle per step, which is how a
    model re-mixes one of them. A handle is an id and a step name; the assertion
    is that it is *only* that, and that no row travelled with it.
    """
    tools = study_tools.StudyTools()
    # No Turn and no Thread: an artifact reachable by id and by nothing else,
    # which is what this assertion needs and all it needs. Ownership is proven
    # where it belongs, in ``tests/test_agent_study_tools.py``.
    answered = dict(
        tools.run_study(ToolContext(user_id=1), {"name": NAME, "symbol": SYMBOL})
    )

    try:
        handles = dict(answered["frames"])
        assert set(handles) == set(registry.study(NAME).step_names)
        for step, handle in handles.items():
            assert handle.endswith(f"#{step}")
            uuid.UUID(handle.split("#", 1)[0])

        call = TurnToolCall(
            id="call-1",
            name="run_study",
            arguments={"name": NAME, "symbol": SYMBOL},
            status=ToolCallStatus.OK,
            result_text=json.dumps(answered, ensure_ascii=False),
            summary="Điều kiện hiện tại: TSTZ",
        )
        context = build_messages(
            Transcript(
                system_prompt="hệ thống",
                turns=(
                    TranscriptTurn(
                        user_text="Điều kiện của TSTZ thế nào?", tool_calls=(call,)
                    ),
                ),
            ),
            ContextBudget(),
        )
        whole = "\n".join(str(message.content or "") for message in context.messages)

        assert answered["artifactId"] in whole
        # A close from inside the cluster and the oldest quarter's profit: two
        # cells that exist only in the frames. The *latest* quarter's profit and
        # the cluster's own bounds are deliberately not probed — those are
        # headline figures, and the model is meant to have them.
        for cell in (
            str(fixture.CLUSTER_LOW_CLOSE),
            str(int(fixture.QUARTER_PROFITS_VND[0])),
        ):
            assert cell not in whole.replace(".0", ""), cell
        assert "net_profit_vnd" not in whole
    finally:
        with get_sync_db() as session:
            session.execute(
                delete(AgentArtifact).where(
                    AgentArtifact.id.in_(
                        [uuid.UUID(answered["artifactId"])]
                        + [
                            uuid.UUID(str(handle).split("#", 1)[0])
                            for handle in (answered.get("frames") or {}).values()
                        ]
                    )
                )
            )


# -- the two derivations with no closed form ------------------------------


@pytest.fixture
def planted():
    """A year written close by close, so a shape can be posed exactly.

    The bars are the fixture's own shape — a constant wick either side of the
    close — so a planted window differs from the fixture's in one thing only:
    the close series. Everything else a reader could confuse for the cause is
    held equal.
    """

    def _write(closes: list[float]) -> None:
        days = fixture.sessions()
        assert len(closes) == len(days), (len(closes), len(days))
        with get_sync_db() as session:
            fixture.clear_bars(session)
            session.add_all(
                BarDaily(
                    symbol=SYMBOL,
                    trading_day=day,
                    series=fixture.SERIES,
                    open=close,
                    high=close + fixture.WICK,
                    low=close - fixture.WICK,
                    close=close,
                    volume=1_000_000,
                    price_basis=fixture.PRICE_BASIS,
                    source=fixture.SOURCE,
                    observed_at=fixture.AS_OF,
                )
                for day, close in zip(days, closes)
            )

    yield _write

    with get_sync_db() as session:
        fixture.clear_bars(session)


#: What the planted windows below are built around, and what they lead with.
#: Anything before the last :data:`RSI_WINDOW_SESSIONS` closes is out of the
#: RSI's reach and out of the zone's, so it is a plateau and says nothing.
PLANTED_PRICE = 70_000.0
LEAD_SESSIONS = fixture.TOTAL_SESSIONS - RSI_WINDOW_SESSIONS
LEAD = [65_000.0] * LEAD_SESSIONS

#: Fourteen alternating ±1 closes: seven gains of one and seven losses of one,
#: so Wilder's seed averages are both exactly ``7/14``.
ALTERNATING: list[float] = []
for _step in range(RSI_PERIOD):
    ALTERNATING.append(
        (ALTERNATING[-1] if ALTERNATING else PLANTED_PRICE)
        + (1 if _step % 2 == 0 else -1)
    )

#: How many sessions of no movement follow the seed. One short of the window's
#: changes minus the seed, so a case can spend a session on a move first.
SETTLED_SESSIONS = RSI_WINDOW_SESSIONS - 1 - RSI_PERIOD


def test_the_rsi_is_wilders(planted, monkeypatch):
    """Two windows with an exact answer, proven arithmetically rather than run.

    Fourteen changes of alternating ±1 make the seed averages equal at ``7/14``
    apiece. A session of no movement multiplies **both** by ``13/14``, so a run
    of them leaves them equal however long it is — and the index is exactly
    fifty. One up change before that run makes them ``7,5/14`` and ``6,5/14``,
    a ratio the run of flat sessions preserves, so the index is exactly
    ``100 × 7,5/14``. That is the whole of Wilder's step: the seed, the
    smoothing, and the fact that smoothing is a decay applied to both sides.

    Read off ``momentum`` rather than off the headline, because ``momentum`` is
    the frame the conditions are compared against and it is not rounded.
    """
    planted([*LEAD, PLANTED_PRICE, *ALTERNATING, *([ALTERNATING[-1]] * SETTLED_SESSIONS)])
    assert run(monkeypatch).frames["momentum"].column("rsi_14")[0] == 50.0

    # The first of the settled sessions is the up move itself; the rest sit on
    # the price it reached, so the window is the same length either way.
    stepped_up = ALTERNATING[-1] + 1
    planted([*LEAD, PLANTED_PRICE, *ALTERNATING, *([stepped_up] * SETTLED_SESSIONS)])
    assert run(monkeypatch).frames["momentum"].column("rsi_14")[0] == pytest.approx(
        100 * 7.5 / 14, abs=1e-9
    )


def test_a_window_with_no_down_move_is_the_top_of_the_scale(planted, monkeypatch):
    planted([*LEAD, *[PLANTED_PRICE + step for step in range(RSI_WINDOW_SESSIONS)]])

    result = run(monkeypatch)

    assert result.frames["momentum"].column("rsi_14")[0] == 100.0
    # A hundred is not below seventy, and the condition says so rather than
    # going quiet.
    assert statuses(result)[LABEL_RSI] == "Chưa đạt"


def test_a_window_that_never_moved_has_no_relative_strength_to_report(
    planted, monkeypatch
):
    """No move at all is an absence, and fifty would be a reading."""
    planted([*LEAD, *[PLANTED_PRICE] * RSI_WINDOW_SESSIONS])

    result = run(monkeypatch)

    assert result.frames["momentum"].column("rsi_14")[0] is None
    assert result.headline["pricePosition"]["rsi14"] is None
    assert statuses(result)[LABEL_RSI] == "Chưa rõ"


#: A window whose last sixty closes are thirty at each end of a 10.000đ span, so
#: the twenty bins are 500đ wide and the two end pairs hold thirty apiece.
TIE_LOW = 60_000.0
TIE_HIGH = 70_000.0


def test_a_tie_between_two_zones_goes_to_the_lower_one(planted, monkeypatch):
    """The only tie-break that is not a fact about iteration order.

    Two pairs of bins holding the same count, one at each end of the window: the
    answer has to be the same on every run over the same data, which is what
    "recomputed every run" means.
    """
    tie = [
        TIE_LOW if step % 2 == 0 else TIE_HIGH for step in range(ZONE_SESSIONS)
    ]
    planted([*[65_000.0] * (fixture.TOTAL_SESSIONS - ZONE_SESSIONS), *tie])

    cluster = run(monkeypatch).headline["pricePosition"]["closeCluster"]

    # The lower pair: 60.000 plus two of the twenty 500đ bins.
    assert (cluster["low"], cluster["high"]) == (TIE_LOW, TIE_LOW + 1_000)
    assert cluster["sessions"] == f"{ZONE_SESSIONS // 2}/{ZONE_SESSIONS}"


def test_a_window_that_never_moved_is_a_zone_of_one_price(planted, monkeypatch):
    flat = 71_000.0
    planted([*[65_000.0] * (fixture.TOTAL_SESSIONS - ZONE_SESSIONS), *[flat] * ZONE_SESSIONS])

    result = run(monkeypatch)
    cluster = result.headline["pricePosition"]["closeCluster"]

    assert (cluster["low"], cluster["high"]) == (flat, flat)
    assert cluster["sessions"] == f"{ZONE_SESSIONS}/{ZONE_SESSIONS}"
    # A zero-width band answers a position of a hundred rather than a null: the
    # price is at the high, which is also the low.
    assert statuses(result)[LABEL_IN_ZONE] == "Đạt"
