"""The battery run: three runs per case, one ``eval_run``, and a hard ceiling.

What this file owns is the *run* rather than the lane: who the ledger charges,
what stops a run, what lands on the ``eval_run`` row, and what the fixture gates
before anything is spent. The Analysis lane's own behaviour — the pipeline, the
three artifact checks, the separated totals — is
``tests/test_eval_analysis_lane.py``.

It also owns the scaffolding both files build a harness from
(:func:`config`, :func:`client_for`, :class:`AnalysisTransport`), because a
second copy of a cooperating route is a second thing to keep in step with the
generation it has to satisfy.

Requires a Postgres it may create and drop databases on, like the fixture tests.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from src.agent.ops import OPS_WINDOW_DAYS
from src.alpha.field_profile import AXIS_ORDER
from src.alpha.generation import Emphasis, Verdict
from src.alpha.models import EvalRun, LlmCallUsage
from src.core.llm import (
    LLMConfig,
    OwnerType,
    Usage,
    Workload,
)
from src.core.llm.admission import EVAL_RUN_COST_MICRO_USD, SpendAdmission
from src.core.llm.client import ReservedLLMClient
from src.core.llm.config import (
    BudgetLanes,
    LLMRoute,
    PricingTable,
    TokenPrices,
)
from src.core.llm.protocol import Completion
from src.eval.cases import (
    AnalysisExpectation,
    EvalCase,
    EvalCategory,
    EvalSurface,
    Expectation,
)
from src.eval.capture import capture_fixture
from src.eval.harness import (
    RUNS_PER_CASE,
    SMOKE_PRICING_VERSION,
    EvalHarness,
    EvalMode,
    smoke_config,
)
from src.eval.report import render_report, report_filename, write_report
from src.eval.roles import FixtureRole
from src.eval.store import create_schema, eval_engine, load_fixture
from src.eval.versions import FixtureVersionMismatch

from . import eval_world as world
from .eval_store import SOURCE_DB, TARGET_DB, create_database, drop_database

SESSION_MODEL = "eval-session-model"
BATCH_MODEL = "eval-batch-model"

# What one Analysis generation returns in output tokens. Small enough that the
# ceiling never fires by accident and the tests that are about the ceiling can
# set the price instead.
FRAGMENT_OUTPUT_TOKENS = 700

# Zero on every input price, so the ceiling arithmetic in these tests is about
# the output reservation and nothing else.
CHEAP_PRICE = 1.0
# What the ceiling tests charge. Priced so that the run stops *inside* the
# second case rather than at a case boundary, which is the harder of the two to
# get right: three generations fit under $2.5 and the fourth does not.
COSTLY_PRICE = EVAL_RUN_COST_MICRO_USD / (FRAGMENT_OUTPUT_TOKENS * 3.5)


def config(
    *,
    eval_usd: float = 1_000.0,
    output_price: float = CHEAP_PRICE,
    run_ceiling_usd: float | None = 2.5,
) -> LLMConfig:
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
        eval_run_cost_ceiling_usd=run_ceiling_usd,
    )


class AnalysisTransport:
    """A route that answers with a fragment built from the envelope it was sent.

    Not a canned string: the semantic pass behind the generation checks the
    citations against *this* envelope, so a fixed fragment would be rejected for
    citing ids the fixture does not have and every test would measure the
    rejection path. Reading the envelope back out of the request is what a
    cooperating model does, and it leaves the misbehaviours to the flags below.
    """

    def __init__(self, *, cite_refused: bool = False, leads: int = 1) -> None:
        self.cite_refused = cite_refused
        self.leads = leads
        self.envelopes: list[dict] = []

    async def dispatch(self, request):
        envelope = json.loads(request.messages[1].content)
        self.envelopes.append(envelope)
        figures = [envelope["priceZone"]] + [
            figure
            for section in envelope["sections"]
            for figure in section["figures"]
        ]
        citable = [
            figure["fieldId"]
            for figure in figures
            if figure["health"] != "refused" and figure["value"] is not None
        ]
        refused = [
            figure["fieldId"] for figure in figures if figure["health"] == "refused"
        ]
        cited = list(citable)
        if self.cite_refused and refused:
            cited.append(refused[0])
        fragment = {
            "verdict": Verdict.HOLD.value,
            "verdictLine": "Vùng giá thường ngày vẫn hẹp.",
            "thesis": "Bằng chứng hiện có chỉ mô tả trạng thái gần đây.",
            "citedFieldIds": cited,
            "axes": [
                {
                    "axis": axis.value,
                    "emphasis": (
                        Emphasis.LEAD.value
                        if index < self.leads
                        else Emphasis.SUPPORT.value
                    ),
                    "emphasisReason": "Trục này mang nhiều bằng chứng dùng được nhất.",
                    "read": "Các chỉ số nằm trong vùng quen thuộc của chính nó.",
                }
                for index, axis in enumerate(AXIS_ORDER)
            ],
        }
        return Completion(
            model=request.model,
            text=json.dumps(fragment, ensure_ascii=False),
            usage=Usage(input_tokens=0, output_tokens=FRAGMENT_OUTPUT_TOKENS),
        )


def client_for(factory, configuration: LLMConfig, transport):
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
        category=EvalCategory.INTERPRETATION,
        surface=EvalSurface.ANALYSIS,
        prompt="",
        role=FixtureRole.BANK,
        expectation=Expectation(analysis=AnalysisExpectation(publishes=True)),
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
    def build(
        *,
        mode: EvalMode = EvalMode.GATE,
        configuration=None,
        transport=None,
        ops_session_factory=None,
    ):
        resolved = configuration or config()
        route = transport or AnalysisTransport()
        return EvalHarness(
            mode=mode,
            fixture=load_fixture(seed, factory),
            session_factory=factory,
            config=resolved,
            # A fresh guarded client per generation, which is what the lane
            # requires: the producer runs each one in an event loop of its own.
            analysis_client_factory=lambda: client_for(factory, resolved, route),
            git_sha="eval-test",
            # Pointed somewhere on purpose. Left unset, the fixed ops query
            # resolves the *application* store — so every test in this file
            # would quietly open the dev database at the end of a run, for a
            # reading none of them assert on.
            ops_session_factory=ops_session_factory or factory,
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

    @pytest.mark.asyncio
    async def test_nothing_is_charged_to_the_fixture_user(self, harness, factory):
        """An eval run is not a customer, so it spends nobody's allowance."""
        result = await harness().run([case("owner-3")])

        rows = usage_rows(factory)
        assert rows, "the battery reserved nothing, so it called nothing"
        assert {row.owner_type for row in rows} == {OwnerType.EVAL_RUN.value}
        assert {row.owner_id for row in rows} == {str(result.run_id)}
        assert {row.user_id for row in rows} == {None}


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
    async def test_a_dev_route_can_disable_only_the_per_run_ceiling(self, harness):
        result = await harness(
            configuration=config(
                eval_usd=1_000.0,
                output_price=COSTLY_PRICE,
                run_ceiling_usd=None,
            )
        ).run([case("unlimited-1"), case("unlimited-2")])

        assert result.complete is True

    @pytest.mark.asyncio
    async def test_a_run_that_would_exceed_two_and_a_half_dollars_stops(self, harness):
        assert EVAL_RUN_COST_MICRO_USD == 2_500_000

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
    async def test_the_stop_is_written_into_the_report(self, harness):
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
        """The eval lane sits above the per-run ceiling and refuses first.

        Recognising only ``eval_budget_exhausted`` would let the battery run to
        the end and publish a full score over cases that never reached the
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


class TestACaseWithNoLaneToRunOn:
    @pytest.mark.asyncio
    async def test_a_turn_case_is_refused_before_anything_is_spent(
        self, harness, factory
    ):
        """The harness that answered a Turn case is gone (``docs/adr/0026``).

        Refused loudly rather than skipped: a case silently dropped is a category
        total that shrank without a word, which is the one failure this battery's
        own reporting rules forbid.
        """
        from src.eval.harness import EvalMisconfigured

        turn_case = EvalCase(
            id="turn-1",
            category=EvalCategory.FALSE_REFUSAL,
            surface=EvalSurface.TURN,
            prompt="Cổ phiếu này đang ở vùng giá nào?",
            role=FixtureRole.BANK,
        )

        with pytest.raises(EvalMisconfigured) as raised:
            await harness().run([turn_case])

        assert "turn-1" in str(raised.value)
        assert usage_rows(factory) == []


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
    async def test_it_records_mode_route_model_and_the_pinned_versions(
        self, harness, factory, seed
    ):
        result = await harness().run([case("row-1")])

        session = factory()
        try:
            row = session.get(EvalRun, result.run_id)
            assert row.mode == "gate"
            assert row.route == "https://eval.example"
            # The batch workload, because that is what the nightly lane runs on.
            assert row.model == BATCH_MODEL
            assert row.prompt_version == result.prompt_version
            assert row.registry_version == result.versions.registry_version
            assert row.fixture_version == seed.fixture_version
            assert row.finished_at is not None
        finally:
            session.close()

    @pytest.mark.asyncio
    async def test_the_tool_catalog_column_says_there_was_no_catalog(
        self, harness, factory
    ):
        """The column is ``NOT NULL`` and no lane in a run calls a tool.

        A hash of a catalog nothing used would read as a pin somebody could
        compare against; this says plainly that there is nothing to compare.
        """
        from src.eval.harness import NO_TOOL_CATALOG

        result = await harness().run([case("row-4")])
        session = factory()
        try:
            assert session.get(EvalRun, result.run_id).tool_catalog_version == (
                NO_TOOL_CATALOG
            )
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

        assert totals["by_category"]["D"] == {"cases": 1, "runs": 3, "passed": 3}
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
        assert gate.model_for(Workload.BATCH) == "production-batch"
        assert smoke.route.base_url == "http://localhost:8317"
        assert smoke.model_for(Workload.BATCH) == "dev-batch"
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
                    model=BATCH_MODEL,
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


class TestTheFieldIsReadOnceAtTheEnd:
    """The fixed ops query, taken by the run so the report cannot omit it.

    `docs/adr/0016` requires the field reading in the next Eval Report, and the
    report is written by a *second* command against a *different* database. So
    the run is where the reading has to happen: anything later would measure a
    window the run did not happen in, and anything the harness does not carry is
    something a person has to remember to paste.
    """

    @pytest.mark.asyncio
    async def test_a_run_carries_a_snapshot_of_the_window_it_finished_in(
        self, harness, factory
    ):
        result = await harness().run([case("ops-1")])

        assert result.ops is not None
        assert result.ops.readable
        assert result.ops.until == result.finished_at
        assert result.ops.window_days == OPS_WINDOW_DAYS

    @pytest.mark.asyncio
    async def test_a_smoke_run_reads_the_field_too(self, harness):
        """The field is the field whichever mode was pointed at the fixture."""
        result = await harness(mode=EvalMode.SMOKE).run([case("ops-2")])
        assert result.ops is not None

    @pytest.mark.asyncio
    async def test_a_stopped_run_still_reads_it(self, harness):
        """A run that produced no score is exactly when production is worth a look."""
        result = await harness(configuration=config(output_price=COSTLY_PRICE)).run(
            [case("ops-3"), case("ops-4")]
        )

        assert result.complete is False
        assert result.ops is not None

    @pytest.mark.asyncio
    async def test_an_unreachable_store_costs_the_reading_and_never_the_run(
        self, harness
    ):
        """The expensive half is not discarded to protect the cheap one.

        And the failure is carried rather than swallowed: a snapshot of zeros
        would read as a quiet week instead of an unread database.
        """

        def refuses():
            raise RuntimeError("connection refused")

        result = await harness(ops_session_factory=refuses).run([case("ops-5")])

        assert result.results  # the battery still produced its scores
        assert result.ops.readable is False
        assert "connection refused" in result.ops.error


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

    @pytest.mark.asyncio
    async def test_the_battery_calls_the_model_once_per_run_and_no_more(
        self, harness, factory
    ):
        """One owner, one lane, and no second kind of call in the ledger."""
        result = await harness().run([case("judge-1")])
        rows = usage_rows(factory)
        assert len(rows) == len(result.results[0].runs)
        assert {row.lane for row in rows} == {"eval"}
