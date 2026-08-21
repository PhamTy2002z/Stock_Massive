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

**Rounds, not calls.**  Four tool-call rounds per Turn — ``MAX_TOOL_ROUNDS``,
and the constant is the authority.  On the ceiling one further call with
``tool_choice="none"`` lets the model answer from what it has, and the
transcript says all four lookup steps were used — information, not an error.  An
answer built on incomplete data beats a blank one, provided its incompleteness
is visible.

Four rather than eight because the round count is not free to choose: a Turn is
admitted against ``TURN_OUTPUT_TOKENS`` and makes at most ``MAX_TOOL_ROUNDS + 1``
calls, so the round count and ``DEFAULT_MAX_OUTPUT_TOKENS`` are one piece of
arithmetic that ``test_the_turn_cannot_outspend_what_it_was_admitted_against``
holds.  Eight rounds buys back the per-call ceiling that a reasoning route spent
entirely on hidden thinking, which is the truncation this file already fixed
once.

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
    ContentPolicyBlocked,
    ContextOverflow,
    DeadlineExpired,
    GatewayTimeout,
    RouteAttempt,
    ModelUnavailable,
    OutputCapExceeded,
    RouteRateLimited,
    SchemaRejected,
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
from src.core.llm.errors import MAX_TOOL_ATTEMPTS, redact

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
from .events import Activity, TurnPublisher, append_step
from .grounding import (
    BLOCKED_TURN_NOTICE,
    GROUNDING_FAILED,
    REPAIR_FALLBACK,
    REPAIR_GUIDANCE,
    BlockKind,
    Citation,
    GroundingFailure,
    RecommendationValidator,
    ReleasedBlock,
    TraceIndex,
    is_recommendation_draft,
    repair_instruction,
)
from .progress import (
    ProgressSource,
    found_detail,
    merge_sources,
    queries_of,
    searching_detail,
    sources_of,
)
from .prompt import AnswerEvidence, AnswerKind, RuntimeContext, classify_answer_kind, render
from . import suggestions
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
MAX_TOOL_ROUNDS = 4

# ``docs/adr/0008``: in-process is correct because uvicorn runs a single worker.
SESSION_CONCURRENCY = 3

# What one call may produce, reasoning included — a reasoning model bills its
# hidden thinking against this same ceiling, so a per-call budget that only fits
# an answer leaves the model no room to reach one. At 2,000 a route that thinks
# at length spent the whole allowance thinking and returned four tokens of
# prose with ``finish_reason`` ``length``: a truncated answer rather than a
# short one.
#
# The three constants here are one piece of arithmetic. A Turn is admitted
# against ``TURN_OUTPUT_TOKENS`` (20,000) in aggregate, and it makes at most
# ``MAX_TOOL_ROUNDS`` + 1 calls, so this ceiling times that count is what the
# Turn can cost at worst. Raising either one without lowering the other spends
# a Turn budget that Budget Validation has already proven against the price
# table, so ``test_the_turn_cannot_outspend_what_it_was_admitted_against``
# holds the identity rather than a comment asking for it to be respected.
DEFAULT_MAX_OUTPUT_TOKENS = 4_000

# What the route calls a completion it had to cut short, and the stable reason
# the Turn ends under when it does. Both are strings the interactive surface
# maps to a sentence; neither is ever shown to the reader as a code.
TRUNCATED = "length"
ANSWER_TRUNCATED = "answer_truncated"

# The stable reasons the five newly named route conditions end a Turn under.
# Named here beside ``ANSWER_TRUNCATED`` because they are the same kind of
# string: the interactive surface maps each to a sentence, none is ever shown as
# a code, and the ops snapshot's ``incomplete_reasons`` tally splits them
# because it groups by whatever this file writes. Before them all five arrived
# as ``route_error``, which counted a retired model and an oversized transcript
# as the same event.
CONTEXT_OVERFLOW = "context_overflow"
OUTPUT_CAP_EXCEEDED = "output_cap_exceeded"
CONTENT_POLICY_BLOCKED = "content_policy_blocked"
MODEL_UNAVAILABLE = "model_unavailable"
SCHEMA_REJECTED = "schema_rejected"
# Our own deadline, kept apart from the route's. ``gateway_timeout`` used to
# carry both, which made the ops snapshot unable to say whether the fix was on
# the route's side or in this process's connection pool.
DEADLINE_EXPIRED = "deadline_expired"

# How the two recoveries this loop owns are bounded (``core/llm/recovery.py``
# names them; the transcript and the output ceiling are the loop's to change).
#
# **Compression** answers ``ContextOverflow``: the route measured what this
# process only estimates, so the estimate that fit is wrong and the remedy is to
# construct the call against a smaller ceiling. Two attempts, then the Turn ends
# — a third would mean compression is not converging, and a Turn that compresses
# forever spends a call per attempt to find that out.
#
# **Lowering the cap** answers ``OutputCapExceeded``: the transcript fits and the
# reserved output ceiling is what pushed the total over. Halved rather than
# nudged, because the route refuses by an amount it does not disclose, and never
# below a floor at which the answer would be cut off mid-sentence — which is the
# ``answer_truncated`` failure this file already fixed once.
MAX_CONTEXT_COMPRESSIONS = 2
CONTEXT_COMPRESSION_FACTOR = 0.6
MAX_OUTPUT_CAP_REDUCTIONS = 2
OUTPUT_CAP_REDUCTION_FACTOR = 0.5
MIN_OUTPUT_TOKENS = 1_000

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

# How many times one Turn's answer may be put through the Gate. Two, so the
# model gets exactly one nudge: the first validation finds the problem and the
# note goes out with the next call, the second is final and whatever it decides
# stands — refused blocks stay off the screen, downgraded ones are replaced by
# the backend's sentence.
#
# A count rather than the flag this used to be, because the cost of a nudge is a
# whole model call: if the per-Turn spend measured in ``llm_call_usage`` climbs
# after the Gate's default was inverted, lowering this to 1 removes every nudge
# without touching another line.
MAX_GATE_ATTEMPTS = 2

# The Gate's one piece of feedback, and the only one there will be. It names the
# condition and the rule; ``grounding.repair_instruction`` guarantees it carries
# no figure, so the rewrite cannot be a restatement of a number the model was
# just told about.

REPAIR_NOTE = (
    "Part of the answer you just wrote was withheld before the reader saw it. "
    "{guidance} Rewrite the whole answer once, with every figure referenced. "
    "This is the only rewrite you get: a figure you still cannot reference is a "
    "figure you do not state."
)
# Priced at its longest wording rather than at the one this Turn happens to
# need, for the same reason the rounds-exhausted note is built once: the budget
# that funds the call and the context ceiling it is constructed against must not
# disagree with the message that actually goes out. A guidance line added later
# is measured here automatically.
REPAIR_NOTE_TOKENS = max(
    estimate_tokens(
        Message(role=Role.SYSTEM, content=REPAIR_NOTE.format(guidance=guidance))
    )
    for guidance in (*REPAIR_GUIDANCE.values(), REPAIR_FALLBACK)
)

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
WEB_TOOLS = frozenset({"web_search", "fetch_url"})
MAX_EXTERNAL_TOOL_CALLS = 6
EXTERNAL_TOOL_EXHAUSTED_MESSAGE = (
    "This Turn has reached its external-tool call limit. Answer from the evidence "
    "already gathered."
)


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
    # The activity trail, checkpointed for the same reason the blocks are: a
    # reader who reconnects to a frozen Turn sees what it got through
    # (``docs/adr/0020``).
    progress: tuple[Mapping[str, Any], ...] = ()

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
    # Every Gate condition that downgraded a block while the Turn went on to
    # answer around it, in order. The Manifest reports these as a blocked
    # recommendation, exactly as it reports one that ended a Turn.
    degraded_codes: tuple[str, ...] = ()
    # How many of those downgrades were drafts carrying a recommendation.
    degraded_recommendations: int = 0

    @property
    def degraded_recommendation_code(self) -> str | None:
        """The first downgrade, for the readers that record exactly one."""
        return self.degraded_codes[0] if self.degraded_codes else None
    # Prose blocks released with one or more figures the Turn could not
    # attribute. Recommendations never contribute: they are blocked instead.
    downgraded_blocks: int = 0
    # The activity trail as the canonical message will store it, and the
    # follow-up questions offered under the answer (``docs/adr/0020``).
    progress: tuple[Mapping[str, Any], ...] = ()
    suggestions: tuple[str, ...] = ()

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
    # The nudge the Gate is allowed, and how many validations it has spent. A
    # refused block is usually a misplaced marker rather than an invented
    # figure, so the model gets one chance to fix its own reference — but only
    # one, and after it the block is downgraded rather than the Turn ended. The
    # ceiling is a count rather than a flag so lowering it to zero nudges is one
    # constant away: the cost of a nudge is a whole model call.
    repair_note: str | None = None
    gate_attempts: int = 0
    # How far this Turn has already given ground to the route, and both are
    # per-Turn rather than per-call: a Turn whose transcript was too large in
    # round two is a Turn whose transcript is too large, and rediscovering that
    # in round three costs another call.
    compressions: int = 0
    output_cap_reductions: int = 0
    # The draft the Gate would have released, kept only when a nudge was spent on
    # an answer that did not need one to survive.
    #
    # A downgrade-only failure means the answer *was* releasable: proven blocks
    # plus the backend's own sentences. The nudge asks the model to attach every
    # figure to a reference, and a reference attached to the wrong call is
    # ``figure_mismatch`` — integrity, which ends the Turn. So the nudge can turn
    # an answer the reader would have received into a blank one. This is the
    # floor under that: the earlier draft is proven again and released instead.
    releasable_text: str | None = None
    # Every Gate condition that downgraded a block while the Turn went on to
    # answer around it, in the order they happened. A list rather than one
    # value: an answer has several blocks, each can be downgraded for its own
    # reason, and a single field would report the last one as though it were the
    # only one. Separate from ``grounding_failure_code``, which is the condition
    # that *ended* a Turn — a downgrade is a block withheld, not a Turn refused.
    degraded_codes: list[str] = field(default_factory=list)
    # How many of those downgrades were drafts actually carrying a
    # recommendation. Counted because the Manifest's ``recommendation`` dimension
    # answers "how often did the Gate refuse a recommendation", and with twenty
    # conditions downgrading on *any* block a market-summary paragraph with one
    # misplaced bracket would otherwise answer it "yes".
    degraded_recommendations: int = 0

    @property
    def degraded_recommendation_code(self) -> str | None:
        """The first downgrade, for the readers that record exactly one.

        The Manifest's ``failure_code`` and the ops query's dimension are single
        values and were before any of this; the full list travels beside them
        rather than instead of them.
        """
        return self.degraded_codes[0] if self.degraded_codes else None
    external_tool_calls: int = 0
    # The open-web trail (``docs/adr/0020``): every phase in order, and the
    # public pages behind the ones that searched.
    progress: list[dict[str, Any]] = field(default_factory=list)
    sources: tuple[ProgressSource, ...] = ()
    result_count: int = 0
    suggestions: tuple[str, ...] = ()

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
            progress=tuple(dict(step) for step in self.progress),
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
        suggest: bool = False,
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
        # The cheap model, for the one non-answer call a Turn makes: the
        # follow-up questions under the answer (``docs/adr/0020``).
        #
        # Off unless asked. Every other provider call this loop makes is part of
        # producing the answer; this one is not, and a loop constructed for a
        # test or for the Eval Battery should not quietly spend money on a
        # garnish nobody in that context reads.
        self._suggest = suggest
        self._suggestion_model = config.model_for(Workload.BATCH)

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
            repairing = state.repair_note is not None

            await self._activity(Activity.ANALYZING, state)
            try:
                completion = await self._call(
                    system_prompt, request, state, final, repairing=repairing
                )
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
            except RouteRateLimited as limited:
                # Its own reason because the remedy is its own: the route
                # answered, and what it said was that this caller has spent its
                # allowance. Nothing here retries it — see ``RouteRateLimited``
                # — and the reader is told to wait rather than told the route is
                # unreachable.
                logger.info(
                    "Turn %s stopped on a rate-limited route (retry_after=%s, "
                    "reset_at=%s)",
                    request.request_message_id,
                    limited.retry_after,
                    limited.reset_at,
                )
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, "route_rate_limited", state
                )
            except DeadlineExpired as expired:
                # *We* stopped waiting, which the client has already answered by
                # rebuilding its transport and asking again. Its own reason
                # because its remedy is its own: an expiry here points at this
                # process's connection pool or at a deadline set too low for the
                # model, while a 504 points at the route.
                attempt = expired.attempt or RouteAttempt()
                logger.warning(
                    "Turn %s stopped waiting for the route after %d attempt(s), "
                    "%.1fs on the last one, %d byte(s) received: %s",
                    request.request_message_id,
                    attempt.attempts,
                    attempt.elapsed_seconds,
                    attempt.bytes_received,
                    redact(str(expired)),
                )
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, DEADLINE_EXPIRED, state
                )
            except GatewayTimeout as timeout:
                # Already retried with backoff inside the client; a third
                # attempt here would silently double the tabled ceiling.
                #
                # Logged for the reason the ``LLMError`` branch below is: this
                # was the only terminal path in the loop that ended a Turn
                # without saying anything, so three quarters of the Turns that
                # died on the route left nothing to classify them by. What a
                # timeout needs beyond the message is how much was spent
                # reaching it — attempts, elapsed, and whether any of the answer
                # arrived — because a route that never spoke and a route that
                # broke off mid-answer are different incidents.
                attempt = timeout.attempt
                if attempt is None or not attempt.measured:
                    # A 5xx is a ``GatewayTimeout`` too, and it arrives with no
                    # measurements: the route answered, quickly and with a body.
                    # Printing "0 byte(s) received" for it would assert the one
                    # thing that number exists to rule out.
                    logger.warning(
                        "Turn %s ended on a gateway timeout after %d attempt(s) "
                        "(the route answered rather than went quiet, so nothing "
                        "was measured): %s",
                        request.request_message_id,
                        attempt.attempts if attempt else 1,
                        redact(str(timeout)),
                    )
                else:
                    logger.warning(
                        "Turn %s ended on a gateway timeout after %d attempt(s), "
                        "%.1fs on the last one, %d byte(s) received: %s",
                        request.request_message_id,
                        attempt.attempts,
                        attempt.elapsed_seconds,
                        attempt.bytes_received,
                        redact(str(timeout)),
                    )
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, "gateway_timeout", state
                )
            except MalformedArguments:
                # Counted and logged at the boundary. Nothing is disabled here.
                raise
            except ContextOverflow as overflow:
                # Reached only after ``_call`` compressed as far as it is allowed
                # to. The remedy was tried and did not work, so the reason stands
                # and the ops snapshot now counts a converging failure rather
                # than an untried one.
                logger.warning(
                    "Turn %s ended because its transcript did not fit the "
                    "context window after %d compression(s): %s",
                    request.request_message_id,
                    state.compressions,
                    redact(str(overflow)),
                )
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, CONTEXT_OVERFLOW, state
                )
            except OutputCapExceeded as capped:
                # Distinct from the above and never folded into it: here the
                # transcript fits and it is the reserved output ceiling that
                # pushed the total over, so trimming the transcript would throw
                # away evidence the Turn already paid for and fix nothing.
                logger.warning(
                    "Turn %s ended because the reserved output ceiling did not "
                    "fit beside its input, down to %d token(s) after %d "
                    "reduction(s): %s",
                    request.request_message_id,
                    self._output_tokens(state),
                    state.output_cap_reductions,
                    redact(str(capped)),
                )
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, OUTPUT_CAP_EXCEEDED, state
                )
            except ContentPolicyBlocked as blocked:
                # The route's filter, not the model — so unlike a
                # ``ModelRefusal`` there are no words of the model's to carry,
                # and the Turn ends incomplete rather than complete.
                logger.warning(
                    "Turn %s was refused by the route's content filter: %s",
                    request.request_message_id,
                    redact(str(blocked)),
                )
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, CONTENT_POLICY_BLOCKED, state
                )
            except ModelUnavailable as unavailable:
                # Nothing here is transient, which is why it is not a timeout.
                # ``error`` rather than ``warning``: a route that stopped serving
                # the configured model fails every Turn until somebody changes
                # configuration.
                logger.error(
                    "Turn %s ended because the route does not serve the "
                    "configured model: %s",
                    request.request_message_id,
                    redact(str(unavailable)),
                )
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, MODEL_UNAVAILABLE, state
                )
            except SchemaRejected as rejected:
                # Loud because it is ours to fix: the Tool Catalog wrote the
                # schemas this route refused.
                logger.error(
                    "Turn %s ended because the route refused our tool schemas: %s",
                    request.request_message_id,
                    redact(str(rejected)),
                )
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, SCHEMA_REJECTED, state
                )
            except LLMError as error:
                # The only place the route's own words survive. Without them a
                # ``route_error`` Turn is indistinguishable from every other
                # one, and the difference between a retired model, an answer
                # with no choices and a refused request is exactly what an
                # operator needs to act on.
                #
                # Now the residue rather than the catch-all: the five classes
                # above carry the conditions that used to arrive here shapeless,
                # so what is left is a 400 whose body this repository has never
                # seen — and the body is what tells us which class it belongs in.
                logger.warning(
                    "Turn %s ended on an unclassified route error: %s",
                    request.request_message_id,
                    redact(str(error)),
                )
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, "route_error", state
                )

            state.add_usage(completion.usage)
            if completion.request_id:
                state.request_id = completion.request_id
            if completion.text:
                state.text = completion.text
            await self._save(state)

            if completion.finish_reason == TRUNCATED:
                # The model ran out of room mid-sentence, so whatever arrived is
                # the front of an answer rather than an answer. Released as a
                # finished Turn it reads as the whole reply — the shape this
                # surfaced in was a single block saying "The user" under a
                # question about the news. The partial text and the traces stay;
                # what changes is that the Turn admits it stopped.
                logger.info(
                    "Turn %s was truncated by the route's output ceiling",
                    request.request_message_id,
                )
                return await self._terminal(
                    request, TurnStatus.INCOMPLETE, ANSWER_TRUNCATED, state
                )

            if final or not completion.tool_calls:
                # The Gate's one rewrite, and only while a round is left to
                # spend on it: on the final round there is no call to carry the
                # note, so the Turn ends the way it always did.
                if not final and self._repair(request, state):
                    await self._save(state)
                    continue
                return await self._terminal(
                    request, TurnStatus.COMPLETE, None, state, rounds_exhausted=final
                )

            assert_distinct_ids(completion.tool_calls)
            searching = any(
                call.name == NEWS_TOOL or call.name in WEB_TOOLS
                for call in completion.tool_calls
            )
            await self._activity(
                Activity.SEARCHING if searching else Activity.READING_DATA,
                state,
                # The queries come from the arguments of the calls about to run,
                # so the chips are on screen while the search happens rather
                # than as a caption on work the reader watched finish.
                detail=searching_detail(queries_of(completion.tool_calls)),
            )
            before = len(state.calls)
            fatal = await self._round(
                completion.tool_calls, request, tool_context, attempts, state
            )
            state.tool_rounds += 1
            await self._found_sources(state, state.calls[before:])
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
        *,
        repairing: bool = False,
    ) -> ConstructedContext:
        """Meet the constructed-context ceiling, note and all.

        The ceiling is this loop's estimate; the route's is the real one. When
        the route says the estimate was wrong, ``state.compressions`` lowers ours
        and the ladder in ``context.py`` does the rest — dropping older Turns and
        collapsing their results in the order it already decided is safest.
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
        if final:
            budget = replace(
                budget, max_tokens=budget.max_tokens - ROUNDS_EXHAUSTED_TOKENS
            )
        if repairing:
            budget = replace(budget, max_tokens=budget.max_tokens - REPAIR_NOTE_TOKENS)
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
        state: _TurnState,
        *,
        repairing: bool = False,
    ) -> Completion:
        """One model call, reserved before dispatch and reconciled after.

        Both halves happen inside the client, which holds no transaction across
        the network call; the loop's job is to name the worst case honestly.
        """
        output_tokens = self._output_tokens(state)
        spend = SpendRequest(
            owner=self._spend.owner(request),
            lane=self._spend.lane,
            workload=Workload.SESSION,
            input_tokens=context.estimated_tokens
            + (ROUNDS_EXHAUSTED_TOKENS if final else 0)
            + (REPAIR_NOTE_TOKENS if repairing else 0),
            output_tokens=output_tokens,
        )
        return await asyncio.wait_for(
            self._client.complete(
                CompletionRequest(
                    model=self._model,
                    messages=tuple(messages),
                    tools=self._catalog.tool_schemas,
                    tool_choice="none" if final else "auto",
                    parallel_tool_calls=True,
                    max_output_tokens=output_tokens,
                ),
                spend,
            ),
            self._call_timeout,
        )

    def _output_tokens(self, state: _TurnState) -> int:
        """The output ceiling this Turn is asking for now.

        Never below :data:`MIN_OUTPUT_TOKENS`: an answer cut off mid-sentence is
        the ``answer_truncated`` failure, and buying a call that fits by making
        its answer unusable is not a recovery.
        """
        ceiling = self._max_output_tokens
        for _ in range(state.output_cap_reductions):
            ceiling = int(ceiling * OUTPUT_CAP_REDUCTION_FACTOR)
        return max(MIN_OUTPUT_TOKENS, ceiling)

    async def _call(
        self,
        system_prompt: str,
        request: TurnRequest,
        state: _TurnState,
        final: bool,
        *,
        repairing: bool,
    ) -> Completion:
        """One round's model call, giving ground where the route says to.

        Two of the recoveries in ``core/llm/recovery.py`` belong here rather than
        in the client, because the transcript and the output ceiling are this
        loop's to change and the client was asked to send them as they were. Both
        are bounded and both re-raise when their budget is spent, so the terminal
        branches above still own the outcome.

        The repair note is cleared only once a call has carried it. A compression
        that discarded it would nudge the model with a note the next call never
        sends, which is a nudge paid for and not delivered.
        """
        while True:
            context = self._construct(
                system_prompt, request, state, final, repairing=repairing
            )
            state.summary_needed = state.summary_needed or context.summary_needed
            messages = list(context.messages)
            if final:
                messages.append(ROUNDS_EXHAUSTED_MESSAGE)
            if repairing and state.repair_note is not None:
                messages.append(Message(role=Role.SYSTEM, content=state.repair_note))

            try:
                completion = await self._complete(
                    request, messages, context, final, state, repairing=repairing
                )
            except ContextOverflow as overflow:
                if state.compressions >= MAX_CONTEXT_COMPRESSIONS:
                    raise
                state.compressions += 1
                smaller = self._construct(
                    system_prompt, request, state, final, repairing=repairing
                )
                if smaller.estimated_tokens >= context.estimated_tokens:
                    # Nothing was given up, so the next call would be the call
                    # that was just refused. This is the ordinary shape of a
                    # short Turn whose *prompt* is most of its input: the ladder
                    # protects the current Turn, and there is no older one to
                    # drop. Paying for an identical attempt to discover that is
                    # exactly the waste the compression budget exists to bound.
                    state.compressions -= 1
                    raise
                logger.info(
                    "Turn %s did not fit the context window at %d estimated "
                    "token(s); compressing to %d (%d of %d) and asking again: %s",
                    request.request_message_id,
                    context.estimated_tokens,
                    smaller.estimated_tokens,
                    state.compressions,
                    MAX_CONTEXT_COMPRESSIONS,
                    redact(str(overflow)),
                )
                continue
            except OutputCapExceeded as capped:
                if state.output_cap_reductions >= MAX_OUTPUT_CAP_REDUCTIONS:
                    raise
                previous = self._output_tokens(state)
                state.output_cap_reductions += 1
                reduced = self._output_tokens(state)
                if reduced >= previous:
                    # Already at the floor, so the next attempt would send the
                    # same request and be refused the same way.
                    state.output_cap_reductions -= 1
                    raise
                logger.info(
                    "Turn %s could not reserve %d output token(s); asking for %d "
                    "instead: %s",
                    request.request_message_id,
                    previous,
                    reduced,
                    redact(str(capped)),
                )
                continue

            # Spent on the call that carried it, so a model that answers the note
            # with tool calls does not carry it into a third attempt.
            if repairing:
                state.repair_note = None
            return completion

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
        denials: list[str | None] = []
        bounded: list[bool] = []
        for call, allowed in zip(calls, admitted):
            denial = None
            if allowed and self._catalog.is_external(call.name):
                if state.external_tool_calls >= MAX_EXTERNAL_TOOL_CALLS:
                    allowed = False
                    denial = EXTERNAL_TOOL_EXHAUSTED_MESSAGE
                else:
                    state.external_tool_calls += 1
            bounded.append(allowed)
            denials.append(denial)
        outcomes = await asyncio.gather(
            *(
                self._dispatch(call, request, tool_context, allowed, denial)
                for call, allowed, denial in zip(calls, bounded, denials)
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
                    signature=call.signature,
                )
            )
        return fatal

    async def _dispatch(
        self,
        call: ToolCall,
        request: TurnRequest,
        tool_context: ToolContext,
        allowed: bool,
        denial: str | None = None,
    ) -> tuple[str, Mapping[str, Any]]:
        """Run one tool under its own deadline, carrying its id back with it."""
        if not allowed:
            return call.id, tool_error_result(
                call.id, call.name, denial or TOOL_EXHAUSTED_MESSAGE
            )
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

    async def _activity(
        self,
        activity: Activity,
        state: _TurnState,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        """Say what phase the Turn is in, and — for the open web — with what.

        No tool name, symbol, argument, raw result, prompt or reasoning reaches
        this from a store-reading lane: that detail stays in the Tool Call Trace
        (``docs/adr/0013``). ``detail`` is the one narrow exception
        ``docs/adr/0020`` grants the open web, and it is built by
        :mod:`src.agent.progress` rather than here, so the shape that may be
        disclosed has exactly one definition.

        An activity is also one of the four checkpoint boundaries ADR-0013
        names, so the draft is saved here past the once-a-second limiter: the
        phase a reconnecting reader is shown has to match the phase the Turn is
        actually in — and now so does the trail behind it.
        """
        append_step(state.progress, {"phase": activity.value, "detail": detail})
        if self._publisher is None:
            return
        self._publisher.activity(activity, detail)
        await self._save(state, boundary=True)

    async def _found_sources(
        self, state: _TurnState, calls: Sequence[TranscriptToolCall]
    ) -> None:
        """Announce what an open-web round came back with, if anything did.

        Separate from the ``searching`` phase because they are different facts
        at different moments: one is what was asked, the other is what answered.
        A round that touched no open-web tool, or found nothing, publishes
        nothing — an empty *Found 0 results* row is noise on a Turn that was
        never searching in the first place.
        """
        found: list[ProgressSource] = []
        for call in calls:
            result = call.result if isinstance(call.result, Mapping) else {}
            found.extend(sources_of(call.name, result))
        if not found:
            return
        # The count is every result the Turn has seen, not the length of the
        # list under it: the list is deduplicated and capped for display, and
        # the reader is being told how much was read, not how much is shown.
        state.result_count += len(found)
        state.sources = merge_sources(state.sources, found)
        await self._activity(
            Activity.FOUND_SOURCES,
            state,
            detail=found_detail(state.sources, state.result_count),
        )

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
        whatever it was about to be. When it was the *only* block, the reader
        still gets :data:`BLOCKED_TURN_NOTICE` — an empty answer under a finished
        search trail says nothing except that the product failed.
        """
        try:
            selections = self._prove(request, state)
        except GroundingFailure as failure:
            recovered = self._fall_back_to_pre_nudge_draft(request, state, failure)
            if recovered is None:
                logger.info(
                    "Turn %s blocked a content block: %s",
                    request.request_message_id,
                    failure,
                )
                state.grounding_failure_code = failure.code
                self._publish_blocks(state)
                if not state.blocks:
                    self._publish_blocked_notice(state)
                # A blocked answer has nothing to illustrate and nothing to
                # follow up: illustrating it would put the figure back on screen
                # that the Gate just kept off it.
                return await self._ended(
                    TurnStatus.INCOMPLETE, GROUNDING_FAILED, state, False
                )
            selections = recovered

        self._publish_blocks(state)
        await self._release_widgets(request, state, selections)
        await self._suggest_followups(request, status, state)
        return await self._ended(status, terminal_reason, state, rounds_exhausted)

    def _fall_back_to_pre_nudge_draft(
        self,
        request: TurnRequest,
        state: _TurnState,
        failure: GroundingFailure,
    ) -> tuple[WidgetSelection, ...] | None:
        """The draft from before the nudge, when the rewrite came back worse.

        ``None`` when there is nothing to fall back to, which is every Turn that
        was never nudged and every Turn whose first attempt was already refused.

        The case this exists for is created by the nudge itself. A
        downgrade-only failure means the answer *was* releasable — proven blocks
        plus the backend's own sentences — and the nudge then asks the model to
        attach every figure to a reference. A reference attached to the wrong
        call is ``figure_mismatch``: integrity, which ends the Turn. Without this
        the reader loses an answer they would have been given one call earlier,
        for a reason that had nothing to do with their question.

        Re-proving cannot raise: this text already proved with downgrades only,
        and the Gate is deterministic over the same traces.
        """
        if state.releasable_text is None:
            return None
        logger.info(
            "Turn %s kept the draft from before its nudge, because the rewrite "
            "failed %s",
            request.request_message_id,
            failure,
        )
        state.text = state.releasable_text
        state.releasable_text = None
        return self._prove(request, state)

    async def _suggest_followups(
        self, request: TurnRequest, status: TurnStatus, state: _TurnState
    ) -> None:
        """Ask the cheap model what the reader might want next.

        Only under an answer that was actually given: a Turn that ended
        ``incomplete``, refused, or released no block has nothing to follow up,
        and offering "what else would you like to know" under an answer that
        could not be given reads as the system not having noticed
        (``docs/adr/0020``).

        Nothing here can end the Turn. :func:`suggestions.generate` swallows its
        own failures, and the worst case is an answer with no panel under it.
        """
        if not self._suggest or status is not TurnStatus.COMPLETE or not state.blocks:
            return
        if state.model_refused:
            return
        answer = "\n\n".join(block.text for block in state.blocks if block.text)
        if not answer.strip():
            return
        body = suggestions.build_request(
            model=self._suggestion_model,
            user_text=request.user_text,
            answer_text=answer,
        )
        state.suggestions = await suggestions.generate(
            self._client,
            body,
            suggestions.spend_for(
                body,
                owner=self._spend.owner(request),
                lane=self._spend.lane,
                estimated_input_tokens=sum(
                    estimate_tokens(message) for message in body.messages
                ),
            ),
        )

    def _prove(
        self, request: TurnRequest, state: _TurnState
    ) -> tuple[WidgetSelection, ...]:
        """Prove each block into ``state.blocks``. Publishes nothing.

        Proof is separated from publication because the Gate is now allowed one
        piece of feedback (:data:`REPAIR_NOTE`): the loop has to know whether an
        answer holds up *before* any of it is on screen, or a rewrite would
        publish the surviving blocks of the first attempt twice. Nothing here
        reaches the publisher, so there is no state in which an invalid block was
        displayed and later retracted — and no state in which a block was
        displayed before the answer it belongs to was withdrawn.

        The blocks proven before a failing one stay in ``state.blocks``, and
        :meth:`_publish_blocks` still emits them. That is the point of failing
        per block rather than per answer — the user keeps the part that was
        proven. Called again for the rewrite, it starts from an empty list: the
        second answer replaces the first one whole.

        Widget markers come out *before* the split, and that ordering is load
        bearing twice over: the Recommendation Validator never sees one, so a
        selection can never be mistaken for the evidence reference attributing
        the figure in front of it; and a selection that is later rejected has
        already been removed from what the reader sees, so a dropped Widget
        leaves no stray marker in the prose.
        """
        state.blocks.clear()
        # Cleared with the blocks, for the same reason: proving runs again for
        # the nudge, and the second answer replaces the first one whole. Left
        # standing, a condition the rewrite fixed would still be recorded
        # against the Turn.
        state.degraded_codes.clear()
        state.degraded_recommendations = 0
        if not state.text:
            return ()
        answer, selections = extract_selections(state.text)
        validator = RecommendationValidator(trading_day=request.runtime.trading_day)
        traces = TraceIndex(state.calls)
        for raw in split_blocks(answer):
            try:
                block = validator.validate(raw, traces)
            except GroundingFailure as failure:
                if not failure.degradable:
                    raise
                # The block is dropped, never shown: what the reader gets
                # instead is the backend's own sentence naming the condition
                # that was not met. The blocks that already passed stay, so a
                # Turn that could not prove one paragraph still answers rather
                # than going blank.
                #
                # Which sentence depends on what the draft was trying to be,
                # read from the draft itself: most conditions fire while a
                # marker is being resolved, before the block's kind is known,
                # and telling a reader who asked about today's market that no
                # price zone was recommended would answer a question they did
                # not ask.
                logger.info(
                    "Turn %s downgraded a block: %s",
                    request.request_message_id,
                    failure,
                )
                was_recommendation = is_recommendation_draft(raw)
                state.degraded_codes.append(failure.code)
                if was_recommendation:
                    state.degraded_recommendations += 1
                notice = failure.notice(recommendation=was_recommendation)
                if any(existing.text == notice for existing in state.blocks):
                    # Three paragraphs failing the same condition produce three
                    # copies of one sentence, which reads as a stutter rather
                    # than as three facts. With twenty conditions downgrading on
                    # any block, multi-block downgrades are the common case. The
                    # code is still recorded once per block above: the record
                    # counts, the screen does not repeat.
                    continue
                block = ReleasedBlock(
                    text=notice,
                    kind=BlockKind.PROSE,
                    # Backend-authored and figure-free, so there is nothing for
                    # it to cite and nothing in it left unattributed.
                    citations=(),
                )
            state.blocks.append(block)
        return selections

    def _publish_blocks(self, state: _TurnState) -> None:
        """Emit what was proven, in the order it was written."""
        if self._publisher is None:
            return
        for block in state.blocks:
            self._publisher.content_block(block.as_wire())

    def _publish_blocked_notice(self, state: _TurnState) -> None:
        """Say that nothing could be proven, rather than saying nothing at all.

        Only when the Gate left the answer empty. A Turn that released even one
        block has already told the reader something, and appending this under it
        would read as a retraction of what did pass.
        """
        notice = ReleasedBlock(
            text=BLOCKED_TURN_NOTICE,
            kind=BlockKind.PROSE,
            # Backend-authored and figure-free, exactly like the degraded
            # recommendation notice: nothing to cite, nothing unattributed.
            citations=(),
        )
        state.blocks.append(notice)
        if self._publisher is not None:
            self._publisher.content_block(notice.as_wire())

    def _repair(self, request: TurnRequest, state: _TurnState) -> bool:
        """Whether this answer needs a nudge and one is still owed.

        Proving twice — here and again in :meth:`_terminal` — costs a regex pass
        over prose the Turn already holds, and buys the property that matters:
        the terminal path stays the only place that publishes, so no answer is
        ever half on screen while its rewrite is being written.

        Two conditions earn a nudge, and inverting the Gate's default is what
        made the second one necessary:

        * a **refused** block, which is an integrity failure and ends the Turn
          if the rewrite does not fix it;
        * a **downgraded** block, which does not end the Turn but does cost the
          reader the paragraph. Before the inversion these raised, so they came
          through the first branch; after it they do not raise at all, and
          without this branch the model would never again be asked to fix a
          misplaced marker — the answer would silently become the backend's
          apology sentence instead.

        The ceiling is :data:`MAX_GATE_ATTEMPTS` validations, so at most one
        nudge per Turn. That is the count the loop already spent at worst, and
        the cost of raising it is a whole model call.
        """
        state.gate_attempts += 1
        if state.gate_attempts >= MAX_GATE_ATTEMPTS:
            # This validation was the last one funded. Proving again here would
            # only discover a problem no call remains to carry a note about, so
            # the terminal path proves once and whatever it decides stands.
            return False
        try:
            self._prove(request, state)
        except GroundingFailure as failure:
            logger.info(
                "Turn %s asked the model to rewrite a refused block: %s",
                request.request_message_id,
                failure,
            )
            state.repair_note = REPAIR_NOTE.format(
                guidance=repair_instruction(failure.code)
            )
            return True
        if state.degraded_codes:
            logger.info(
                "Turn %s asked the model to rewrite a downgraded block: %s",
                request.request_message_id,
                ", ".join(state.degraded_codes),
            )
            # Nothing raised, so this draft is releasable as it stands. Kept
            # before the nudge, because the nudge is allowed to make it worse.
            state.releasable_text = state.text
            state.repair_note = REPAIR_NOTE.format(
                guidance=repair_instruction(state.degraded_codes[0])
            )
            return True
        return False

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
            degraded_codes=tuple(state.degraded_codes),
            degraded_recommendations=state.degraded_recommendations,
            downgraded_blocks=sum(
                bool(block.unverified_figures) for block in state.blocks
            ),
            progress=tuple(dict(step) for step in state.progress),
            suggestions=state.suggestions,
        )


__all__ = [
    "ANSWER_TRUNCATED",
    "CONTEXT_COMPRESSION_FACTOR",
    "DEADLINE_EXPIRED",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "LLM_CALL_TIMEOUT_SECONDS",
    "MAX_CONTEXT_COMPRESSIONS",
    "MAX_EXTERNAL_TOOL_CALLS",
    "MAX_OUTPUT_CAP_REDUCTIONS",
    "MAX_TOOL_ROUNDS",
    "MIN_OUTPUT_TOKENS",
    "OUTPUT_CAP_REDUCTION_FACTOR",
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
