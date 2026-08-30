"""The screener, against a synthetic market whose ranking is arithmetic.

``earnings_fixture`` plants 45 symbols with distinct ranks on both axes, so the
composite is ``growth_rank × price_rank / n²`` and the expected order is a
designed permutation rather than a snapshot of a run. Four properties are
checked here that are not about arithmetic at all, and each is a promise this
Study makes:

**The exclusions add up.** Every symbol is counted at the first gate it fails,
so the ladder in the ``filters`` frame plus the survivors equals the universe. A
screener whose counts do not add up is one nobody can check.

**The frames never reach the model.** Asserted off the messages a Turn would
send, because a clean payload and a clean transcript are two different claims.

**The headline has no imperative in it.** A regex, because the failure mode is a
later edit adding one word to the only field the model reads.

**Compute opens no socket.** The store is the whole input; a screen that reached
a provider while a reader waited would spend the round on fifteen hundred calls.

**Asserted through the engine rather than against a function.** The Study is a
plan now: its arithmetic lives in the sandbox and there is no ``compute`` to
call, so every test here runs the plan and reads the frames back off the rows it
wrote. That is also the honest subject — what a reader sees comes out of those
rows and out of nothing else. The cases that used to reach a private function
(the period rule, the roster, a window that mixes price bases) are posed by
planting the store state that provokes them and read off the frame that comes
back.

**Eight steps cost about a second and a half.** So the fourteen assertions that
are all about the *same* answer share one run through :func:`baseline`, and only
a case that needs a different store — or different parameters — pays for its
own.
"""

from __future__ import annotations

import json
import re
import socket
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import delete, select

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
from src.stocks.financial import STATEMENT_INCOME
from src.stocks.models import BarDaily, FinancialStatementLine
from src.stocks.signals.fields import PERCENTILE_ABSOLUTE_FLOOR
from src.stocks.signals.issues import SignalIssue
from src.studies import registry
from src.studies.contracts import StudyRefused
from src.studies.reads_daily import INDEX_SYMBOL
from src.studies.templates.earnings_dislocation import (
    CALENDAR_LOOKBACK_DAYS,
    GATES,
    GATE_ABOVE_PRICE_CHANGE,
    GATE_BELOW_GROWTH_THRESHOLD,
    GATE_LABELS,
    GATE_PRICE_WINDOW_UNUSABLE,
    HEADLINE_TOP,
    LIQUIDITY_FLOOR_VND,
    METHOD_NOTES,
    NAME,
    QUADRANT_HIGH_GROWTH_LOW_PRICE,
    QUADRANT_LOW_GROWTH_HIGH_PRICE,
    REACTION_SESSIONS,
    START_ROW_LABEL,
    WINDOW_CLOSES,
)
from src.studies.templates.params import (
    TOP_N_CEILING,
    TOP_N_FLOOR,
    EarningsDislocationParams,
)

from . import earnings_fixture as fixture
from .template_run import run_template

#: The vocabulary a screen may never speak, in the field the model reads.
#: Case-insensitive, because the failure is the word and not its casing.
IMPERATIVE = re.compile(r"nên mua|mua ngay|bán ngay|WAIT|BUY|SELL", re.IGNORECASE)


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture
def market():
    """The planted market, committed, then removed again."""
    with get_sync_db() as session:
        fixture.load(session)

    yield

    with get_sync_db() as session:
        fixture.clear(session)


def screen(monkeypatch, params: dict | None = None):
    """The Study's own plan over the fixture's universe, as-of pinned.

    ``universe="declared"`` with the fixture's symbols passed in, so the golden
    numbers are a fact about this file and not about whatever the listing
    register in the test store happens to hold. The market path is proven
    separately.

    The as-of is pinned for the reason the hand-written Study was handed one:
    the fixture's sessions are fixed calendar days, and a run left on the wall
    clock would fall outside the template's own ``CALENDAR_LOOKBACK_DAYS`` a few
    weeks from now — every number here would then start refusing for a reason
    that is about the date the suite ran.
    """
    return run_template(
        NAME,
        {"period": fixture.PERIOD, "universe": "declared", **(params or {})},
        universe=fixture.SYMBOLS,
        monkeypatch=monkeypatch,
        as_of=fixture.AS_OF,
    )


@pytest.fixture(scope="module")
def baseline():
    """One run of the default screen, shared by every assertion about it.

    The rows are planted, read, and taken away again inside the fixture: what
    the tests below hold is the answer, and none of them needs the store that
    produced it still standing.
    """
    with get_sync_db() as session:
        fixture.load(session)
    try:
        with pytest.MonkeyPatch.context() as patch:
            return screen(patch)
    finally:
        with get_sync_db() as session:
            fixture.clear(session)


def ladder(result) -> dict[str, tuple[int, int]]:
    """The ``filters`` frame as ``{gate code: (excluded, remaining)}``.

    Keyed back to the codes here rather than carried in the frame. That table is
    printed to a reader by the appendix under the board, so every cell of it is
    the gate's Vietnamese sentence; a test that wants the gate's identity looks
    the sentence up.
    """
    codes = {label: code for code, label in GATE_LABELS.items()}
    return {
        codes.get(row[0], row[0]): (row[2], row[3])
        for row in result.frames["filters"].rows
    }


def ranking(result) -> dict[str, dict]:
    """The ``ranking`` frame keyed by symbol, each row keyed by column name."""
    frame = result.frames["ranking"]
    return {
        row[frame.columns.index("symbol")]: dict(zip(frame.columns, row))
        for row in frame.rows
    }


def scatter(result) -> dict[str, dict]:
    """The ``scatter`` frame keyed by symbol."""
    frame = result.frames["scatter"]
    return {
        row[frame.columns.index("symbol")]: dict(zip(frame.columns, row))
        for row in frame.rows
    }


# -- the ranking, against the construction ---------------------------------


def test_the_ranking_is_the_order_the_two_axes_together_determine(baseline):
    assert [item["symbol"] for item in baseline.headline["top"]] == list(
        fixture.EXPECTED_TOP
    )
    # Neither axis alone produces that order, which is the whole point of the
    # fixture's scrambled rank pairs: growth alone would open with ZZE07 and the
    # price axis alone would put ZZE33 third.
    assert baseline.headline["top"][0]["symbol"] != "ZZE07"
    assert baseline.frames["ranking"].column("symbol") == list(fixture.EXPECTED_TOP)
    # And the table is ranked in the order it is sorted in, one to eight.
    assert baseline.frames["ranking"].column("rank") == list(
        range(1, len(fixture.EXPECTED_TOP) + 1)
    )


def test_the_composite_is_the_product_of_the_two_percentiles(baseline):
    rows = ranking(baseline)

    for candidate in fixture.MATCHING:
        row = rows[candidate.symbol]
        # growth_rank / 33 and price_rank / 33, because every value on both axes
        # is distinct and a percentile counts ties as below.
        assert row["growth_percentile"] == pytest.approx(
            candidate.growth_rank / fixture.CANDIDATE_COUNT, abs=1e-4
        )
        assert row["rel_return_percentile"] == pytest.approx(
            candidate.price_rank / fixture.CANDIDATE_COUNT, abs=1e-4
        )
        assert row["dislocation_rank"] == pytest.approx(
            candidate.dislocation_rank, abs=1e-4
        )


def test_every_figure_behind_a_ranked_row_is_the_one_the_fixture_built(baseline):
    rows = ranking(baseline)

    for candidate in fixture.MATCHING:
        row = rows[candidate.symbol]
        assert row["growth_pct"] == pytest.approx(candidate.growth_pct, abs=0.01)
        assert row["net_profit_vnd"] == pytest.approx(candidate.net_profit_vnd, abs=1)
        assert row["prior_net_profit_vnd"] == pytest.approx(
            fixture.PRIOR_PROFIT_VND, abs=1
        )
        assert row["rel_return_pct"] == pytest.approx(
            candidate.rel_return_pct, abs=0.01
        )
        assert row["return_pct"] == pytest.approx(candidate.return_pct, abs=0.01)
        assert row["index_return_pct"] == pytest.approx(
            fixture.INDEX_RETURN_PCT, abs=0.01
        )
        # Twenty of the 21 closes are 10.000đ, so the median of close × volume
        # is 10.000 × 400.000 exactly — comfortably over the three-billion floor.
        assert row["adtv_vnd"] == pytest.approx(
            fixture.BASE_CLOSE * fixture.LIQUID_VOLUME, abs=1
        )
        assert row["adtv_vnd"] >= LIQUIDITY_FLOOR_VND


def test_the_price_axis_is_measured_against_the_index_and_not_against_zero(baseline):
    """The index rose 2%, so a symbol that also rose 2% has not outperformed.

    Constructed rather than asserted in the abstract: ZZE44's own return is
    +18% and its relative return is +16%, and if the index were ignored the two
    would be the same number.
    """
    background = {item.symbol: item for item in fixture.BACKGROUND}
    row = scatter(baseline)["ZZE44"]

    assert row["rel_return_pct"] == pytest.approx(
        background["ZZE44"].rel_return_pct, abs=0.01
    )
    assert row["rel_return_pct"] != pytest.approx(
        background["ZZE44"].return_pct, abs=0.01
    )


# -- the exclusions --------------------------------------------------------


def test_the_exclusions_and_the_survivors_add_up_to_the_universe(baseline):
    counts = ladder(baseline)

    excluded = sum(counts[gate][0] for gate in GATES)
    assert excluded + baseline.headline["afterFilters"] == fixture.SCREENED
    assert baseline.headline["screened"] == fixture.SCREENED
    # The same arithmetic off the headline, which is the only copy the model
    # sees. Zero-count gates are absent there by design.
    assert (
        sum(baseline.headline["excluded"].values())
        + baseline.headline["afterFilters"]
        == fixture.SCREENED
    )
    # And the ladder's own remaining column walks down to the survivors.
    assert counts[GATES[-1]][1] == baseline.headline["afterFilters"]


def test_each_gate_removes_exactly_the_symbols_planted_for_it(baseline):
    counts = ladder(baseline)

    for gate, expected in fixture.EXCLUDED_COUNTS.items():
        assert counts[gate][0] == expected, gate
    assert counts[GATE_BELOW_GROWTH_THRESHOLD][0] == fixture.BELOW_GROWTH
    assert counts[GATE_ABOVE_PRICE_CHANGE][0] == fixture.ABOVE_PRICE_CHANGE
    # The guard that has never fired: no stored row carries a second price basis.
    assert counts[GATE_PRICE_WINDOW_UNUSABLE][0] == 0


def test_every_gate_appears_in_the_ladder_even_when_it_removed_nothing(baseline):
    assert set(ladder(baseline)) == {START_ROW_LABEL, *GATES}
    # A reader asking "why is my symbol not here" has to see the gate ran.
    assert baseline.frames["filters"].column("gate")[1:] == [
        GATE_LABELS[gate] for gate in GATES
    ]


def test_a_window_that_mixes_price_bases_is_excluded_rather_than_compared(
    market, monkeypatch
):
    """Two bases in one window make a return between two different prices.

    Every row written today is ``adjusted_at_source``, so this is the guard for
    the day a second basis arrives — and it excludes one symbol rather than
    refusing the screen, because the other 44 are still comparable.

    Posed by planting the second basis rather than by calling the gate, which is
    the only road left now that the gates are one ``np.select`` inside the
    sandbox. The row is the fixture's own and the fixture takes it away again.
    """
    with get_sync_db() as session:
        session.execute(
            BarDaily.__table__.update()
            .where(BarDaily.symbol == "ZZE21")
            .where(BarDaily.trading_day == fixture.LAST_SESSION)
            .values(price_basis="raw")
        )

    result = screen(monkeypatch)

    assert ladder(result)[GATE_PRICE_WINDOW_UNUSABLE][0] == 1
    assert "ZZE21" not in [item["symbol"] for item in result.headline["top"]]
    assert (
        sum(result.headline["excluded"].values()) + result.headline["afterFilters"]
        == fixture.SCREENED
    )


# -- the period ------------------------------------------------------------


def test_the_default_period_skips_a_quarter_the_market_has_half_filed(
    market, monkeypatch
):
    """The newest quarter is not the newest *screenable* quarter.

    Three of the fixture's symbols have filed ``2026-Q3`` and forty-two have
    filed ``2026-Q2``, which is what a market mid-reporting-season looks like. A
    default of ``max(period)`` would screen three companies and call it the
    market — so the quarter the run reports is the whole assertion.
    """
    result = screen(monkeypatch, {"period": None})

    assert result.headline["period"] == fixture.PERIOD
    assert result.headline["priorPeriod"] == fixture.PRIOR_PERIOD
    # The quarter a reader is shown comes off the same cell.
    assert result.kpi("Kỳ báo cáo").value.raw == "quý II/2026"


def test_a_store_with_no_statement_line_refuses_and_names_the_filings(
    market, monkeypatch
):
    """The one refusal that is about the store having nothing at all.

    Scoped to the symbols this fixture planted rather than truncating the table:
    while the fixture is loaded those rows *are* the table, so the store the run
    meets is the empty one the case needs, and a committed truncation would take
    rows a market-wide scan collected. The refusal is what the period rule
    returning nothing looks like from outside — it is raised by the first step,
    before anything is read.
    """
    with get_sync_db() as session:
        session.execute(
            delete(FinancialStatementLine).where(
                FinancialStatementLine.symbol.in_(fixture.SYMBOLS)
            )
        )

    with pytest.raises(StudyRefused) as refusal:
        screen(monkeypatch, {"period": None})

    assert refusal.value.issue is SignalIssue.FUNDAMENTAL_NOT_STORED


def test_a_quarter_too_few_symbols_filed_refuses_rather_than_ranking_a_handful(
    market, monkeypatch
):
    """A percentile over three names is a rank wearing a distribution's clothes.

    The floor is the Signal Field pack's absolute one, and the refusal names
    both counts so a reader can tell a thin store from a thin market.
    """
    with pytest.raises(StudyRefused) as refusal:
        screen(monkeypatch, {"period": fixture.HALF_FILED_PERIOD})

    assert refusal.value.issue is SignalIssue.INSUFFICIENT_CROSS_SECTION
    assert str(PERCENTILE_ABSOLUTE_FLOOR) in refusal.value.detail
    assert f"of {fixture.SCREENED} symbols" in refusal.value.detail
    # And which quarter was short, because "45 symbols do not carry a filing" is
    # a sentence a reader will attach to whichever quarter they had in mind.
    assert fixture.HALF_FILED_PERIOD in refusal.value.detail


@pytest.fixture
def a_short_index_window():
    """The market's own window cut down to fewer closes than the screen needs.

    Cut across the whole span the template reads rather than across the
    fixture's own sessions: the read reaches back 45 calendar days, and a store
    another suite left VN-Index rows in would fill the gap straight back up —
    which is a screen that answers when the case says it must not. Everything
    removed is read first and written back afterwards, so posing the case costs
    no row this file did not plant.
    """
    table = BarDaily.__table__
    floor = fixture.AS_OF.date() - timedelta(days=CALENDAR_LOOKBACK_DAYS)
    condition = (
        (table.c.symbol == INDEX_SYMBOL)
        & (table.c.trading_day >= floor)
        & (table.c.trading_day < fixture.sessions()[5])
    )
    with get_sync_db() as session:
        removed = [
            dict(row) for row in session.execute(select(table).where(condition)).mappings()
        ]
        session.execute(delete(table).where(condition))

    yield

    with get_sync_db() as session:
        if removed:
            session.execute(table.insert(), removed)


def test_a_short_index_window_refuses_and_says_so_about_the_index(
    market, a_short_index_window, monkeypatch
):
    """Without VN-Index there is no relative return, and an absolute one would
    answer a different question than the one asked."""
    with pytest.raises(StudyRefused) as refusal:
        screen(monkeypatch)

    assert refusal.value.issue is SignalIssue.INSUFFICIENT_SESSIONS
    assert INDEX_SYMBOL in refusal.value.detail
    assert str(WINDOW_CLOSES) in refusal.value.detail


# -- parameters ------------------------------------------------------------


def test_the_top_count_is_clamped_and_the_period_shape_is_refused():
    assert (
        EarningsDislocationParams.model_validate({"top_n": 500}).top_n == TOP_N_CEILING
    )
    assert EarningsDislocationParams.model_validate({"top_n": 0}).top_n == TOP_N_FLOOR
    assert (
        EarningsDislocationParams.model_validate({"period": " 2026-q2 "}).period
        == "2026-Q2"
    )
    with pytest.raises(ValueError):
        EarningsDislocationParams.model_validate({"period": "quý 2"})


def test_the_defaults_are_the_screen_the_plan_asked_for():
    params = EarningsDislocationParams()

    assert params.min_profit_growth_pct == 20
    assert params.max_price_change_pct == 5
    assert params.top_n == 10
    assert params.universe == "market"
    assert params.period is None


def test_a_wider_top_count_lengthens_the_table_and_not_the_headline(
    market, monkeypatch
):
    """``top_n`` is what the Signal Desk draws; the headline stays budgeted at ten."""
    result = screen(
        monkeypatch, {"top_n": TOP_N_CEILING, "min_profit_growth_pct": 1}
    )

    assert len(result.frames["ranking"].rows) == TOP_N_CEILING
    assert len(result.headline["top"]) == HEADLINE_TOP


def test_the_market_universe_is_the_listing_register(market, monkeypatch):
    """The scope nobody passes a list for: the register decides who is screened.

    Read off the funnel rather than off the resolver, which is the road a
    template's universe travels now — the first row of the ladder is everything
    the screen started from, and under ``universe="market"`` that is the roster.
    """
    with get_sync_db() as session:
        fixture.load_roster(session)

    result = screen(monkeypatch, {"universe": "market"})

    assert ladder(result)[START_ROW_LABEL][1] == fixture.SCREENED
    assert result.headline["screened"] == fixture.SCREENED
    # And the roster path is the same screen: the same eight names come back.
    assert [item["symbol"] for item in result.headline["top"]] == list(
        fixture.EXPECTED_TOP
    )


# -- the shape of the answer ----------------------------------------------


def test_the_headline_says_which_session_and_which_population(baseline):
    headline = baseline.headline

    assert headline["asOfSession"] == fixture.LAST_SESSION.isoformat()
    assert headline["measured"] == fixture.CANDIDATE_COUNT
    assert headline["afterFilters"] == len(fixture.MATCHING)


def test_the_headline_holds_no_imperative_language(baseline):
    serialized = json.dumps(baseline.headline, ensure_ascii=False)

    assert IMPERATIVE.search(serialized) is None, serialized


def test_the_headline_stays_inside_the_budget_the_model_pays_for(baseline):
    serialized = json.dumps(baseline.headline, ensure_ascii=False)

    assert len(serialized) < 1_800, len(serialized)


def test_the_quadrants_describe_the_data_and_never_recommend(baseline):
    quadrants = set(baseline.frames["scatter"].column("quadrant"))

    assert QUADRANT_HIGH_GROWTH_LOW_PRICE in quadrants
    assert QUADRANT_LOW_GROWTH_HIGH_PRICE in quadrants
    for label in quadrants:
        assert IMPERATIVE.search(label) is None, label
        assert "hấp dẫn" not in label.lower()
        assert "nên" not in label and "hãy" not in label
    # The four regions are drawn in four interchangeable hues, never a ramp: a
    # scale would rank them on the reader's behalf.
    roles = set(baseline.frames["scatter"].point_roles)
    assert roles and all(role.startswith("category:") for role in roles)


def test_the_provenance_carries_the_limits_the_screen_cannot_design_away(baseline):
    provenance = baseline.artifact.provenance

    # The window every return is measured over, and not the row count of any
    # frame derived from it: the merge takes sessions from the steps that read
    # the store, so a 45-row calculation cannot report itself as 45 sessions.
    assert provenance.sessions_used == WINDOW_CLOSES
    notes = " ".join(provenance.method_notes)
    # The three limits the data forced: an approximated traded value, a window
    # that is not anchored to a publication date, and a listing as it stands now.
    assert "ước bằng trung vị" in notes
    assert f"{REACTION_SESSIONS} phiên" in notes
    assert "niêm yết hiện hành" in notes
    assert "Thứ hạng lệch pha" in notes


def test_the_method_belongs_beside_the_reason_and_never_inside_it(baseline):
    """A healthy screen says nothing about health, and still states its limits.

    The method used to be joined onto the reason, so a screen with nothing wrong
    printed five clauses of methodology as its health line — and the reader who
    only wanted to know whether the numbers were thin read all of them.

    Five clauses is now five plus whatever the engine adds for a plan of
    calculations, capped where the strip stops being a strip. What this holds is
    the ordering the cap depends on: the Study's own sentences lead, so what a
    cap drops is the engine's line about the run and never a limit of the
    screen.
    """
    provenance = baseline.artifact.provenance

    assert provenance.health == "normal"
    assert provenance.reason is None
    assert provenance.method_notes[: len(METHOD_NOTES)] == METHOD_NOTES
    # Nothing about the plan's own machinery reaches the strip: the note naming
    # the calculation's digest is exactly what the cap is there to drop.
    assert not any("phép tính mã" in note for note in provenance.method_notes)


def test_no_note_a_reader_meets_is_written_in_this_systems_own_words(baseline):
    """Every sentence on the strip is about the companies, not about the code.

    The case that named this: the strip printed the ranking formula's own
    identifier in the middle of a Vietnamese sentence.
    """
    provenance = baseline.artifact.provenance
    forbidden = ("dislocation_rank", "adjusted_at_source", "store", "roster")

    for sentence in (*provenance.method_notes, provenance.reason or ""):
        for word in forbidden:
            assert word not in sentence


def test_a_thinly_filed_universe_is_reported_as_degraded(market, monkeypatch):
    """Coverage is a fact about the store, and the strip says which one.

    The fixture's own screen is healthy — 42 of 45 symbols carry the quarter —
    and a screen over a universe the scan has barely reached is not, however
    complete the ranking looks.
    """
    with get_sync_db() as session:
        # Five filings away, which puts coverage at 37 of 45 — under the floor,
        # and still far enough above the percentile's minimum sample that the
        # screen answers rather than refusing.
        session.execute(
            delete(FinancialStatementLine).where(
                FinancialStatementLine.symbol.in_(
                    [item.symbol for item in fixture.BACKGROUND[:5]]
                ),
                FinancialStatementLine.period == fixture.PERIOD,
                FinancialStatementLine.statement == STATEMENT_INCOME,
            )
        )

    result = screen(monkeypatch)

    assert result.artifact.provenance.health == "degraded"
    reason = result.artifact.provenance.reason or ""
    # The quarter as a reader writes it, not the code the filings are keyed by.
    assert "quý II/2026" in reason
    assert fixture.PERIOD not in reason
    assert result.headline["measured"] == fixture.CANDIDATE_COUNT - 5


def test_the_board_draws_the_ranking_the_scatter_and_the_ladder(baseline):
    """The names, the cloud they stand out of, and the appendix that explains it.

    The frames a board carries are filed under ``f0``, ``f1``… by the composer,
    so a block is identified by the columns it draws — those are the plan's own
    vocabulary and they name exactly one frame apiece. The ladder is the block
    that answers "why is my symbol not here", which is the first question any
    screen gets, and it sits in the appendix because a plain table is the
    appendix's job.
    """
    board = baseline.board
    definition = registry.study(NAME)
    drawn = [
        (section.heading, block)
        for section in board.sections
        for block in section.blocks
        if hasattr(block, "widget")
    ]

    assert board.archetype == definition.archetype == "screen"
    assert IMPERATIVE.search(board.title) is None
    assert [(heading, block.widget) for heading, block in drawn] == [
        ("Xếp hạng", "ranked_bars"),
        ("Toàn bộ mã đo được", "scatter_quadrant"),
    ]
    # The ranking is drawn on its composite, the scatter on its two axes.
    assert drawn[0][1].options["value"] == "dislocation_rank"
    assert {drawn[1][1].options["x"], drawn[1][1].options["y"]} == {
        "growth_pct",
        "rel_return_pct",
    }
    # The ladder, plainly, under everything else — and it is the same frame the
    # funnel figures on the strip were resolved out of.
    assert board.appendix is not None
    assert board.appendix.widget == "data_table"
    assert board.appendix.frame == baseline.kpi("Số mã quét").value.frame
    # No frame is drawn twice.
    frames_drawn = [block.frame for _, block in drawn] + [board.appendix.frame]
    assert len(set(frames_drawn)) == len(frames_drawn)


def test_the_strip_carries_the_four_figures_the_dropped_tiles_frame_did(baseline):
    """The v1 ``stat_tiles`` block's four numbers, now four resolved cells.

    The quarter, the symbols screened, the symbols measured and the symbols
    matched — each one a reference into a frame a picture also draws, which is
    the rule the KPI strip replaced the tiles frame under. The quarter used to
    be read off the panel's title; it is a cell now, so it is checked as one.
    """
    period = baseline.frames["period"]
    filters = baseline.frames["filters"]
    remaining = filters.columns.index("remaining")

    assert baseline.kpi("Kỳ báo cáo").value.raw == period.column("words")[0]
    assert baseline.kpi("Số mã quét").value.raw == fixture.SCREENED
    assert baseline.kpi("Đo được cả hai trục").value.raw == fixture.CANDIDATE_COUNT
    assert baseline.kpi("Qua cả hai ngưỡng").value.raw == len(fixture.MATCHING)
    assert baseline.kpi("Qua cả hai ngưỡng").role == "focus"
    # Every figure is a cell of a frame this run produced, at the row it says.
    for label in ("Số mã quét", "Đo được cả hai trục", "Qua cả hai ngưỡng"):
        cell = baseline.kpi(label).value
        assert cell.column == "remaining"
        assert filters.rows[cell.row][remaining] == cell.raw
    assert all(cell.value.frame.startswith("f") for cell in baseline.board.kpis)


def test_a_run_persists_a_frame_per_step_and_never_the_headline(baseline):
    assert baseline.artifact.study_name == NAME
    assert set(baseline.frames) == set(registry.study(NAME).step_names)
    # Every step is addressable, which is what lets a model re-mix one.
    assert set(baseline.artifact.steps) == set(baseline.frames)
    assert all("#" in reference for reference in baseline.artifact.steps.values())
    # Nothing to warm: every input is a store read, which is what lets a
    # market-wide screen answer inside one round.
    assert registry.study(NAME).requires == ()


# -- the two laws ---------------------------------------------------------


def test_the_plan_reaches_no_provider_and_opens_no_socket(market, monkeypatch):
    """The store is the whole input, proven by making a new socket impossible.

    The engine's connection is warmed first and then held in the pool, so the
    database stays reachable while anything reaching outward — a provider
    client, an HTTP call inside a read — fails loudly instead of quietly costing
    a reader the round.
    """
    opened: list[str] = []
    real_connect = socket.socket.connect

    def refuse(self, address, *args, **kwargs):
        opened.append(str(address))
        raise AssertionError(f"the plan opened a socket to {address!r}")

    with get_sync_db() as session:
        session.execute(select(BarDaily.symbol).limit(1)).all()

    socket.socket.connect = refuse
    try:
        result = screen(monkeypatch)
    finally:
        socket.socket.connect = real_connect

    assert opened == []
    assert result.headline["afterFilters"] == len(fixture.MATCHING)


def test_the_frames_are_absent_from_the_messages_a_turn_would_send(market):
    """The whole rule, read off the transcript rather than off the payload.

    The cells probed here live only in the frames: a background symbol's ticker,
    which is on the scatter and never in the headline, and a gate label from the
    ladder. The top ten's own figures are exempt by design — they are what the
    model is given.

    ``frames`` on the payload is now a map of step *references* rather than the
    absence it used to be, and that is the point of a plan whose steps are
    artifacts: a model that ran a template can draw one of its frames without
    ever being handed a row of it. So the map is checked for being addresses and
    nothing else.
    """
    with get_sync_db() as session:
        fixture.load_roster(session)
        before = {row for row in session.execute(select(AgentArtifact.id)).scalars()}

    tools = study_tools.StudyTools()
    answered = dict(
        tools.run_study(
            ToolContext(user_id=1), {"name": NAME, "period": fixture.PERIOD}
        )
    )

    try:
        assert set(answered["frames"]) == set(registry.study(NAME).step_names)
        assert all(
            re.fullmatch(r"[0-9a-f-]{36}#\w+", reference)
            for reference in answered["frames"].values()
        )
        call = TurnToolCall(
            id="call-1",
            name="run_study",
            arguments={"name": NAME, "period": fixture.PERIOD},
            status=ToolCallStatus.OK,
            result_text=json.dumps(answered, ensure_ascii=False),
            summary="Lợi nhuận tăng, giá chưa theo",
        )
        context = build_messages(
            Transcript(
                system_prompt="hệ thống",
                turns=(
                    TranscriptTurn(
                        user_text="Mã nào lợi nhuận tăng mà giá chưa theo?",
                        tool_calls=(call,),
                    ),
                ),
            ),
            ContextBudget(),
        )
        whole = "\n".join(str(message.content or "") for message in context.messages)

        assert answered["artifactId"] in whole
        # The market path ran: the register is what it screened.
        assert answered["headline"]["screened"] >= fixture.SCREENED
        assert answered["headline"]["top"][0]["symbol"] == fixture.EXPECTED_TOP[0]
        # Cells that exist only in a frame.
        for cell in (
            "ZZE44",
            "Thanh khoản dưới sàn",
            "growth_percentile",
            "quadrant",
        ):
            assert cell not in whole, cell
    finally:
        with get_sync_db() as session:
            # Every row the run wrote: one composition and one per step. The
            # runner commits them, so a test that started them owns taking them
            # away — and by difference rather than by the composition's id,
            # because eight of the nine are addressable only through it.
            current = set(session.execute(select(AgentArtifact.id)).scalars())
            fresh = current - before
            assert uuid.UUID(answered["artifactId"]) in fresh
            session.execute(delete(AgentArtifact).where(AgentArtifact.id.in_(fresh)))
            fixture.clear_roster(session)
