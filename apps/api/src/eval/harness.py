"""The battery run: three runs per case, one ``eval_run``, and a hard ceiling.

Four properties are what this module is for.

**The loop is the real one.** ``AgentLoop``, the Tool Catalog, ``prepare_bars()``
and the Signal Registry are the deployed ones, pointed at the eval database. The
only substitutions are a Universe pinned by the fixture — configuration in the
serving system too — and a market state fixed at ``closed``, because a state read
from the wall clock would make the same fixture a different exam depending on the
hour it was run.

**Every provider call names ``eval_run`` as its owner.** Not a bookkeeping
detail: ``docs/adr/0014`` requires an owner with a non-null id for the atomic
reservation, and ``eval_run`` exists precisely because a Markdown report has
nothing to point at. The loop takes the owner as a :class:`SpendIdentity`, so
the battery reserves through the same locked transaction a user's Turn does.

**The ceiling never lies.** $2.5 a gate run, enforced in that same transaction.
On exhaustion the run **stops** and reports ``eval_budget_exhausted``, and
:class:`EvalRunResult` comes back ``complete=False`` with no category rates.
A battery that truncated itself and published a score would be a battery that
lies, so the incomplete result is not a score with a caveat — it has no score.

**Three runs, all kept.** The scoring rules that consume them differ by category
and land with those categories; this module's job is to run each case three
times and throw none of the outcomes away.

**Two surfaces, one run.** A Turn case goes through :class:`AgentLoop` and an
Analysis case through the nightly pipeline (``src/eval/analysis_lane.py``),
inside the same ``eval_run``, the same ceiling and the same ledger. The nightly
artifact is not exempt from the battery for having a schema — a schema proves
shape rather than content, and ``verdictLine``, ``thesis`` and the per-axis
``read`` are prose users meet every day. What the two lanes must not share is a
total, so :attr:`EvalRunResult.category_totals` counts them apart.

**The field is read once, at the end, and never written to.** ``docs/adr/0016``
requires the fixed ops query's output to appear in the Eval Report, so the run
takes one read-only snapshot of the *application* store (``src/agent/ops.py``)
and carries it on the result. This is the only part of a battery run that opens
``DATABASE_URL`` at all, and a store it cannot reach produces a snapshot saying
so rather than a failed run: the battery measures a frozen fixture, and the
field reading sits beside that score as a reconciliation rather than inside it.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, time, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from sqlalchemy.orm import Session

from src.agent.loop import AgentLoop, SpendIdentity, TurnOutcome, TurnRequest
from src.agent.manifest import EvidenceManifest, assemble_message, build_manifest
from src.agent.ops import OPS_WINDOW_DAYS, OpsSnapshot, read_ops_snapshot
from src.agent.persistence import AgentPersistence
from src.agent.prompt import PROMPT_VERSION, MarketState, RuntimeContext
from src.agent.tools.suite import IntelligentQuantCatalog
from src.agent.turns import gate_outcomes, rendered_blocks
from src.alpha.analysis_run import RunStatus
from src.alpha.models import EvalRun
from src.core.config import Settings, get_settings
from src.core.llm import (
    BUDGET_REFUSAL_REASONS,
    BudgetLane,
    BudgetRefusal,
    LLMConfig,
    OwnerType,
    Workload,
    build_client,
    llm_config_from_settings,
)
from src.core.llm.config import LLMRoute, PricingTable, TokenPrices
from src.core.news_lane import NewsLane
from src.stocks.providers.normalize import VN_TZ
from src.stocks.universe import Universe

from .analysis_lane import AnalysisBudgetExhausted, AnalysisLane
from .baseline import BaselineComparison, compare_to_baseline, resolve_baseline
from .cases import EvalCase, EvalCategory, EvalSurface, battery
from .fixture import FixtureSeed
from .scoring import DeterministicScore, score_analysis, score_turn
from .verdict import HARD_FAIL_CHECKS
from .store import LoadedFixture, load_fixture
from .versions import PinnedVersions, running_versions

logger = logging.getLogger(__name__)

#: ``docs/adr/0016``: every case runs three times, and all three outcomes are
#: kept. The criteria that consume them differ by category — 3/3 for safety, a
#: rate for quality — and none of that is decided here.
RUNS_PER_CASE = 3

#: The Trading Day is the fixture's, so the market state has to be a constant
#: rather than the clock's answer. ``closed`` is the honest one for a frozen
#: end-of-day store: every session in it has finished.
FIXTURE_MARKET_STATE = MarketState.CLOSED

#: What a smoke route charges. Zero is a fact about the dev lane rather than a
#: way around the ceiling — the reservation is still written, so the ledger path
#: is exercised at zero cost, which is exactly what a smoke run is for.
SMOKE_PRICING_VERSION = "smoke-free"
_FREE = TokenPrices(input=0.0, cached_input=0.0, cache_write=0.0, output=0.0)


class EvalMode(str, Enum):
    """The two modes, one of which gates."""

    # The dev route, at zero cost. Proves the harness and the deterministic
    # assertions still work, and has **no gating value**, because it does not
    # exercise the production model.
    SMOKE = "smoke"
    # The production route and production models. Only a gate run may be
    # attached to a pull request.
    GATE = "gate"

    @property
    def gating(self) -> bool:
        return self is EvalMode.GATE


class EvalMisconfigured(RuntimeError):
    """The battery cannot run as asked, and says so before spending anything."""


class EvalBudgetExhausted(RuntimeError):
    """A case could not be funded, so the run stopped. There is no score.

    Carries **which** ceiling bound, not a single fixed string. The $2.5 per-run
    ceiling of ``docs/adr/0016`` is the one this ticket is about, but the $5
    monthly eval lane of ``docs/adr/0014`` sits above it and an exhausted lane
    refuses the same call for a different reason. Recognising only
    ``eval_budget_exhausted`` would let the battery run to the end and publish a
    full score over Turns that never reached the model — which is the exact lie
    the ADR forbids, arrived at from the other direction.
    """

    def __init__(self, case_id: str, reason: str, detail: str) -> None:
        self.case_id = case_id
        self.reason = reason
        self.detail = detail
        super().__init__(
            f"{reason} at case {case_id}: {detail}. The run stopped rather than "
            "dropping the remaining cases and reporting a score."
        )


#: What ``answer_kind`` says on the Analysis lane. An Analysis has no
#: ``AnswerKind`` — that vocabulary is a Turn's — and a blank column would read
#: as a Turn that ended without deciding what kind of answer it had given.
ANALYSIS_ANSWER_KIND = "analysis"


@dataclass(frozen=True)
class CaseRun:
    """One of the three runs of one case, kept whole.

    One shape for both surfaces, with the fields only one of them fills saying
    so. A Turn has an ``answer_kind`` and tool calls; an Analysis has a verdict
    and cites field ids. Two types would mean two report writers and two ways of
    counting a pass, and the report's whole job is to put the lanes side by side.
    """

    run_index: int
    score: DeterministicScore
    # The verbatim answer, which is one of ``docs/adr/0016``'s three defences
    # against a rubber-stamped human rubric: the text being judged is embedded
    # in the report, so a careless pass leaves a readable trace. On the Analysis
    # lane that is every sentence the model wrote — the verdict line, the
    # thesis, and both narrations of all four axes.
    answer: str
    status: str
    terminal_reason: str | None
    answer_kind: str
    tool_calls: tuple[str, ...]
    # The Analysis lane's extracted column and the ids its verdict rested on,
    # both empty on the Turn lane, which has neither.
    verdict: str | None = None
    cited_field_ids: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.score.passed

    def as_wire(self) -> dict[str, Any]:
        return {
            "run_index": self.run_index,
            "status": self.status,
            "terminal_reason": self.terminal_reason,
            "answer_kind": self.answer_kind,
            "tool_calls": list(self.tool_calls),
            "verdict": self.verdict,
            "cited_field_ids": list(self.cited_field_ids),
            "answer": self.answer,
            "score": self.score.as_wire(),
        }


@dataclass(frozen=True)
class CaseResult:
    """One case and its three runs."""

    case: EvalCase
    runs: tuple[CaseRun, ...]
    # What the user actually typed, with the fixture's own ticker in place of
    # the seat. Kept because it is what a human reviewer scores against, and a
    # template is not a question anybody was asked.
    prompt: str = ""

    @property
    def passed_runs(self) -> int:
        return sum(1 for run in self.runs if run.passed)

    def as_wire(self) -> dict[str, Any]:
        return {
            "case_id": self.case.id,
            "category": self.case.category.value,
            "surface": self.case.surface.value,
            "prompt": self.prompt or self.case.prompt,
            "intent": self.case.intent,
            "runs": [run.as_wire() for run in self.runs],
        }


@dataclass(frozen=True)
class EvalRunResult:
    """What one battery run produced, and whether it produced a score at all."""

    run_id: uuid.UUID
    mode: EvalMode
    route: str
    model: str
    versions: PinnedVersions
    prompt_version: str
    fixture_version: str
    started_at: datetime
    finished_at: datetime
    results: tuple[CaseResult, ...]
    complete: bool = True
    stopped_reason: str | None = None
    report_path: str | None = None
    # What the last passing gate run scored, and whether comparing against it
    # means anything. ``None`` where no comparison was attempted at all: a smoke
    # run, or a run that stopped and has no score to compare.
    baseline: BaselineComparison | None = None
    # The fixed ops query's reading of the live service, taken once at the end
    # of the run. ``docs/adr/0016`` requires it in the report, so it rides on
    # the result rather than being fetched by the report writer: the document is
    # written by a second command, minutes or hours later, and a window measured
    # then would be a different window from the one the run happened in.
    ops: OpsSnapshot | None = None

    @property
    def gating(self) -> bool:
        """Only a complete gate run may be attached to a pull request."""
        return self.mode.gating and self.complete

    @property
    def hard_fails(self) -> tuple[str, ...]:
        """Every case where a run pointed somewhere its evidence cannot.

        ``docs/adr/0016``'s one overriding failure mode: narrating a registered
        field **backwards in sign** is a hard fail at 1/3, even when its
        category is above threshold — *that is the exact defect that
        disqualified the assessed external library, and it must not dissolve
        into an average.*

        Which checks count is ``verdict``'s to say, and it is asked rather than
        restated: this property exists so the fact survives into
        ``eval_run.category_totals``, where the baseline query can read it off a
        row whose runs are long gone.

        Case ids rather than a count, because the rule is about a case rather
        than about a rate, and the next question a reader has is *which one*.
        """
        return tuple(
            sorted(
                {
                    result.case.id
                    for result in self.results
                    for run in result.runs
                    for check in run.score.results
                    if check.failed and check.check.value in HARD_FAIL_CHECKS
                }
            )
        )

    @property
    def category_totals(self) -> Mapping[str, Any]:
        """Per-category cases, runs and passes — and nothing derived.

        Rates are not stored. The thresholds differ by category and the hard
        fail on a backwards sign overrides every rate (``docs/adr/0016``), so a
        stored percentage would be a number two later readers would disagree
        about the meaning of. Counts are what both of them can compute from.

        The baseline's **identity** is stored beside them, and only that: which
        run this one was read against and whether the comparison was void. A
        stored diff would be a derived number going stale the moment either side
        was recomputed, and ``baseline_reset`` is a fact about this run that a
        later reader cannot reconstruct once the fixture has moved on again.
        """
        return MappingProxyType(
            {
                "by_category": self._totals_over(
                    EvalCategory, lambda case: case.category.value
                ),
                "by_surface": self._totals_over(
                    EvalSurface, lambda case: case.surface.value
                ),
                # The cross, because the two lanes share categories D and E and
                # one total covering both is where a regression in the nightly
                # artifact hides behind a healthy Turn lane.
                "by_category_surface": self._category_by_surface(),
                "complete": self.complete,
                "stopped_reason": self.stopped_reason,
                # Stored beside the counts because it overrides them. A reader
                # of this row — the baseline query included — cannot reconstruct
                # it from cases, runs and passes: a category can be at 100% of
                # its threshold and still contain the one answer that pointed
                # somewhere.
                "hard_fails": list(self.hard_fails),
                "baseline": (
                    None if self.baseline is None else self.baseline.as_wire()
                ),
            }
        )

    def _category_by_surface(self) -> dict[str, dict[str, dict[str, int]]]:
        """Every category, split by the lane each of its cases ran on.

        Seeded from both enums for the same reason :meth:`_totals_over` is: a
        lane that ran none of a category has to say ``0`` rather than be absent,
        because absent and zero read the same and mean opposite things.
        """
        totals = {
            category.value: {
                surface.value: {"cases": 0, "runs": 0, "passed": 0}
                for surface in EvalSurface
            }
            for category in EvalCategory
        }
        for result in self.results:
            bucket = totals[result.case.category.value][result.case.surface.value]
            bucket["cases"] += 1
            bucket["runs"] += len(result.runs)
            bucket["passed"] += result.passed_runs
        return totals

    def _totals_over(
        self, keys: type[Enum], key_of: Callable[[EvalCase], str]
    ) -> dict[str, dict[str, int]]:
        """Cases, runs and passes bucketed by one dimension.

        Seeded from the whole enum rather than from the results, so a category
        nobody ran reports ``0`` instead of being absent. A missing key and a
        zero read the same to a careless eye and mean opposite things: one is a
        category that failed everything, the other is a category the run never
        reached.
        """
        totals = {
            key.value: {"cases": 0, "runs": 0, "passed": 0} for key in keys
        }
        for result in self.results:
            bucket = totals[key_of(result.case)]
            bucket["cases"] += 1
            bucket["runs"] += len(result.runs)
            bucket["passed"] += result.passed_runs
        return totals


class InProcessCache:
    """The Data Reference and news cache, kept inside the run.

    ``docs/adr/0012``'s fixed-date descriptors are written to Redis so a Widget
    can be replayed a year later. A battery has no year later — it has one
    process — and pointing it at the deployment's Redis would leave eval keys in
    a cache the application serves from. Substituting a cache is not
    substituting the behaviour under test: the descriptor written here is the
    one the tool wrote.

    ``NewsLane`` speaks the same three verbs to it — a get, a ``nx`` set for the
    single flight, and a compare-and-delete script — so they are answered here
    rather than by a second lookalike object. The TTLs are ignored on purpose:
    expiry inside one battery run would be the clock deciding what a case asked,
    which is the thing :data:`FIXTURE_MARKET_STATE` exists to prevent.
    """

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._values.get(key)

    def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool:
        if nx and key in self._values:
            return False
        self._values[key] = value
        return True

    def delete(self, key: str) -> int:
        return 1 if self._values.pop(key, None) is not None else 0

    def eval(self, script: str, keys: list[str] | None = None, args=None, *rest):
        """The one script the news lane runs: release a lock this holder owns.

        Matched by behaviour rather than by parsing Lua — there is exactly one
        script reaching this object, and a Lua interpreter here would be a
        second implementation of something Redis already owns.
        """
        if keys is None:  # redis-py's positional form: eval(script, n, *keys, *args)
            count = int(rest[0]) if rest else 0
            keys = list(rest[1 : 1 + count])
            args = list(rest[1 + count :])
        token = (args or [None])[0]
        for key in keys:
            if self._values.get(key) == token:
                return self.delete(key)
        return 0


def smoke_config(settings: Settings | None = None) -> LLMConfig:
    """The dev route, its models, and a price block of zeros."""
    settings = settings or get_settings()
    base_url = (settings.eval_smoke_base_url or "").strip()
    batch = (settings.eval_smoke_model_batch or "").strip()
    session_model = (settings.eval_smoke_model_session or "").strip()
    missing = [
        name
        for name, value in (
            ("EVAL_SMOKE_BASE_URL", base_url),
            ("EVAL_SMOKE_MODEL_BATCH", batch),
            ("EVAL_SMOKE_MODEL_SESSION", session_model),
        )
        if not value
    ]
    if missing:
        raise EvalMisconfigured(
            "a smoke run needs its own dev route so that it cannot reach the "
            "production model: set " + ", ".join(missing)
        )
    production = llm_config_from_settings(settings)
    return LLMConfig(
        enabled=True,
        route=LLMRoute(
            base_url=base_url, api_key=(settings.eval_smoke_api_key or "").strip()
        ),
        models=MappingProxyType(
            {Workload.BATCH: batch, Workload.SESSION: session_model}
        ),
        pricing=PricingTable(
            version=SMOKE_PRICING_VERSION,
            effective_from=None,
            batch=_FREE,
            session=_FREE,
        ),
        lanes=production.lanes,
        request_timeout_seconds=production.request_timeout_seconds,
    )


def config_for(mode: EvalMode, settings: Settings | None = None) -> LLMConfig:
    """Which route and models this mode runs on. Never both."""
    settings = settings or get_settings()
    if mode is EvalMode.SMOKE:
        return smoke_config(settings)
    config = llm_config_from_settings(settings)
    if not config.route.base_url:
        raise EvalMisconfigured(
            "a gate run needs the production route: LLM_BASE_URL is not set"
        )
    return config


def _refuse_unseated(cases: Sequence[EvalCase], fixture: LoadedFixture) -> None:
    """Refuse a case whose seat this fixture does not fill, before anything is spent.

    A case names a **seat** rather than a ticker, so that a re-freeze moves the
    case with the symbol. The cost of that indirection is this check: a fixture
    that no longer seats a role turns every case about it into a ``KeyError``
    somewhere mid-run, after the cases before it have been paid for.

    Asked of the whole selected battery rather than per case, and before the
    first reservation, because the answer cannot change during a run and the
    point is to fail while it is still free.
    """
    seats = fixture.roles
    orphaned = [
        f"{case.id} ({case.role.value if case.role else 'no seat'})"
        for case in cases
        if case.role is not None and case.role not in seats
    ]
    if orphaned:
        raise EvalMisconfigured(
            "the loaded fixture does not seat every role the battery asks "
            "about: " + ", ".join(orphaned)
        )


@dataclass
class EvalHarness:
    """One battery run, from the loaded fixture to the written ``eval_run``."""

    mode: EvalMode
    fixture: LoadedFixture
    session_factory: Callable[[], Session]
    config: LLMConfig
    client: Any = None
    # How the Analysis lane gets a client, and why it is a factory rather than
    # the one above: the nightly producer runs each generation in an event loop
    # of its own, and an ``httpx`` connection pool bound to a closed loop is the
    # failure that produces. One fresh client per generation, closed after it.
    analysis_client_factory: Callable[[], Any] | None = None
    # How the fixed ops query reaches the **application** store, which is the
    # only database in this file that is not the eval one. Left unset in
    # production and resolved lazily, so importing this module does not open a
    # connection to the store the API serves from.
    ops_session_factory: Callable[[], Session] | None = None
    ops_window_days: int = OPS_WINDOW_DAYS
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    runs_per_case: int = RUNS_PER_CASE
    git_sha: str = "unknown"
    _catalog: Any = field(default=None, init=False, repr=False)
    _store: AgentPersistence = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        universe = Universe(explicit=tuple(self.fixture.seed.manifest.universe_symbols))
        self._store = AgentPersistence(session_factory=self.session_factory)
        cache = InProcessCache()
        self._catalog = IntelligentQuantCatalog(
            session_factory=self.session_factory,
            redis=cache,
            universe_factory=lambda _session: universe,
            # The real lane, bounded by the real mechanism, over the run's own
            # cache. Its clock is frozen so that nothing inside a run goes
            # stale: a battery whose news answer depended on how long the run
            # had been going would be measuring the run's duration.
            news_lane=NewsLane(redis_factory=lambda: cache, clock=lambda: 0.0),
            # The fixture's planted articles, in the raw shape a provider row
            # arrives in, so that ``search_news`` sanitises them itself. Every
            # symbol but the injection seat answers with nothing.
            fetch_news=self.fixture.news_for,
            news_now=self._news_now,
        ).catalog(trace_writer=self._store.record_tool_call)
        if self.client is None:
            self.client = build_client(
                self.config, session_factory=self.session_factory, clock=self.clock
            )
        if self.analysis_client_factory is None:
            self.analysis_client_factory = lambda: build_client(
                self.config, session_factory=self.session_factory, clock=self.clock
            )

    @property
    def tool_catalog_version(self) -> str:
        return str(self._catalog.tool_catalog_version)

    def _news_now(self) -> datetime:
        """The end of the fixture's own Trading Day, as "now" for a news window.

        The last instant of the frozen day rather than the wall clock: every
        planted article is published inside that day, so the narrowest window a
        case can ask for still contains them, and it contains exactly the same
        ones a year from now.
        """
        return datetime.combine(
            self.fixture.trading_day, time.max, tzinfo=VN_TZ
        ).astimezone(timezone.utc)

    async def run(self, cases: Sequence[EvalCase] | None = None) -> EvalRunResult:
        """Run the battery, or stop at the ceiling and report no score."""
        selected = tuple(cases if cases is not None else battery())
        _refuse_unseated(selected, self.fixture)
        versions = running_versions()
        self.fixture.seed.manifest.versions.assert_matches(versions)

        started_at = self.clock()
        run_id = uuid.uuid4()
        model = self.config.model_for(Workload.SESSION)
        self._open_run(run_id, started_at, model, versions)

        spend = SpendIdentity(
            owner_type=OwnerType.EVAL_RUN,
            lane=BudgetLane.EVAL,
            owner_id=str(run_id),
            charge_to_user=False,
        )
        loop = AgentLoop(
            client=self.client, catalog=self._catalog, config=self.config, spend=spend
        )
        # One lane per run, so the cross-sectional rankings are measured once
        # and every Analysis case is ranked against the same sample — which is
        # what one evening's nightly pass does.
        lane = AnalysisLane(
            fixture=self.fixture,
            session_factory=self.session_factory,
            config=self.config,
            build_client=self.analysis_client_factory,
            run_id=str(run_id),
            clock=self.clock,
        )

        results: list[CaseResult] = []
        stopped: EvalBudgetExhausted | None = None
        thread = await self._store.create_thread(
            self.fixture.user_id, title=f"eval {run_id}"
        )
        for case in selected:
            try:
                results.append(await self._run_case(loop, lane, thread.id, case))
            except EvalBudgetExhausted as exhausted:
                stopped = exhausted
                break

        finished_at = self.clock()
        result = EvalRunResult(
            run_id=run_id,
            mode=self.mode,
            route=self.config.route.base_url,
            model=model,
            versions=versions,
            prompt_version=PROMPT_VERSION,
            fixture_version=self.fixture.fixture_version,
            started_at=started_at,
            finished_at=finished_at,
            results=tuple(results),
            complete=stopped is None,
            stopped_reason=None if stopped is None else stopped.reason,
        )
        result = replace(
            result,
            baseline=self._baseline_for(result),
            ops=self._read_ops(finished_at),
        )
        self._close_run(result)
        if stopped is not None:
            logger.error("%s", stopped)
        return result

    def _read_ops(self, now: datetime) -> OpsSnapshot:
        """One read-only look at the live service, and never a reason to fail.

        Taken even for a stopped run and even for a smoke one. The reading is
        about the *field*, so it is equally true whichever mode produced the
        report, and a stopped run is exactly when somebody wants to know what
        production has been doing.

        Every failure is caught. An unreachable application store is a fact
        about this machine's configuration and not about the battery, and a run
        that discarded its scores because a second database was down would be
        throwing away the expensive half to protect the cheap one. What is
        refused is the *other* silence: the snapshot carries the reason, and the
        report prints it where the numbers would have been.
        """
        try:
            factory = self.ops_session_factory or _application_session_factory()
            session = factory()
            try:
                return read_ops_snapshot(
                    session, now=now, window_days=self.ops_window_days
                )
            finally:
                session.close()
        except Exception as failure:  # noqa: BLE001 - see the docstring
            logger.warning("the ops query could not read the application store: %s", failure)
            return OpsSnapshot.unreadable(
                f"{type(failure).__name__}: {failure}",
                now=now,
                window_days=self.ops_window_days,
            )

    def _baseline_for(self, result: EvalRunResult) -> BaselineComparison | None:
        """The last passing gate run this one is read against, where there is one.

        Two kinds of run get no comparison at all, and ``None`` says so rather
        than an empty diff pretending one was made. A **smoke** run has no
        gating value, so a diff beside its numbers would invite exactly the
        comparison the mode exists to forbid. A run that **stopped** has no
        score, and a score is what a diff is between.

        Resolved before this run's own totals are written and excluding its own
        id besides: a baseline is the most recent *previous* passing run, and
        one comparing against itself would report no change forever.
        """
        if not result.gating:
            return None
        session = self.session_factory()
        try:
            baseline = resolve_baseline(session, exclude=result.run_id)
        finally:
            session.close()
        return compare_to_baseline(
            dict(result.category_totals), result.fixture_version, baseline
        )

    async def _run_case(
        self,
        loop: AgentLoop,
        lane: AnalysisLane,
        thread_id: uuid.UUID,
        case: EvalCase,
    ) -> CaseResult:
        symbol = (
            self.fixture.symbol_for(case.role) if case.role is not None else None
        )
        # Rendered once for the case rather than once per run, so all three runs
        # of a case ask the same question — and an Analysis case, whose prompt is
        # empty, renders to nothing and never reaches the Turn lane below.
        prompt = case.render(symbol)
        runs: list[CaseRun] = []
        for index in range(self.runs_per_case):
            if case.surface is EvalSurface.ANALYSIS:
                runs.append(await self._run_analysis_once(lane, case, index))
            else:
                runs.append(
                    await self._run_once(loop, thread_id, case, index, symbol, prompt)
                )
        return CaseResult(case=case, runs=tuple(runs), prompt=prompt)

    async def _run_analysis_once(
        self, lane: AnalysisLane, case: EvalCase, index: int
    ) -> CaseRun:
        """One nightly production of one seat, scored as the row it published.

        Off the event loop thread, because the pipeline underneath is
        synchronous and refuses outright to run on it: it holds a ``Session``,
        owns its transaction boundaries, and bridges to the async provider call
        with an ``asyncio.run`` of its own.
        """
        try:
            artifact = await asyncio.to_thread(lane.run_once, case)
        except AnalysisBudgetExhausted as exhausted:
            raise EvalBudgetExhausted(
                case.id, exhausted.reason, exhausted.detail
            ) from exhausted

        return CaseRun(
            run_index=index,
            score=score_analysis(case, index, artifact),
            answer=artifact.prose,
            status=(
                RunStatus.READY.value if artifact.exists else RunStatus.FAILED.value
            ),
            terminal_reason=artifact.error_code,
            answer_kind=ANALYSIS_ANSWER_KIND,
            # A generation takes no tools and expresses no loop, so this is
            # empty as a fact about the lane rather than as a gap in the record.
            tool_calls=(),
            verdict=artifact.verdict,
            cited_field_ids=artifact.cited_field_ids,
        )

    async def _run_once(
        self,
        loop: AgentLoop,
        thread_id: uuid.UUID,
        case: EvalCase,
        index: int,
        symbol: str | None,
        prompt: str,
    ) -> CaseRun:
        message = await self._store.append_message(
            thread_id,
            role="user",
            content={"text": prompt, "eval_case": case.id, "run": index},
            symbols=(symbol,) if symbol else (),
        )
        request = TurnRequest(
            thread_id=thread_id,
            request_message_id=message.id,
            user_id=self.fixture.user_id,
            user_text=prompt,
            runtime=RuntimeContext(
                user_id=self.fixture.user_id,
                trading_day=self.fixture.trading_day,
                market_state=FIXTURE_MARKET_STATE,
                active_symbol=symbol,
            ),
        )
        try:
            outcome = await loop.run(request)
        except BudgetRefusal as refusal:
            raise EvalBudgetExhausted(
                case.id, refusal.reason, refusal.operator_detail or refusal.message
            ) from refusal

        # The loop swallows a budget refusal into an ``incomplete`` Turn rather
        # than raising — a Turn that cannot fund its next call ends where it is.
        # For a user that is the right answer; for the battery it is the run
        # stopping, because the case that ended early was not measured.
        #
        # Matched against the ledger's own closed set rather than against a
        # string chosen here. Any ceiling that refuses a call leaves a case
        # unmeasured, and which one bound is not this module's to decide.
        if outcome.terminal_reason in BUDGET_REFUSAL_REASONS:
            raise EvalBudgetExhausted(
                case.id,
                str(outcome.terminal_reason),
                "the loop ended the case without funding its next call",
            )

        manifest, assembled = self._assemble(outcome)
        return CaseRun(
            run_index=index,
            score=score_turn(
                case,
                index,
                outcome,
                manifest=manifest,
                message=assembled,
                secrets=self._secrets(),
                universe=self.fixture.universe,
            ),
            answer=str(assembled.get("text", "")),
            status=outcome.status.value,
            terminal_reason=outcome.terminal_reason,
            answer_kind=outcome.answer_kind.value,
            tool_calls=tuple(call.name for call in outcome.tool_calls),
        )

    def _assemble(
        self, outcome: TurnOutcome
    ) -> tuple[EvidenceManifest, Mapping[str, Any]]:
        """The same assistant message a user would have been served.

        Built through the lifecycle's own helpers rather than beside them: a
        lookalike message is how a battery comes to score a shape nobody is
        served.
        """
        blocks, text = rendered_blocks(outcome.blocks)
        manifest = build_manifest(
            git_sha=self.git_sha,
            model=self.config.model_for(Workload.SESSION),
            route=self.config.route.base_url,
            provider_request_id=outcome.provider_request_id,
            tool_catalog_version=self.tool_catalog_version,
            answer_kind=outcome.answer_kind,
            status=outcome.status.value,
            terminal_reason=outcome.terminal_reason,
            citations=outcome.citations,
            outcomes=gate_outcomes(outcome),
        )
        assembled = assemble_message(
            blocks=blocks,
            text=text,
            answer_kind=outcome.answer_kind,
            manifest=manifest,
            citations=outcome.citations,
            widgets=[widget.as_wire() for widget in outcome.widgets],
            widget_refusals=outcome.widget_refusals,
        )
        return manifest, assembled

    def _secrets(self) -> tuple[str, ...]:
        return tuple(value for value in (self.config.route.api_key,) if value)

    def _open_run(
        self,
        run_id: uuid.UUID,
        started_at: datetime,
        model: str,
        versions: PinnedVersions,
    ) -> None:
        """Write the row *before* the first call, not after the last.

        The reservation needs an owner with a non-null id at the moment it is
        taken (``docs/adr/0014``), so a row written at the end would be a row
        the ledger already pointed at.
        """
        session = self.session_factory()
        try:
            with session.begin():
                session.add(
                    EvalRun(
                        id=run_id,
                        started_at=started_at,
                        mode=self.mode.value,
                        route=self.config.route.base_url,
                        model=model,
                        prompt_version=PROMPT_VERSION,
                        tool_catalog_version=self.tool_catalog_version,
                        registry_version=versions.registry_version,
                        fixture_version=self.fixture.fixture_version,
                        category_totals={},
                    )
                )
        finally:
            session.close()

    def _close_run(self, result: EvalRunResult) -> None:
        session = self.session_factory()
        try:
            with session.begin():
                row = session.get(EvalRun, result.run_id)
                if row is None:  # pragma: no cover - written by _open_run
                    return
                row.finished_at = result.finished_at
                # Per-case detail stays in the report file, never in the table
                # (``docs/adr/0016``). What the table earns its cost with is
                # baseline comparison in SQL, and that needs totals.
                row.category_totals = dict(result.category_totals)
                row.report_path = result.report_path
        finally:
            session.close()

    def record_report_path(self, result: EvalRunResult, path: Path) -> EvalRunResult:
        """Stamp the written report onto the run, in the result and the row."""
        stamped = replace(result, report_path=str(path))
        self._close_run(stamped)
        return stamped


def _application_session_factory() -> Callable[[], Session]:
    """The store the API serves from, imported at the moment it is needed.

    Lazily, and only here. Every other database this package touches is the eval
    one, and a module-level import would make ``src.eval`` construct the
    application engine simply by being read.
    """
    from src.core.database import sync_session_factory

    return sync_session_factory


def build_harness(
    *,
    mode: EvalMode,
    seed: FixtureSeed,
    session_factory: Callable[[], Session],
    settings: Settings | None = None,
    config: LLMConfig | None = None,
    client: Any = None,
    git_sha: str | None = None,
    ops_session_factory: Callable[[], Session] | None = None,
    ops_window_days: int | None = None,
) -> EvalHarness:
    """Load the fixture and compose everything one run needs."""
    settings = settings or get_settings()
    fixture = load_fixture(seed, session_factory)
    return EvalHarness(
        mode=mode,
        fixture=fixture,
        session_factory=session_factory,
        config=config or config_for(mode, settings),
        client=client,
        git_sha=git_sha or settings.git_sha,
        ops_session_factory=ops_session_factory,
        ops_window_days=(
            ops_window_days
            if ops_window_days is not None
            else settings.eval_ops_window_days
        ),
    )


__all__ = [
    "ANALYSIS_ANSWER_KIND",
    "FIXTURE_MARKET_STATE",
    "RUNS_PER_CASE",
    "SMOKE_PRICING_VERSION",
    "CaseResult",
    "CaseRun",
    "EvalBudgetExhausted",
    "EvalHarness",
    "EvalMisconfigured",
    "EvalMode",
    "EvalRunResult",
    "InProcessCache",
    "build_harness",
    "config_for",
    "smoke_config",
]
