"""The hand-rolled agent loop over ``LLMClient`` (``docs/adr/0008``).

No framework: not LangGraph, not pydantic-ai, not the Agents SDK, not
``tool_runner``.  There is no graph to orchestrate — the twelve tools are plain
functions — and every framework marries one client abstraction, precisely where
the ``LLMClient`` boundary already exists for three other reasons.  The cost is
stated plainly: dispatch, retry, trimming and streaming are ours, and so is
correctness.  This module is where we pay it.

Four properties are worth reading the code for.

**The id assertion.**  Parallel calls dispatch through ``asyncio.gather`` so one
failing tool does not kill the round, and every result is matched back to its
own ``tool_call_id`` before it goes near the model.  A gateway was *measured*
keying streamed tool calls on a counter instead of the upstream
``output_index``, concatenating two calls' arguments into invalid JSON under the
wrong id while returning 200.  That class of failure never surfaces at runtime;
it only makes the answers wrong.  So a mismatched, missing or repeated id is a
:class:`ToolCallIdMismatch` — a ``malformed_arguments``, raised immediately.

**Rounds, not calls.**  Eight tool-call rounds per Turn.  On the ceiling one
further call with ``tool_choice="none"`` lets the model answer from what it has,
and the transcript says all eight lookup steps were used — information, not an
error.  An answer built on incomplete data beats a blank one, provided its
incompleteness is visible.

**No apology call.**  A Turn that cannot fund its next call ends where it is,
with its partial message and the traces of what ran.  Spending a call to
apologise for having no budget is the one thing that must not happen here.

**Nothing is disabled automatically.**  ``malformed_arguments`` is counted and
logged loudly; an operator flips ``alpha_desk_enabled`` by hand.  A cutoff that
fires on two errors is a mechanism that can cause its own outage.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from typing import Any

from src.core.llm import (
    AuthUnavailable,
    BudgetLane,
    BudgetRefusal,
    CallOwner,
    Completion,
    CompletionRequest,
    GatewayTimeout,
    LLMClient,
    LLMConfig,
    LLMError,
    MalformedArguments,
    Message,
    ModelRefusal,
    OwnerType,
    Role,
    SpendRequest,
    ToolAttempts,
    ToolCall,
    Usage,
    Workload,
    llm_metrics,
    tool_error_result,
)

from .context import (
    ConstructedContext,
    ContextBudget,
    Transcript,
    TranscriptToolCall,
    TranscriptTurn,
    build_messages,
    estimate_tokens,
)
from .prompt import AnswerEvidence, AnswerKind, RuntimeContext, classify_answer_kind, render
from .tools.catalog import ToolCatalog, ToolContext

logger = logging.getLogger(__name__)

# ``docs/specs/0003`` §6: counted by round, so a round that fans out to five
# tools costs the same one step as a round that calls one.
MAX_TOOL_ROUNDS = 8

# ``docs/adr/0008``: in-process is correct because uvicorn runs a single worker.
SESSION_CONCURRENCY = 3

# Well inside the ≤20,000 aggregate output the Turn is admitted against, so a
# Turn has room for several rounds rather than one expensive one.
DEFAULT_MAX_OUTPUT_TOKENS = 2_000

ROUNDS_EXHAUSTED_NOTE = (
    f"All {MAX_TOOL_ROUNDS} lookup rounds for this Turn have been used. Answer from "
    "the evidence already gathered, and state plainly which evidence you were not "
    "able to obtain."
)

TOOL_EXHAUSTED_MESSAGE = (
    "this tool has already failed twice in this Turn and will not be called again; "
    "take a different approach or say what is missing"
)


class SessionCapacityExceeded(RuntimeError):
    """The 4th concurrent session, refused rather than queued.

    Queueing behind a 60-second Turn puts the user in front of a spinner with
    no estimable end, so the answer is immediate and honest.
    """

    status_code = 503

    def __init__(self, limit: int = SESSION_CONCURRENCY) -> None:
        super().__init__(
            f"the service is already running {limit} agent sessions; try again shortly"
        )
        self.limit = limit


class SessionSlots:
    """Three concurrent Turns at the route, and no queue behind them."""

    def __init__(self, limit: int = SESSION_CONCURRENCY) -> None:
        self._limit = limit
        self._semaphore = asyncio.Semaphore(limit)

    @asynccontextmanager
    async def occupy(self):
        # ``locked()`` is true exactly when no permit is left, and no await sits
        # between the check and the acquire, so the pair is atomic on the event
        # loop and the acquire below cannot block.
        if self._semaphore.locked():
            raise SessionCapacityExceeded(self._limit)
        await self._semaphore.acquire()
        try:
            yield
        finally:
            self._semaphore.release()


class ToolCallIdMismatch(MalformedArguments):
    """A tool call whose id cannot be trusted to identify it.

    A ``MalformedArguments`` rather than a class of its own: it is the same
    measured failure — the route violating its contract — and the taxonomy says
    what happens next, which is that the Turn fails immediately.
    """


@dataclass(frozen=True)
class TurnRequest:
    """One user message and everything needed to answer it."""

    thread_id: Any
    request_message_id: int
    user_id: int
    user_text: str
    runtime: RuntimeContext
    history: tuple[TranscriptTurn, ...] = ()
    summary: str | None = None
    summarised_turns: int = 0


@dataclass(frozen=True)
class TurnDraft:
    """What has been produced so far, for checkpointing."""

    text: str | None
    rounds_used: int
    tool_calls: tuple[TranscriptToolCall, ...]


@dataclass(frozen=True)
class TurnOutcome:
    """How the Turn ended, and what it leaves behind."""

    # complete | incomplete | cancelled
    status: str
    terminal_reason: str | None
    text: str | None
    answer_kind: AnswerKind
    rounds_used: int
    rounds_exhausted: bool
    tool_calls: tuple[TranscriptToolCall, ...]
    usage: Usage
    summary_needed: bool = False


Checkpoint = Callable[[TurnDraft], Awaitable[None] | None]
Cancelled = Callable[[], bool]


def pair_results(
    calls: Sequence[ToolCall],
    outcomes: Sequence[Any],
) -> tuple[tuple[ToolCall, Any], ...]:
    """Match every dispatch outcome to the call it was made for, or fail loudly.

    The pairing is by position because that is how ``asyncio.gather`` returns,
    and the id carried back through the dispatch is then checked against the id
    that was sent. Both halves matter: position alone is what the measured
    gateway bug corrupted, and an id alone cannot tell a caller that a result
    went missing.
    """
    if len(calls) != len(outcomes):
        raise ToolCallIdMismatch(
            f"the round dispatched {len(calls)} tool calls and got back "
            f"{len(outcomes)} results"
        )
    paired: list[tuple[ToolCall, Any]] = []
    for call, outcome in zip(calls, outcomes):
        if isinstance(outcome, tuple) and len(outcome) == 2:
            returned_id, value = outcome
            if returned_id != call.id:
                llm_metrics().record_malformed_arguments(
                    f"result for {call.name} came back under id {returned_id!r} "
                    f"but was dispatched under {call.id!r}"
                )
                raise ToolCallIdMismatch(
                    f"a tool result came back under id {returned_id!r} after being "
                    f"dispatched under {call.id!r}; the route's tool-call ids cannot "
                    "be trusted for this Turn"
                )
            paired.append((call, value))
        else:
            paired.append((call, outcome))
    return tuple(paired)


def assert_distinct_ids(calls: Sequence[ToolCall]) -> None:
    """Refuse a round whose calls cannot be told apart."""
    seen: set[str] = set()
    for call in calls:
        if not call.id:
            llm_metrics().record_malformed_arguments(
                f"the route asked for {call.name} with no tool-call id"
            )
            raise ToolCallIdMismatch(
                f"the route asked for tool {call.name} with no tool-call id, so its "
                "result could not be identified"
            )
        if call.id in seen:
            llm_metrics().record_malformed_arguments(
                f"the route repeated tool-call id {call.id!r} inside one round"
            )
            raise ToolCallIdMismatch(
                f"the route repeated tool-call id {call.id!r} inside one round; this "
                "is the failure that concatenates two calls' arguments"
            )
        seen.add(call.id)


class AgentLoop:
    """One Turn, from the user's message to a terminal state."""

    def __init__(
        self,
        *,
        client: LLMClient,
        catalog: ToolCatalog,
        config: LLMConfig,
        budget: ContextBudget | None = None,
        slots: SessionSlots | None = None,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        checkpoint: Checkpoint | None = None,
    ) -> None:
        self._client = client
        self._catalog = catalog
        self._budget = budget or ContextBudget()
        self._slots = slots or SessionSlots()
        self._max_output_tokens = max_output_tokens
        self._checkpoint = checkpoint
        # Resolved once, here. ``docs/adr/0008``: models split by workload and
        # never inside the loop, because an in-loop cheap-router split adds a
        # decision point whose quality cannot be measured until the Eval
        # Battery exists.
        self._model = config.model_for(Workload.SESSION)

    async def run(
        self,
        request: TurnRequest,
        cancelled: Cancelled = lambda: False,
    ) -> TurnOutcome:
        async with self._slots.occupy():
            return await self._run(request, cancelled)

    async def _run(self, request: TurnRequest, cancelled: Cancelled) -> TurnOutcome:
        attempts = ToolAttempts()
        calls_made: list[TranscriptToolCall] = []
        text: str | None = None
        usage = _UsageTotals()
        tool_rounds = 0
        evidence = _EvidenceCounters()
        summary_needed = False
        tool_context = ToolContext(
            user_id=request.user_id,
            trading_day=request.runtime.trading_day,
            active_symbol=request.runtime.active_symbol,
        )
        system_prompt = render(request.runtime)

        for round_index in range(MAX_TOOL_ROUNDS + 1):
            if cancelled():
                return self._ended(
                    "cancelled", "cancelled_by_user", text, tool_rounds,
                    calls_made, usage, evidence, summary_needed,
                )

            final = round_index == MAX_TOOL_ROUNDS
            context = self._construct(system_prompt, request, calls_made, final)
            summary_needed = summary_needed or context.summary_needed
            messages = list(context.messages)
            if final:
                messages.append(Message(role=Role.SYSTEM, content=ROUNDS_EXHAUSTED_NOTE))

            try:
                completion = await self._complete(request, messages, context, final)
            except BudgetRefusal as refusal:
                # No further LLM call, of any kind. The partial answer and the
                # traces of what ran are what the user gets.
                logger.info(
                    "Turn %s ended without budget for its next call: %s",
                    request.request_message_id,
                    refusal.operator_detail or refusal.reason,
                )
                return self._ended(
                    "incomplete", refusal.reason, text, tool_rounds,
                    calls_made, usage, evidence, summary_needed,
                )
            except ModelRefusal as refusal:
                usage.add(refusal.usage)
                evidence.model_refused = True
                return self._ended(
                    "complete", "model_refusal", refusal.refusal, tool_rounds,
                    calls_made, usage, evidence, summary_needed,
                )
            except AuthUnavailable:
                # Never retried: a dead credential turns one failure into a run
                # of identical ones.
                return self._ended(
                    "incomplete", "auth_unavailable", text, tool_rounds,
                    calls_made, usage, evidence, summary_needed,
                )
            except GatewayTimeout:
                # Already retried with backoff inside the client; a third
                # attempt here would silently double the tabled ceiling.
                return self._ended(
                    "incomplete", "gateway_timeout", text, tool_rounds,
                    calls_made, usage, evidence, summary_needed,
                )
            except MalformedArguments:
                # Counted and logged at the boundary. Nothing is disabled here.
                raise
            except LLMError:
                return self._ended(
                    "incomplete", "route_error", text, tool_rounds,
                    calls_made, usage, evidence, summary_needed,
                )

            usage.add(completion.usage)
            if completion.text:
                text = completion.text
            await self._save(text, tool_rounds, calls_made)

            if final or not completion.tool_calls:
                return self._ended(
                    "complete", None, text, tool_rounds,
                    calls_made, usage, evidence, summary_needed,
                    rounds_exhausted=final,
                )

            assert_distinct_ids(completion.tool_calls)
            try:
                calls_made.extend(
                    await self._round(
                        completion.tool_calls, request, tool_context, attempts, evidence
                    )
                )
            except AuthUnavailable:
                # A tool's own channel died — the news lane is the one that can.
                # Same class, same behaviour: never retried, surfaced as
                # re-auth needed.
                return self._ended(
                    "incomplete", "auth_unavailable", text, tool_rounds,
                    calls_made, usage, evidence, summary_needed,
                )
            tool_rounds += 1
            await self._save(text, tool_rounds, calls_made)

            # Cancellation stops *after* the in-flight tool call completes.
            # Every tool is read-only, so there is nothing to roll back, and a
            # half-cancel path costs more than the call it would save.
            if cancelled():
                return self._ended(
                    "cancelled", "cancelled_by_user", text, tool_rounds,
                    calls_made, usage, evidence, summary_needed,
                )

        raise RuntimeError("the round loop ended without a terminal state")  # pragma: no cover

    def _construct(
        self,
        system_prompt: str,
        request: TurnRequest,
        calls_made: Sequence[TranscriptToolCall],
        final: bool,
    ) -> ConstructedContext:
        """Meet the constructed-context ceiling, note and all."""
        budget = self._budget
        if final:
            note = Message(role=Role.SYSTEM, content=ROUNDS_EXHAUSTED_NOTE)
            budget = replace(budget, max_tokens=budget.max_tokens - estimate_tokens(note))
        transcript = Transcript(
            system_prompt=system_prompt,
            turns=(
                *request.history,
                TranscriptTurn(
                    user_text=request.user_text,
                    tool_calls=tuple(calls_made),
                ),
            ),
            summary=request.summary,
            summarised_turns=request.summarised_turns,
        )
        return build_messages(transcript, budget)

    async def _complete(
        self,
        request: TurnRequest,
        messages: Sequence[Message],
        context: ConstructedContext,
        final: bool,
    ) -> Completion:
        """One model call, reserved before dispatch and reconciled after.

        Both halves happen inside the client, which holds no transaction across
        the network call; the loop's job is to name the worst case honestly.
        """
        spend = SpendRequest(
            owner=CallOwner(
                type=OwnerType.TURN_REQUEST_MESSAGE,
                id=str(request.request_message_id),
                user_id=request.user_id,
            ),
            lane=BudgetLane.TURN,
            workload=Workload.SESSION,
            input_tokens=context.estimated_tokens
            + (estimate_tokens(messages[-1]) if final else 0),
            output_tokens=self._max_output_tokens,
        )
        return await self._client.complete(
            CompletionRequest(
                model=self._model,
                messages=tuple(messages),
                tools=self._catalog.tool_schemas,
                tool_choice="none" if final else "auto",
                parallel_tool_calls=True,
                max_output_tokens=self._max_output_tokens,
            ),
            spend,
        )

    async def _round(
        self,
        calls: Sequence[ToolCall],
        request: TurnRequest,
        tool_context: ToolContext,
        attempts: ToolAttempts,
        evidence: "_EvidenceCounters",
    ) -> tuple[TranscriptToolCall, ...]:
        """Dispatch one round concurrently; one failing tool does not kill it."""
        # The two-attempt cap is spent before dispatch, not after failure: the
        # calls in a round run concurrently, so a round that asked for the same
        # broken tool three times would otherwise get three attempts out of a
        # limit of two.
        allowance = {call.name: attempts.remaining(call.name) for call in calls}
        admitted: list[bool] = []
        for call in calls:
            admitted.append(allowance[call.name] > 0)
            allowance[call.name] = max(0, allowance[call.name] - 1)

        outcomes = await asyncio.gather(
            *(
                self._dispatch(call, request, tool_context, allowed)
                for call, allowed in zip(calls, admitted)
            ),
            return_exceptions=True,
        )
        results: list[TranscriptToolCall] = []
        for call, outcome in pair_results(calls, outcomes):
            if isinstance(outcome, BaseException):
                result = self._failure(call, outcome, attempts)
            else:
                result = outcome
            evidence.observe(result)
            results.append(
                TranscriptToolCall(
                    call_id=call.id,
                    name=call.name,
                    arguments=dict(call.arguments),
                    result=result,
                )
            )
        return tuple(results)

    async def _dispatch(
        self,
        call: ToolCall,
        request: TurnRequest,
        tool_context: ToolContext,
        allowed: bool,
    ) -> tuple[str, Mapping[str, Any]]:
        """Run one tool, carrying its own id back with its result."""
        if not allowed:
            return call.id, tool_error_result(call.id, call.name, TOOL_EXHAUSTED_MESSAGE)
        result = await self._catalog.dispatch(
            call.name,
            call.arguments,
            tool_context,
            thread_id=request.thread_id,
            request_message_id=request.request_message_id,
        )
        return call.id, result

    @staticmethod
    def _failure(
        call: ToolCall,
        error: BaseException,
        attempts: ToolAttempts,
    ) -> Mapping[str, Any]:
        """Turn one tool's failure into something the model can act on."""
        if isinstance(error, (MalformedArguments, AuthUnavailable, asyncio.CancelledError)):
            raise error
        attempts.record_failure(call.name)
        logger.warning("Tool %s failed: %s", call.name, error)
        return tool_error_result(call.id, call.name, str(error))

    async def _save(
        self,
        text: str | None,
        rounds_used: int,
        calls_made: Sequence[TranscriptToolCall],
    ) -> None:
        if self._checkpoint is None:
            return
        saved = self._checkpoint(
            TurnDraft(text=text, rounds_used=rounds_used, tool_calls=tuple(calls_made))
        )
        if inspect.isawaitable(saved):
            await saved

    @staticmethod
    def _ended(
        status: str,
        terminal_reason: str | None,
        text: str | None,
        rounds_used: int,
        calls_made: Sequence[TranscriptToolCall],
        usage: "_UsageTotals",
        evidence: "_EvidenceCounters",
        summary_needed: bool,
        rounds_exhausted: bool = False,
    ) -> TurnOutcome:
        return TurnOutcome(
            status=status,
            terminal_reason=terminal_reason,
            text=text,
            answer_kind=classify_answer_kind(evidence.snapshot()),
            rounds_used=rounds_used,
            rounds_exhausted=rounds_exhausted,
            tool_calls=tuple(calls_made),
            usage=usage.total(),
            summary_needed=summary_needed,
        )


@dataclass
class _UsageTotals:
    """Five counters summed across a Turn's calls.

    ``None`` usage is not zero usage: a provider that supplied no evidence has
    not told us the call was free, so it is skipped rather than added in.
    """

    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0

    def add(self, usage: Usage | None) -> None:
        if usage is None:
            return
        self.input_tokens += usage.input_tokens
        self.cached_input_tokens += usage.cached_input_tokens
        self.cache_write_tokens += usage.cache_write_tokens
        self.output_tokens += usage.output_tokens
        self.reasoning_tokens += usage.reasoning_tokens

    def total(self) -> Usage:
        return Usage(
            input_tokens=self.input_tokens,
            cached_input_tokens=self.cached_input_tokens,
            cache_write_tokens=self.cache_write_tokens,
            output_tokens=self.output_tokens,
            reasoning_tokens=self.reasoning_tokens,
        )


@dataclass
class _EvidenceCounters:
    """What the harness saw, in the Contract's classification terms."""

    model_refused: bool = False
    universe_refusals: int = 0
    grounded_tool_calls: int = 0

    def observe(self, result: Mapping[str, Any]) -> None:
        if result.get("reason") == "not_in_universe":
            self.universe_refusals += 1
        elif "error" not in result:
            self.grounded_tool_calls += 1

    def snapshot(self) -> AnswerEvidence:
        return AnswerEvidence(
            model_refused=self.model_refused,
            universe_refusals=self.universe_refusals,
            grounded_tool_calls=self.grounded_tool_calls,
        )


__all__ = [
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "MAX_TOOL_ROUNDS",
    "ROUNDS_EXHAUSTED_NOTE",
    "SESSION_CONCURRENCY",
    "AgentLoop",
    "SessionCapacityExceeded",
    "SessionSlots",
    "ToolCallIdMismatch",
    "TurnDraft",
    "TurnOutcome",
    "TurnRequest",
    "assert_distinct_ids",
    "pair_results",
]
