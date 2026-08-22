"""The Analysis lane: the nightly pipeline, over the fixture, inside one run.

Four properties, and each is one the report would otherwise be quietly wrong
about:

*The pipeline is the deployed one.* ``produce_analysis`` publishes the row and
``analysis_producer`` assembles the envelope from the eval store. Nothing here
substitutes either, so what the lane scores is an artifact the nightly pass
would have written.

*Three runs are three generations.* Production is idempotent per
``(symbol, trading_day)`` and the fixture arrives carrying the ``analysis`` rows
the real store held, so a lane that did not clear the pair would score one
generation three times and call it agreement.

*Every generation is charged to the ``eval_run``.* Same ceiling, same ledger and
same locked transaction a user's Analysis gets — and the production per-call
ceilings are still asked, on the spend the producer built, before the owner is
changed.

*A case enters its own category total.* The report is read by category, and a
category that counted the wrong cases is a report nobody can act on.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from src.alpha.field_profile import AXIS_ORDER
from src.alpha.generation import Verdict
from src.alpha.models import Analysis, EvalRun, LlmCallUsage
from src.core.llm import (
    BudgetLane,
    BudgetRefusal,
    CallOwner,
    OwnerType,
    SpendRequest,
    Workload,
)
from src.core.llm.admission import (
    ANALYSIS_INPUT_PER_CALL,
    EVAL_RUN_COST_MICRO_USD,
)
from src.eval.analysis_lane import EvalOwnedClient
from src.eval.capture import capture_fixture
from src.eval.cases import (
    AnalysisExpectation,
    EvalCase,
    EvalCategory,
    EvalSurface,
    Expectation,
)
from src.eval.harness import RUNS_PER_CASE, EvalHarness, EvalMode
from src.eval.roles import FixtureRole
from src.eval.scoring import Check
from src.eval.store import create_schema, eval_engine, load_fixture

from . import eval_world as world
from .eval_store import SOURCE_DB, TARGET_DB, create_database, drop_database
from .test_eval_harness import (
    FRAGMENT_OUTPUT_TOKENS,
    AnalysisTransport,
    client_for,
    config,
)


def analysis_case(identifier: str, **overrides) -> EvalCase:
    defaults = dict(
        id=identifier,
        category=EvalCategory.INTERPRETATION,
        surface=EvalSurface.ANALYSIS,
        prompt="",
        role=FixtureRole.BANK,
        expectation=Expectation(analysis=AnalysisExpectation(publishes=True)),
        intent="a lane fixture, not a battery case",
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
    def build(*, configuration=None, transport=None):
        resolved = configuration or config()
        analysis = transport or AnalysisTransport()
        return EvalHarness(
            mode=EvalMode.GATE,
            fixture=load_fixture(seed, factory),
            session_factory=factory,
            config=resolved,
            # A fresh guarded client per generation, which is what the lane
            # requires: the producer runs each one in an event loop of its own.
            analysis_client_factory=lambda: client_for(factory, resolved, analysis),
            git_sha="eval-test",
            # Never the application store: this file asserts nothing about the
            # field, and left unset the run would open the dev database.
            ops_session_factory=factory,
        )

    return build


def usage_rows(factory) -> list[LlmCallUsage]:
    session = factory()
    try:
        return list(
            session.execute(select(LlmCallUsage).order_by(LlmCallUsage.id)).scalars()
        )
    finally:
        session.close()


class TestTheNightlyPipelineRunsUnmodified:
    @pytest.mark.asyncio
    async def test_a_case_publishes_a_real_analysis_row(self, harness, factory):
        result = await harness().run([analysis_case("lane-1")])

        run = result.results[0].runs[0]
        assert run.verdict == Verdict.HOLD.value
        assert run.cited_field_ids

        session = factory()
        try:
            published = session.execute(
                select(Analysis).where(Analysis.symbol == world.BANK)
            ).scalars().all()
        finally:
            session.close()
        assert len(published) == 1
        assert published[0].payload["audit"]["promptVersion"]
        assert published[0].payload["evidence"]["symbol"] == world.BANK

    @pytest.mark.asyncio
    async def test_the_verbatim_prose_is_every_sentence_the_model_wrote(
        self, harness
    ):
        result = await harness().run([analysis_case("lane-2")])
        answer = result.results[0].runs[0].answer
        assert "Vùng giá thường ngày vẫn hẹp." in answer
        assert "Bằng chứng hiện có chỉ mô tả trạng thái gần đây." in answer
        # One reading per axis, so a rubric scores the whole artifact.
        assert answer.count("Các chỉ số nằm trong vùng quen thuộc") == len(AXIS_ORDER)

    @pytest.mark.asyncio
    async def test_the_envelope_the_model_saw_came_from_the_fixture(self, harness):
        transport = AnalysisTransport()
        await harness(transport=transport).run([analysis_case("lane-3")])
        assert transport.envelopes
        assert transport.envelopes[0]["tradingDay"] == world.TRADING_DAY.isoformat()
        assert transport.envelopes[0]["industry"] == "banks"


class TestThreeRunsAreThreeGenerations:
    @pytest.mark.asyncio
    async def test_the_pair_is_cleared_so_each_run_produces_again(
        self, harness, factory
    ):
        """Idempotent production would otherwise score one artifact three times."""
        transport = AnalysisTransport()
        result = await harness(transport=transport).run([analysis_case("lane-4")])

        assert len(result.results[0].runs) == RUNS_PER_CASE
        assert len(transport.envelopes) == RUNS_PER_CASE
        assert len(usage_rows(factory)) == RUNS_PER_CASE

    @pytest.mark.asyncio
    async def test_only_this_pair_is_cleared_and_not_the_table(
        self, harness, factory
    ):
        """The fixture's other Analyses are part of the photograph."""
        # Seated after the harness is built, because building it loads the
        # fixture — and loading truncates and refills every captured table.
        built = harness()
        session = factory()
        with session.begin():
            session.add(
                Analysis(
                    symbol=world.ORDINARY,
                    trading_day=world.TRADING_DAY,
                    verdict="hold",
                    payload={"kept": True},
                    schema_version=1,
                )
            )
        session.close()

        await built.run([analysis_case("lane-5")])

        session = factory()
        try:
            kept = session.execute(
                select(Analysis).where(Analysis.symbol == world.ORDINARY)
            ).scalars().all()
        finally:
            session.close()
        assert len(kept) == 1


class TestEveryGenerationNamesTheEvalRun:
    @pytest.mark.asyncio
    async def test_the_owner_is_the_eval_run_and_the_lane_is_eval(
        self, harness, factory
    ):
        result = await harness().run([analysis_case("owner-a1")])

        rows = usage_rows(factory)
        assert rows
        assert {row.owner_type for row in rows} == {OwnerType.EVAL_RUN.value}
        assert {row.owner_id for row in rows} == {str(result.run_id)}
        assert {row.lane for row in rows} == {"eval"}
        # The batch workload, because that is what the nightly lane runs on.
        assert {row.model for row in rows} == {
            config().model_for(Workload.BATCH)
        }

    @pytest.mark.asyncio
    async def test_the_ceiling_stops_the_run_rather_than_dropping_cases(
        self, harness
    ):
        costly = config(output_price=EVAL_RUN_COST_MICRO_USD / FRAGMENT_OUTPUT_TOKENS)
        result = await harness(configuration=costly).run(
            [analysis_case("ceiling-a1"), analysis_case("ceiling-a2")]
        )

        assert result.complete is False
        assert result.stopped_reason == "eval_budget_exhausted"
        assert result.gating is False

    @pytest.mark.asyncio
    async def test_the_production_per_call_ceilings_are_still_asked(self):
        """Redirecting the owner first would exempt the battery from them.

        They are keyed on the Analysis Run owner inside admission, so a battery
        that changed the owner and then reserved would admit an envelope the
        nightly pass refuses — and report a passing case for a symbol production
        cannot produce.
        """
        client = EvalOwnedClient(lambda: None, "run-1")
        oversized = SpendRequest(
            owner=CallOwner(type=OwnerType.ANALYSIS_RUN, id="7"),
            lane=BudgetLane.ANALYSIS,
            workload=Workload.BATCH,
            input_tokens=ANALYSIS_INPUT_PER_CALL + 1,
            output_tokens=1,
        )
        with pytest.raises(BudgetRefusal) as refused:
            await client.complete(object(), oversized)
        assert refused.value.reason == "analysis_input_per_call"
        # And it is not recorded as a ceiling that bound the battery. An
        # envelope too large for one generation is a case the pipeline correctly
        # refused; stopping the run over it would drop every case after it for a
        # defect in this one.
        assert client.refusal is None


class TestTheThreeChecksOnlyThisLaneHas:
    @pytest.mark.asyncio
    async def test_a_healthy_artifact_passes_all_three(self, harness):
        result = await harness().run([analysis_case("checks-1")])
        run = result.results[0].runs[0]
        for check in (
            Check.ANALYSIS_CITED_PROFILE,
            Check.ANALYSIS_REFUSED_FIELD,
            Check.ANALYSIS_LEAD_AXIS,
        ):
            verdict = next(item for item in run.score.results if item.check is check)
            assert verdict.passed, verdict.detail
        assert run.passed

    @pytest.mark.asyncio
    async def test_a_run_the_pipeline_refused_is_recorded_as_a_failure_by_name(
        self, harness
    ):
        """The short-history seat has no core evidence, so nothing is published."""
        gap = analysis_case(
            "checks-2",
            category=EvalCategory.DATA_GAP,
            role=FixtureRole.BELOW_MIN_SESSIONS,
            expectation=Expectation(
                analysis=AnalysisExpectation(
                    publishes=False, failure_code="insufficient_core_evidence"
                )
            ),
        )
        result = await harness().run([gap])

        run = result.results[0].runs[0]
        assert run.status == "failed"
        assert run.terminal_reason == "insufficient_core_evidence"
        assert run.passed, "the case expected exactly this refusal"

    @pytest.mark.asyncio
    async def test_a_refused_citation_is_rejected_by_the_pipeline_and_the_lane(
        self, harness
    ):
        """Both, and that is the point: one proves the other is still wired.

        ``validate_fragment`` refuses the fragment, the one sanctioned
        regeneration produces the same thing, and the attempt fails
        ``invalid_model_output``. The lane then scores a case that expected an
        artifact and did not get one.
        """
        result = await harness(transport=AnalysisTransport(cite_refused=True)).run(
            [analysis_case("checks-3")]
        )

        run = result.results[0].runs[0]
        assert run.terminal_reason == "invalid_model_output"
        assert not run.passed


class TestTheTotalsAreReadableByCategoryAndBySurface:
    @pytest.mark.asyncio
    async def test_one_run_totals_its_cases_under_the_surface_they_ran_on(
        self, harness, factory
    ):
        result = await harness().run([analysis_case("mixed-analysis")])

        totals = result.category_totals
        assert totals["by_surface"]["analysis"]["cases"] == 1
        assert totals["by_surface"]["analysis"]["runs"] == RUNS_PER_CASE
        # Present at zero rather than absent: a missing key and a zero read the
        # same to a careless eye and mean opposite things.
        assert totals["by_surface"]["turn"] == {"cases": 0, "runs": 0, "passed": 0}

        session = factory()
        try:
            stored = session.get(EvalRun, result.run_id).category_totals
        finally:
            session.close()
        assert stored["by_surface"]["analysis"]["cases"] == 1

    @pytest.mark.asyncio
    async def test_an_analysis_case_enters_its_own_category_total(self, harness):
        result = await harness().run(
            [
                analysis_case(
                    "mixed-e",
                    category=EvalCategory.DATA_GAP,
                    role=FixtureRole.LIMIT_LOCK_DENSE,
                )
            ]
        )
        assert result.category_totals["by_category"]["E"]["cases"] == 1
        assert result.category_totals["by_category"]["D"]["cases"] == 0
