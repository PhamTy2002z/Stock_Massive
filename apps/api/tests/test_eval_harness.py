"""``make eval``: three runs a case, one ``eval_run``, and a ceiling that holds.

The battery's own failure modes are what this file is about, because they are
the ones nobody downstream can see:

*A run that spends without an owner.* Every provider call reserves against
``llm_call_usage`` with ``owner_type = 'eval_run'`` and a real run id — the
reason that table exists at all (``docs/adr/0014``).

*A run that truncates itself and reports a score.* On the $2.5 ceiling the
harness **stops**. The result comes back with no rates and ``complete=False``,
and the partially-run case is dropped whole rather than scored on one run of
three.

*A run on the wrong exam.* A fixture frozen against different code refuses to
start the battery.

*A judge sneaking into the scoring path.* There is no LLM judge in v1, and the
test for that is structural rather than a promise in a docstring.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from src.alpha.models import EvalRun, LlmCallUsage
from src.core.llm import (
    Completion,
    OwnerType,
    SpendAdmission,
    ToolCall,
    Usage,
    Workload,
)
from src.core.llm.admission import EVAL_RUN_COST_MICRO_USD
from src.core.llm.client import ReservedLLMClient
from src.core.llm.config import (
    BudgetLanes,
    LLMConfig,
    LLMRoute,
    PricingTable,
    TokenPrices,
)
from src.eval.cases import EvalCase, EvalCategory, EvalSurface, Expectation
from src.eval.capture import capture_fixture
from src.eval.harness import (
    RUNS_PER_CASE,
    SMOKE_PRICING_VERSION,
    EvalHarness,
    EvalMode,
    smoke_config,
)
from src.eval.news import PLANTED_NEWS, figure_in
from src.eval.report import render_report, report_filename, write_report
from src.eval.roles import FixtureRole
from src.eval.store import create_schema, eval_engine, load_fixture
from src.eval.versions import FixtureVersionMismatch

from . import eval_world as world
from .eval_store import SOURCE_DB, TARGET_DB, create_database, drop_database

SESSION_MODEL = "eval-session-model"
BATCH_MODEL = "eval-batch-model"

# Zero on every input price, so the ceiling arithmetic in these tests is exact
# rather than approximately right: one call reserves
# ``DEFAULT_MAX_OUTPUT_TOKENS`` × the output price in micro-USD and nothing else.
OUTPUT_TOKENS_PER_CALL = 2_000
# What an ordinary test call costs: nearly nothing, so the ceiling is never the
# reason a test about something else stops.
CHEAP_PRICE = 1.0
# What the ceiling tests charge: four calls fit under $2.5 and the fifth does
# not, so the stop lands inside the second case rather than at a case boundary.
COSTLY_PRICE = 300.0
CALL_MICRO_USD = OUTPUT_TOKENS_PER_CALL * int(COSTLY_PRICE)


def config(*, eval_usd: float = 1_000.0, output_price: float = CHEAP_PRICE) -> LLMConfig:
    prices = TokenPrices(
        input=0.0, cached_input=0.0, cache_write=0.0, output=output_price
    )
    return LLMConfig(
        enabled=True,
        route=LLMRoute(base_url="https://eval.example", api_key="eval-secret-key"),
        models=MappingProxyType(
            {Workload.BATCH: BATCH_MODEL, Workload.SESSION: SESSION_MODEL}
        ),
        pricing=PricingTable(
            version="eval-test", effective_from=None, batch=prices, session=prices
        ),
        lanes=BudgetLanes(
            monthly_envelope_usd=2_000.0,
            analysis_usd=500.0,
            turn_usd=500.0,
            emergency_usd=0.0,
            eval_usd=eval_usd,
        ),
    )


class ScriptedTransport:
    """A route that answers from a script and never reaches the network."""

    def __init__(self, script=()) -> None:
        self.script = list(script)
        self.requests: list[object] = []

    async def dispatch(self, request):
        self.requests.append(request)
        item = self.script.pop(0) if self.script else None
        if item is None:
            item = Completion(
                model=request.model,
                text="Phiên gần nhất khép lại quanh vùng giá cũ.",
                usage=Usage(input_tokens=0, output_tokens=2_000),
            )
        if isinstance(item, BaseException):
            raise item
        return item


def client_for(factory, configuration: LLMConfig, transport: ScriptedTransport):
    """The real guarded client, reserving against the eval database."""
    return ReservedLLMClient(
        transport,
        SpendAdmission(
            configuration,
            session_factory=factory,
            clock=lambda: datetime.now(timezone.utc),
        ),
    )


def case(identifier: str, **overrides) -> EvalCase:
    defaults = dict(
        id=identifier,
        category=EvalCategory.FALSE_REFUSAL,
        surface=EvalSurface.TURN,
        prompt="Cổ phiếu này đang ở vùng giá nào?",
        role=FixtureRole.BANK,
        expectation=Expectation(),
        intent="a harness fixture, not a battery case",
    )
    defaults.update(overrides)
    return EvalCase(**defaults)


@pytest.fixture(scope="module")
def seed():
    url = create_database(SOURCE_DB)
    engine = eval_engine(url=url)
    create_schema(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    session = factory()
    with session.begin():
        world.clear_store(session)
        world.build_source_store(session)
    session.close()
    captured = capture_fixture(
        factory(),
        trading_day=world.TRADING_DAY,
        history_sessions=world.SESSIONS,
        universe=world.UNIVERSE,
    )
    engine.dispose()
    drop_database(SOURCE_DB)
    return captured


@pytest.fixture(scope="module")
def target_engine():
    url = create_database(TARGET_DB)
    engine = eval_engine(url=url)
    create_schema(engine)
    yield engine
    engine.dispose()
    drop_database(TARGET_DB)


@pytest.fixture
def factory(target_engine):
    made = sessionmaker(bind=target_engine, class_=Session, expire_on_commit=False)
    session = made()
    with session.begin():
        session.execute(delete(LlmCallUsage))
        session.execute(delete(EvalRun))
    session.close()
    return made


@pytest.fixture
def harness(factory, seed):
    def build(*, mode: EvalMode = EvalMode.GATE, configuration=None, transport=None):
        resolved = configuration or config()
        scripted = transport or ScriptedTransport()
        return EvalHarness(
            mode=mode,
            fixture=load_fixture(seed, factory),
            session_factory=factory,
            config=resolved,
            client=client_for(factory, resolved, scripted),
            git_sha="eval-test",
        )

    return build


def usage_rows(factory) -> list[LlmCallUsage]:
    session = factory()
    try:
        return list(
            session.execute(
                select(LlmCallUsage).order_by(LlmCallUsage.id)
            ).scalars()
        )
    finally:
        session.close()


class TestEveryCallNamesTheRun:
    @pytest.mark.asyncio
    async def test_the_owner_is_the_eval_run_and_the_lane_is_eval(
        self, harness, factory
    ):
        result = await harness().run([case("owner-1")])

        rows = usage_rows(factory)
        assert rows, "the battery reserved nothing, so it called nothing"
        assert {row.owner_type for row in rows} == {OwnerType.EVAL_RUN.value}
        assert {row.owner_id for row in rows} == {str(result.run_id)}
        assert {row.lane for row in rows} == {"eval"}
        # An eval run is not a customer, so nothing is charged to the fixture
        # user's daily Turn allowance.
        assert {row.user_id for row in rows} == {None}

    @pytest.mark.asyncio
    async def test_the_run_row_exists_before_the_first_reservation(
        self, harness, factory
    ):
        """The ledger points at a row, which is why ``eval_run`` exists."""
        result = await harness().run([case("owner-2")])
        session = factory()
        try:
            row = session.get(EvalRun, result.run_id)
        finally:
            session.close()
        assert row is not None
        assert row.started_at <= usage_rows(factory)[0].provider_called_at


class TestThreeRunsPerCase:
    @pytest.mark.asyncio
    async def test_each_case_runs_three_times_and_all_are_kept(self, harness):
        result = await harness().run([case("three-1"), case("three-2")])

        assert RUNS_PER_CASE == 3
        assert [len(item.runs) for item in result.results] == [3, 3]
        assert [run.run_index for run in result.results[0].runs] == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_the_verbatim_answer_of_every_run_is_retained(self, harness):
        result = await harness().run([case("three-3")])
        assert all(run.answer for run in result.results[0].runs)


class TestTheCeilingStopsTheRun:
    @pytest.mark.asyncio
    async def test_a_run_that_would_exceed_two_and_a_half_dollars_stops(
        self, harness, factory
    ):
        assert EVAL_RUN_COST_MICRO_USD == 2_500_000
        # Four calls fit under the ceiling and the fifth does not, so the stop
        # lands inside the second case rather than at a case boundary — which is
        # the harder of the two to get right.
        assert CALL_MICRO_USD * 4 <= EVAL_RUN_COST_MICRO_USD < CALL_MICRO_USD * 5

        result = await harness(configuration=config(output_price=COSTLY_PRICE)).run(
            [case("ceiling-1"), case("ceiling-2")]
        )

        assert result.complete is False
        assert result.stopped_reason == "eval_budget_exhausted"

    @pytest.mark.asyncio
    async def test_the_truncated_case_is_dropped_rather_than_scored(self, harness):
        """One run of three is not a case; scoring it would be the lie."""
        result = await harness(configuration=config(output_price=COSTLY_PRICE)).run(
            [case("ceiling-3"), case("ceiling-4")]
        )

        assert [item.case.id for item in result.results] == ["ceiling-3"]
        assert all(len(item.runs) == RUNS_PER_CASE for item in result.results)

    @pytest.mark.asyncio
    async def test_a_stopped_run_is_never_gating_and_says_it_did_not_finish(
        self, harness
    ):
        result = await harness(configuration=config(output_price=COSTLY_PRICE)).run(
            [case("ceiling-5"), case("ceiling-6")]
        )

        assert result.gating is False
        assert result.category_totals["complete"] is False
        assert result.category_totals["stopped_reason"] == "eval_budget_exhausted"

    @pytest.mark.asyncio
    async def test_the_stop_is_written_into_the_report(self, harness, tmp_path):
        result = await harness(configuration=config(output_price=COSTLY_PRICE)).run(
            [case("ceiling-7"), case("ceiling-8")]
        )
        rendered = render_report(result)
        assert "eval_budget_exhausted" in rendered
        assert "did not finish" in rendered

    @pytest.mark.asyncio
    async def test_an_exhausted_lane_stops_the_run_just_as_the_ceiling_does(
        self, harness
    ):
        """The $5 lane sits above the per-run ceiling and refuses first.

        Recognising only ``eval_budget_exhausted`` would let the battery run to
        the end and publish a full score over Turns that never reached the
        model — the ADR's lie, arrived at from the other direction.
        """
        starved = config(output_price=COSTLY_PRICE, eval_usd=0.0)
        result = await harness(configuration=starved).run(
            [case("lane-1"), case("lane-2")]
        )

        assert result.complete is False
        assert result.stopped_reason == "lane_budget_exhausted"
        assert result.results == ()
        assert result.gating is False

    def test_every_reason_the_ledger_raises_is_in_the_closed_set(self):
        """The set the harness matches against is pinned to the refusals.

        Maintained by hand at a distance it would drift the first time a ceiling
        was added — and the drift is silent, because the battery would simply
        stop noticing that ceiling.
        """
        import ast

        from src.core.llm import BUDGET_REFUSAL_REASONS

        tree = ast.parse(Path("src/core/llm/admission.py").read_text())
        raised = {
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "BudgetRefusal"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        }
        assert raised == set(BUDGET_REFUSAL_REASONS)


class TestASeatTheFixtureDoesNotFill:
    @pytest.mark.asyncio
    async def test_a_case_naming_an_unseated_role_stops_the_run_before_it_pays(
        self, harness, factory, seed
    ):
        """A case names a seat so a re-freeze moves it with the symbol.

        The cost of that indirection is this check. A fixture that no longer
        seats a role turns every case about it into a ``KeyError`` mid-run,
        after the cases before it have been paid for.
        """
        from src.eval.harness import EvalMisconfigured

        built = harness()
        without_bank = {
            role: symbol
            for role, symbol in seed.manifest.roles.items()
            if role is not FixtureRole.BANK
        }
        built.fixture = replace(
            built.fixture,
            seed=replace(
                seed, manifest=replace(seed.manifest, roles=without_bank)
            ),
        )

        with pytest.raises(EvalMisconfigured) as raised:
            await built.run([case("unseated-1", role=FixtureRole.BANK)])

        assert "unseated-1" in str(raised.value)
        assert usage_rows(factory) == []


class TestTheRunRow:
    @pytest.mark.asyncio
    async def test_it_records_mode_route_model_and_the_four_versions(
        self, harness, factory, seed
    ):
        built = harness()
        result = await built.run([case("row-1")])

        session = factory()
        try:
            row = session.get(EvalRun, result.run_id)
            assert row.mode == "gate"
            assert row.route == "https://eval.example"
            assert row.model == SESSION_MODEL
            assert row.prompt_version == result.prompt_version
            assert row.tool_catalog_version == built.tool_catalog_version
            assert row.registry_version == result.versions.registry_version
            assert row.fixture_version == seed.fixture_version
            assert row.finished_at is not None
        finally:
            session.close()

    @pytest.mark.asyncio
    async def test_per_category_totals_are_stored_and_per_case_detail_is_not(
        self, harness, factory
    ):
        result = await harness().run([case("row-2")])
        session = factory()
        try:
            totals = session.get(EvalRun, result.run_id).category_totals
        finally:
            session.close()

        assert totals["by_category"]["B"] == {"cases": 1, "runs": 3, "passed": 3}
        encoded = repr(totals)
        assert "row-2" not in encoded
        assert "answer" not in encoded

    @pytest.mark.asyncio
    async def test_the_report_path_is_stamped_onto_the_row(
        self, harness, factory, tmp_path
    ):
        built = harness()
        result = await built.run([case("row-3")])
        path = write_report(result, tmp_path)
        built.record_report_path(result, path)

        session = factory()
        try:
            assert session.get(EvalRun, result.run_id).report_path == str(path)
        finally:
            session.close()


class TestSmokeIsFreeAndNonGating:
    @pytest.mark.asyncio
    async def test_a_smoke_run_reserves_but_costs_nothing(self, harness, factory):
        free = replace(
            config(),
            pricing=PricingTable(
                version=SMOKE_PRICING_VERSION,
                effective_from=None,
                batch=TokenPrices(0.0, 0.0, 0.0, 0.0),
                session=TokenPrices(0.0, 0.0, 0.0, 0.0),
            ),
        )
        result = await harness(mode=EvalMode.SMOKE, configuration=free).run(
            [case("smoke-1")]
        )

        rows = usage_rows(factory)
        assert rows, "a smoke run still proves the reservation path"
        assert {row.reserved_micro_usd for row in rows} == {0}
        assert result.mode is EvalMode.SMOKE
        assert result.gating is False

    @pytest.mark.asyncio
    async def test_its_report_cannot_occupy_the_baseline_filename(self, harness):
        result = await harness(mode=EvalMode.SMOKE).run([case("smoke-2")])
        assert "smoke" in report_filename(result)

    def test_a_smoke_run_without_its_own_route_refuses(self):
        from src.core.config import Settings
        from src.eval.harness import EvalMisconfigured

        with pytest.raises(EvalMisconfigured) as raised:
            smoke_config(Settings(eval_smoke_base_url=""))
        assert "EVAL_SMOKE_BASE_URL" in str(raised.value)

    def test_smoke_and_gate_never_resolve_to_the_same_route(self):
        """A smoke run that reached the production model would be a paid run.

        Which is worse than it sounds: it would also carry gating weight it has
        not earned, because a reader comparing two reports sees the model name
        and not the mode that chose it.
        """
        from src.core.config import Settings
        from src.eval.harness import config_for

        settings = Settings(
            llm_base_url="https://production.example",
            llm_model_session="production-session",
            llm_model_batch="production-batch",
            eval_smoke_base_url="http://localhost:8317",
            eval_smoke_model_session="dev-session",
            eval_smoke_model_batch="dev-batch",
        )
        gate = config_for(EvalMode.GATE, settings)
        smoke = config_for(EvalMode.SMOKE, settings)

        assert gate.route.base_url == "https://production.example"
        assert gate.model_for(Workload.SESSION) == "production-session"
        assert smoke.route.base_url == "http://localhost:8317"
        assert smoke.model_for(Workload.SESSION) == "dev-session"
        assert smoke.pricing.version == SMOKE_PRICING_VERSION

    def test_a_gate_run_without_the_production_route_refuses(self):
        from src.core.config import Settings
        from src.eval.harness import EvalMisconfigured, config_for

        with pytest.raises(EvalMisconfigured) as raised:
            config_for(EvalMode.GATE, Settings(llm_base_url=""))
        assert "LLM_BASE_URL" in str(raised.value)


class TestTheFixtureGatesTheBattery:
    @pytest.mark.asyncio
    async def test_a_moved_version_refuses_to_start(self, harness, factory, seed):
        built = harness()
        built.fixture = replace(
            built.fixture,
            seed=replace(
                seed,
                manifest=replace(
                    seed.manifest,
                    versions=replace(
                        seed.manifest.versions, registry_version="0" * 16
                    ),
                ),
            ),
        )
        with pytest.raises(FixtureVersionMismatch):
            await built.run([case("stale-1")])

        assert usage_rows(factory) == []


class TestTheToolLayerIsTheRealOne:
    @pytest.mark.asyncio
    async def test_a_tool_call_reaches_the_fixture_store_and_is_traced(
        self, harness, factory
    ):
        symbol = world.BANK
        transport = ScriptedTransport(
            [
                Completion(
                    model=SESSION_MODEL,
                    tool_calls=(
                        ToolCall(
                            id="call_0",
                            name="get_price_series",
                            arguments={"symbol": symbol, "window_days": 21},
                            output_index=0,
                        ),
                    ),
                    usage=Usage(input_tokens=0, output_tokens=1),
                ),
                Completion(
                    model=SESSION_MODEL,
                    text="Vùng giá gần nhất đi ngang.",
                    usage=Usage(input_tokens=0, output_tokens=1),
                ),
            ]
            # Every later run answers from the default script.
        )
        result = await harness(transport=transport).run(
            [case("tools-1", role=FixtureRole.BANK)]
        )

        first = result.results[0].runs[0]
        assert first.tool_calls == ("get_price_series",)

        from src.alpha.models import AgentToolCall

        session = factory()
        try:
            traced = session.execute(
                select(AgentToolCall.tool_name, AgentToolCall.status)
            ).all()
        finally:
            session.close()
        assert ("get_price_series", "ok") in traced


class TestTheFixturesOwnNewsReachesTheLoop:
    """Category F is only worth running if the article gets to the model.

    Three ways it could silently not: the lane failing closed with no Redis, the
    sanitiser dropping an uncleared source, and the news window measured from
    the wall clock rather than from the fixture's frozen Trading Day. Each would
    leave six green injection cases over an article nobody saw.
    """

    @staticmethod
    def news_call(symbol: str, window_days: int = 7):
        return ScriptedTransport(
            [
                Completion(
                    model=SESSION_MODEL,
                    tool_calls=(
                        ToolCall(
                            id="call_0",
                            name="search_news",
                            arguments={"symbol": symbol, "window_days": window_days},
                            output_index=0,
                        ),
                    ),
                    usage=Usage(input_tokens=0, output_tokens=1),
                ),
                Completion(
                    model=SESSION_MODEL,
                    text="Bản tin có kèm chỉ dẫn; tôi ghi nhận và không làm theo.",
                    usage=Usage(input_tokens=0, output_tokens=1),
                ),
            ]
        )

    @staticmethod
    def traced_news(factory, symbol: str) -> list[dict]:
        """This symbol's news traces, newest last.

        Filtered by symbol because the eval database outlives one test: the
        traces of every case in the module are still in it, and reading the
        first row would read whichever test ran first.
        """
        from src.alpha.models import AgentToolCall

        session = factory()
        try:
            return [
                row.result
                for row in session.execute(
                    select(AgentToolCall)
                    .where(AgentToolCall.tool_name == "search_news")
                    .order_by(AgentToolCall.id)
                ).scalars()
                if (row.arguments or {}).get("symbol") == symbol
            ]
        finally:
            session.close()

    @pytest.mark.asyncio
    async def test_the_planted_articles_are_served_through_the_real_tool(
        self, harness, factory, seed
    ):
        symbol = seed.manifest.roles[FixtureRole.INJECTION_NEWS]
        built = harness(transport=self.news_call(symbol))
        await built.run(
            [case("news-1", role=FixtureRole.INJECTION_NEWS)]
        )

        results = self.traced_news(factory, symbol)
        assert results, "the battery never reached search_news"
        assert results[-1]["count"] == len(PLANTED_NEWS)
        served = " ".join(
            item["untrusted_evidence"]["content"] for item in results[-1]["items"]
        )
        assert figure_in(served)

    @pytest.mark.asyncio
    async def test_the_narrowest_window_still_holds_them(self, harness, factory, seed):
        """The clock is the fixture's day, so a one-day window is not empty."""
        symbol = seed.manifest.roles[FixtureRole.INJECTION_NEWS]
        built = harness(transport=self.news_call(symbol, window_days=1))
        await built.run([case("news-2", role=FixtureRole.INJECTION_NEWS)])

        assert self.traced_news(factory, symbol)[-1]["count"] == len(PLANTED_NEWS)

    @pytest.mark.asyncio
    async def test_every_other_symbol_answers_with_no_news(
        self, harness, factory, seed
    ):
        built = harness(transport=self.news_call(world.BANK))
        await built.run([case("news-3", role=FixtureRole.BANK)])

        result = self.traced_news(factory, world.BANK)[-1]
        assert result["count"] == 0
        assert result["reason"] == "no_cleared_news_in_window"

class TestTheBaselineIsResolvedFromTheTable:
    """In SQL, from ``eval_run``, which is the other reason that table exists."""

    def seat_previous_run(self, factory, *, fixture_version: str, mode="gate"):
        import uuid as _uuid
        from datetime import timedelta

        from src.eval.verdict import THRESHOLDS

        run_id = _uuid.uuid4()
        session = factory()
        with session.begin():
            session.add(
                EvalRun(
                    id=run_id,
                    started_at=datetime.now(timezone.utc) - timedelta(days=1),
                    finished_at=datetime.now(timezone.utc) - timedelta(days=1),
                    mode=mode,
                    route="https://eval.example",
                    model=SESSION_MODEL,
                    prompt_version="v1",
                    tool_catalog_version="tc-1",
                    registry_version="reg-1",
                    fixture_version=fixture_version,
                    category_totals={
                        "by_category": {
                            category.value: {"cases": 4, "runs": 12, "passed": 12}
                            for category in THRESHOLDS
                        },
                        "by_surface": {},
                        "complete": True,
                        "stopped_reason": None,
                    },
                    report_path="docs/eval/2026-08-13-v1.md",
                )
            )
        session.close()
        return run_id

    @pytest.mark.asyncio
    async def test_a_gate_run_is_read_against_the_last_passing_gate_run(
        self, harness, factory, seed
    ):
        previous = self.seat_previous_run(
            factory, fixture_version=seed.fixture_version
        )
        result = await harness().run([case("baseline-1")])

        assert result.baseline is not None
        assert result.baseline.baseline.run_id == previous
        assert result.baseline.baseline_reset is False

    @pytest.mark.asyncio
    async def test_the_baseline_it_used_is_stored_on_the_row(
        self, harness, factory, seed
    ):
        previous = self.seat_previous_run(
            factory, fixture_version=seed.fixture_version
        )
        result = await harness().run([case("baseline-2")])

        session = factory()
        try:
            stored = session.get(EvalRun, result.run_id).category_totals
        finally:
            session.close()
        assert stored["baseline"]["baseline_run_id"] == str(previous)
        assert stored["baseline"]["baseline_reset"] is False

    @pytest.mark.asyncio
    async def test_a_moved_fixture_voids_the_baseline(self, harness, factory):
        self.seat_previous_run(factory, fixture_version="2020-01-01-oldfixture")
        result = await harness().run([case("baseline-3")])

        assert result.baseline.baseline_reset is True
        assert result.baseline.diffs == ()

    @pytest.mark.asyncio
    async def test_a_smoke_run_is_compared_against_nothing(
        self, harness, factory, seed
    ):
        self.seat_previous_run(factory, fixture_version=seed.fixture_version)
        result = await harness(mode=EvalMode.SMOKE).run([case("baseline-4")])
        assert result.baseline is None

    @pytest.mark.asyncio
    async def test_a_stopped_run_has_no_score_to_compare(
        self, harness, factory, seed
    ):
        self.seat_previous_run(factory, fixture_version=seed.fixture_version)
        result = await harness(configuration=config(output_price=COSTLY_PRICE)).run(
            [case("baseline-5"), case("baseline-6")]
        )
        assert result.complete is False
        assert result.baseline is None


class TestNoLlmJudge:
    def test_the_scoring_module_cannot_reach_a_model(self):
        """Structural, not a promise: the module has no route to a provider.

        ``docs/adr/0016`` refuses an LLM judge in v1 because an uncalibrated one
        is the same self-certification ADR-0010 rejected. A docstring saying so
        would not survive the first person who wanted a second opinion on a
        borderline answer.
        """
        source = Path("src/eval/scoring.py").read_text(encoding="utf-8")
        for forbidden in (
            "build_client",
            "LLMClient",
            "CompletionRequest",
            ".complete(",
            "httpx",
        ):
            assert forbidden not in source, f"{forbidden} reached the scoring path"

    def test_the_battery_calls_the_model_once_per_run_and_only_through_the_loop(
        self, harness, factory
    ):
        """One owner, one lane, and no second kind of call in the ledger."""
        import asyncio

        result = asyncio.run(harness().run([case("judge-1")]))
        rows = usage_rows(factory)
        assert len(rows) == len(result.results[0].runs)
