"""The second surface: the nightly pipeline, run over the same Eval Fixture.

**The pipeline is the deployed one.** ``produce_analysis`` owns the lifecycle,
``analysis_producer`` assembles the envelope, and ``generate_fragment`` makes the
single strict structured-output call with its own semantic validation. Nothing
here is an eval-only branch through any of them: what this module supplies is
the same three things the Turn lane supplies — the eval database, a fixed
Trading Day, and an owner for the spend.

**Every generation is charged to the ``eval_run``.** The nightly path names the
Analysis Run as its owner, which is right in production and wrong here: the
battery's ceiling is $2.5 per run and it is enforced against
``owner_type = 'eval_run'`` (``docs/adr/0014``, ``docs/adr/0016``). So the spend
is redirected at the client boundary rather than by branching inside the
producer — see :class:`EvalOwnedClient`, which asks admission the production
per-call questions *first* and only then changes the owner. Skipping that would
let the battery admit an envelope production would have refused.

**A case runs three times, so the pair is reset three times.** The fixture is a
photograph of a real store and carries the ``analysis`` rows that store held, and
production is idempotent per ``(symbol, trading_day)`` — so without clearing the
pair, run one would find the captured Analysis and runs two and three would find
run one's. Three runs of a case have to be three generations, and the eval
database is disposable precisely so that clearing them costs nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from src.alpha.analysis_run import RunOrigin, RunStatus, produce_analysis
from src.alpha.models import Analysis, AnalysisRun
from src.alpha.production import analysis_producer
from src.core.llm import (
    BudgetLane,
    BudgetRefusal,
    CallOwner,
    Completion,
    CompletionRequest,
    LLMClient,
    LLMConfig,
    OwnerType,
    SpendRequest,
    check_candidate_shape,
)
from src.stocks.signals.serving import CrossSection

from .artifact import AnalysisArtifact
from .cases import EvalCase
from .store import LoadedFixture


class EvalOwnedClient:
    """The production client, with every reservation charged to the ``eval_run``.

    A wrapper rather than a parameter threaded through the producer, because the
    Analysis path has no equivalent of the Turn loop's ``SpendIdentity`` and
    inventing one would put an eval-shaped hole in three production signatures
    for a fact only the battery needs.

    Two things it must not lose, and both are why this is more than a ``replace``:

    *The production per-call ceilings.* They are keyed on the Analysis Run owner
    inside admission, so redirecting the owner first would silently exempt the
    battery from the ≤6,000-token input rule. :func:`check_candidate_shape` is
    asked of the **original** spend, so an envelope the nightly pass would refuse
    is refused here too.

    *Which ceiling bound.* A refusal is recorded before it is re-raised, because
    the producer turns it into a ``ProductionFailure`` whose code says
    ``budget_exhausted`` and whose reason has been flattened into a sentence. The
    battery has to stop on an exhausted ceiling rather than score the cases that
    follow, and it cannot decide that from prose.

    Note where the two live relative to the ``try``. :func:`check_candidate_shape`
    runs **outside** it, so a refusal from the production per-call ceilings is
    never recorded as a ceiling that bound the *battery* — an envelope too large
    for one generation is a case the pipeline correctly refused, and stopping the
    whole run over it would drop the cases that come after for a defect in this
    one. Only a refusal from admission, under the ``eval_run`` owner, is a
    ceiling this run has hit.

    The inner client is built per call, and that is not thrift. The nightly
    producer runs each generation in an event loop of its own (``asyncio.run``),
    and an ``httpx.AsyncClient`` binds its connection pool to the loop that first
    used it — so one client held across three runs would be a pool bound to a
    loop that has closed.
    """

    def __init__(self, build: Callable[[], LLMClient], owner_id: str) -> None:
        self._build = build
        self._owner_id = owner_id
        self.refusal: BudgetRefusal | None = None

    async def complete(
        self, request: CompletionRequest, spend: SpendRequest | None = None
    ) -> Completion:
        if spend is not None:
            check_candidate_shape(spend)
            spend = replace(
                spend,
                owner=CallOwner(type=OwnerType.EVAL_RUN, id=self._owner_id),
                lane=BudgetLane.EVAL,
            )
        client = self._build()
        try:
            return await client.complete(request, spend)
        except BudgetRefusal as refused:
            self.refusal = refused
            raise
        finally:
            # ``build`` returns a fresh client every time, so closing it here is
            # the only place it can be closed: the loop it was used in is about
            # to end, and a pool outliving its loop is the bug this guards.
            await client.aclose()

    async def aclose(self) -> None:  # pragma: no cover - nothing is held open
        return None


class AnalysisBudgetExhausted(RuntimeError):
    """A generation could not be funded, so the lane cannot measure this case."""

    def __init__(self, case_id: str, refusal: BudgetRefusal) -> None:
        self.case_id = case_id
        self.reason = refusal.reason
        self.detail = refusal.operator_detail or refusal.message
        super().__init__(f"{self.reason} at case {case_id}: {self.detail}")


@dataclass
class AnalysisLane:
    """One battery run's worth of nightly production over the fixture."""

    fixture: LoadedFixture
    session_factory: Callable[[], Session]
    config: LLMConfig
    build_client: Callable[[], LLMClient]
    run_id: str
    # Set once per lane and shared by every case, exactly as one evening's
    # nightly pass shares them: a percentile is a position within a sample, so
    # measuring it per case would rank each symbol against a sample measured at
    # a different moment.
    cross_sections: Mapping[str, CrossSection] | None = None
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    _client: EvalOwnedClient = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = EvalOwnedClient(self.build_client, self.run_id)

    @property
    def trading_day(self) -> date:
        return self.fixture.trading_day

    def run_once(self, case: EvalCase) -> AnalysisArtifact:
        """Produce this seat's Analysis once, and hand back what it left behind.

        Synchronous, because the lifecycle it drives is: ``produce_analysis``
        holds a ``Session`` and owns its own transaction boundaries, and the
        producer refuses outright to run on the event loop thread. The harness
        calls this through ``asyncio.to_thread`` for that reason.
        """
        assert case.role is not None  # refused at construction
        symbol = self.fixture.symbol_for(case.role)
        # Cleared per run rather than trusted to be empty. A ceiling stops the
        # whole battery, so in practice this is only ever ``None`` here — but a
        # refusal left over from a previous case would attribute that stop to
        # the wrong one, and the attribution is the whole value of the field.
        self._client.refusal = None
        self._clear_pair(symbol)

        session = self.session_factory()
        try:
            outcome = produce_analysis(
                session,
                symbol,
                self.trading_day,
                self._producer(),
                origin=RunOrigin.NIGHTLY,
            )
        finally:
            session.close()

        if self._client.refusal is not None:
            # The producer flattens a refused reservation into a
            # ``ProductionFailure`` whose message is prose, so the reason is
            # taken from the refusal itself. Any ceiling that refused a call
            # leaves this case unmeasured, and which one bound is not this
            # module's to decide.
            raise AnalysisBudgetExhausted(case.id, self._client.refusal)

        if outcome.status is RunStatus.READY and outcome.analysis is not None:
            return AnalysisArtifact.published(
                symbol=symbol,
                trading_day=self.trading_day,
                verdict=str(outcome.analysis.verdict),
                payload=dict(outcome.analysis.payload or {}),
            )
        return AnalysisArtifact.unpublished(
            symbol=symbol,
            trading_day=self.trading_day,
            error_code=outcome.error_code,
            error_message=outcome.error_message,
        )

    def _producer(self):
        return analysis_producer(
            client=self._client,
            config=self.config,
            session_factory=self.session_factory,
            clock=self.clock,
            cross_sections=self.cross_sections,
        )

    def _clear_pair(self, symbol: str) -> None:
        """Forget that this pair was ever produced, so the next run produces.

        Both rows, and in one transaction. An ``analysis`` row left behind makes
        ``produce_analysis`` a no-op that returns the previous run's artifact,
        and an ``analysis_run`` row left behind carries the attempt count into
        the next run and locks the third one out at the three-attempt ceiling.

        Only the pair, never the table. The fixture's other Analyses are part of
        the photograph — the rail reads them — and clearing them would make the
        store the battery runs against depend on the order the cases ran in.
        """
        session = self.session_factory()
        try:
            with session.begin():
                session.execute(
                    delete(Analysis).where(
                        Analysis.symbol == symbol,
                        Analysis.trading_day == self.trading_day,
                    )
                )
                session.execute(
                    delete(AnalysisRun).where(
                        AnalysisRun.symbol == symbol,
                        AnalysisRun.trading_day == self.trading_day,
                    )
                )
        finally:
            session.close()


__all__ = [
    "AnalysisBudgetExhausted",
    "AnalysisLane",
    "EvalOwnedClient",
]
