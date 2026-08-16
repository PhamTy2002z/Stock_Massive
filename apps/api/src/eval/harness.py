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
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from sqlalchemy.orm import Session

from src.agent.loop import AgentLoop, SpendIdentity, TurnOutcome, TurnRequest
from src.agent.manifest import EvidenceManifest, assemble_message, build_manifest
from src.agent.persistence import AgentPersistence
from src.agent.prompt import PROMPT_VERSION, MarketState, RuntimeContext
from src.agent.tools.suite import IntelligentQuantCatalog
from src.agent.turns import gate_outcomes, rendered_blocks
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
from src.stocks.universe import Universe

from .cases import EvalCase, EvalCategory, EvalSurface, battery
from .fixture import FixtureSeed
from .scoring import DeterministicScore, score_turn
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


@dataclass(frozen=True)
class CaseRun:
    """One of the three runs of one case, kept whole."""

    run_index: int
    score: DeterministicScore
    # The verbatim answer, which is one of ``docs/adr/0016``'s three defences
    # against a rubber-stamped human rubric: the text being judged is embedded
    # in the report, so a careless pass leaves a readable trace.
    answer: str
    status: str
    terminal_reason: str | None
    answer_kind: str
    tool_calls: tuple[str, ...]

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
            "answer": self.answer,
            "score": self.score.as_wire(),
        }


@dataclass(frozen=True)
class CaseResult:
    """One case and its three runs."""

    case: EvalCase
    runs: tuple[CaseRun, ...]

    @property
    def passed_runs(self) -> int:
        return sum(1 for run in self.runs if run.passed)

    def as_wire(self) -> dict[str, Any]:
        return {
            "case_id": self.case.id,
            "category": self.case.category.value,
            "surface": self.case.surface.value,
            "prompt": self.case.prompt,
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

    @property
    def gating(self) -> bool:
        """Only a complete gate run may be attached to a pull request."""
        return self.mode.gating and self.complete

    @property
    def category_totals(self) -> Mapping[str, Any]:
        """Per-category cases, runs and passes — and nothing derived.

        Rates are not stored. The thresholds differ by category and the hard
        fail on a backwards sign overrides every rate (``docs/adr/0016``), so a
        stored percentage would be a number two later readers would disagree
        about the meaning of. Counts are what both of them can compute from.
        """
        return MappingProxyType(
            {
                "by_category": self._totals_over(
                    EvalCategory, lambda case: case.category.value
                ),
                "by_surface": self._totals_over(
                    EvalSurface, lambda case: case.surface.value
                ),
                "complete": self.complete,
                "stopped_reason": self.stopped_reason,
            }
        )

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
    """The Data Reference cache, kept inside the run.

    ``docs/adr/0012``'s fixed-date descriptors are written to Redis so a Widget
    can be replayed a year later. A battery has no year later — it has one
    process — and pointing it at the deployment's Redis would leave eval keys in
    a cache the application serves from. Substituting a cache is not
    substituting the behaviour under test: the descriptor written here is the
    one the tool wrote.
    """

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._values.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._values[key] = value
        return True


def _no_news(symbol: str) -> Sequence[Mapping[str, Any]]:  # pragma: no cover
    """Never reached: the lane refuses before a fetch is attempted.

    Present so that no configuration of this harness can end up holding the
    live VCI fetcher. A battery that read today's news would be a battery on
    live data, which is the one thing the frozen fixture exists to prevent.
    """
    return ()


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


def _refuse_unrunnable(cases: Sequence[EvalCase]) -> None:
    """Refuse a case this harness has no lane for, before anything is spent.

    Only the Turn lane exists here. The Analysis lane runs the nightly pipeline
    over the same fixture and is issue #97; its cases carry no prompt, so
    running one through :meth:`EvalHarness._run_once` would ask the model a
    blank question and score whatever came back. Loud, and named, because a
    silent blank Turn would land in the report as an ordinary failure.
    """
    orphaned = [case.id for case in cases if case.surface is not EvalSurface.TURN]
    if orphaned:
        raise EvalMisconfigured(
            "this harness runs the Turn lane only; the Analysis lane is #97. "
            "Refusing: " + ", ".join(orphaned)
        )


@dataclass
class EvalHarness:
    """One battery run, from the loaded fixture to the written ``eval_run``."""

    mode: EvalMode
    fixture: LoadedFixture
    session_factory: Callable[[], Session]
    config: LLMConfig
    client: Any = None
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    runs_per_case: int = RUNS_PER_CASE
    git_sha: str = "unknown"
    _catalog: Any = field(default=None, init=False, repr=False)
    _store: AgentPersistence = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        universe = Universe(explicit=tuple(self.fixture.seed.manifest.universe_symbols))
        self._store = AgentPersistence(session_factory=self.session_factory)
        self._catalog = IntelligentQuantCatalog(
            session_factory=self.session_factory,
            redis=InProcessCache(),
            universe_factory=lambda _session: universe,
            # No Redis means no cache, no single flight and no lane, and the
            # lane fails closed rather than making the unbounded live call. The
            # fixture's own news lands with the injection category (#95); until
            # then "news refused" is the fixture's honest answer and is itself
            # one of category E's data gaps.
            news_lane=NewsLane(redis_factory=lambda: None),
            fetch_news=_no_news,
        ).catalog(trace_writer=self._store.record_tool_call)
        if self.client is None:
            self.client = build_client(
                self.config, session_factory=self.session_factory, clock=self.clock
            )

    @property
    def tool_catalog_version(self) -> str:
        return str(self._catalog.tool_catalog_version)

    async def run(self, cases: Sequence[EvalCase] | None = None) -> EvalRunResult:
        """Run the battery, or stop at the ceiling and report no score."""
        selected = tuple(cases if cases is not None else battery())
        _refuse_unrunnable(selected)
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

        results: list[CaseResult] = []
        stopped: EvalBudgetExhausted | None = None
        thread = await self._store.create_thread(
            self.fixture.user_id, title=f"eval {run_id}"
        )
        for case in selected:
            try:
                results.append(await self._run_case(loop, thread.id, case))
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
        self._close_run(result)
        if stopped is not None:
            logger.error("%s", stopped)
        return result

    async def _run_case(
        self, loop: AgentLoop, thread_id: uuid.UUID, case: EvalCase
    ) -> CaseResult:
        runs: list[CaseRun] = []
        for index in range(self.runs_per_case):
            runs.append(await self._run_once(loop, thread_id, case, index))
        return CaseResult(case=case, runs=tuple(runs))

    async def _run_once(
        self, loop: AgentLoop, thread_id: uuid.UUID, case: EvalCase, index: int
    ) -> CaseRun:
        symbol = (
            self.fixture.symbol_for(case.role) if case.role is not None else None
        )
        message = await self._store.append_message(
            thread_id,
            role="user",
            content={"text": case.prompt, "eval_case": case.id, "run": index},
            symbols=(symbol,) if symbol else (),
        )
        request = TurnRequest(
            thread_id=thread_id,
            request_message_id=message.id,
            user_id=self.fixture.user_id,
            user_text=case.prompt,
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


def build_harness(
    *,
    mode: EvalMode,
    seed: FixtureSeed,
    session_factory: Callable[[], Session],
    settings: Settings | None = None,
    config: LLMConfig | None = None,
    client: Any = None,
    git_sha: str | None = None,
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
    )


__all__ = [
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
