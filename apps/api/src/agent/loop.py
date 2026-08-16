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
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from src.alpha.refusals import AlphaRefusal
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
from src.core.llm.errors import MAX_TOOL_ATTEMPTS

from .blocks import split_blocks
from .context import (
    ConstructedContext,
    ContextBudget,
    Transcript,
    TranscriptToolCall,
    TranscriptTurn,
    build_messages,
    estimate_tokens,
)
from .events import Activity, TurnPublisher
from .grounding import (
    GROUNDING_FAILED,
    Citation,
    GroundingFailure,
    RecommendationValidator,
    ReleasedBlock,
    TraceIndex,
)
from .prompt import AnswerEvidence, AnswerKind, RuntimeContext, classify_answer_kind, render
from .tools.catalog import ToolCatalog, ToolContext, refusal_reason
from .widgets import (
    WidgetSelection,
    WidgetSpec,
    WidgetValidator,
    extract_selections,
    user_requested_multiple,
    user_requested_visual,
)

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
# Built once so the three places that care about it — the message appended to
# the final call, the budget it is charged against, and the reservation that
# funds it — cannot disagree about what it costs.
ROUNDS_EXHAUSTED_MESSAGE = Message(role=Role.SYSTEM, content=ROUNDS_EXHAUSTED_NOTE)
ROUNDS_EXHAUSTED_TOKENS = estimate_tokens(ROUNDS_EXHAUSTED_MESSAGE)

TOOL_EXHAUSTED_MESSAGE = (
    "this tool has already failed twice in this Turn and will not be called again; "
    "take a different approach or say what is missing"
)

# ``docs/adr/0013``'s timings, minus the Turn deadline, which belongs to the
# lifecycle rather than to one loop: the deadline bounds a Turn including the
# time it spends waiting for a slot, and this class only exists once it has one.
#
# The call timeout duplicates the transport's own by design. The transport's
# guards one HTTP request; this one guards the whole call including retries, so
# a route that answers slowly three times cannot quietly spend six minutes of a
# ten-minute Turn.
LLM_CALL_TIMEOUT_SECONDS = 120.0
# Shorter than the call timeout, because a tool reads the local store or one
# allowlisted news source: past this, waiting costs the Turn more than the
# result is worth.
TOOL_TIMEOUT_SECONDS = 30.0

# The one tool whose activity is a search rather than a read. Kept as a name
# check here because ``turn.activity`` may never expose a tool name — this maps
# a name to a generic phase, which is the opposite of leaking one.
NEWS_TOOL = "search_news"


class TurnStatus(str, Enum):
    """How a Turn ended, in the lifecycle table's own vocabulary."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    CANCELLED = "cancelled"


class SessionCapacityExceeded(AlphaRefusal):
    """The 4th concurrent session, refused rather than queued.

    Queueing behind a 60-second Turn puts the user in front of a spinner with
    no estimable end, so the answer is immediate and honest — and for the same
    reason it carries no ``Retry-After``: the only number that could go there
    would be a guess at when someone else's Turn ends.

    An :class:`AlphaRefusal` so the application's existing handler maps it to
    503 with the same body shape as every other refusal, and under the reason
    admission already uses for this exact condition — a capacity refusal should
    read the same whether it was caught at the route or at the ledger.
    """

    def __init__(self, limit: int = SESSION_CONCURRENCY) -> None:
        super().__init__(
            reason="system_active_turns",
            message="The service is at its active Turn capacity. Try again shortly.",
            status_code=503,
        )
        self.limit = limit


class SessionSlots:
    """Three concurrent Turns at the route, and no queue behind them."""

    def __init__(self, limit: int = SESSION_CONCURRENCY) -> None:
        self._limit = limit
        self._semaphore = asyncio.Semaphore(limit)

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def full(self) -> bool:
        """Whether a Turn asking for a slot right now would be refused.

        Read without taking one, for admission: the ``POST`` has to answer 503
        *before* a stream opens rather than let the refusal surface as a
        terminal event seconds later. It is a sample and not a reservation — a
        Turn admitted here still meets :meth:`occupy`, and losing that race ends
        the Turn honestly, where losing this one would only have cost a round
        trip.
        """
        return self._semaphore.locked()

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


class ToolTimeout(TimeoutError):
    """One tool that did not answer inside its own, shorter deadline."""

    def __init__(self, tool_name: str, seconds: float) -> None:
        super().__init__(f"tool {tool_name} did not answer within {seconds:g}s")
        self.tool_name = tool_name


@dataclass(frozen=True)
class TurnRequest:
    """One user message and everything needed to answer it."""

    thread_id: uuid.UUID | str
    request_message_id: int
    user_id: int
    user_text: str
    runtime: RuntimeContext
    history: tuple[TranscriptTurn, ...] = ()
    summary: str | None = None
    summarised_turns: int = 0


@dataclass(frozen=True)
class SpendIdentity:
    """Which durable artifact this loop's provider calls are charged to.

    ``docs/adr/0014`` requires every provider call to name an owner with a
    non-null id, and there are two artifacts that can be that owner for a run of
    *this* loop: the user's request message, which is a Turn, and an
    ``eval_run``, which is the Eval Battery running the very same loop over the
    frozen fixture (``docs/adr/0016``).

    A parameter rather than a branch inside :meth:`AgentLoop._complete`, because
    the alternative to a seam here is an eval-only code path through the agent
    loop — and a battery that exercises a different loop from the one that
    answers users measures the wrong thing.

    ``charge_to_user`` is off for the battery deliberately. The eval user is a
    fixture actor rather than a customer; charging it the per-user daily Turn
    allowance would refuse the battery on its twenty-first case for a reason
    that has nothing to do with what the battery is measuring.
    """

    owner_type: OwnerType = OwnerType.TURN_REQUEST_MESSAGE
    lane: BudgetLane = BudgetLane.TURN
    owner_id: str | None = None
    charge_to_user: bool = True

    def owner(self, request: "TurnRequest") -> CallOwner:
        return CallOwner(
            type=self.owner_type,
            id=self.owner_id or str(request.request_message_id),
            user_id=request.user_id if self.charge_to_user else None,
        )


#: What a Turn served to a user is charged to, and the default everywhere.
TURN_SPEND = SpendIdentity()


@dataclass(frozen=True)
class TurnDraft:
    """What has been produced so far, for checkpointing.

    ``blocks`` rather than ``text`` is what a reconnecting browser renders: they
    are the units that were *proven*, and a draft that carried unreleased prose
    would put an unvalidated figure into the snapshot the Gate exists to keep
    out of the stream.

    ``boundary`` says this checkpoint is one of the moments ``docs/adr/0013``
    names — an activity, a Widget, a cancellation, a terminal state — rather
    than ordinary progress. The rate limiter that keeps checkpoints to at most
    one a second reads it, and nothing else does.
    """

    text: str | None
    rounds_used: int
    tool_calls: tuple[TranscriptToolCall, ...]
    blocks: tuple[ReleasedBlock, ...] = ()
    # The Widget specs that passed validation, in the order selected. Present
    # in the draft for the same reason the blocks are: a reconnecting browser
    # renders the checkpoint, and ``widget.ready`` is emitted only *after* the
    # spec is in one (``docs/adr/0012``).
    widgets: tuple[WidgetSpec, ...] = ()
    widget_refusals: tuple[Mapping[str, Any], ...] = ()
    boundary: bool = False
    # Classified from the same evidence the outcome will be, so a Turn the
    # deadline kills before it returns one is still written under the answer
    # kind it had earned rather than under a default.
    answer_kind: AnswerKind = AnswerKind.EDUCATION

    @property
    def citations(self) -> tuple[Citation, ...]:
        return tuple(
            citation for block in self.blocks for citation in block.citations
        )


@dataclass(frozen=True)
class TurnOutcome:
    """How the Turn ended, and what it leaves behind."""

    status: TurnStatus
    terminal_reason: str | None
    text: str | None
    answer_kind: AnswerKind
    rounds_used: int
    rounds_exhausted: bool
    tool_calls: tuple[TranscriptToolCall, ...]
    usage: Usage
    summary_needed: bool = False
    # The blocks that passed the Recommendation Gate and were emitted, in order.
    blocks: tuple[ReleasedBlock, ...] = ()
    # The Widget specs that passed validation, and the refusals worth showing.
    widgets: tuple[WidgetSpec, ...] = ()
    widget_refusals: tuple[Mapping[str, Any], ...] = ()
    # The route's id for the last call it answered, for the Evidence Manifest.
    provider_request_id: str | None = None
    # Which Gate condition refused, when one did. The Turn's terminal reason
    # stays the stable ``grounding_failed``; this is the operator's detail and
    # the ops query's dimension.
    grounding_failure_code: str | None = None

    @property
    def citations(self) -> tuple[Citation, ...]:
        """Every cited field of every released block, in the order emitted."""
        return tuple(
            citation for block in self.blocks for citation in block.citations
        )


Checkpoint = Callable[[TurnDraft], Awaitable[None] | None]
Cancelled = Callable[[], bool]


@dataclass
class _TurnState:
    """Everything one Turn accumulates, in one place.

    A single mutable object rather than seven locals threaded through every
    terminal path: the eight ``_ended`` call sites differ only in status and
    reason, and a positional tail of six values is where a swap goes unnoticed.
    """

    text: str | None = None
    tool_rounds: int = 0
    usage: Usage = field(default_factory=Usage)
    calls: list[TranscriptToolCall] = field(default_factory=list)
    model_refused: bool = False
    universe_refusals: int = 0
    grounded_tool_calls: int = 0
    summary_needed: bool = False
    blocks: list[ReleasedBlock] = field(default_factory=list)
    widgets: list[WidgetSpec] = field(default_factory=list)
    widget_refusals: list[Mapping[str, Any]] = field(default_factory=list)
    request_id: str | None = None
    grounding_failure_code: str | None = None

    def add_usage(self, usage: Usage | None) -> None:
        # ``None`` usage is not zero usage: a provider that supplied no evidence
        # has not told us the call was free, so it is skipped rather than added.
        if usage is not None:
            self.usage = self.usage + usage

    def observe(self, result: Mapping[str, Any]) -> None:
        """Classify one tool result the way the Contract classifies answers."""
        reason = refusal_reason(result)
        if reason == "not_in_universe":
            self.universe_refusals += 1
        elif reason is None:
            self.grounded_tool_calls += 1

    def evidence(self) -> AnswerEvidence:
        return AnswerEvidence(
            model_refused=self.model_refused,
            universe_refusals=self.universe_refusals,
            grounded_tool_calls=self.grounded_tool_calls,
        )

    def draft(self, *, boundary: bool = False) -> TurnDraft:
        return TurnDraft(
            text=self.text,
            rounds_used=self.tool_rounds,
            tool_calls=tuple(self.calls),
            blocks=tuple(self.blocks),
            widgets=tuple(self.widgets),
            widget_refusals=tuple(self.widget_refusals),
            boundary=boundary,
            answer_kind=classify_answer_kind(self.evidence()),
        )


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


def admit_round(calls: Sequence[ToolCall], attempts: ToolAttempts) -> tuple[bool, ...]:
    """Decide which of a round's calls may be dispatched.

    The two-attempt cap governs *retries*. A tool that has already failed gets
    only the attempts it has left, and because a round runs concurrently that
    allowance has to be spent before dispatch rather than after failure —
    otherwise three parallel calls to one broken tool all get through.

    A tool that has not failed yet has nothing to retry, so a healthy fan-out —
    one tool asked about three symbols in one round, which the prompt's own
    tool-use policy invites — is never gated.
    """
    allowance = {call.name: attempts.remaining(call.name) for call in calls}
    admitted: list[bool] = []
    for call in calls:
        left = allowance[call.name]
        if left >= MAX_TOOL_ATTEMPTS:
            admitted.append(True)
            continue
        admitted.append(left > 0)
        allowance[call.name] = max(0, left - 1)
    return tuple(admitted)


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
        publisher: TurnPublisher | None = None,
        call_timeout_seconds: float = LLM_CALL_TIMEOUT_SECONDS,
        tool_timeout_seconds: float = TOOL_TIMEOUT_SECONDS,
        spend: SpendIdentity = TURN_SPEND,
    ) -> None:
        self._spend = spend
        self._client = client
        self._catalog = catalog
        self._budget = budget or ContextBudget()
        self._slots = slots or SessionSlots()
        self._max_output_tokens = max_output_tokens
        self._checkpoint = checkpoint
        self._publisher = publisher
        self._call_timeout = call_timeout_seconds
        self._tool_timeout = tool_timeout_seconds
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
        state = _TurnState()
        attempts = ToolAttempts()
        tool_context = ToolContext(
            user_id=request.user_id,
            trading_day=request.runtime.trading_day,
            active_symbol=request.runtime.active_symbol,
        )
        system_prompt = render(request.runtime)

        for round_index in range(MAX_TOOL_ROUNDS + 1):
            if cancelled():
                return await self._terminal(
                    request, TurnStatus.CANCELLED, "cancelled_by_user", state
                )

            final = round_index == MAX_TOOL_ROUNDS
            context = self._construct(system_prompt, request, state, final)
            state.summary_needed = state.summary_needed or context.summary_needed
            messages = list(context.messages)
            if final:
                messages.append(ROUNDS_EXHAUSTED_MESSAGE)

            await self._activity(Activity.ANALYZING, state)
            try:
                completion = await self._complete(request, messages, context, final)
            except TimeoutError:
                # Its own reason, and its own ceiling: the transport's timeout
                # covers one HTTP request, this one covers the call including
                # every retry the client made inside it.
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, "llm_call_timeout", state
                )
            except BudgetRefusal as refusal:
                # No further LLM call, of any kind. The partial answer and the
                # traces of what ran are what the user gets.
                logger.info(
                    "Turn %s ended without budget for its next call: %s",
                    request.request_message_id,
                    refusal.operator_detail or refusal.reason,
                )
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, refusal.reason, state
                )
            except ModelRefusal as refusal:
                state.add_usage(refusal.usage)
                state.model_refused = True
                state.text = refusal.refusal
                return await self._terminal(
                    request, TurnStatus.COMPLETE, "model_refusal", state
                )
            except AuthUnavailable:
                # Never retried: a dead credential turns one failure into a run
                # of identical ones. ``auth_unavailable`` is the stable reason
                # the interactive surface renders as *re-auth needed*.
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, "auth_unavailable", state
                )
            except GatewayTimeout:
                # Already retried with backoff inside the client; a third
                # attempt here would silently double the tabled ceiling.
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, "gateway_timeout", state
                )
            except MalformedArguments:
                # Counted and logged at the boundary. Nothing is disabled here.
                raise
            except LLMError:
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, "route_error", state
                )

            state.add_usage(completion.usage)
            if completion.request_id:
                state.request_id = completion.request_id
            if completion.text:
                state.text = completion.text
            await self._save(state)

            if final or not completion.tool_calls:
                return await self._terminal(
                    request, TurnStatus.COMPLETE, None, state, rounds_exhausted=final
                )

            assert_distinct_ids(completion.tool_calls)
            await self._activity(
                Activity.SEARCHING
                if any(call.name == NEWS_TOOL for call in completion.tool_calls)
                else Activity.READING_DATA,
                state,
            )
            fatal = await self._round(
                completion.tool_calls, request, tool_context, attempts, state
            )
            state.tool_rounds += 1
            await self._save(state, boundary=True)

            if isinstance(fatal, ToolTimeout):
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, "tool_timeout", state
                )
            if isinstance(fatal, AuthUnavailable):
                # A tool's own channel died — the news lane is the one that can.
                # Same class, same behaviour: never retried, surfaced as re-auth
                # needed, and the round's healthy siblings are already recorded.
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, "auth_unavailable", state
                )
            if fatal is not None:
                raise fatal

            # Cancellation stops *after* the in-flight tool call completes.
            # Every tool is read-only, so there is nothing to roll back, and a
            # half-cancel path costs more than the call it would save.
            if cancelled():
                return await self._terminal(
                    request, TurnStatus.CANCELLED, "cancelled_by_user", state
                )

        raise RuntimeError("the round loop ended without a terminal state")  # pragma: no cover

    def _construct(
        self,
        system_prompt: str,
        request: TurnRequest,
        state: _TurnState,
        final: bool,
    ) -> ConstructedContext:
        """Meet the constructed-context ceiling, note and all."""
        budget = self._budget
        if final:
            budget = replace(
                budget, max_tokens=budget.max_tokens - ROUNDS_EXHAUSTED_TOKENS
            )
        transcript = Transcript(
            system_prompt=system_prompt,
            turns=(
                *request.history,
                TranscriptTurn(
                    user_text=request.user_text,
                    tool_calls=tuple(state.calls),
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
            owner=self._spend.owner(request),
            lane=self._spend.lane,
            workload=Workload.SESSION,
            input_tokens=context.estimated_tokens
            + (ROUNDS_EXHAUSTED_TOKENS if final else 0),
            output_tokens=self._max_output_tokens,
        )
        return await asyncio.wait_for(
            self._client.complete(
                CompletionRequest(
                    model=self._model,
                    messages=tuple(messages),
                    tools=self._catalog.tool_schemas,
                    tool_choice="none" if final else "auto",
                    parallel_tool_calls=True,
                    max_output_tokens=self._max_output_tokens,
                ),
                spend,
            ),
            self._call_timeout,
        )

    async def _round(
        self,
        calls: Sequence[ToolCall],
        request: TurnRequest,
        tool_context: ToolContext,
        attempts: ToolAttempts,
        state: _TurnState,
    ) -> BaseException | None:
        """Dispatch one round concurrently; one failing tool does not kill it.

        Every result is recorded before a fatal failure is handed back, so a
        dead credential on the news channel does not throw away the three store
        reads that succeeded beside it.
        """
        admitted = admit_round(calls, attempts)
        outcomes = await asyncio.gather(
            *(
                self._dispatch(call, request, tool_context, allowed)
                for call, allowed in zip(calls, admitted)
            ),
            return_exceptions=True,
        )
        fatal: BaseException | None = None
        for call, outcome in pair_results(calls, outcomes):
            if isinstance(outcome, BaseException):
                if isinstance(
                    outcome,
                    (
                        MalformedArguments,
                        AuthUnavailable,
                        ToolTimeout,
                        asyncio.CancelledError,
                    ),
                ):
                    fatal = fatal or outcome
                    continue
                result = self._record_failure(call, outcome, attempts)
            else:
                result = outcome
            state.observe(result)
            state.calls.append(
                TranscriptToolCall(
                    call_id=call.id,
                    name=call.name,
                    arguments=dict(call.arguments),
                    result=result,
                )
            )
        return fatal

    async def _dispatch(
        self,
        call: ToolCall,
        request: TurnRequest,
        tool_context: ToolContext,
        allowed: bool,
    ) -> tuple[str, Mapping[str, Any]]:
        """Run one tool under its own deadline, carrying its id back with it."""
        if not allowed:
            return call.id, tool_error_result(call.id, call.name, TOOL_EXHAUSTED_MESSAGE)
        try:
            result = await asyncio.wait_for(
                self._catalog.dispatch(
                    call.name,
                    call.arguments,
                    tool_context,
                    thread_id=request.thread_id,
                    request_message_id=request.request_message_id,
                ),
                self._tool_timeout,
            )
        except TimeoutError as exc:
            raise ToolTimeout(call.name, self._tool_timeout) from exc
        return call.id, result

    @staticmethod
    def _record_failure(
        call: ToolCall,
        error: BaseException,
        attempts: ToolAttempts,
    ) -> Mapping[str, Any]:
        """Turn one tool's failure into something the model can act on.

        A shape rather than prose, so the model can tell a tool that failed
        from a tool that answered "nothing found" — different facts about the
        world, leading to different next moves.
        """
        attempts.record_failure(call.name)
        logger.warning("Tool %s failed: %s", call.name, error)
        return tool_error_result(call.id, call.name, str(error))

    async def _save(self, state: _TurnState, *, boundary: bool = False) -> None:
        if self._checkpoint is None:
            return
        saved = self._checkpoint(state.draft(boundary=boundary))
        if inspect.isawaitable(saved):
            await saved

    async def _activity(self, activity: Activity, state: _TurnState) -> None:
        """Say what phase the Turn is in, and nothing about how.

        No tool name, symbol, argument, raw result, prompt or reasoning: the
        full detail stays in the Tool Call Trace, and the activity line is
        ephemeral rather than a verbose tool history (``docs/adr/0013``).

        An activity is also one of the four checkpoint boundaries that decision
        names, so the draft is saved here past the once-a-second limiter: the
        phase a reconnecting reader is shown has to match the phase the Turn is
        actually in.
        """
        if self._publisher is None:
            return
        self._publisher.activity(activity)
        await self._save(state, boundary=True)

    async def _terminal(
        self,
        request: TurnRequest,
        status: TurnStatus,
        terminal_reason: str | None,
        state: _TurnState,
        rounds_exhausted: bool = False,
    ) -> TurnOutcome:
        """Release whatever the model produced, then end the Turn.

        Every terminal path runs through here, including the ones that end
        badly. A Turn that ran out of budget, lost its credential or was
        cancelled still produced prose, and prose that has passed the Gate is
        exactly what makes an ``incomplete`` useful rather than empty — the
        difference ``docs/adr/0013`` draws between ``incomplete`` and ``failed``.
        A model refusal reaches the user by the same route: it is an answer, and
        an answer nobody is shown is not a refusal, it is a silence.

        A block that cannot be proven overrides the status it was heading for:
        the Turn becomes ``incomplete`` with the stable ``grounding_failed``,
        whatever it was about to be.
        """
        try:
            selections = self._release(request, state)
        except GroundingFailure as failure:
            logger.info(
                "Turn %s blocked a content block: %s",
                request.request_message_id,
                failure,
            )
            state.grounding_failure_code = failure.code
            status, terminal_reason = TurnStatus.INCOMPLETE, GROUNDING_FAILED
            rounds_exhausted = False
        else:
            # Only a Turn whose text survived the Gate gets a picture. A blocked
            # answer has nothing to illustrate, and illustrating it anyway would
            # put the figure back on screen that the Gate just kept off it.
            await self._release_widgets(request, state, selections)
        return await self._ended(status, terminal_reason, state, rounds_exhausted)

    def _release(
        self, request: TurnRequest, state: _TurnState
    ) -> tuple[WidgetSelection, ...]:
        """Prove each block, then emit it. Never the other way round.

        The ordering is not a convention this function happens to follow: the
        publisher is reached only from inside the loop below, after
        :meth:`RecommendationValidator.validate` has returned. A block that
        fails raises out of here with nothing published, so there is no state in
        which an invalid block was displayed and later retracted.

        Blocks already released stay released. That is the point of failing per
        block rather than per answer — the user keeps the part that was proven.

        Widget markers come out *before* the split, and that ordering is load
        bearing twice over: the Recommendation Validator never sees one, so a
        selection can never be mistaken for the evidence reference attributing
        the figure in front of it; and a selection that is later rejected has
        already been removed from what the reader sees, so a dropped Widget
        leaves no stray marker in the prose.
        """
        if not state.text:
            return ()
        answer, selections = extract_selections(state.text)
        validator = RecommendationValidator(trading_day=request.runtime.trading_day)
        traces = TraceIndex(state.calls)
        for raw in split_blocks(answer):
            block = validator.validate(raw, traces)
            state.blocks.append(block)
            if self._publisher is not None:
                self._publisher.content_block(block.as_wire())
        return selections

    async def _release_widgets(
        self,
        request: TurnRequest,
        state: _TurnState,
        selections: Sequence[WidgetSelection],
    ) -> None:
        """Validate, checkpoint, then announce — in that order and no other.

        ``docs/adr/0012`` puts ``widget.ready`` after both, so a subscriber that
        acts on the event finds the spec already in the checkpoint it would
        reconnect to. Getting this the other way round would produce an event
        pointing at a spec that does not exist yet, which is precisely the race
        a reconnecting browser would hit and nobody else would.

        A rejection is not an error path. The text answer is already released
        and stays complete; the picture is simply missed, which is the whole
        argument for a named registry over a chart grammar.
        """
        if not selections:
            return
        await self._activity(Activity.PREPARING_VISUAL, state)
        validator = WidgetValidator(
            trading_day=request.runtime.trading_day,
            allow_second=user_requested_multiple(request.user_text),
            requested=user_requested_visual(request.user_text),
        )
        specs, rejections = validator.validate_all(selections, TraceIndex(state.calls))
        state.widgets.extend(specs)
        state.widget_refusals.extend(
            rejection.as_wire() for rejection in rejections if rejection.deep_link
        )
        if not specs and not state.widget_refusals:
            return
        await self._save(state, boundary=True)
        if self._publisher is not None:
            for spec in specs:
                self._publisher.widget_ready(spec.as_wire())

    async def _ended(
        self,
        status: TurnStatus,
        terminal_reason: str | None,
        state: _TurnState,
        rounds_exhausted: bool = False,
    ) -> TurnOutcome:
        """Checkpoint what survived, then describe how the Turn ended.

        The checkpoint happens on every terminal path, including a Turn
        cancelled before its first model call: a Turn that leaves nothing
        behind is a Turn the user cannot be told anything about.
        """
        await self._save(state, boundary=True)
        return TurnOutcome(
            status=status,
            terminal_reason=terminal_reason,
            text=state.text,
            answer_kind=classify_answer_kind(state.evidence()),
            rounds_used=state.tool_rounds,
            rounds_exhausted=rounds_exhausted,
            tool_calls=tuple(state.calls),
            usage=state.usage,
            summary_needed=state.summary_needed,
            blocks=tuple(state.blocks),
            widgets=tuple(state.widgets),
            widget_refusals=tuple(state.widget_refusals),
            provider_request_id=state.request_id,
            grounding_failure_code=state.grounding_failure_code,
        )


__all__ = [
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "LLM_CALL_TIMEOUT_SECONDS",
    "MAX_TOOL_ROUNDS",
    "ROUNDS_EXHAUSTED_MESSAGE",
    "ROUNDS_EXHAUSTED_NOTE",
    "ROUNDS_EXHAUSTED_TOKENS",
    "SESSION_CONCURRENCY",
    "TOOL_TIMEOUT_SECONDS",
    "TURN_SPEND",
    "AgentLoop",
    "SessionCapacityExceeded",
    "SessionSlots",
    "SpendIdentity",
    "ToolCallIdMismatch",
    "ToolTimeout",
    "TurnDraft",
    "TurnOutcome",
    "TurnRequest",
    "TurnStatus",
    "admit_round",
    "assert_distinct_ids",
    "pair_results",
]
