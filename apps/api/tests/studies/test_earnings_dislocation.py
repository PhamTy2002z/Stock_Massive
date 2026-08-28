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
"""

from __future__ import annotations

import json
import re
import socket
import uuid

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
from src.studies import registry, runner
from src.studies.contracts import StudyContext, StudyRefused
from src.studies.earnings_dislocation import (
    GATES,
    GATE_ABOVE_PRICE_CHANGE,
    GATE_BELOW_GROWTH_THRESHOLD,
    GATE_PRICE_WINDOW_UNUSABLE,
    LIQUIDITY_FLOOR_VND,
    NAME,
    QUADRANT_HIGH_GROWTH_LOW_PRICE,
    QUADRANT_LOW_GROWTH_HIGH_PRICE,
    REACTION_SESSIONS,
    TOP_N_CEILING,
    TOP_N_FLOOR,
    WINDOW_CLOSES,
    EarningsDislocationParams,
    _default_period,
    _universe,
    compute,
)
from src.studies.reads_daily import INDEX_SYMBOL

from . import earnings_fixture as fixture

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


def screen_in(session, params: dict | None = None):
    """The Study's own compute over the fixture's universe, as-of pinned.

    ``universe="declared"`` with the fixture's symbols passed in, so the golden
    numbers are a fact about this file and not about whatever the listing
    register in the test store happens to hold. The market path is proven
    separately.

    Takes the session so a test that has to break something can break it inside
    a transaction it then rolls back — the store this suite runs against is a
    real database, and a delete that escaped would take rows nobody planted.
    """
    return compute(
        StudyContext(
            params=EarningsDislocationParams.model_validate(
                {
                    "period": fixture.PERIOD,
                    "universe": "declared",
                    **(params or {}),
                }
            ),
            session=session,
            as_of=fixture.AS_OF,
            universe=fixture.SYMBOLS,
        )
    )


def screen(params: dict | None = None):
    with get_sync_db() as session:
        return screen_in(session, params)


def ladder(result) -> dict[str, tuple[int, int]]:
    """The ``filters`` frame as ``{gate code: (excluded, remaining)}``."""
    return {row[0]: (row[3], row[4]) for row in result.frames["filters"].rows}


def ranking(result) -> dict[str, tuple]:
    """The ``ranking`` frame keyed by symbol."""
    return {row[1]: row for row in result.frames["ranking"].rows}


# -- the ranking, against the construction ---------------------------------


def test_the_ranking_is_the_order_the_two_axes_together_determine(market):
    result = screen()

    assert [item["symbol"] for item in result.headline["top"]] == list(
        fixture.EXPECTED_TOP
    )
    # Neither axis alone produces that order, which is the whole point of the
    # fixture's scrambled rank pairs: growth alone would open with ZZE07 and the
    # price axis alone would put ZZE33 third.
    assert result.headline["top"][0]["symbol"] != "ZZE07"
    assert [row[1] for row in result.frames["ranking"].rows] == list(
        fixture.EXPECTED_TOP
    )


def test_the_composite_is_the_product_of_the_two_percentiles(market):
    result = screen()
    rows = ranking(result)

    for candidate in fixture.MATCHING:
        row = rows[candidate.symbol]
        # growth_rank / 33 and price_rank / 33, because every value on both axes
        # is distinct and a percentile counts ties as below.
        assert row[10] == pytest.approx(
            candidate.growth_rank / fixture.CANDIDATE_COUNT, abs=1e-4
        )
        assert row[11] == pytest.approx(
            candidate.price_rank / fixture.CANDIDATE_COUNT, abs=1e-4
        )
        assert row[2] == pytest.approx(candidate.dislocation_rank, abs=1e-4)


def test_every_figure_behind_a_ranked_row_is_the_one_the_fixture_built(market):
    rows = ranking(screen())

    for candidate in fixture.MATCHING:
        row = rows[candidate.symbol]
        assert row[3] == pytest.approx(candidate.growth_pct, abs=0.01)
        assert row[4] == pytest.approx(candidate.net_profit_vnd, abs=1)
        assert row[5] == pytest.approx(fixture.PRIOR_PROFIT_VND, abs=1)
        assert row[6] == pytest.approx(candidate.rel_return_pct, abs=0.01)
        assert row[7] == pytest.approx(candidate.return_pct, abs=0.01)
        assert row[8] == pytest.approx(fixture.INDEX_RETURN_PCT, abs=0.01)
        # Twenty of the 21 closes are 10.000đ, so the median of close × volume
        # is 10.000 × 400.000 exactly — comfortably over the three-billion floor.
        assert row[9] == pytest.approx(
            fixture.BASE_CLOSE * fixture.LIQUID_VOLUME, abs=1
        )
        assert row[9] >= LIQUIDITY_FLOOR_VND


def test_the_price_axis_is_measured_against_the_index_and_not_against_zero(market):
    """The index rose 2%, so a symbol that also rose 2% has not outperformed.

    Constructed rather than asserted in the abstract: ZZE44's own return is
    +18% and its relative return is +16%, and if the index were ignored the two
    would be the same number.
    """
    scatter = {row[0]: row for row in screen().frames["scatter"].rows}

    background = {item.symbol: item for item in fixture.BACKGROUND}
    row = scatter["ZZE44"]
    assert row[2] == pytest.approx(background["ZZE44"].rel_return_pct, abs=0.01)
    assert row[2] != pytest.approx(background["ZZE44"].return_pct, abs=0.01)


# -- the exclusions --------------------------------------------------------


def test_the_exclusions_and_the_survivors_add_up_to_the_universe(market):
    result = screen()
    counts = ladder(result)

    excluded = sum(counts[gate][0] for gate in GATES)
    assert excluded + result.headline["afterFilters"] == fixture.SCREENED
    assert result.headline["screened"] == fixture.SCREENED
    # The same arithmetic off the headline, which is the only copy the model
    # sees. Zero-count gates are absent there by design.
    assert (
        sum(result.headline["excluded"].values()) + result.headline["afterFilters"]
        == fixture.SCREENED
    )
    # And the ladder's own remaining column walks down to the survivors.
    assert counts[GATES[-1]][1] == result.headline["afterFilters"]


def test_each_gate_removes_exactly_the_symbols_planted_for_it(market):
    counts = ladder(screen())

    for gate, expected in fixture.EXCLUDED_COUNTS.items():
        assert counts[gate][0] == expected, gate
    assert counts[GATE_BELOW_GROWTH_THRESHOLD][0] == fixture.BELOW_GROWTH
    assert counts[GATE_ABOVE_PRICE_CHANGE][0] == fixture.ABOVE_PRICE_CHANGE
    # The guard that has never fired: no stored row carries a second price basis.
    assert counts[GATE_PRICE_WINDOW_UNUSABLE][0] == 0


def test_every_gate_appears_in_the_ladder_even_when_it_removed_nothing(market):
    result = screen()

    assert set(ladder(result)) == {"universe", *GATES}
    # A reader asking "why is my symbol not here" has to see the gate ran.
    assert [row[0] for row in result.frames["filters"].rows][1:] == list(GATES)


def test_a_window_that_mixes_price_bases_is_excluded_rather_than_compared(market):
    """Two bases in one window make a return between two different prices.

    Every row written today is ``adjusted_at_source``, so this is the guard for
    the day a second basis arrives — and it excludes one symbol rather than
    refusing the screen, because the other 44 are still comparable.
    """
    with get_sync_db() as session:
        session.execute(
            BarDaily.__table__.update()
            .where(BarDaily.symbol == "ZZE21")
            .where(BarDaily.trading_day == fixture.LAST_SESSION)
            .values(price_basis="raw")
        )
        result = screen_in(session)
        session.rollback()

    assert ladder(result)[GATE_PRICE_WINDOW_UNUSABLE][0] == 1
    assert "ZZE21" not in [item["symbol"] for item in result.headline["top"]]
    assert sum(result.headline["excluded"].values()) + result.headline[
        "afterFilters"
    ] == fixture.SCREENED


# -- the period ------------------------------------------------------------


def test_the_default_period_skips_a_quarter_the_market_has_half_filed(market):
    """The newest quarter is not the newest *screenable* quarter.

    Three of the fixture's symbols have filed ``2026-Q3`` and forty-two have
    filed ``2026-Q2``, which is what a market mid-reporting-season looks like. A
    default of ``max(period)`` would screen three companies and call it the
    market.
    """
    with get_sync_db() as session:
        assert _default_period(session) == fixture.PERIOD

    result = screen({"period": None})

    assert result.headline["period"] == fixture.PERIOD
    assert result.headline["priorPeriod"] == fixture.PRIOR_PERIOD


def test_a_store_with_no_statement_line_refuses_and_names_the_filings(market):
    """The one refusal that is about the store having nothing at all.

    Emptied inside a transaction and rolled back: this is the only assertion in
    the file that needs the whole table gone, and a committed truncation would
    take rows a market-wide scan collected.
    """
    with get_sync_db() as session:
        session.execute(delete(FinancialStatementLine))

        assert _default_period(session) is None
        with pytest.raises(StudyRefused) as refusal:
            screen_in(session, {"period": None})

        session.rollback()

    assert refusal.value.issue is SignalIssue.FUNDAMENTAL_NOT_STORED


def test_a_quarter_too_few_symbols_filed_refuses_rather_than_ranking_a_handful(
    market,
):
    """A percentile over three names is a rank wearing a distribution's clothes.

    The floor is the Signal Field pack's absolute one, and the refusal names
    both counts so a reader can tell a thin store from a thin market.
    """
    with pytest.raises(StudyRefused) as refusal:
        screen({"period": fixture.HALF_FILED_PERIOD})

    assert refusal.value.issue is SignalIssue.INSUFFICIENT_CROSS_SECTION
    assert str(PERCENTILE_ABSOLUTE_FLOOR) in refusal.value.detail
    assert fixture.HALF_FILED_PERIOD in refusal.value.detail


def test_a_short_index_window_refuses_and_says_so_about_the_index(market):
    """Without VN-Index there is no relative return, and an absolute one would
    answer a different question than the one asked."""
    with get_sync_db() as session:
        session.execute(
            delete(BarDaily)
            .where(BarDaily.symbol == INDEX_SYMBOL)
            .where(BarDaily.trading_day.in_(fixture.sessions()[:5]))
        )
        with pytest.raises(StudyRefused) as refusal:
            screen_in(session)

        session.rollback()

    assert refusal.value.issue is SignalIssue.INSUFFICIENT_SESSIONS
    assert INDEX_SYMBOL in refusal.value.detail
    assert str(WINDOW_CLOSES) in refusal.value.detail


# -- parameters ------------------------------------------------------------


def test_the_top_count_is_clamped_and_the_period_shape_is_refused():
    assert (
        EarningsDislocationParams.model_validate({"top_n": 500}).top_n
        == TOP_N_CEILING
    )
    assert (
        EarningsDislocationParams.model_validate({"top_n": 0}).top_n == TOP_N_FLOOR
    )
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


def test_a_wider_top_count_lengthens_the_table_and_not_the_headline(market):
    """``top_n`` is what the Signal Desk draws; the headline stays budgeted at ten."""
    result = screen({"top_n": TOP_N_CEILING, "min_profit_growth_pct": 1})

    assert len(result.frames["ranking"].rows) == TOP_N_CEILING
    assert len(result.headline["top"]) == 10


def test_the_market_universe_is_the_listing_register(market):
    with get_sync_db() as session:
        fixture.load_roster(session)
        session.flush()

        listed = _universe(session, "market", ())

        assert set(fixture.SYMBOLS) <= set(listed)
        session.rollback()


# -- the shape of the answer ----------------------------------------------


def test_the_headline_says_which_session_and_which_population(market):
    headline = screen().headline

    assert headline["asOfSession"] == fixture.LAST_SESSION.isoformat()
    assert headline["measured"] == fixture.CANDIDATE_COUNT
    assert headline["afterFilters"] == len(fixture.MATCHING)


def test_the_headline_holds_no_imperative_language(market):
    serialized = json.dumps(screen().headline, ensure_ascii=False)

    assert IMPERATIVE.search(serialized) is None, serialized


def test_the_headline_stays_inside_the_budget_the_model_pays_for(market):
    serialized = json.dumps(screen().headline, ensure_ascii=False)

    assert len(serialized) < 1_800, len(serialized)


def test_the_quadrants_describe_the_data_and_never_recommend(market):
    result = screen()
    quadrants = {row[3] for row in result.frames["scatter"].rows}

    assert QUADRANT_HIGH_GROWTH_LOW_PRICE in quadrants
    assert QUADRANT_LOW_GROWTH_HIGH_PRICE in quadrants
    for label in quadrants:
        assert IMPERATIVE.search(label) is None, label
        assert "hấp dẫn" not in label.lower()
        assert "nên" not in label and "hãy" not in label


def test_the_provenance_carries_the_limits_the_screen_cannot_design_away(market):
    provenance = screen().provenance

    assert provenance.sessions_used == WINDOW_CLOSES
    reason = provenance.reason or ""
    # The three limits the data forced: an approximated traded value, a window
    # that is not anchored to a publication date, and a roster of today.
    assert "xấp xỉ" in reason
    assert f"{REACTION_SESSIONS} phiên" in reason
    assert "roster" in reason
    assert "dislocation_rank" in reason


def test_a_thinly_filed_universe_is_reported_as_degraded(market):
    """Coverage is a fact about the store, and the strip says which one.

    The fixture's own screen is healthy — 42 of 45 symbols carry the quarter —
    and a screen over a universe the scan has barely reached is not, however
    complete the ranking looks.
    """
    assert screen().provenance.health == "normal"

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
        result = screen_in(session)
        session.rollback()

    assert result.provenance.health == "degraded"
    assert fixture.PERIOD in (result.provenance.reason or "")
    assert result.headline["measured"] == fixture.CANDIDATE_COUNT - 5


def test_the_signal_desk_draws_four_blocks_over_frames_the_study_produced(market):
    definition = registry.study(NAME)
    result = screen()
    spec = definition.view(result)

    assert [block.widget for block in spec.blocks] == [
        "stat_tiles",
        "scatter_quadrant",
        "ranked_bars",
        "data_table",
    ]
    assert all(block.frame in result.frames for block in spec.blocks)
    assert set(result.frames) == set(definition.frames)
    assert fixture.PERIOD in spec.title
    assert IMPERATIVE.search(spec.title) is None


def test_a_run_through_the_runner_persists_the_frames_and_freezes_the_as_of(market):
    """Through the runner, which resolves the universe itself.

    The market path rather than ``declared``: the runner builds the context's
    universe from the declared Universe, and this store holds no sessions for
    those thirty symbols. The register is what a market screen reads anyway.
    """
    with get_sync_db() as session:
        fixture.load_roster(session)
        stored = runner.run(
            NAME,
            {"period": fixture.PERIOD},
            session=session,
            warm=None,
        )
        row = session.get(AgentArtifact, stored.id)

        assert stored.study_name == NAME
        assert row.frames["ranking"]["rows"][0][1] == fixture.EXPECTED_TOP[0]
        assert row.provenance["asOf"] == stored.provenance.as_of.isoformat()
        # Nothing to warm: every input is a store read, which is what lets a
        # market-wide screen answer inside one round.
        assert registry.study(NAME).requires == ()
        session.rollback()


# -- the two laws ---------------------------------------------------------


def test_compute_reaches_no_provider_and_opens_no_socket(market):
    """The store is the whole input, proven by making a new socket impossible.

    The session's connection is warmed first and then held, so the database
    stays reachable while anything reaching outward — a provider client, an
    HTTP call inside a read — fails loudly instead of quietly costing a reader
    the round.
    """
    opened: list[str] = []
    real_connect = socket.socket.connect

    def refuse(self, address, *args, **kwargs):
        opened.append(str(address))
        raise AssertionError(f"compute opened a socket to {address!r}")

    with get_sync_db() as session:
        session.execute(select(BarDaily.symbol).limit(1)).all()
        socket.socket.connect = refuse
        try:
            result = screen_in(session)
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
    """
    with get_sync_db() as session:
        fixture.load_roster(session)

    tools = study_tools.StudyTools()
    answered = dict(
        tools.run_study(
            ToolContext(user_id=1), {"name": NAME, "period": fixture.PERIOD}
        )
    )

    try:
        assert "frames" not in answered
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
            session.execute(
                delete(AgentArtifact).where(
                    AgentArtifact.id == uuid.UUID(answered["artifactId"])
                )
            )
            fixture.clear_roster(session)
