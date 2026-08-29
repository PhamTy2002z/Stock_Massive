"""The condition review, against a window whose every answer is known.

The fixture (``condition_fixture.py``) plants a plateau, a decline, a ramp and a
sixty-session cluster, so each number asserted here is derivable from that
construction rather than copied from a run: the 52-week band is the close series
plus a constant wick, the twelve-month return is the last close over the first,
and the accumulation zone is the pair of histogram bins the cluster was built to
fill. A change in the arithmetic therefore shows up as a wrong answer to a
question with a right one.

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
from src.studies import registry, runner
from src.studies.contracts import StudyContext, StudyRefused
from src.studies.entry_condition_review import (
    HORIZON_CEILING,
    HORIZON_FLOOR,
    LABEL_IN_ZONE,
    LABEL_OFF_HIGH,
    LABEL_PROFIT_IMPROVED,
    LABEL_PROFIT_POSITIVE,
    LABEL_RETURN_12M,
    LABEL_RSI,
    MIN_SESSIONS,
    NAME,
    ConditionReviewParams,
    _EVIDENCE_NAMES,
    _concentration_zone,
    _rsi,
    compute,
)

from . import condition_fixture as fixture

SYMBOL = fixture.SYMBOL

#: Wilder's RSI over the fixture's last hundred closes. Not hand-derived — the
#: recursion has no closed form — so the implementation is pinned analytically by
#: ``test_the_rsi_is_wilders`` below and this is the value it produces for this
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


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


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


def review(params: dict | None = None):
    """The Study's own compute, with the as-of pinned to the fixture's close."""
    with get_sync_db() as session:
        return compute(
            StudyContext(
                params=ConditionReviewParams.model_validate(
                    {"symbol": SYMBOL, **(params or {})}
                ),
                session=session,
                as_of=fixture.AS_OF,
                # This Study reads no membership rule: the four axes it measures
                # come from the store's own rows, and a symbol the backfill has
                # not reached refuses for want of sessions rather than for want
                # of a declaration.
                universe=(),
            )
        )


def statuses(result) -> dict[str, str]:
    """The checklist as ``{condition: status}``, in the words it is sent in.

    Vietnamese rather than tokens: the frame is also what the disclosure under
    the block prints, so the status travels as the word a reader reads.
    """
    return {row[0]: row[1] for row in result.frames["conditions"].rows}


# -- the four axes, against the construction -------------------------------


def test_the_band_and_the_position_are_the_ones_the_fixture_built(window):
    position = review().headline["pricePosition"]

    assert position["last"] == fixture.LAST_CLOSE
    assert position["high52w"] == fixture.HIGH_52W
    assert position["low52w"] == fixture.LOW_52W
    # (71.350 - 67.900) / (80.100 - 67.900), to the two decimals a rate earns.
    assert position["percentile"] == pytest.approx(28.28, abs=0.01)
    assert position["offHighPct"] == pytest.approx(-10.92, abs=0.01)
    # The last close over the first of the 250 sessions, and nothing else.
    assert position["return12mPct"] == pytest.approx(-10.81, abs=0.01)
    assert position["rsi14"] == pytest.approx(FIXTURE_RSI, abs=0.01)


def test_the_accumulation_zone_is_the_pair_of_bins_the_cluster_filled(window):
    cluster = review().headline["pricePosition"]["closeCluster"]

    # The last sixty closes span 68.000–74.000, so the twenty bins are 300đ
    # wide and the cluster sits in the eleventh and twelfth of them.
    assert cluster["low"] == fixture.ZONE_LOW
    assert cluster["high"] == fixture.ZONE_HIGH
    assert cluster["sessions"] == f"{fixture.ZONE_SESSIONS_IN}/60"


def test_the_zone_is_recomputed_from_the_window_and_never_carried_over(window):
    """The same store, a wider horizon, the same sixty-session zone.

    The zone's window is fixed in the Study rather than following the parameter
    the model passed, so a reader cannot change what "vùng tích luỹ" means by
    asking for a longer line.
    """
    narrow = review().headline["pricePosition"]["closeCluster"]
    wide = review({"horizon_sessions": HORIZON_CEILING}).headline["pricePosition"][
        "closeCluster"
    ]

    assert narrow == wide


def test_the_earnings_axis_reads_the_eight_stored_quarters(window):
    result = review()
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


def test_the_checklist_statuses_are_the_ones_the_fixture_determines(window):
    result = review()

    assert statuses(result) == EXPECTED_STATUSES
    assert result.headline["conditions"]["met"] == 5
    assert result.headline["conditions"]["notMet"] == 1
    assert result.headline["conditions"]["unknown"] == 0
    # The labels the model narrates are the labels the Signal Desk draws — one text,
    # written here, never composed by a model.
    assert [item["label"] for item in result.headline["conditions"]["items"]] == [
        row[0] for row in result.frames["conditions"].rows
    ]


def test_every_condition_names_the_frame_its_number_is_in(window):
    result = review()

    for key, name in _EVIDENCE_NAMES.items():
        assert key in result.frames, key
        assert name != key

    named = {row[4] for row in result.frames["conditions"].rows}
    assert named <= set(_EVIDENCE_NAMES.values())


def test_a_row_points_at_a_picture_in_words_a_reader_can_follow(window):
    """The pointer is printed into a tooltip, so it is Vietnamese and not a key.

    The case: the browser rendered "Số liệu trong khối price_context" over a row
    about the twelve-month return.
    """
    result = review()

    for row in result.frames["conditions"].rows:
        assert "_" not in row[4], row


def test_a_symbol_with_no_quarters_still_answers_with_an_unknown_earnings_axis(
    window,
):
    with get_sync_db() as session:
        fixture.clear_quarters(session)

    result = review()

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
    assert result.provenance.health == "degraded"
    assert "quý lợi nhuận so sánh được" in (result.provenance.reason or "")


def test_fewer_than_eight_quarters_is_still_an_unknown_trend(window):
    with get_sync_db() as session:
        fixture.load_quarters(session, profits=(1_000e9, 1_100e9, 1_200e9))

    result = review()

    # Three quarters is no year-on-year pair at all, and a partial trend read as
    # a trend would be a different claim from the one the data supports.
    assert result.headline["earningsTrend"] == "unknown"
    assert statuses(result)[LABEL_PROFIT_POSITIVE] == "Đạt"
    assert statuses(result)[LABEL_PROFIT_IMPROVED] == "Chưa rõ"


def test_a_loss_making_base_quarter_gets_no_percentage(window):
    """A percentage change from a loss is a number nobody can use.

    The direction is still knowable, so the condition is answered from the sign
    of the change while the frame's percentage stays absent.
    """
    with get_sync_db() as session:
        fixture.load_quarters(
            session,
            profits=(-500e9, 100e9, 100e9, 100e9, 200e9, 200e9, 200e9, 200e9),
        )

    result = review()
    quarters = result.frames["earnings_quarters"].rows

    # Q3/2025 against a negative Q3/2024: no percentage, but it did improve.
    assert quarters[4][2] is None
    assert result.headline["earningsTrend"] == "improving"


# -- refusal, clamping, and the shape of the answer ------------------------


def test_a_window_shorter_than_a_year_refuses_and_names_the_store(window):
    with get_sync_db() as session:
        fixture.load_bars(session, keep=MIN_SESSIONS - 1)

    with pytest.raises(StudyRefused) as refusal:
        review()

    assert refusal.value.issue is SignalIssue.INSUFFICIENT_SESSIONS
    # The refusal is about the store rather than about the company, and it says
    # so with both numbers in it.
    assert f"{MIN_SESSIONS} needed" in refusal.value.detail
    assert str(MIN_SESSIONS - 1) in refusal.value.detail


def test_a_window_that_mixes_price_bases_refuses_rather_than_comparing_them(window):
    """Two bases in one window make a 52-week high nobody traded at.

    Every row written today is ``adjusted_at_source``, so this is the guard for
    the day a second basis arrives rather than a branch anybody has seen.
    """
    with get_sync_db() as session:
        session.execute(
            BarDaily.__table__.update()
            .where(BarDaily.symbol == SYMBOL)
            .where(BarDaily.trading_day == fixture.LAST_SESSION)
            .values(price_basis="raw")
        )

    with pytest.raises(StudyRefused) as refusal:
        review()

    assert refusal.value.issue is SignalIssue.MIXED_PRICE_BASIS
    assert "adjusted_at_source" in refusal.value.detail


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


def test_the_headline_says_which_session_it_is_true_of(window):
    headline = review().headline

    assert headline["asOfSession"] == fixture.LAST_SESSION.isoformat()
    assert headline["sessionsUsed"] == fixture.TOTAL_SESSIONS


def test_the_headline_holds_no_imperative_language(window):
    serialized = json.dumps(review().headline, ensure_ascii=False)

    assert IMPERATIVE.search(serialized) is None, serialized


def test_the_headline_stays_inside_the_budget_the_model_pays_for(window):
    serialized = json.dumps(review().headline, ensure_ascii=False)

    # Roughly three hundred tokens. The six condition labels are the bulk of it
    # and they are the part the model cannot be given any other way.
    assert len(serialized) < 1_800, len(serialized)


def test_the_signal_desk_draws_five_blocks_over_frames_the_study_produced(window):
    definition = registry.study(NAME)
    result = review()
    spec = definition.view(result)

    assert [block.widget for block in spec.blocks] == [
        "stat_tiles",
        "range_strip",
        "line_series",
        "bar_series",
        "condition_checklist",
    ]
    assert all(block.frame in result.frames for block in spec.blocks)
    assert set(result.frames) == set(definition.frames)
    assert SYMBOL in spec.title
    # The fixed disclosure travels with the block rather than being composed in
    # the browser, and it does not tell the reader to do anything.
    note = spec.blocks[-1].options["note"]
    assert IMPERATIVE.search(note) is None
    assert "nên" not in note and "hãy" not in note


def test_a_run_through_the_runner_persists_the_frames_and_freezes_the_as_of(window):
    with get_sync_db() as session:
        stored = runner.run(
            NAME, {"symbol": SYMBOL}, session=session, warm=None
        )
        row = session.get(AgentArtifact, stored.id)

        assert stored.study_name == NAME
        assert row.frames["conditions"]["rows"][0][0] == LABEL_OFF_HIGH
        assert row.provenance["asOf"] == stored.provenance.as_of.isoformat()
        # Nothing was warmed: this Study declares no inputs a provider has to
        # fetch, which is what lets it answer inside one round.
        assert registry.study(NAME).requires == ()
        session.rollback()


# -- the law: frames never reach a message --------------------------------


def test_the_frames_are_absent_from_the_messages_a_turn_would_send(window):
    """The whole rule, read off the transcript rather than off the payload.

    Every number checked here is one a reader sees on the Signal Desk and the model
    must not: a close from the price series, the zone bounds, a quarter's
    profit. The headline's own figures are exempt by design — they are what the
    model is given — so the assertions name cells that live only in frames.
    """
    tools = study_tools.StudyTools()
    # No Turn and no Thread: an artifact reachable by id and by nothing else,
    # which is what this assertion needs and all it needs. Ownership is proven
    # where it belongs, in ``tests/test_agent_study_tools.py``.
    answered = dict(
        tools.run_study(ToolContext(user_id=1), {"name": NAME, "symbol": SYMBOL})
    )

    try:
        assert "frames" not in answered
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
        assert "price_context" not in whole
    finally:
        with get_sync_db() as session:
            session.execute(
                delete(AgentArtifact).where(
                    AgentArtifact.id == uuid.UUID(answered["artifactId"])
                )
            )


# -- the two derivations with no closed form ------------------------------


def test_the_rsi_is_wilders():
    """Two cases with an exact answer, and the three that are undefined.

    Fourteen changes of alternating ±1 make the seed averages equal, so the
    index is exactly fifty before any smoothing happens. One more up change
    makes the averages 7,5/14 and 6,5/14, so the index is exactly 100 × 7,5/14 —
    which is the whole of Wilder's step, proven arithmetically.
    """
    alternating = [100.0]
    for step in [1, -1] * 7:
        alternating.append(alternating[-1] + step)

    assert _rsi(alternating) == 50.0
    assert _rsi([*alternating, alternating[-1] + 1]) == pytest.approx(
        100 * 7.5 / 14, abs=1e-9
    )
    # No down move at all is the top of the scale.
    assert _rsi([100.0 + step for step in range(20)]) == 100.0
    # No move at all has no relative strength to report, and fifty would be a
    # reading rather than an absence.
    assert _rsi([100.0] * 20) is None
    assert _rsi([100.0] * 14) is None


def test_a_tie_between_two_zones_goes_to_the_lower_one():
    """The only tie-break that is not a fact about iteration order.

    Two bins at each end holding the same count: the answer has to be the same
    on every run over the same data, which is what "recomputed every run" means.
    """
    closes = [0.0, 0.0, 100.0, 100.0]

    zone = _concentration_zone(closes)

    assert (zone.low, zone.high) == (0.0, 10.0)
    assert zone.sessions == 2


def test_a_window_that_never_moved_is_a_zone_of_one_price():
    zone = _concentration_zone([71_000.0] * 60)

    assert (zone.low, zone.high) == (71_000.0, 71_000.0)
    assert zone.sessions == 60
