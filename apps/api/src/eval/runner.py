"""Typed replay runner over the real Conversation and Analysis lifecycles."""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agent.loop import AgentLoop
from src.agent.prompt import RuntimeContext
from src.agent.registry import ToolEntry
from src.agent.turns import TurnService
from src.alpha.analysis_run import (
    RunStatus,
    produce_analysis,
    published_analysis,
    stored_run,
)
from src.alpha.models import AnalysisToolCall
from src.alpha.production import analysis_producer
from src.core.llm import BudgetRefusal, LLMConfig, Workload

from .contracts import CaseFile, SnapshotFile, TrajectoryEvent, TrialOutcome
from .recording import (
    LiveEvalLLMClient,
    RecordingLLMClient,
    RecordingTraceWriter,
    ScriptedLLMClient,
    TrajectoryRecorder,
    sanitize_artifact,
    tool_trace_projection,
)
from .world import FixtureWorld

SessionFactory = Callable[[], Session]
Clock = Callable[[], datetime]
Mode = Literal["smoke", "live"]


class LiveModeNotAuthorized(ValueError):
    """A paid replay omitted or contradicted its explicit authorization."""


class EvaluationStopped(RuntimeError):
    """An eval-only deadline or cancellation stopped an Analysis at the model seam."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class LiveAuthorization:
    route: str
    ceiling_usd: float


@dataclass(frozen=True)
class ObservableOutcome:
    surface: Literal["conversation", "analysis"]
    lifecycle_status: str
    terminal_reason: str | None
    persisted_id: str | None
    content: Mapping[str, Any]


@dataclass(frozen=True)
class EvalResult:
    trial: TrialOutcome
    observable: ObservableOutcome
    trajectory: tuple[TrajectoryEvent, ...]
    provider_access_attempts: tuple[str, ...] = ()
    scope_violations: tuple[str, ...] = ()


class _RunCeilingClient:
    """Refuse before delegation when worst-case reservations exceed the run cap."""

    def __init__(self, client: Any, *, config: LLMConfig, ceiling_usd: float) -> None:
        self._client = client
        self._config = config
        self._ceiling = ceiling_usd
        self._reserved = 0.0

    async def complete(self, request: Any, spend: Any = None) -> Any:
        if spend is None:
            raise ValueError("a live eval call needs a SpendRequest")
        prices = self._config.prices_for(spend.workload)
        requested = prices.cost_usd(
            input_tokens=spend.input_tokens,
            output_tokens=spend.output_tokens,
        )
        if self._reserved + requested > self._ceiling:
            raise BudgetRefusal(
                "eval_run_ceiling",
                "The explicit evaluation run ceiling is exhausted.",
                operator_detail=(
                    f"reserved={self._reserved:.6f} requested={requested:.6f} "
                    f"ceiling={self._ceiling:.6f}"
                ),
            )
        self._reserved += requested
        return await self._client.complete(request, spend)


class _StopSignal:
    """A thread-safe, first-reason-wins stop signal shared with Analysis."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._reason: str | None = None
        self._lock = threading.Lock()

    def stop(self, reason: str) -> None:
        with self._lock:
            if not self._event.is_set():
                self._reason = reason
                self._event.set()

    @property
    def reason(self) -> str | None:
        return self._reason if self._event.is_set() else None


class _StoppableClient:
    """Cancel an in-flight model await so the Analysis worker can unwind cleanly."""

    def __init__(self, client: Any, signal: _StopSignal) -> None:
        self._client = client
        self._signal = signal

    async def complete(self, request: Any, spend: Any = None) -> Any:
        if self._signal.reason is not None:
            raise EvaluationStopped(self._signal.reason)
        pending = asyncio.create_task(self._client.complete(request, spend))
        try:
            while True:
                done, _ = await asyncio.wait({pending}, timeout=0.01)
                if pending in done:
                    return await pending
                if self._signal.reason is not None:
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)
                    raise EvaluationStopped(self._signal.reason)
        except BaseException:
            if not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
            raise


class _ProtocolGuardClient:
    """Reject ambiguous model-issued tool call identifiers before dispatch."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def complete(self, request: Any, spend: Any = None) -> Any:
        completion = await self._client.complete(request, spend)
        call_ids = [str(call.id or "") for call in completion.tool_calls]
        if any(not call_id for call_id in call_ids):
            from src.core.llm import MalformedArguments

            raise MalformedArguments(
                "the route produced a tool call without an identifier",
                usage=completion.usage,
            )
        if len(call_ids) != len(set(call_ids)):
            from src.core.llm import MalformedArguments

            raise MalformedArguments(
                "the route produced duplicate tool-call identifiers",
                usage=completion.usage,
            )
        return completion


class _OwnerLoopClient:
    """Keep a loop-bound live client on the loop that owns its transport."""

    def __init__(self, client: Any, owner_loop: asyncio.AbstractEventLoop) -> None:
        self._client = client
        self._owner_loop = owner_loop

    async def complete(self, request: Any, spend: Any = None) -> Any:
        submitted = asyncio.run_coroutine_threadsafe(
            self._client.complete(request, spend), self._owner_loop
        )
        try:
            return await asyncio.wrap_future(submitted)
        except BaseException:
            submitted.cancel()
            raise


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EvalRunner:
    """Dispatch one case and normalize only its persisted public outcome."""

    def __init__(
        self,
        *,
        config: LLMConfig,
        session_factory: SessionFactory,
        clock: Clock = _utcnow,
        deadline_seconds: float = 120.0,
    ) -> None:
        self._config = config
        self._session_factory = session_factory
        self._clock = clock
        self._deadline = deadline_seconds

    async def run(
        self,
        *,
        case: CaseFile,
        snapshots: Sequence[SnapshotFile],
        tool_catalog: Sequence[ToolEntry],
        client: Any,
        run_id: str,
        trial_index: int,
        mode: Mode = "smoke",
        live_authorization: LiveAuthorization | None = None,
        cancel_after_seconds: float | None = None,
    ) -> EvalResult:
        self._authorize(mode, client, live_authorization)
        started_at = self._clock()
        started = time.monotonic()
        recorder = TrajectoryRecorder(clock=self._clock)
        if isinstance(client, ScriptedLLMClient):
            client.with_admission(
                config=self._config,
                session_factory=self._session_factory,
                clock=self._clock,
            )
        guarded = client
        if live_authorization is not None:
            guarded = _RunCeilingClient(
                guarded,
                config=self._config,
                ceiling_usd=live_authorization.ceiling_usd,
            )
        guarded = _ProtocolGuardClient(guarded)
        stop_signal = _StopSignal() if case.surface == "analysis" else None
        timers: list[asyncio.Task[Any]] = []
        if stop_signal is not None:
            guarded = _StoppableClient(guarded, stop_signal)

            async def stop_after(seconds: float, reason: str) -> None:
                await asyncio.sleep(max(0.0, seconds))
                stop_signal.stop(reason)

            timers.append(
                asyncio.create_task(stop_after(self._deadline, "analysis_deadline"))
            )
            if cancel_after_seconds is not None:
                timers.append(
                    asyncio.create_task(
                        stop_after(cancel_after_seconds, "evaluation_cancelled")
                    )
                )
        recording = RecordingLLMClient(guarded, recorder=recorder)
        world = FixtureWorld(
            case=case,
            snapshots=snapshots,
            session_factory=self._session_factory,
            tool_catalog=tool_catalog,
            clock=self._clock,
            stop_reason=(
                None if stop_signal is None else lambda: stop_signal.reason
            ),
        )

        try:
            with world:
                if case.surface == "conversation":
                    observable = await self._run_conversation(
                        case,
                        world,
                        recording,
                        recorder,
                        cancel_after_seconds=cancel_after_seconds,
                    )
                    recorder.order_existing_tool_events()
                else:
                    assert stop_signal is not None
                    observable = await self._run_analysis(
                        case, world, recording, recorder, stop_signal
                    )

                observable = ObservableOutcome(
                    surface=observable.surface,
                    lifecycle_status=observable.lifecycle_status,
                    terminal_reason=observable.terminal_reason,
                    persisted_id=observable.persisted_id,
                    content=dict(sanitize_artifact(observable.content)),
                )
                if world.provider_access_attempts or world.scope_violations:
                    terminal = "incomplete"
                    reason = (
                        "provider_source_access_forbidden"
                        if world.provider_access_attempts
                        else "fixture_scope_violation"
                    )
                    observable = ObservableOutcome(
                        surface=observable.surface,
                        lifecycle_status=observable.lifecycle_status,
                        terminal_reason=reason,
                        persisted_id=observable.persisted_id,
                        content=observable.content,
                    )
                else:
                    terminal = self._terminal_for(observable)

                recorder.emit(
                    "terminal",
                    {
                        "status": terminal,
                        "lifecycle_status": observable.lifecycle_status,
                        "terminal_reason": observable.terminal_reason,
                    },
                )
        finally:
            for timer in timers:
                timer.cancel()
            if timers:
                await asyncio.gather(*timers, return_exceptions=True)

        finished_at = self._clock()
        elapsed_ms = max(0, round((time.monotonic() - started) * 1_000))
        workload = (
            Workload.SESSION if case.surface == "conversation" else Workload.BATCH
        )
        usage = recording.usage
        cost = None
        if recording.usage_known:
            cost = self._config.prices_for(workload).cost_usd(
                input_tokens=usage.input_tokens,
                cached_input_tokens=usage.cached_input_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                output_tokens=usage.output_tokens,
                reasoning_tokens=usage.reasoning_tokens,
            )
        events = recorder.events
        trial = TrialOutcome(
            schema="eval.trial@1",
            run_id=run_id,
            case_id=case.case_id,
            trial_index=trial_index,
            started_at=started_at,
            finished_at=finished_at,
            terminal=terminal,
            usage_tokens=usage.total_tokens,
            usage_known=recording.usage_known,
            cost_usd=cost,
            latency_ms=elapsed_ms,
            tool_calls=sum(event.kind == "tool_call" for event in events),
        )
        return EvalResult(
            trial=trial,
            observable=observable,
            trajectory=events,
            provider_access_attempts=tuple(world.provider_access_attempts),
            scope_violations=tuple(world.scope_violations),
        )

    def _authorize(
        self,
        mode: Mode,
        client: Any,
        authorization: LiveAuthorization | None,
    ) -> None:
        if mode not in ("smoke", "live"):
            raise ValueError(f"unknown eval mode {mode!r}")
        if mode == "smoke":
            if authorization is not None:
                raise LiveModeNotAuthorized(
                    "offline smoke does not accept live authorization"
                )
            if not bool(getattr(client, "offline", False)):
                raise LiveModeNotAuthorized("offline smoke requires a scripted client")
            return
        if authorization is None:
            raise LiveModeNotAuthorized(
                "live eval requires an explicit route and run ceiling"
            )
        if not isinstance(client, LiveEvalLLMClient):
            raise LiveModeNotAuthorized(
                "live eval requires a case-local LiveEvalLLMClient"
            )
        if not client.belongs_to(
            config=self._config, session_factory=self._session_factory
        ):
            raise LiveModeNotAuthorized(
                "live eval client pricing and ledger must belong to this runner"
            )
        if client.route != authorization.route:
            raise LiveModeNotAuthorized(
                "live eval client route does not match its authorization"
            )
        if authorization.route != self._config.route.base_url:
            raise LiveModeNotAuthorized(
                "live eval authorization route does not match configured route"
            )
        if authorization.ceiling_usd <= 0:
            raise LiveModeNotAuthorized("live eval ceiling must be positive")

    async def _run_conversation(
        self,
        case: CaseFile,
        world: FixtureWorld,
        client: RecordingLLMClient,
        recorder: TrajectoryRecorder,
        *,
        cancel_after_seconds: float | None,
    ) -> ObservableOutcome:
        assert world.user_id is not None
        thread = await world.store.create_thread(world.user_id, title=case.title)
        world.bind_thread(thread.id)
        trace = RecordingTraceWriter(
            world.store.record_tool_call,
            recorder=recorder,
            argument_allowlists=world.argument_allowlists,
        )
        operation_timeout = max(0.001, self._deadline / 2)

        def loop_factory(*, checkpoint: Any, publisher: Any) -> AgentLoop:
            return AgentLoop(
                client=client,
                config=self._config,
                toolsets=world.toolsets,
                checkpoint=checkpoint,
                publisher=publisher,
                trace=trace,
                clock=self._clock,
                call_timeout_seconds=operation_timeout,
                tool_timeout_seconds=operation_timeout,
                deadline_seconds=self._deadline,
            )

        service = TurnService(
            store=world.store,
            loop_factory=loop_factory,
            config=self._config,
            deadline_seconds=self._deadline,
        )
        turn_id = uuid.uuid4()
        cancellation: asyncio.Task[Any] | None = None
        try:
            handle = await service.create(
                user_id=world.user_id,
                thread_id=thread.id,
                turn_id=turn_id,
                user_text=case.input.prompt or "",
                runtime=RuntimeContext(
                    today=case.as_of,
                    user_name=(
                        None
                        if case.user_context is None
                        else case.user_context.display_name
                    ),
                ),
                symbols=tuple(
                    dict.fromkeys(
                        evidence.entity.upper()
                        for snapshot in world.snapshots
                        for evidence in snapshot.evidence
                        if 3 <= len(evidence.entity) <= 10
                    )
                ),
            )
            running = service.running(handle.turn.id)
            if running is None or running.task is None:
                raise RuntimeError("new eval Turn did not own an execution task")
            if cancel_after_seconds is not None:
                async def request_cancel() -> None:
                    await asyncio.sleep(max(0.0, cancel_after_seconds))
                    await service.cancel(world.user_id or 0, turn_id)

                cancellation = asyncio.create_task(request_cancel())
            await asyncio.wait_for(running.task, timeout=self._deadline + 1)
            settled = await world.store.read_turn(world.user_id, turn_id)
            view = await world.store.read_thread(world.user_id, thread.id)
            if settled is None or view is None:
                raise RuntimeError("settled eval Turn is not readable")
            assistant = next(
                (
                    message
                    for message in view.messages
                    if message.id == settled.response_message_id
                ),
                None,
            )
            content = {} if assistant is None else dict(assistant.content)
            checkpoint_text = str((settled.draft_content or {}).get("text") or "")
            if assistant is not None and checkpoint_text != str(content.get("text") or ""):
                raise RuntimeError("Turn checkpoint and persisted assistant message disagree")
            return ObservableOutcome(
                surface="conversation",
                lifecycle_status=settled.status,
                terminal_reason=settled.terminal_reason,
                persisted_id=(
                    None
                    if settled.response_message_id is None
                    else str(settled.response_message_id)
                ),
                content=content,
            )
        finally:
            if cancellation is not None and not cancellation.done():
                cancellation.cancel()
                await asyncio.gather(cancellation, return_exceptions=True)
            await service.shutdown(timeout=0)

    async def _run_analysis(
        self,
        case: CaseFile,
        world: FixtureWorld,
        client: RecordingLLMClient,
        recorder: TrajectoryRecorder,
        stop_signal: _StopSignal,
    ) -> ObservableOutcome:
        symbol = case.input.symbol or ""
        trading_day = case.input.trading_day
        if trading_day is None:
            raise ValueError("an analysis eval case needs trading_day")
        owner_loop = asyncio.get_running_loop()
        producer = analysis_producer(
            client=_OwnerLoopClient(client, owner_loop),
            config=self._config,
            session_factory=self._session_factory,
            clock=self._clock,
            cross_sections={},
            evidence_loop=True,
        )

        def execute() -> Any:
            with self._session_factory() as session:
                return produce_analysis(session, symbol, trading_day, producer)

        outcome = None
        runner_failure: str | None = None
        worker = asyncio.create_task(asyncio.to_thread(execute))
        try:
            outcome = await asyncio.shield(worker)
        except asyncio.CancelledError as cancelled:
            stop_signal.stop("evaluation_cancelled")
            current = asyncio.current_task()
            if current is not None:
                while current.cancelling():
                    current.uncancel()
            await asyncio.gather(worker, return_exceptions=True)
            raise cancelled
        except EvaluationStopped as exc:
            runner_failure = exc.reason
        except Exception as exc:  # noqa: BLE001 - normalize the persisted state
            runner_failure = f"analysis_runner_exception:{type(exc).__name__}"
        with self._session_factory() as session:
            run = stored_run(session, symbol, trading_day)
            trace_rows = ()
            if run is not None:
                trace_rows = tuple(
                    session.execute(
                        select(AnalysisToolCall)
                        .where(AnalysisToolCall.run_id == run.id)
                        .order_by(
                            AnalysisToolCall.round_index.asc(),
                            AnalysisToolCall.seq.asc(),
                        )
                    ).scalars()
                )
            recorder.interleave_tool_events(
                tuple(
                    (
                        None if row.tool_call_id is None else str(row.tool_call_id),
                        tool_trace_projection(
                            {
                                "tool_call_id": row.tool_call_id,
                                "tool_name": row.tool_name,
                                "arguments": row.arguments,
                                "result": row.result,
                                "status": row.status,
                                "outcome": None,
                                "latency_ms": row.latency_ms,
                                "error": row.error,
                            },
                            argument_allowlist=world.argument_allowlists.get(
                                row.tool_name, frozenset()
                            ),
                        ),
                        row.started_at,
                    )
                    for row in trace_rows
                )
            )
            analysis = (
                outcome.analysis
                if outcome is not None
                else published_analysis(session, symbol, trading_day)
            )
            content = {} if analysis is None else dict(analysis.payload)
            return ObservableOutcome(
                surface="analysis",
                lifecycle_status=(
                    outcome.status.value
                    if outcome is not None
                    else "failed"
                    if run is None
                    else str(run.status)
                ),
                terminal_reason=(
                    outcome.error_code if outcome is not None else runner_failure
                ),
                persisted_id=None if analysis is None else str(analysis.id),
                content=content,
            )

    @staticmethod
    def _terminal_for(observable: ObservableOutcome) -> str:
        if observable.terminal_reason == "evaluation_cancelled":
            return "cancelled"
        if observable.surface == "conversation":
            return {
                "complete": "completed",
                "incomplete": "incomplete",
                "cancelled": "cancelled",
            }.get(observable.lifecycle_status, "failed")
        return (
            "completed"
            if observable.lifecycle_status == RunStatus.READY.value
            else "failed"
            if observable.lifecycle_status == RunStatus.FAILED.value
            else "incomplete"
        )


__all__ = [
    "EvalResult",
    "EvalRunner",
    "EvaluationStopped",
    "LiveAuthorization",
    "LiveModeNotAuthorized",
    "ObservableOutcome",
]
