"""The hand-rolled agent loop over ``LLMClient``.

No framework: not LangGraph, not pydantic-ai, not the Agents SDK, not
``tool_runner``. There is no graph to orchestrate — five tools are plain
functions — and every framework marries one client abstraction, precisely where
the ``LLMClient`` boundary already exists for three other reasons. The cost is
stated plainly: dispatch, trimming, recovery and streaming are ours, and so is
correctness. This module is where we pay it.

What the loop does, and nothing more: render the prompt, ask the model, run the
tools it asked for, show it what came back, and stop. It does not decide what an
answer is allowed to say. The harness this replaced did, and the machinery for
it — an evidence manifest, a recommendation validator, labelled blocks, a widget
protocol — is gone with the tools that fed it.

Five properties are worth reading the code for.

**Rounds, not calls.** :data:`MAX_TOOL_ROUNDS` tool rounds per Turn, and the
constant is the authority. On the ceiling one further call with
``tool_choice="none"`` lets the model answer from what it has, and it is told the
rounds are spent — information, not an error. The round count is not free to
choose: a Turn is admitted against ``TURN_OUTPUT_TOTAL`` and makes at most
``MAX_TOOL_ROUNDS + 1`` calls, so the round count and
:data:`DEFAULT_MAX_OUTPUT_TOKENS` are one piece of arithmetic.

**Two recoveries that look alike and are opposites.** ``ContextOverflow`` means
the input did not fit, so the transcript is compressed and asked again.
``OutputCapExceeded`` means the transcript fits and the *reserved output ceiling*
pushed the total over, so trimming the transcript would discard evidence the
Turn already paid for and fix nothing. Both are bounded, and both re-raise when
their budget is spent so the terminal branch still names the condition.

**No apology call.** A Turn that cannot fund its next call ends where it is,
with its partial answer and the traces of what ran. Spending a call to
apologise for having no budget is the one thing that must not happen here.

**An absent answer is not an answer.** A Turn whose reply is empty is
``incomplete`` under :data:`EMPTY_ANSWER`, never ``complete``. The one paid call
this loop buys on a failure is the exception that proves the rule above: after a
round of tools returned results and the model replied with nothing, one nudge is
bought because the evidence is already paid for and a call can still turn it into
an answer. A Turn that has run no tool buys nothing, because there would be
nothing for the note to point at — that is the apology call.

**The text the reader gets is the sum of the deltas.** Every piece of prose the
model produces is recorded and published as a delta in the same step, so a
reconnecting browser rebuilding from a checkpoint and a browser that followed
the stream cannot disagree about what was said.

**Narration is not the answer, and the model is told both.** Prose from a round
that went on to call tools describes work rather than concluding it, so it is
published as a ``thought`` and the surface files it in the timeline instead of
in the reply. It is *not* withheld from the model: ``state.text`` keeps every
piece, and that is the string the next Turn's transcript is built from. How a
surface chooses to draw a sentence must not change what the model saw.

**Nothing is disabled automatically.** ``malformed_arguments`` is counted and
logged loudly; an operator flips the switch by hand. A cutoff that fires on two
errors is a mechanism that can cause its own outage.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol

from src.alpha.models import (
    TOOL_CALL_OK,
    TOOL_CALL_TIMEOUT,
    TOOL_CALL_TOOL_ERROR,
    TOOL_CALL_UNKNOWN_TOOL,
)
from src.alpha.refusals import AlphaRefusal
from src.core.llm import (
    AuthUnavailable,
    BudgetLane,
    BudgetRefusal,
    CallOwner,
    Completion,
    CompletionRequest,
    ContentPolicyBlocked,
    ContextOverflow,
    DeadlineExpired,
    GatewayTimeout,
    LLMClient,
    LLMConfig,
    LLMError,
    MalformedArguments,
    Message,
    ModelRefusal,
    ModelUnavailable,
    OutputCapExceeded,
    OwnerType,
    Role,
    RouteAction,
    RouteRateLimited,
    SchemaRejected,
    SpendRequest,
    ToolCall,
    ToolSchema,
    Usage,
    Workload,
    llm_metrics,
    recovery_for,
)
from src.core.llm.errors import redact
from src.core.config import get_settings

from . import registry
from .budget import TurnBudget, thresholds_for_context, trim_text
from .definitions import resolve_tool_surface
from .executor import UNKNOWN_TOOL, ExecutionOutcome, ToolExecutor
from .executor import ToolCall as ExecutorToolCall
from .guardrails import TurnGuardrails
# The transcript types and the context constructor live beside the loop rather
# than inside it: the transport names the same ``TranscriptTurn`` when it reads a
# Thread out of the store (``messages.py``).
from .messages import (
    ANSWER,
    CHARS_PER_TOKEN,
    DOMAIN_BODY,
    MAX_SUMMARY_CHARS,
    MESSAGE_OVERHEAD_TOKENS,
    SUMMARY_LABEL,
    SYSTEM_DYNAMIC,
    THOUGHT,
    ConstructedContext,
    ContextComposition,
    ConstructedContextTooLarge,
    ContextBudget,
    ToolCallStatus,
    Transcript,
    TranscriptTurn,
    TurnAttachment,
    TurnToolCall,
    build_messages,
    context_projection,
    display_results,
    estimate_tokens,
    shown_result,
    summarise_call,
)
from .prompt import RuntimeContext, cache_key, prefix as prompt_prefix, render
from .domain import active_pack
from .toolsets import CHAT_TOOLSETS

logger = logging.getLogger(__name__)

# Counted by round, so a round that fans out to five tools costs the same one
# step as a round that calls one.
#
# Four, and the number is arithmetic rather than taste: a Turn is admitted
# against ``TURN_OUTPUT_TOTAL`` (20,000) and makes at most ``MAX_TOOL_ROUNDS +
# 1`` calls at :data:`DEFAULT_MAX_OUTPUT_TOKENS` each. Raising one without
# lowering the other spends a budget nothing has validated.
MAX_TOOL_ROUNDS = 4

# In-process is correct because uvicorn runs a single worker.
#
# The default only. ``service.py`` wires the semaphore from the same configured
# ceiling the ledger checks, because the two enforce one number from opposite
# sides — the ledger counts active rows across the deployment, the semaphore
# counts running tasks in this process — and a deployment that raised one and
# not the other would have raised nothing.
SESSION_CONCURRENCY = 3

# What one call may produce, reasoning included — a reasoning model bills its
# hidden thinking against this same ceiling, so a per-call budget that only fits
# an answer leaves the model no room to reach one. At 2,000 a route that thinks
# at length spent the whole allowance thinking and returned four tokens of prose
# with ``finish_reason`` ``length``: a truncated answer rather than a short one.
DEFAULT_MAX_OUTPUT_TOKENS = 4_000

# What the route calls a completion it had to cut short, and the stable reason
# the Turn ends under when it does. Both are strings the interactive surface
# maps to a sentence; neither is ever shown to the reader as a code.
TRUNCATED = "length"
ANSWER_TRUNCATED = "answer_truncated"

# The stable reasons a Turn ends under. Grouped here because they are one kind
# of string: the interactive surface maps each to a sentence, none is ever shown
# as a code, and the ops snapshot's tally splits by whatever this file writes.
AUTH_UNAVAILABLE = "auth_unavailable"
CANCELLED_BY_USER = "cancelled_by_user"
CONTENT_POLICY_BLOCKED = "content_policy_blocked"
CONTEXT_OVERFLOW = "context_overflow"
# The route answered, was paid for, and said nothing a reader can use. Its own
# reason because its remedy is its own: neither the transcript nor the output
# ceiling is wrong, and there is nothing to retry that has not been retried —
# ``core/llm/client.py`` already asked again and swapped the model before
# handing this back.
EMPTY_ANSWER = "empty_answer"
GATEWAY_TIMEOUT = "gateway_timeout"
LLM_CALL_TIMEOUT = "llm_call_timeout"
MODEL_REFUSAL = "model_refusal"
MODEL_UNAVAILABLE = "model_unavailable"
OUTPUT_CAP_EXCEEDED = "output_cap_exceeded"
ROUTE_ERROR = "route_error"
ROUTE_RATE_LIMITED = "route_rate_limited"
SCHEMA_REJECTED = "schema_rejected"
# Our own deadline, kept apart from the route's. ``gateway_timeout`` used to
# carry both, which made the ops snapshot unable to say whether the fix was on
# the route's side or in this process's connection pool.
DEADLINE_EXPIRED = "deadline_expired"
# And apart from both: the *Turn* ran out of wall clock, which is neither the
# route being slow once nor this process failing to connect.
TURN_DEADLINE = "turn_deadline"

#: Every route condition that ends a Turn, and the reason it ends under. Looked
#: up by MRO like ``recovery_for``, so a subclass added later inherits its
#: parent's reason rather than arriving as ``route_error``.
_TERMINAL_REASONS: dict[type[BaseException], str] = {
    ContextOverflow: CONTEXT_OVERFLOW,
    OutputCapExceeded: OUTPUT_CAP_EXCEEDED,
    ContentPolicyBlocked: CONTENT_POLICY_BLOCKED,
    ModelUnavailable: MODEL_UNAVAILABLE,
    SchemaRejected: SCHEMA_REJECTED,
    RouteRateLimited: ROUTE_RATE_LIMITED,
    AuthUnavailable: AUTH_UNAVAILABLE,
    # Before ``GatewayTimeout`` in intent, and correct by MRO regardless:
    # ``DeadlineExpired`` is a subclass, so it is found first.
    DeadlineExpired: DEADLINE_EXPIRED,
    GatewayTimeout: GATEWAY_TIMEOUT,
    LLMError: ROUTE_ERROR,
}


def terminal_reason_for(error: BaseException) -> str:
    """The stable reason this route failure ends a Turn under."""
    for klass in type(error).__mro__:
        reason = _TERMINAL_REASONS.get(klass)
        if reason is not None:
            return reason
    return ROUTE_ERROR


# How the two recoveries this loop owns are bounded. ``core/llm/recovery.py``
# names the actions; the transcript and the output ceiling are the loop's to
# change, which is why the client hands both conditions up.
#
# **Compression** answers ``ContextOverflow``: the route measured what this
# process only estimates, so the estimate that fit was wrong and the remedy is
# to construct the call against a smaller ceiling. Two attempts, then the Turn
# ends — a third would mean compression is not converging, and a Turn that
# compresses forever spends a call per attempt to find that out.
MAX_CONTEXT_COMPRESSIONS = 2
CONTEXT_COMPRESSION_FACTOR = 0.6
# **Lowering the cap** answers ``OutputCapExceeded``. Halved rather than nudged,
# because the route refuses by an amount it does not disclose, and never below a
# floor at which the answer would be cut off mid-sentence — which is the
# ``answer_truncated`` failure this loop reports separately.
MAX_OUTPUT_TOKENS_REDUCTIONS = 2
OUTPUT_TOKENS_REDUCTION_FACTOR = 0.5
MIN_OUTPUT_TOKENS = 1_000

# How much of a call's ceiling one *round* may spend across its recoveries.
# Without a second bound here, a round that compresses twice and lowers its cap
# twice could spend five call ceilings and arrive at the Turn deadline — which
# ends the Turn without naming the route condition that caused it.
ROUND_TIMEOUT_MULTIPLE = 2.0

# The call timeout duplicates the transport's own by design. The transport's
# guards one HTTP request; this one guards the whole call including the retries
# the client makes inside it, so a route that answers slowly three times cannot
# quietly spend six minutes of a ten-minute Turn.
LLM_CALL_TIMEOUT_SECONDS = 120.0
# Shorter, because a tool reads the local store or one page of the open web:
# past this, waiting costs the Turn more than the result is worth.
TOOL_TIMEOUT_SECONDS = 30.0
# The whole Turn, wall clock, checked between rounds. ``turns.py`` holds the
# same number as a hard ``wait_for``; this one fires first at a round boundary,
# which is the difference between a Turn that ends with its partial answer
# attached and a task that is simply cancelled.
TURN_DEADLINE_SECONDS = 600.0

# How many calls to tools that cost money or reach off this deployment one Turn
# may make. A round cap alone does not bound this: one round may fan out to five
# searches.
#
# *Which* tools those are is asked of the registry rather than listed here. A
# Turn can now also read this system's own store, and those reads are a Postgres
# query inside the deployment — charging them against a ceiling that exists
# because a search costs money and a page belongs to somebody else would spend
# the web allowance on evidence that has neither property.
# Seven since 2026-08-29, and the number is a measurement rather than a
# preference. The goal it has to fund is two or three searches plus three or
# four page reads — five to seven calls — and six cut straight through the
# middle of that.
#
# What it cost, measured on ``llm_call_usage`` the day it moved: a web-first
# Turn ran 42,002 micro-USD on average over ten Turns (p50 34,447, max 70,694),
# across a mean of 3.6 model calls. One extra page read adds its own result to
# the transcript, and the transcript is resent on every later round, so the
# pessimistic marginal cost is the page cap (22,000 chars, roughly 7,300 tokens)
# times the rounds that follow it, times the input price of 2 micro-USD a token:
# about 58,000 micro-USD if the read lands in the first of four rounds. That puts
# a worst-case Turn near 100,000 against ``TURN_COST_MICRO_USD`` of 500,000 — a
# fivefold margin — and near 71,000 in the ordinary case.
#
# The envelope agrees. The Turn lane holds $30 of the $45 month, which buys
# roughly 420 web-first Turns at the new figure against 714 at the old one; this
# deployment has run 611 Turns in total, ever. The ceiling was never what money
# was short of.
#
# Below eight on purpose. ``executor.MAX_EXTERNAL_CALLS_PER_ROUND`` is 8, and
# while the Turn ceiling is under it the per-round gate has never fired in
# production; raising this to 8 or beyond would light up a path nothing has
# exercised, which is a different change with a different risk.
#
# It expires. The prices above are the route's prices on the day of the
# measurement, so a route change is a reason to run the arithmetic again rather
# than to trust this comment.
MAX_EXTERNAL_TOOL_CALLS = 7
EXTERNAL_TOOL_EXHAUSTED_MESSAGE = (
    "This turn has reached its limit on external tool calls. Answer from what has "
    "already been gathered, and say what you could not look up."
)

# The only remaining conversation surface is chat.
CHAT_MODE = "chat"

def domain_body_note() -> str:
    """The active pack's own half of the prompt, for a Turn that reached for it.

    A system note rather than a section of the rendered prompt: the prompt is
    rendered once per Turn and is identical across Turns, which makes it a
    cacheable prefix.
    Sent with every remaining call once it is on, like the mode note and unlike
    ``state.note``, because a playbook that lasted one round is a playbook the
    model has forgotten by the time the tool results come back.

    Read through ``active_pack`` rather than bound at import: the pack is what
    swapping a domain swaps, and a value copied into a module-level constant
    here is the copy a second domain would have to come back and edit.

    Written down for whoever turns prompt caching on: once
    ``LLMRoute.prompt_cache_control`` is live, a note at the tail is paid for in
    full on every call, and the right home for this text becomes a second block
    immediately after the core — still inside the cacheable head, cached from
    the second call onward. That is a decision for the phase that owns the cache
    boundary, and nothing here is built ahead of it.
    """
    return active_pack().body_text


def domain_body_tokens(state: "_TurnState") -> int:
    """What the pack body costs this call, or zero where it carries none.

    Nothing reserves this any more, and that is the improvement. The body used
    to be a message appended after the context was constructed, so the ceiling
    the transcript was trimmed against had to be lowered by a number computed
    here — and a reservation is only ever an estimate of a message somebody else
    builds. Since the body moved inside the system message it is measured like
    every other block of the prompt, by :func:`estimate_tokens`, from the string
    that actually goes out.

    Kept because the question is still worth asking — a diagnostic and the
    replay harness both want to know what a Turn is paying for its playbook —
    and because it is the one place that answer is written down.
    """
    return active_pack().body_tokens if state.domain_body else 0


ROUNDS_EXHAUSTED_NOTE = (
    f"All {MAX_TOOL_ROUNDS} tool rounds for this turn have been used. Answer from "
    "what has already been gathered, and say plainly what you were not able to "
    "look up."
)

# What a system note is priced at, and the length it is held to. One reservation
# rather than a measurement of the sentence that happens to apply: the budget
# that funds the call and the ceiling the context is constructed against must
# not disagree with the message that actually goes out.
SYSTEM_NOTE_TOKENS = 160

# What the model is told when it came back from a round of tools with no reply,
# and how many times a Turn may say it. One, and low on purpose: the same shape
# Hermes gives ``_post_tool_empty_retried``, a once-only flag. A second nudge
# buys a second paid call to learn what the first one already established.
#
# Said only where it can be acted on. A Turn that has not run a tool has nothing
# for this note to point at, and spending a call to ask it to try again would be
# the apology call this loop does not make.
MAX_EMPTY_NUDGES = 1
EMPTY_AFTER_TOOLS_NOTE = (
    "Your last message contained no answer for the reader — only the sentence "
    "introducing the tool calls. The results of those calls are above. Write the "
    "answer now from what they returned, and say plainly which part of the "
    "question they did not settle."
)

# How long one round's tools may take, all of them together. The calls of a
# round run concurrently, so this is a per-call ceiling for the ordinary batch
# and a total for the rare sequential one. Its own reason because its remedy is
# its own: a tool that never returns is a tool to fix, not a route to retry.
TOOL_TIMEOUT = "tool_timeout"


def trace_status(*, ok: bool, error: str | None) -> str:
    """One call's outcome in the vocabulary its column was declared with.

    The Tool Call Trace carries two different questions and one column each:
    ``status`` is the small closed set an ops reading groups by, and ``error`` is
    the specific reason under it. Writing ``"error"`` into ``status`` — which is
    not one of its four values — collapsed the first question into the second and
    left ``unknown_tool`` counting zero for every deployment that ever ran.

    Only two error names get a group of their own, and both because their remedy
    is their own: a tool that does not exist is a capability nobody has written,
    and a tool that does not answer is a bound that is missing. Everything else —
    a blocked call, a halted turn, a failed dispatch, a fan-out over the round's
    ceiling — is a tool call that went wrong, and the ``error`` column is where
    they stay told apart.
    """
    if ok:
        return TOOL_CALL_OK
    if error == UNKNOWN_TOOL:
        return TOOL_CALL_UNKNOWN_TOOL
    if error == TOOL_TIMEOUT:
        return TOOL_CALL_TIMEOUT
    return TOOL_CALL_TOOL_ERROR


class TurnStatus(str, Enum):
    """How a Turn ended, in the lifecycle table's own vocabulary."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    CANCELLED = "cancelled"


class SessionCapacityExceeded(AlphaRefusal):
    """The 4th concurrent session, refused rather than queued.

    Queueing behind a 60-second Turn puts the user in front of a spinner with no
    estimable end, so the answer is immediate and honest — and for the same
    reason it carries no ``Retry-After``: the only number that could go there
    would be a guess at when someone else's Turn ends.
    """

    def __init__(self, limit: int = SESSION_CONCURRENCY) -> None:
        super().__init__(
            reason="system_active_turns",
            message="The service is at its active Turn capacity. Try again shortly.",
            status_code=503,
        )
        self.limit = limit


class SessionSlots:
    """How many Turns run at the route at once, with no queue behind them.

    ``limit=None`` removes the ceiling, for a deployment whose configured
    ``active_turns_system`` is unlimited. Nothing else changes: a Turn still
    passes through :meth:`occupy`.
    """

    def __init__(self, limit: int | None = SESSION_CONCURRENCY) -> None:
        self._limit = limit
        self._semaphore = None if limit is None else asyncio.Semaphore(limit)

    @property
    def limit(self) -> int | None:
        return self._limit

    @property
    def full(self) -> bool:
        """Whether a Turn asking for a slot right now would be refused.

        Read without taking one, for admission: the ``POST`` has to answer 503
        *before* a stream opens rather than let the refusal surface as a terminal
        event seconds later. It is a sample and not a reservation — a Turn
        admitted here still meets :meth:`occupy`, and losing that race ends the
        Turn honestly, where losing this one would only have cost a round trip.
        """
        return self._semaphore is not None and self._semaphore.locked()

    @asynccontextmanager
    async def occupy(self):
        if self._semaphore is None:
            yield
            return
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


# Every reason ``SpendAdmission`` can refuse a Turn with, and the status each one
# is. Exhaustive on purpose: a reason with no entry here would fall through to a
# 500, turning a rule the user could act on into an outage they cannot.
#
# The split between 429 and 503 is by *whose* allowance ran out, not by how.
# ``user_active_turn`` is a capacity condition and a user one, so it is 429 — a
# rule the caller can act on. ``system_active_turns`` is the same kind of
# condition about everybody, so it is 503 with no ``Retry-After``.
ADMISSION_STATUS: dict[str, int] = {
    "user_turn_starts_daily": 429,
    "user_active_turn": 429,
    "user_spend_daily": 429,
    "user_spend_rolling_30d": 429,
    "lane_budget_exhausted": 503,
    "system_active_turns": 503,
}

# Anything unmapped is a refusal this file did not anticipate. 503 rather than
# 500, because every configured ceiling is a temporary condition and none of
# them is a fault.
UNMAPPED_ADMISSION_STATUS = 503


class TurnRefused(AlphaRefusal):
    """A Turn refused at admission, before a row or a stream existed.

    The two-request transport rests on one property: an admission failure
    never opens a stream. Folding admission into the stream
    would turn a refusal into an in-band event the client has to parse, and it
    would make the idempotency key arrive at the same moment as the work.
    """

    def __init__(
        self,
        reason: str,
        message: str,
        status_code: int,
        *,
        reset_at: datetime | None = None,
    ) -> None:
        super().__init__(reason=reason, message=message, status_code=status_code)
        self.reset_at = reset_at

    @classmethod
    def of(cls, refusal: BudgetRefusal) -> "TurnRefused":
        """Carry the ledger's own reason and sentence onto the wire unchanged."""
        return cls(
            reason=refusal.reason,
            message=refusal.message,
            status_code=ADMISSION_STATUS.get(refusal.reason, UNMAPPED_ADMISSION_STATUS),
            reset_at=refusal.reset_at,
        )


class TurnPreflight(Protocol):
    """The one thing admission needs from the spend ledger.

    Narrower than the ledger itself on purpose: admission must not be able to
    reserve anything, and a type that could would be an invitation to.
    """

    def preflight_turn(self, user_id: int, *, output_tokens: int) -> None: ...


class TurnAdmission:
    """The one question the ``POST`` asks before it creates anything.

    The ceilings are not this class's. They belong to
    ``core/llm/admission.py``, which is also the authority that enforces them at
    dispatch. What is here is the part the ledger cannot own: the in-process
    semaphore, and the mapping from a stable reason onto a status code.
    """

    def __init__(
        self,
        spend: TurnPreflight,
        *,
        slots: SessionSlots,
        output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    ) -> None:
        self._spend = spend
        self._slots = slots
        self._output_tokens = output_tokens

    async def admit(self, *, user_id: int) -> None:
        """Return quietly, or refuse with the reason and the status.

        The semaphore is asked first and costs no query. The two checks answer
        the same question from opposite sides — the ledger counts active rows
        across the deployment, the semaphore counts running tasks in this
        process — and either one being full is a full service.

        Async, and the ledger runs in a thread, because it is synchronous
        SQLAlchemy: calling it inside a coroutine blocks every other request in
        the process, which here would mean one user's admission query stalling
        every SSE stream this process is holding open.
        """
        if self._slots.full:
            raise TurnRefused(
                reason="system_active_turns",
                message="The service is at its active Turn capacity. Try again shortly.",
                status_code=503,
            )
        try:
            await asyncio.to_thread(
                self._spend.preflight_turn,
                user_id,
                output_tokens=self._output_tokens,
            )
        except BudgetRefusal as refusal:
            raise TurnRefused.of(refusal) from refusal


class ToolCallIdMismatch(MalformedArguments):
    """A tool call whose id cannot be trusted to identify it.

    A ``MalformedArguments`` rather than a class of its own: it is the same
    measured failure — the route violating its contract — and the taxonomy says
    what happens next, which is that the Turn fails immediately rather than
    ending with an answer built on results paired to the wrong call.
    """


# ---------------------------------------------------------------------------
# The request, the draft, and the outcome.
# ---------------------------------------------------------------------------


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
    #: The Turn's own id, where the caller has one.
    #:
    #: Optional because unit tests and offline harnesses may run without a
    #: persisted Turn row.
    turn_id: uuid.UUID | str | None = None
    #: What the reader attached to *this* question, payload included.
    #:
    #: Only this Turn's. The earlier Turns arrive through ``history`` carrying
    #: metadata alone, which is what stops the n-th question of a Thread from
    #: resending n images.
    attachments: tuple[TurnAttachment, ...] = ()


@dataclass(frozen=True)
class TurnDraft:
    """What has been produced so far, for checkpointing.

    ``boundary`` says this checkpoint is one of the named moments — a tool
    call, a cancellation, a terminal state — rather than ordinary
    progress. The rate limiter that keeps checkpoints to at most one a second
    reads it, and nothing else does.
    """

    text: str | None
    rounds_used: int
    tool_calls: tuple[TurnToolCall, ...]
    boundary: bool = False
    #: The reply alone, and the narration alone. Both derived from the same
    #: prose ``text`` already holds, and both checkpointed, because the surface
    #: rebuilding from a checkpoint has to draw the same two things the stream
    #: drew — a reader who reconnected must not lose the timeline.
    answer: str | None = None
    thoughts: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class TurnOutcome:
    """How the Turn ended, and what it leaves behind."""

    status: TurnStatus
    terminal_reason: str | None
    text: str | None
    rounds_used: int
    rounds_exhausted: bool
    tool_calls: tuple[TurnToolCall, ...]
    usage: Usage
    summary_needed: bool = False
    #: The reply without the narration, and the narration by round. ``text``
    #: stays whole beside them: it is what the next Turn's transcript is built
    #: from, and these two are what a screen draws.
    answer: str | None = None
    thoughts: tuple[Mapping[str, Any], ...] = ()
    #: Wall-clock milliseconds this Turn took, for the line that says so.
    elapsed_ms: int = 0
    #: The route's id for the last call it answered, so a disputed answer can be
    #: traced back at the provider. ``None`` when the route supplied none: the
    #: whole value of the field is that somebody can look it up.
    provider_request_id: str | None = None


class TurnPublisher(Protocol):
    """The three events this loop emits, as the transport must accept them.

    A protocol rather than an import so that the loop depends on the shape of
    the transport and not on its module: these methods are all a test needs to
    observe, and the SSE layer is free to add events of its own that the loop
    knows nothing about.

    A protocol rather than an import keeps the loop independent of transport.
    """

    def content_delta(self, text: str) -> Any:
        """Exactly the text just appended to the answer, in order."""

    def tool_call(self, payload: Mapping[str, Any]) -> Any:
        """One tool call's current state: ``id``, ``name``, ``status``, ``summary``."""


Checkpoint = Callable[[TurnDraft], Awaitable[None] | None]
Cancelled = Callable[[], bool]
#: How one tool call is written down. A callback rather than a store handle for
#: the reason the checkpoint is one: a Turn never holds a database session.
TraceWriter = Callable[[Mapping[str, Any]], Awaitable[Any] | Any]


def assert_distinct_ids(calls: Sequence[ToolCall]) -> None:
    """Refuse a round whose calls cannot be told apart.

    A gateway was *measured* keying streamed tool calls on a local counter
    instead of the upstream index, concatenating two calls' arguments into
    invalid JSON under the wrong id while returning 200. That class of failure
    never surfaces at runtime; it only makes the answers wrong. So a missing or
    repeated id ends the Turn here, loudly, rather than downstream quietly.
    """
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


@dataclass
class _TurnState:
    """Everything one Turn accumulates, in one place.

    A single mutable object rather than a dozen locals threaded through every
    terminal path: the terminal call sites differ only in status and reason, and
    a positional tail of six values is where a swap goes unnoticed.
    """

    #: Every piece of prose the Turn produced, joined. What the *model* reads
    #: next Turn, and deliberately unchanged by the split below: how a surface
    #: chooses to draw a sentence must not change what the model saw.
    started: float = field(default_factory=time.monotonic)
    #: Which surface asked, copied from the request so every terminal path can
    #: read it: :meth:`AgentLoop._ended` is reached from a dozen call sites and
    #: threading the request through all of them to answer one question is how
    #: one of them comes to be forgotten.
    #: Which Turn this is, which conversation it belongs to, and what was asked.
    turn_id: str | None = None
    thread_id: str | None = None
    question: str = ""
    text: str | None = None
    #: The same prose minus the thoughts: what the *reader* is shown as the
    #: reply. Held separately rather than derived by subtracting one string from
    #: another, because a subtraction would be exact only until two pieces
    #: happened to share a prefix.
    answer: str | None = None
    #: Prose written in a round that went on to call tools, keyed by that round.
    thoughts: dict[int, str] = field(default_factory=dict)
    tool_rounds: int = 0
    usage: Usage = field(default_factory=Usage)
    calls: list[TurnToolCall] = field(default_factory=list)
    #: Every page this Turn has already put in front of the reader, by the key
    #: that decides whether two links are one page (``messages.dedup_key``).
    #:
    #: Per-Turn because that is the scope the duplication actually has. Two
    #: searches issued in the same breath land on the same article often enough
    #: to matter — 21 of 223 links over a recorded run — while no single search
    #: returned one link twice, so a set scoped any narrower than this would be
    #: a set that never rejected anything.
    shown_sources: set[str] = field(default_factory=set)
    #: Every page the *model* has already been given, this Turn, by key.
    #:
    #: A second set rather than a reuse of ``shown_sources``, and the two are
    #: not the same question. That one is about a screen: a rail row is drawn
    #: once and never retracted, so a link enters it the moment it is rendered.
    #: This one is about a prompt: a search result is dropped from a later call
    #: only because an earlier call is *still carrying it*, and the two
    #: populations diverge the moment a result is capped for display
    #: (``MAX_DISPLAY_RESULTS``) or the moment a call is shown but not sent.
    #: Sharing one set would let a link the rail drew suppress a result the
    #: model never saw.
    context_sources: set[str] = field(default_factory=set)
    model_refused: bool = False
    summary_needed: bool = False
    request_id: str | None = None
    # How far this Turn has already given ground to the route. Both are per-Turn
    # rather than per-call: a Turn whose transcript was too large in round two is
    # a Turn whose transcript is too large, and rediscovering that in round three
    # costs another call.
    compressions: int = 0
    output_reductions: int = 0
    external_calls: int = 0
    # Per-Turn like the two above, and for the same reason: a route that answered
    # without a reply once has been asked again already, and rediscovering that in
    # a later round costs another call.
    empty_nudges: int = 0
    # The note waiting for the next call to carry it, and cleared by the call
    # that sent it: a Turn told twice about one observation has been charged
    # twice for it.
    note: str | None = None
    # Whether this Turn has been handed the active pack's half of the prompt.
    #
    # Per-Turn, like ``mode`` above and for the same reason: whether the reader
    # asked something about the domain is a fact about this Turn, and a flag one
    # level up would leak the answer into the next reader's Turn. ``_TurnState``
    # is built once per ``_run``, ``AgentLoop`` once per Turn, so this cannot
    # outlive the question that set it.
    #
    # Sticky once true. A model told the playbook in round two still needs it in
    # round three, when the tool results it has to read come back — and a rule
    # that arrives and leaves again is worse than one that never came, because
    # the answer is written under the version of the instructions the last call
    # happened to carry.
    domain_body: bool = False
    #: Where the last call's input tokens went, by layer.
    #:
    #: Held on the Turn rather than returned, because the two readers of it are
    #: not the caller of ``_call``: a measurement harness replaying this Turn
    #: wants the breakdown of the call that was actually sent, and a diagnostic
    #: wants the last one when a Turn ends badly. Overwritten each round, which
    #: is the honest shape — a round is what a composition describes.
    composition: ContextComposition = field(default_factory=ContextComposition)
    #: What identifies the cacheable head every call of this Turn sends.
    #:
    #: Carried so it can be attached to each request and read back off a trace
    #: — an answer that came out wrong is asked "which prompt produced it", and
    #: a version number alone cannot answer that once a domain pack can change
    #: the prompt without the version moving.
    #:
    #: It does **not** steer the provider. The route's cache is keyed on the
    #: first bytes of the request and always was; this is the harness's own name
    #: for those bytes, and calling it a cache key without saying so would
    #: invite somebody to "fix" caching by editing it.
    cache_identity: str = ""
    # Set when the guardrail ladder halted the tool loop. The Turn does not end:
    # it makes its answering call one round early, which is what the halt
    # guidance asks for — ending here would throw away evidence the reader was
    # already owed.
    tools_halted: bool = False

    def add_usage(self, usage: Usage | None) -> None:
        # ``None`` usage is not zero usage: a provider that supplied no evidence
        # has not told us the call was free, so it is skipped rather than added.
        if usage is not None:
            self.usage = self.usage + usage

    def narration(self) -> tuple[Mapping[str, Any], ...]:
        """What was said on the way to the answer, in round order."""
        return tuple(
            {"round": index, "text": text}
            for index, text in sorted(self.thoughts.items())
        )

    def draft(self, *, boundary: bool = False) -> TurnDraft:
        return TurnDraft(
            text=self.text,
            answer=self.answer,
            thoughts=self.narration(),
            rounds_used=self.tool_rounds,
            tool_calls=tuple(self.calls),
            boundary=boundary,
        )


class AgentLoop:
    """One Turn, from the user's message to a terminal state."""

    def __init__(
        self,
        *,
        client: LLMClient,
        config: LLMConfig,
        toolsets: Sequence[str] | str | None = None,
        budget: ContextBudget | None = None,
        slots: SessionSlots | None = None,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        checkpoint: Checkpoint | None = None,
        publisher: TurnPublisher | None = None,
        trace: TraceWriter | None = None,
        call_timeout_seconds: float = LLM_CALL_TIMEOUT_SECONDS,
        tool_timeout_seconds: float = TOOL_TIMEOUT_SECONDS,
        deadline_seconds: float | None = TURN_DEADLINE_SECONDS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        # A conversation's selection, never "every bundle this build registered".
        # One of those bundles reads this system's evidence plane for the
        # Analysis lane, and a default that expanded to everything would hand it
        # to every Turn (``toolsets.CHAT_TOOLSETS``).
        self._toolsets = CHAT_TOOLSETS if toolsets is None else toolsets
        self._budget = budget or ContextBudget()
        self._slots = slots or SessionSlots()
        self._max_output_tokens = max_output_tokens
        self._checkpoint = checkpoint
        self._publisher = publisher
        self._trace = trace
        self._call_timeout = call_timeout_seconds
        self._tool_timeout = tool_timeout_seconds
        self._deadline = deadline_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        # Resolved once, here. Models split by workload and never inside the
        # loop, because an in-loop cheap-router split adds a
        # decision point whose quality nothing measures.
        self._model = config.model_for(Workload.SESSION)
        # Read once from the route, here, and carried into every constructed
        # context. From the route rather than from ``get_settings()``: the flag
        # belongs to the route this client was built for, and asking the
        # environment again would be a second answer to the same question — one
        # that could say "vision" about a route the probe never measured.
        #
        # ``messages`` reads no configuration at all, which is what keeps
        # ``build_messages`` pure. This module has one unrelated settings read,
        # for how much of a question a log line may keep.
        self._vision = config.route.vision
        # The output budget scales with the window the harness actually sends,
        # not with whatever the model advertises: the constructed context is
        # capped at ``TURN_CONTEXT_PER_CALL`` by admission, so a share of a
        # larger window would be a share of context this loop never fills.
        self._context_tokens = self._budget.max_tokens

    # -- entry point ------------------------------------------------------

    async def run(
        self, request: TurnRequest, cancelled: Cancelled = lambda: False
    ) -> TurnOutcome:
        async with self._slots.occupy():
            return await self._run(request, cancelled)

    async def _run(self, request: TurnRequest, cancelled: Cancelled) -> TurnOutcome:
        state = _TurnState(
            turn_id=str(request.turn_id) if request.turn_id is not None else None,
            thread_id=str(request.thread_id),
            question=_asked(request.user_text),
        )
        surface = resolve_tool_surface(self._toolsets)
        tools = surface.offered_schemas
        # The identity of this Turn's cacheable head, computed once where every
        # part of it is already in hand. Model, prompt version and hash, the
        # resolved tool surface — the schemas travel in the same head as the
        # prompt — and the pack, because two Turns on the same model with the
        # same tools are not the same prompt under two domains.
        #
        # Nothing about *this* Turn is in it: no user, no thread, no date, no
        # mode, no question. A key carrying any of those would be a key that
        # never matches, which is a cache that costs and never pays.
        state.cache_identity = cache_key(
            self._model, surface.identity_digest, active_pack().identity
        )
        turn_budget = TurnBudget(
            thresholds_for_context(self._context_tokens),
            registry_limits={
                tool.name: tool.max_result_size_chars
                for tool in surface.tools
                if tool.max_result_size_chars is not None
            },
        )
        executor = ToolExecutor(
            context=registry.ToolContext(
                user_id=request.user_id,
                thread_id=_as_uuid(request.thread_id),
                turn_id=_as_uuid(request.turn_id),
                now=self._clock(),
            ),
            guardrails=TurnGuardrails(),
            trace=self._trace_writer(request, turn_budget),
            surface=surface,
        )
        system_prompt = render(request.runtime)
        state.domain_body = True

        for round_index in range(MAX_TOOL_ROUNDS + 1):
            if cancelled():
                return await self._ended(
                    state, TurnStatus.CANCELLED, CANCELLED_BY_USER
                )
            if self._expired(state):
                logger.info(
                    "Turn %s ran out of wall clock after %d round(s)",
                    request.request_message_id,
                    state.tool_rounds,
                )
                return await self._ended(
                    state, TurnStatus.INCOMPLETE, TURN_DEADLINE
                )

            # Two different reasons for one behaviour, kept apart because they
            # are told to the model differently. ``exhausted`` means the round
            # ceiling is reached, which the model is told about so it can say
            # what it could not look up. A halt from the guardrail ladder ends
            # the *tool* loop rather than the Turn — this call is the answering
            # one — but the rounds are not gone, and saying they are would be
            # false.
            exhausted = round_index == MAX_TOOL_ROUNDS
            final = exhausted or state.tools_halted

            try:
                completion = await self._call(
                    system_prompt, request, state, turn_budget, tools, final, exhausted
                )
            except MalformedArguments:
                # Counted and logged at the boundary, and never absorbed: the
                # route violated its contract, and an answer built on top of
                # that is an answer nobody can trust. Nothing is disabled here.
                raise
            except TimeoutError:
                # Our ceiling on one ``complete`` including every retry the
                # client made inside it, distinct from the transport's per-request
                # timeout and from the Turn deadline.
                return await self._ended(
                    state, TurnStatus.INCOMPLETE, LLM_CALL_TIMEOUT
                )
            except BudgetRefusal as refusal:
                # No further LLM call, of any kind. The partial answer and the
                # traces of what ran are what the user gets.
                logger.info(
                    "Turn %s ended without budget for its next call: %s",
                    request.request_message_id,
                    refusal.operator_detail or refusal.reason,
                )
                return await self._ended(
                    state, TurnStatus.INCOMPLETE, refusal.reason
                )
            except ModelRefusal as refusal:
                # An answer, and an answer nobody is shown is not a refusal but
                # a silence. So the words are published like any other prose and
                # the Turn ends complete.
                state.add_usage(refusal.usage)
                state.model_refused = True
                self._append_text(state, refusal.refusal or "")
                return await self._ended(state, TurnStatus.COMPLETE, MODEL_REFUSAL)
            except LLMError as error:
                return await self._ended(
                    state, TurnStatus.INCOMPLETE, self._route_failure(request, error)
                )

            state.add_usage(completion.usage)
            if completion.request_id:
                state.request_id = completion.request_id
            if completion.text:
                # A round that also asked for tools was narrating, not
                # concluding: the model said what it was about to look up. The
                # decision is made here because this is the one place both
                # halves of the completion are in hand — the prose and whether
                # any tool call came with it.
                self._append_text(
                    state,
                    completion.text,
                    thought=bool(completion.tool_calls) and not final,
                )
            await self._save(state)

            if completion.finish_reason == TRUNCATED:
                # The model ran out of room mid-sentence, so what arrived is the
                # front of an answer rather than an answer. Released as a
                # finished Turn it would read as the whole reply. The partial
                # text and the traces stay; what changes is that the Turn admits
                # it stopped.
                logger.info(
                    "Turn %s was truncated by the route's output ceiling",
                    request.request_message_id,
                )
                return await self._ended(
                    state, TurnStatus.INCOMPLETE, ANSWER_TRUNCATED
                )

            if final or not completion.tool_calls:
                if not state.answer:
                    # No reply, and ``_call`` either had nothing to point the
                    # model at or has already spent its one nudge. A Turn with
                    # no answer is not a finished answer: released as
                    # ``complete`` it puts a Turn on screen that says it is done
                    # and holds nothing to read, or — worse, because it looks
                    # deliberate — holds only the sentence that introduced the
                    # tool calls. Whatever narration there was still travels on
                    # the message; what changes is that the Turn admits it never
                    # answered.
                    logger.warning(
                        "Turn %s ended without an answer after %d round(s) of "
                        "tools and %d nudge(s)",
                        request.request_message_id,
                        state.tool_rounds,
                        state.empty_nudges,
                    )
                    return await self._ended(
                        state,
                        TurnStatus.INCOMPLETE,
                        EMPTY_ANSWER,
                        # Still true, and still the reader's business: a Turn that
                        # spent every round and then answered nothing is a
                        # different thing to fix from one that answered nothing on
                        # its first call.
                        rounds_exhausted=exhausted,
                    )
                return await self._ended(
                    state, TurnStatus.COMPLETE, None, rounds_exhausted=exhausted
                )

            assert_distinct_ids(completion.tool_calls)
            failed = await self._round(
                completion.tool_calls, state, turn_budget, executor
            )
            state.tool_rounds += 1
            await self._save(state, boundary=True)
            if failed is not None:
                return await self._ended(state, TurnStatus.INCOMPLETE, failed)

            # Cancellation stops *after* the in-flight calls complete. The one
            # tool that writes writes a single row of the user's own memory, so
            # there is nothing to roll back, and a half-cancel path costs more
            # than the call it would save.
            if cancelled():
                return await self._ended(
                    state, TurnStatus.CANCELLED, CANCELLED_BY_USER
                )

        raise RuntimeError(  # pragma: no cover - the range above is exhaustive
            "the round loop ended without a terminal state"
        )

    # -- the model call ---------------------------------------------------

    def _appended(
        self, request: TurnRequest, state: _TurnState, exhausted: bool
    ) -> tuple[tuple[Message, str, int], ...]:
        """The system messages added after the context was constructed.

        Each one comes with the layer it is charged to and what it is charged,
        so the caller has one list to send and one list to account for. The
        reservation in ``_construct`` reads the same values from the same
        helpers, which is what keeps the ceiling the transcript was trimmed
        against and the request that actually goes out from disagreeing.

        The pack body is **not** here, and used to be. It is prompt material,
        and since it moved into the system message it is carried and measured by
        the constructed context like the rest of the prompt — a Turn that
        reserved room for it here as well would be paying for it twice.
        """
        appended: list[tuple[Message, str, int]] = []
        if exhausted:
            appended.append(
                (
                    Message(role=Role.SYSTEM, content=ROUNDS_EXHAUSTED_NOTE),
                    SYSTEM_DYNAMIC,
                    SYSTEM_NOTE_TOKENS,
                )
            )
        if state.note:
            appended.append(
                (
                    Message(role=Role.SYSTEM, content=state.note),
                    SYSTEM_DYNAMIC,
                    SYSTEM_NOTE_TOKENS,
                )
            )
        return tuple(appended)

    def _construct(
        self,
        system_prompt: str,
        request: TurnRequest,
        state: _TurnState,
        turn_budget: TurnBudget,
        exhausted: bool,
    ) -> ConstructedContext:
        """Meet the constructed-context ceiling, notes and all.

        The ceiling is this loop's estimate; the route's is the real one. When
        the route says the estimate was wrong, ``state.compressions`` lowers ours
        and the ladder does the rest — dropping older Turns and collapsing their
        results in the order it already decided is safest.
        """
        budget = self._budget
        if state.compressions:
            budget = replace(
                budget,
                max_tokens=int(
                    budget.max_tokens
                    * CONTEXT_COMPRESSION_FACTOR ** state.compressions
                ),
            )
        # Room for whatever is appended after the context is built, read off
        # the same list ``_call`` appends, so the ceiling the transcript is
        # trimmed against and the request that actually goes out cannot
        # disagree. Dynamic notes live in ``_appended`` and are not restated here.
        reserved = sum(
            tokens for _, _, tokens in self._appended(request, state, exhausted)
        )
        if reserved:
            budget = replace(budget, max_tokens=budget.max_tokens - reserved)
        transcript = Transcript(
            system_prompt=system_prompt,
            # The prompt's own stable half, so a route configured for prompt
            # caching gets its breakpoint where ``prompt.prefix()`` draws it.
            # Ignored by every route that does not, and by the token estimate
            # either way.
            system_prefix=prompt_prefix(),
            # The pack's playbook, between the core and this Turn's values. A
            # Turn that has not touched the domain sends ``None`` and gets the
            # message it always got. Read every construction rather than once,
            # because the third trigger fires mid-Turn: the body appears on the
            # call after the model asks for a domain tool and stays to the end.
            system_body=domain_body_note() if state.domain_body else None,
            vision=self._vision,
            turns=(
                *request.history,
                TranscriptTurn(
                    user_text=request.user_text,
                    tool_calls=self._shown_calls(state, turn_budget),
                    attachments=request.attachments,
                ),
            ),
            summary=request.summary,
            summarised_turns=request.summarised_turns,
        )
        return build_messages(transcript, budget)

    def _shown_calls(
        self, state: _TurnState, turn_budget: TurnBudget
    ) -> tuple[TurnToolCall, ...]:
        """This Turn's calls with the output budget applied to their results.

        Applied on every construction rather than once when the result arrived,
        because rung three is a fact about the *Turn*: a result gathered three
        rounds ago can be asked to give ground now, and a copy trimmed at
        arrival could not.
        """
        trimmed = {result.call_id: result.text for result in turn_budget.rebalance()}
        if not trimmed:
            return tuple(state.calls)
        # ``context_text`` and never ``result_text``: rung three is the model's
        # copy giving ground, and writing the shorter string over the trace's
        # copy would make the audit record say the tool returned less than it
        # did.
        return tuple(
            replace(call, context_text=trimmed[call.id])
            if call.id in trimmed
            else call
            for call in state.calls
        )

    def _output_tokens(self, state: _TurnState) -> int:
        """The output ceiling this Turn is asking for now.

        Never below :data:`MIN_OUTPUT_TOKENS`: an answer cut off mid-sentence is
        the ``answer_truncated`` failure, and buying a call that fits by making
        its answer unusable is not a recovery.
        """
        ceiling = self._max_output_tokens
        for _ in range(state.output_reductions):
            ceiling = int(ceiling * OUTPUT_TOKENS_REDUCTION_FACTOR)
        return max(MIN_OUTPUT_TOKENS, ceiling)

    async def _complete(
        self,
        request: TurnRequest,
        messages: Sequence[Message],
        context: ConstructedContext,
        state: _TurnState,
        tools: Sequence[ToolSchema],
        final: bool,
        reserved_tokens: int,
    ) -> Completion:
        """One model call, reserved before dispatch and reconciled after.

        Both halves happen inside the client, which holds no transaction across
        the network call; the loop's job is to name the worst case honestly.
        """
        output_tokens = self._output_tokens(state)
        spend = SpendRequest(
            # Every provider call names a durable owner with a non-null id, and for this loop that owner is always the user's
            # request message.
            owner=CallOwner(
                type=OwnerType.TURN_REQUEST_MESSAGE,
                id=str(request.request_message_id),
                user_id=request.user_id,
            ),
            lane=BudgetLane.TURN,
            workload=Workload.SESSION,
            input_tokens=context.estimated_tokens + reserved_tokens,
            output_tokens=output_tokens,
        )
        return await asyncio.wait_for(
            self._client.complete(
                CompletionRequest(
                    model=self._model,
                    # Local to this process: ``metadata`` is read by this
                    # harness and by tests, and the transport does not put it on
                    # the wire. That is deliberate — the route has not been
                    # shown to read any cache field, and sending one it ignores
                    # would be a claim in the request body that nothing behind
                    # it honours.
                    metadata={"cache_identity": state.cache_identity},
                    messages=tuple(messages),
                    tools=tuple(tools),
                    # On the ceiling the model answers from what it has: another
                    # round of tools it cannot spend would come back as a call
                    # nobody runs.
                    tool_choice="none" if final else "auto",
                    parallel_tool_calls=True,
                    max_output_tokens=output_tokens,
                ),
                spend,
            ),
            self._call_timeout,
        )

    async def _call(
        self,
        system_prompt: str,
        request: TurnRequest,
        state: _TurnState,
        turn_budget: TurnBudget,
        tools: Sequence[ToolSchema],
        final: bool,
        exhausted: bool,
    ) -> Completion:
        """One round's model call, giving ground where the route says to.

        Two of the actions in ``core/llm/recovery.py`` belong here rather than in
        the client, because the transcript and the output ceiling are this loop's
        to change and the client was asked to send them as they were. Both are
        bounded, and both re-raise when their budget is spent so the terminal
        branch still owns the outcome.

        Bounded in time as well as in attempts: ``_complete`` caps one call
        including the client's retries, and this caps the round, because five
        calls at that cap would reach the Turn deadline — which ends a Turn
        without naming the condition these recoveries exist to report.
        """
        started = time.monotonic()

        def rebuild() -> ConstructedContext:
            return self._construct(
                system_prompt, request, state, turn_budget, exhausted
            )

        while True:
            context = rebuild()
            state.summary_needed = state.summary_needed or context.summary_needed
            appended = self._appended(request, state, exhausted)
            messages = [*context.messages, *(message for message, _, _ in appended)]
            # One arithmetic, not two. What funds the call is the sum of what
            # explains it, so the reservation cannot drift from the breakdown
            # the way two hand-copied expressions eventually would.
            composition = context.composition
            for _, layer, tokens in appended:
                composition = composition.plus(**{layer: tokens})
            state.composition = composition
            reserved = composition.total - context.estimated_tokens

            try:
                completion = await self._complete(
                    request, messages, context, state, tools, final, reserved
                )
            except LLMError as error:
                action = recovery_for(error).action
                if action is RouteAction.COMPRESS:
                    self._compress(request, state, context, rebuild, error, started)
                    continue
                if action is RouteAction.LOWER_OUTPUT_CAP:
                    self._lower_output_cap(request, state, error, started)
                    continue
                raise

            if self._nudge_empty(request, state, completion, started):
                continue

            # Spent on the call that carried it, so a model that answers a note
            # with tool calls does not carry it into a third attempt.
            state.note = None
            return completion

    def _compress(
        self,
        request: TurnRequest,
        state: _TurnState,
        context: ConstructedContext,
        rebuild: Callable[[], ConstructedContext],
        error: LLMError,
        started: float,
    ) -> None:
        """Give up transcript and ask again, or re-raise having tried.

        Re-raises rather than returning a flag: every exit from this function
        except "compressed, try again" is the original condition, and a caller
        that had to inspect a return value could forget one of them.
        """
        if state.compressions >= MAX_CONTEXT_COMPRESSIONS:
            logger.warning(
                "Turn %s did not fit the context window after %d compression(s): %s",
                request.request_message_id,
                state.compressions,
                redact(str(error)),
            )
            raise error
        if self._round_spent(started) or self._expired(state):
            # A round that has already used its share of the Turn is not given
            # another call: the next thing it would meet is the Turn deadline,
            # and that path ends the Turn without this reason attached.
            raise error
        state.compressions += 1
        try:
            # Rebuilt at the new ceiling to find out whether anything was
            # actually given up, using the caller's own closure so the two
            # constructions cannot drift apart in their arguments.
            smaller = rebuild()
        except ConstructedContextTooLarge:
            # The compressed ceiling is below what the protected Turn needs even
            # fully collapsed. That is still the route's ``context_overflow``,
            # and raising the constructor's own error instead would leave the
            # Turn with nothing to classify it by.
            state.compressions -= 1
            raise error from None
        if smaller.estimated_tokens >= context.estimated_tokens:
            # Nothing was given up, so the next call would be the call that was
            # just refused. This is the ordinary shape of a short Turn whose
            # *prompt* is most of its input: there is no older Turn to drop.
            # Paying for an identical attempt to discover that is exactly the
            # waste the compression budget exists to bound.
            state.compressions -= 1
            raise error
        logger.info(
            "Turn %s did not fit at %d estimated token(s); compressing to %d "
            "(%d of %d) and asking again: %s",
            request.request_message_id,
            context.estimated_tokens,
            smaller.estimated_tokens,
            state.compressions,
            MAX_CONTEXT_COMPRESSIONS,
            redact(str(error)),
        )

    def _lower_output_cap(
        self,
        request: TurnRequest,
        state: _TurnState,
        error: LLMError,
        started: float,
    ) -> None:
        """Reserve less output and ask again, or re-raise having tried.

        Never folded into compression, and the distinction is the whole point:
        here the transcript fits and the *reserved output ceiling* is what pushed
        the total over, so trimming the transcript would throw away evidence the
        Turn already paid for and fix nothing.
        """
        if state.output_reductions >= MAX_OUTPUT_TOKENS_REDUCTIONS:
            logger.warning(
                "Turn %s could not fit its reserved output ceiling beside its "
                "input, down to %d token(s) after %d reduction(s): %s",
                request.request_message_id,
                self._output_tokens(state),
                state.output_reductions,
                redact(str(error)),
            )
            raise error
        if self._round_spent(started) or self._expired(state):
            raise error
        previous = self._output_tokens(state)
        state.output_reductions += 1
        reduced = self._output_tokens(state)
        if reduced >= previous:
            # Already at the floor, so the next attempt would send the same
            # request and be refused the same way.
            state.output_reductions -= 1
            raise error
        logger.info(
            "Turn %s could not reserve %d output token(s); asking for %d instead: %s",
            request.request_message_id,
            previous,
            reduced,
            redact(str(error)),
        )

    def _nudge_empty(
        self,
        request: TurnRequest,
        state: _TurnState,
        completion: Completion,
        started: float,
    ) -> bool:
        """Ask once more for the answer a round of tools never produced.

        A bool rather than the raise the other two recoveries use, and the
        difference is not a style choice: they are handed a route condition and
        every exit but one is that condition re-raised. Here nothing failed. The
        route answered, the answer was paid for, and it contained no reply — so
        there is no exception to carry and the caller decides what an absent
        answer means.

        The condition is ``state.answer`` and not ``state.text``. The Contract
        asks the model for one sentence before every tool call
        (``prompt/sections.py``), and :meth:`_append_text` files those sentences
        as thoughts, so a Turn that ran tools almost always has prose. What it
        can lack is a *reply*, and a Turn whose whole reply is "let me look that
        up" is the failure this treats: ``turns.py`` falls back to the narration
        when there is no answer, which publishes the introduction as though it
        were the conclusion.

        Only where the note can be acted on, which means only after a round of
        tools. Before that there is nothing above for the model to read and the
        call would buy an apology.
        """
        # ``completion.text`` and not only ``state.answer``: this runs inside the
        # call, before :meth:`_append_text` has filed anything, so the state still
        # describes the rounds *before* this one. A completion that brought prose
        # of its own is about to become the reply.
        if completion.tool_calls or completion.text or state.answer:
            return False
        if state.tool_rounds == 0 or state.empty_nudges >= MAX_EMPTY_NUDGES:
            return False
        if self._round_spent(started) or self._expired(state):
            # Same bound the other two recoveries take: a round that has spent
            # its share of the Turn is not given another call, because the next
            # thing it would meet is the Turn deadline — which ends the Turn
            # without naming this condition.
            return False
        state.empty_nudges += 1
        state.note = EMPTY_AFTER_TOOLS_NOTE
        logger.warning(
            "Turn %s produced no reply after %d round(s) of tools "
            "(model=%s finish_reason=%r); asking once more",
            request.request_message_id,
            state.tool_rounds,
            completion.model,
            completion.finish_reason,
        )
        return True

    # -- one round of tools -----------------------------------------------

    async def _round(
        self,
        calls: Sequence[ToolCall],
        state: _TurnState,
        turn_budget: TurnBudget,
        executor: ToolExecutor,
    ) -> str | None:
        """Announce, dispatch, and record one round. Every call gets a result.

        Answers the terminal reason the round produced, or ``None`` when the Turn
        may continue. A round has exactly one way to end a Turn — its tools not
        answering inside :data:`TOOL_TIMEOUT_SECONDS` — and every other failure
        is a result the model reads.

        A call the external-tool budget stops is answered with the reason rather
        than dropped, for the reason the executor answers a blocked one: a tool
        call with no result at all is a transcript the model has to guess at, and
        most routes refuse the request outright.
        """
        planned: list[TurnToolCall] = []
        runnable: list[ExecutorToolCall] = []
        for call in calls:
            # The client proves every tool call's arguments parse before a
            # ``Completion`` exists, so this is a second line of defence rather
            # than the invariant: a route that hands over something that is not
            # an arguments object gets it passed through to the executor, which
            # answers the model with what was wrong with it. Crashing here would
            # turn a route's contract violation into a 500.
            arguments = dict(call.arguments) if isinstance(call.arguments, Mapping) else {}
            resolved = (
                None
                if executor.surface is None
                else executor.surface.by_name.get(call.name)
            )
            record = TurnToolCall(
                id=call.id,
                name=call.name,
                arguments=arguments,
                summary=summarise_call(call.name, arguments, resolved=resolved),
                signature=call.signature,
                round=state.tool_rounds,
                resolved_tool=resolved,
            )
            if record.reads_external:
                if state.external_calls >= MAX_EXTERNAL_TOOL_CALLS:
                    record = replace(
                        record,
                        status=ToolCallStatus.ERROR,
                        error="external_budget_exhausted",
                        result_text=EXTERNAL_TOOL_EXHAUSTED_MESSAGE,
                        dispatched=False,
                    )
                    planned.append(record)
                    continue
                state.external_calls += 1
            planned.append(record)
            runnable.append(
                ExecutorToolCall(
                    id=call.id, name=call.name, arguments=call.arguments
                )
            )

        index = {record.id: position for position, record in enumerate(planned)}
        state.calls.extend(planned)
        offset = len(state.calls) - len(planned)
        for record in planned:
            # Only what is about to run is announced as running. A call the
            # budget already refused has one state, not two, and publishing a
            # ``running`` it never entered would put a spinner on screen for
            # work nobody started.
            if record.status is ToolCallStatus.RUNNING:
                self._publish_call(record)

        outcome: ExecutionOutcome | None = None
        timed_out = False
        if runnable:
            try:
                outcome = await asyncio.wait_for(
                    executor.run(runnable), self._tool_timeout
                )
            except TimeoutError:
                # The tools each bound their own network and database work, so
                # reaching this means one of those bounds is missing or wrong.
                # The Turn ends here rather than waiting out its whole deadline
                # on a call that is not coming back.
                timed_out = True
                logger.warning(
                    "A round of %d tool call(s) did not answer within %.0fs",
                    len(runnable),
                    self._tool_timeout,
                )
            else:
                for result in outcome.results:
                    position = offset + index[result.call_id]
                    finished = replace(
                        state.calls[position],
                        status=(
                            ToolCallStatus.OK if result.ok else ToolCallStatus.ERROR
                        ),
                        result_text=result.text,
                        # What the model reads, which is the result minus the
                        # pages this Turn has already put in front of it. Built
                        # from the same structured payload the display
                        # projection is built from, and beside it, so there is
                        # one place a result becomes two audiences' copies.
                        context_text=context_projection(
                            result.tool_name,
                            result.payload,
                            result.text,
                            seen=state.context_sources,
                        ),
                        error=result.error,
                        guidance=result.guidance,
                        duration_ms=result.duration_ms,
                        dispatched=result.dispatched,
                        # Built from the structured payload rather than by
                        # re-parsing ``result.text``: the executor already holds
                        # the object, and a second parse is a second chance to
                        # read a provider's JSON differently from the first.
                        results=display_results(
                            result.tool_name,
                            result.payload,
                            seen=state.shown_sources,
                        ),
                        # The advisory scan's verdict, carried from where the
                        # result first existed. Never merged into ``guidance``:
                        # guidance is the harness talking to the model, and this
                        # is the harness talking to the reader.
                        scan=result.scan,
                    )
                    state.calls[position] = finished
                    # The budget measures what the model is given, not what
                    # the tool returned. Rungs two and three decide how much of
                    # a Turn's results have to give ground, and deciding that
                    # against a longer string than the one being sent would trim
                    # a context that already fitted.
                    turn_budget.add(
                        finished.id, finished.name, finished.model_text
                    )

        # The results the budget never saw, because they never ran. Added anyway,
        # so the trimming ladder measures the same set of results the model
        # reads.
        for record in planned:
            if not record.dispatched and record.model_text:
                turn_budget.add(record.id, record.name, record.model_text)

        if timed_out:
            # Settled rather than left running, so a reader who reconnects to the
            # finished Turn is not shown a spinner on a call nothing is waiting
            # for any more.
            for position in range(offset, len(state.calls)):
                call = state.calls[position]
                if call.status is ToolCallStatus.RUNNING:
                    state.calls[position] = replace(
                        call,
                        status=ToolCallStatus.ERROR,
                        error=TOOL_TIMEOUT,
                        dispatched=False,
                    )

        for position in range(offset, len(state.calls)):
            self._publish_call(state.calls[position])

        if timed_out:
            return TOOL_TIMEOUT

        if outcome is not None and outcome.halted:
            state.tools_halted = True
            # Carried as a system note rather than appended to a result: it is
            # about the Turn, not about any one call, and the next call is the
            # answering one.
            state.note = outcome.guidance
            logger.info(
                "Tool calling halted after %d round(s): %s",
                state.tool_rounds,
                outcome.halt_reason,
            )
        return None

    def _trace_writer(
        self, request: TurnRequest, turn_budget: TurnBudget
    ) -> TraceWriter | None:
        """Adapt the executor's trace entry to the Tool Call Trace row.

        The executor knows what happened to a call; only the loop knows which
        Turn it happened in. So the shapes are joined here, in the one place
        both facts exist, rather than by giving the executor a request it has no
        other use for.

        The body is written down, not just its size. With no citations and no
        manifest, the Tool Call Trace is the only surviving record of what an
        answer rested on, and a column holding a character count answers no
        question anyone would open it to ask. It is held to the same per-result
        budget the model reads under, so one enormous page cannot make a row
        nothing can load — the count beside it says how much was cut.
        """
        writer = self._trace
        if writer is None:
            return None

        async def write(entry: Mapping[str, Any]) -> None:
            name = str(entry.get("tool") or "")
            body = str(entry.get("result_text") or "")
            stored, _cursor = trim_text(body, turn_budget.limit_for(name))
            written = writer(
                {
                    "thread_id": request.thread_id,
                    "request_message_id": request.request_message_id,
                    "tool_name": name,
                    "tool_call_id": entry.get("call_id"),
                    "arguments": dict(entry.get("arguments") or {}),
                    "result": {
                        "text": stored,
                        "chars": len(body),
                        "dispatched": bool(entry.get("dispatched", True)),
                    },
                    "status": trace_status(
                        ok=bool(entry.get("ok")),
                        error=(
                            str(entry["error"])
                            if entry.get("error") is not None
                            else None
                        ),
                    ),
                    "error": entry.get("error"),
                    "latency_ms": entry.get("duration_ms"),
                }
            )
            if inspect.isawaitable(written):
                await written

        return write

    # -- publication and checkpointing ------------------------------------

    def _append_text(
        self,
        state: _TurnState,
        piece: str,
        *,
        thought: bool = False,
    ) -> None:
        """Append prose and publish exactly what was appended.

        One step rather than two, because the property that matters is that the
        answer stored on the message and the concatenation of the deltas are the
        same string: a browser that followed the stream and a browser that
        rebuilt from a checkpoint must not be able to disagree about what was
        said. The separator therefore travels *inside* the delta.

        ``thought`` marks prose from a round that went on to call tools. Such a
        piece still joins ``state.text``, because that is what the model reads
        next Turn and nothing about how a surface draws it should change what
        the model saw. It additionally joins ``state.thoughts`` under the
        current round, and goes out as a delta the surface files in its timeline
        rather than in the answer.
        """
        if not piece:
            return
        state.text = piece if state.text is None else f"{state.text}\n\n{piece}"
        if thought:
            index = state.tool_rounds
            state.thoughts[index] = state.thoughts.get(index, "") + piece
            if self._publisher is not None:
                self._publisher.content_delta(piece, kind=THOUGHT, round=index)
            return
        # The separator travels inside the delta, which is what keeps the
        # concatenation of the answer deltas equal to the stored answer.
        delta = piece if state.answer is None else f"\n\n{piece}"
        state.answer = (state.answer or "") + delta
        if self._publisher is not None:
            self._publisher.content_delta(delta, kind=ANSWER, round=state.tool_rounds)

    def _publish_call(self, call: TurnToolCall) -> None:
        if self._publisher is not None:
            self._publisher.tool_call(call.as_wire())

    async def _save(self, state: _TurnState, *, boundary: bool = False) -> None:
        if self._checkpoint is None:
            return
        saved = self._checkpoint(state.draft(boundary=boundary))
        if inspect.isawaitable(saved):
            await saved

    # -- terminal ---------------------------------------------------------

    def _route_failure(self, request: TurnRequest, error: LLMError) -> str:
        """Log one route failure at the level its remedy deserves, and name it.

        The only place the route's own words survive. Without them a
        ``route_error`` Turn is indistinguishable from every other one, and the
        difference between a retired model, a refused schema and a rate limit is
        exactly what an operator acts on.
        """
        reason = terminal_reason_for(error)
        # Ours to fix, so it is an error: a route that refused our schemas or
        # stopped serving the configured model fails every Turn until somebody
        # changes something here.
        loud = reason in {SCHEMA_REJECTED, MODEL_UNAVAILABLE}
        logger.log(
            logging.ERROR if loud else logging.WARNING,
            "Turn %s ended on %s: %s",
            request.request_message_id,
            reason,
            redact(str(error)),
        )
        return reason

    async def _ended(
        self,
        state: _TurnState,
        status: TurnStatus,
        terminal_reason: str | None,
        *,
        rounds_exhausted: bool = False,
    ) -> TurnOutcome:
        """Checkpoint what survived, then describe how the Turn ended.

        Every terminal path runs through here, including the ones that end
        badly. A Turn that ran out of budget, lost its credential or was
        cancelled still produced prose, and prose is what makes an ``incomplete``
        useful rather than empty — the difference between ``incomplete`` and
        ``failed``.

        """
        await self._save(state, boundary=True)
        return TurnOutcome(
            status=status,
            terminal_reason=terminal_reason,
            text=state.text,
            answer=state.answer,
            thoughts=state.narration(),
            elapsed_ms=int((time.monotonic() - state.started) * 1000),
            rounds_used=state.tool_rounds,
            rounds_exhausted=rounds_exhausted,
            tool_calls=tuple(state.calls),
            usage=state.usage,
            summary_needed=state.summary_needed,
            provider_request_id=state.request_id,
        )

    # -- clocks -----------------------------------------------------------

    def _round_budget(self) -> float:
        """How long one round may spend, retries and recoveries included."""
        return self._call_timeout * ROUND_TIMEOUT_MULTIPLE

    def _round_spent(self, started: float) -> bool:
        return time.monotonic() - started >= self._round_budget()

    def _expired(self, state: _TurnState) -> bool:
        """Whether the Turn has run out of the wall clock it was given."""
        if self._deadline is None:
            return False
        return time.monotonic() - state.started >= self._deadline


#: How much of a question is kept in the record below, in development. Long
#: enough to tell two questions apart when they are read as a list, short enough
#: that a pasted report does not become a log line nobody scrolls past.
ASKED_LIMIT = 200

#: The same, anywhere that is not development. A reader's question is theirs;
#: outside the machine it was typed on, the log keeps enough to see the shape
#: of what was asked and no more.
ASKED_LIMIT_OUTSIDE_DEBUG = 60

#: The two calls whose pairing this looks for.


def _asked(text: str) -> str:
    """The question, shortened to what this environment may keep of it."""
    limit = ASKED_LIMIT if get_settings().debug else ASKED_LIMIT_OUTSIDE_DEBUG
    asked = " ".join(text.split())
    if len(asked) <= limit:
        return asked
    return asked[: limit - 1] + "…"


def _as_uuid(identifier: uuid.UUID | str | None) -> uuid.UUID | None:
    """One of the Turn's ids as a UUID, or ``None`` when it is not one.

    ``None`` rather than a raise: these ids reach the tools as the scope of a
    read and as the owner of a row, and a Turn whose thread id is a test fixture
    should still be answerable — the tools ask about the *user*, who is always
    known, and a row with no owner is reachable by its own id.
    """
    if isinstance(identifier, uuid.UUID):
        return identifier
    if identifier is None:
        return None
    try:
        return uuid.UUID(str(identifier))
    except (TypeError, ValueError):
        return None


__all__ = [
    "ADMISSION_STATUS",
    "ANSWER_TRUNCATED",
    "ASKED_LIMIT",
    "AUTH_UNAVAILABLE",
    "CANCELLED_BY_USER",
    "CHARS_PER_TOKEN",
    "CHAT_MODE",
    "CONTENT_POLICY_BLOCKED",
    "CONTEXT_COMPRESSION_FACTOR",
    "CONTEXT_OVERFLOW",
    "DEADLINE_EXPIRED",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "EXTERNAL_TOOL_EXHAUSTED_MESSAGE",
    "GATEWAY_TIMEOUT",
    "LLM_CALL_TIMEOUT",
    "LLM_CALL_TIMEOUT_SECONDS",
    "MAX_CONTEXT_COMPRESSIONS",
    "MAX_EXTERNAL_TOOL_CALLS",
    "MAX_OUTPUT_TOKENS_REDUCTIONS",
    "MAX_SUMMARY_CHARS",
    "MAX_TOOL_ROUNDS",
    "MESSAGE_OVERHEAD_TOKENS",
    "MIN_OUTPUT_TOKENS",
    "MODEL_REFUSAL",
    "MODEL_UNAVAILABLE",
    "OUTPUT_CAP_EXCEEDED",
    "OUTPUT_TOKENS_REDUCTION_FACTOR",
    "ROUNDS_EXHAUSTED_NOTE",
    "ROUND_TIMEOUT_MULTIPLE",
    "ROUTE_ERROR",
    "ROUTE_RATE_LIMITED",
    "SCHEMA_REJECTED",
    "SESSION_CONCURRENCY",
    "SUMMARY_LABEL",
    "SYSTEM_NOTE_TOKENS",
    "TOOL_TIMEOUT",
    "TOOL_TIMEOUT_SECONDS",
    "TRUNCATED",
    "TURN_DEADLINE",
    "TURN_DEADLINE_SECONDS",
    "UNMAPPED_ADMISSION_STATUS",
    "AgentLoop",
    "ConstructedContext",
    "ConstructedContextTooLarge",
    "ContextBudget",
    "SessionCapacityExceeded",
    "SessionSlots",
    "ToolCallIdMismatch",
    "ToolCallStatus",
    "Transcript",
    "TranscriptTurn",
    "TurnAttachment",
    "TurnDraft",
    "TurnAdmission",
    "TurnOutcome",
    "TurnPreflight",
    "TurnPublisher",
    "TurnRefused",
    "TurnRequest",
    "TurnStatus",
    "TurnToolCall",
    "assert_distinct_ids",
    "domain_body_note",
    "domain_body_tokens",
    "build_messages",
    "estimate_tokens",
    "shown_result",
    "summarise_call",
    "terminal_reason_for",
    "trace_status",
]
