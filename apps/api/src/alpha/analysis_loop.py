"""The Analysis lane's loop: ask, read, ask again, then answer.

``generation.py`` sends the evidence envelope once and takes what comes back.
That was the right shape while the envelope was the whole of what this system
could say, and it is not: the **Analysis Field Profile** fixes eleven figures for
every symbol on every Trading Day, and sixteen of the thirty registered **Signal
Field**s have therefore never reached an Analysis at all
(``plans/reports/baseline-oneshot-260822.md``). One shot cannot reach them
because there is no round in which to ask.

So this module is the same generation with a *check* step in front of it. The
seed is the envelope ``build_envelope`` already assembles — core evidence
included, so a loop that calls nothing produces exactly what the one-shot lane
produces. Rounds are spent on substitution and depth: a figure came back refused
for want of history, and the catalog says which field needs less.

**What is deliberately not reused.** ``agent/loop.py`` is not parameterised and
not called. It takes a ``TurnRequest`` with a thread, a request message and a
user; it publishes to a ``TurnPublisher`` and saves to a transcript; it builds
its context from the chat prompt contract. An Analysis Run has no thread, no
message and nobody watching a stream — ``generation.py`` chooses ``stream=False``
and says why. Driving it from here would mean inventing a thread and a message,
which is the thing this repository refuses. What *is* reused is every part below
the orchestrator: the executor, the guardrails, the reservation, the fragment
format and all six of its semantic rules.

**What this module gives up, and what it buys.** ``envelope.py`` states the
property being surrendered — *"an Analysis rebuilt tomorrow from the same store
has to say the same thing"* — and ``generation.py`` defines determinism as fixed
inputs and fixed control flow. A loop breaks fixed control flow. What replaces it
is audit: every call and every result is written to ``analysis_tool_call``, so the
path an Analysis took is readable even though it is not repeatable. That trade is
the whole reason the trace table landed first.

**Fail-open at every gate.** A tool that raises is a result. A round that times
out ends the tool phase rather than the Analysis. Rounds exhausted without a
valid fragment fails under ``invalid_model_output``, a code the taxonomy already
has. No path here publishes an empty Analysis, and no path invents a new failure
code.

**No spill ladder.** A figure is about 730 bytes and the catalog about 5KB, so no
result in this lane needs trimming to fit a window. What each tool declares
(``registry.get_max_result_size``) is honoured as a bug-stop, and the chat lane's
aggregate rebalancing — which would trim store evidence this Analysis had already
paid to read — is not ported.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import Any

from src.agent import registry
from src.agent.budget import trim_text
from src.agent.executor import (
    BLOCKED_CALL,
    HALTED_TURN,
    INVALID_ARGUMENTS,
    TOOL_UNAVAILABLE,
    UNKNOWN_TOOL,
    ExecutionOutcome,
    ToolExecutor,
)
from src.agent.executor import ToolCall as ExecutorToolCall
from src.agent.guardrails import GuardrailThresholds, TurnGuardrails
from src.agent.tools.signals import TOOLSET as SIGNALS_TOOLSET
from src.agent.tools.signals import axis_of
from src.core.database import get_sync_db
from src.core.llm import (
    AuthUnavailable,
    BudgetRefusal,
    Completion,
    CompletionRequest,
    LLMClient,
    LLMError,
    Message,
    ModelRefusal,
    Role,
    ToolSchema,
)
from src.stocks.signals.registry import REGISTRY

from .envelope import (
    EvidenceEnvelope,
    EvidenceFigure,
    EvidenceSection,
    Health,
)
from .field_profile import AXIS_ORDER, Axis
from .generation import (
    FRAGMENT_FORMAT,
    MAX_GENERATIONS_PER_ATTEMPT,
    MAX_OUTPUT_TOKENS,
    SYSTEM_PROMPT,
    AnalysisFragment,
    FragmentRejected,
    budget_failure,
    parsed_fragment,
    spend_for,
    validate_fragment,
)
from .models import AnalysisToolCall
from .producer import ProductionFailure, sanitized_reason

logger = logging.getLogger(__name__)

# The loop's own contract version. ``v1`` is the one-shot instruction set, which
# still exists and is still reachable, and a fragment produced under one cannot
# be compared with a fragment produced under the other — that is what the stamp
# is for.
LOOP_PROMPT_VERSION = "v2"

# How many rounds of tool calls the model gets before the answer is asked for.
#
# The arithmetic, because the chat lane's own round ceiling is a calculation
# rather than a taste and this one has a different denominator. An Analysis may
# spend ``ANALYSIS_OUTPUT_TOKENS`` (3,000) across every call it makes. This lane
# makes at most ``MAX_TOOL_ROUNDS`` calls at :data:`ROUND_OUTPUT_TOKENS` plus one
# final call at ``generation.MAX_OUTPUT_TOKENS``:
#
#     6 x 380 + 700 = 2,980 <= 3,000
#
# checked at import below. The sanctioned regeneration is funded out of what the
# loop did not actually spend, which admission decides on the evidence in the
# ledger rather than on this estimate — a loop that used all six rounds may find
# it unaffordable, and ``generation.budget_failure`` already says exactly that.
MAX_TOOL_ROUNDS = 6

# What one tool round may produce, reasoning included. Set at the measured level:
# a six-round loop produced about 2,200 output tokens across its tool rounds,
# which is a little over 360 a round. A round that runs out mid-tool-call comes
# back with no calls at all, and this loop reads that as "the model is done
# asking" — degrading to the one-shot answer rather than failing, but degrading.
ROUND_OUTPUT_TOKENS = 380

if MAX_TOOL_ROUNDS * ROUND_OUTPUT_TOKENS + MAX_OUTPUT_TOKENS > 3_000:
    # Checked here rather than left to a reviewer, for the reason
    # ``generation.py`` checks its own: raise either number and the lane spends
    # an allowance nothing validated, without a test going red.
    raise ValueError(
        f"{MAX_TOOL_ROUNDS} rounds at {ROUND_OUTPUT_TOKENS} tokens plus a final "
        f"call at {MAX_OUTPUT_TOKENS} is more output than one Analysis may spend"
    )

# How long one round of store reads may take before the tool phase is abandoned.
# Both tools read Postgres and neither leaves the deployment, so this is a bound
# on a query that will not come back rather than on a network somebody else owns.
TOOL_TIMEOUT_SECONDS = 30.0

#: The rungs, sized for a lane that has six rounds rather than the chat lane's
#: four and two tools rather than five.
#:
#: Every threshold has to be *reachable* inside the round budget, which is the
#: defect the chat lane carries at this base: ``block_after=5`` and
#: ``halt_after=8`` cannot be reached in four rounds, so the ladder is
#: warn-only. Here: an exact repeat is warned on its first recurrence and refused
#: on its second, which costs the loop two of its six rounds; four failures of one
#: tool halts the tool phase and leaves the final call funded. Not copied from the
#: chat lane, because copying a number is how an unreachable threshold spreads.
ANALYSIS_THRESHOLDS = GuardrailThresholds(
    exact_failure_warn_after=1,
    same_tool_failure_warn_after=2,
    no_progress_warn_after=2,
    exact_failure_block_after=2,
    same_tool_failure_halt_after=4,
)

# Added to the one-shot contract rather than replacing it: the six rules the
# fragment is proved against do not change, and a second copy of them would be a
# second contract. What changes is that the envelope is no longer the whole of
# what the model may know.
LOOP_CONTRACT = """
Before you answer, you may read more of the evidence plane.

- The envelope in the user message is where you start, not everything there is.
  list_fields names every Signal Field this system can compute, with the unit it
  is in and the minimum sessions it needs.
- A figure whose health is refused carries both a reasonCode and a sentence
  saying what the store could not do. The work that reason asks for is to find a
  usable substitute, not to narrate around the hole. minSessions in the catalog
  is where to look: a field refused for want of history is often answerable by
  one that needs less of it.
- get_field reads one field for the symbol and Trading Day already under
  analysis. You do not name a symbol, a date or a peer group, and you cannot:
  those are fixed before you are called.
- A field you fetch may be cited exactly like a seeded one, under the same rule —
  only ok or degraded. A refused figure can never support the verdict, however
  many times you ask for it.
- Do not ask again for a field that came back refused. The reason will not have
  changed, and the round is gone.
- Ask for what the evidence you hold does not answer. If it answers the question
  this symbol raises, call nothing and write the Analysis.
"""

LOOP_SYSTEM_PROMPT = SYSTEM_PROMPT + LOOP_CONTRACT

# What ``analysis_tool_call.status`` records, mapped from what the executor
# reports. The column's vocabulary is closed, so an executor error with no
# mapping lands on ``tool_error`` rather than inventing a sixth value.
_STATUS_BY_ERROR: Mapping[str, str] = {
    UNKNOWN_TOOL: "unknown_tool",
    TOOL_UNAVAILABLE: "blocked",
    BLOCKED_CALL: "blocked",
    HALTED_TURN: "blocked",
    INVALID_ARGUMENTS: "tool_error",
}

# The longest a stored result may be. The trace is an audit record and not a
# second copy of the store, and a figure is 730 bytes — this is the bound that
# stops one pathological result from being written a thousand times.
MAX_TRACE_RESULT_CHARS = 8_000

SessionOpener = Callable[[], Any]
Clock = Callable[[], datetime]


@dataclass(frozen=True)
class LoopOutcome:
    """One Analysis's generation, and the evidence it ended up resting on.

    ``envelope`` is the seed plus every figure the loop fetched, because the
    payload is rendered from an envelope and a figure the model cited has to be
    in the one that is rendered. ``rounds_used`` and ``calls`` are what Phase 5's
    substitution rate is measured from, and they are counted here rather than
    re-derived from the trace so a lost trace row cannot change the answer.
    """

    fragment: AnalysisFragment
    envelope: EvidenceEnvelope
    rounds_used: int
    calls: int
    fetched_field_ids: tuple[str, ...]


async def generate_fragment_in_loop(
    client: LLMClient,
    envelope: EvidenceEnvelope,
    *,
    model: str,
    run_id: int | str,
    session_opener: SessionOpener = get_sync_db,
    clock: Clock | None = None,
    max_rounds: int = MAX_TOOL_ROUNDS,
) -> LoopOutcome:
    """Run the loop and prove one fragment, or fail the attempt by name.

    The generation half is ``generation.py``'s and is unchanged: temperature 0,
    strict structured output, no tools on the final call, the six semantic rules,
    and exactly one regeneration when the first fragment is invalid and
    admission will still fund it. What is in front of it is the tool phase, and
    the tool phase can only ever *add* figures — there is no path by which it
    removes one, edits one, or supplies a number of its own.
    """
    now = clock or (lambda: datetime.now(timezone.utc))
    context = registry.ToolContext(
        symbol=envelope.symbol,
        trading_day=envelope.trading_day,
        now=now(),
    )
    guardrails = TurnGuardrails(thresholds=ANALYSIS_THRESHOLDS)
    executor = ToolExecutor(context=context, guardrails=guardrails)
    tools = _tool_schemas()

    messages: list[Message] = [
        Message(role=Role.SYSTEM, content=LOOP_SYSTEM_PROMPT),
        Message(
            role=Role.USER,
            content=json.dumps(envelope.as_wire(), ensure_ascii=False),
        ),
    ]
    fetched: dict[str, EvidenceFigure] = {}
    rounds_used = 0
    calls_made = 0

    for round_index in range(max_rounds):
        completion = await _call(
            client,
            CompletionRequest(
                model=model,
                messages=tuple(messages),
                tools=tools,
                tool_choice="auto",
                max_output_tokens=ROUND_OUTPUT_TOKENS,
                temperature=0.0,
                stream=False,
            ),
            run_id,
        )
        if not completion.tool_calls:
            # The model is done asking. Whatever prose came with the decision is
            # deliberately dropped: narration about the work is not the Analysis,
            # and the fragment is the only thing this lane publishes.
            break

        rounds_used += 1
        requested = tuple(
            ExecutorToolCall(id=call.id, name=call.name, arguments=call.arguments)
            for call in completion.tool_calls
        )
        calls_made += len(requested)

        try:
            outcome = await asyncio.wait_for(
                executor.run(requested), TOOL_TIMEOUT_SECONDS
            )
        except TimeoutError:
            # Both tools bound their own database work, so reaching this means a
            # bound is missing rather than that the store is slow. The tool phase
            # ends and the Analysis is still written from what it holds.
            logger.warning(
                "A round of %d store read(s) did not answer within %.0fs; "
                "answering from the evidence already gathered",
                len(requested),
                TOOL_TIMEOUT_SECONDS,
            )
            await _record_round(
                session_opener,
                run_id,
                round_index,
                requested,
                None,
                now(),
            )
            break

        await _record_round(
            session_opener, run_id, round_index, requested, outcome, now()
        )

        messages.append(
            Message(role=Role.ASSISTANT, tool_calls=completion.tool_calls)
        )
        for call, result in zip(requested, outcome.results, strict=True):
            body = result.text
            limit = registry.get_max_result_size(call.name)
            if limit is not None:
                shown, cursor = trim_text(body, limit)
                body = shown if cursor is None else f"{shown}\n{cursor.sentence}"
            if result.guidance and result.guidance not in body:
                body = f"{body}\n{result.guidance}"
            messages.append(
                Message(
                    role=Role.TOOL,
                    content=body,
                    tool_call_id=call.id,
                    name=call.name,
                )
            )
            figure = _figure_in(result)
            if figure is not None and figure.field_id not in envelope.field_ids:
                fetched.setdefault(figure.field_id, figure)

        if outcome.halted:
            break

    expanded = _expanded(envelope, tuple(fetched.values()))
    fragment = await _final_call(client, expanded, messages, model=model, run_id=run_id)
    return LoopOutcome(
        fragment=fragment,
        envelope=expanded,
        rounds_used=rounds_used,
        calls=calls_made,
        fetched_field_ids=tuple(fetched),
    )


async def _final_call(
    client: LLMClient,
    envelope: EvidenceEnvelope,
    messages: Sequence[Message],
    *,
    model: str,
    run_id: int | str,
) -> AnalysisFragment:
    """The one-shot generation, run over the conversation the loop built.

    Identical to what ``generation.py`` does today — no tools, ``tool_choice``
    stated as ``none``, the strict fragment schema, one regeneration handed the
    machine-readable errors. The only difference is what precedes it in the
    message list, and that is the whole point.
    """
    rejection: FragmentRejected | None = None
    previous: str | None = None
    history = list(messages)

    for _ in range(MAX_GENERATIONS_PER_ATTEMPT):
        turn = list(history)
        if rejection is not None:
            turn.append(Message(role=Role.ASSISTANT, content=previous or ""))
            turn.append(Message(role=Role.USER, content=rejection.as_feedback()))
        completion = await _call(
            client,
            CompletionRequest(
                model=model,
                messages=tuple(turn),
                tools=(),
                tool_choice="none",
                response_format=FRAGMENT_FORMAT,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.0,
                stream=False,
            ),
            run_id,
            rejection=rejection,
        )
        previous = completion.text or ""
        try:
            return validate_fragment(parsed_fragment(completion), envelope)
        except FragmentRejected as rejected:
            rejection = rejected

    assert rejection is not None  # the loop only exits here through a rejection
    raise ProductionFailure(
        "invalid_model_output",
        "Fragment vẫn không hợp lệ sau một lần sinh lại: "
        f"{sanitized_reason(str(rejection))}",
    )


async def _call(
    client: LLMClient,
    request: CompletionRequest,
    run_id: int | str,
    *,
    rejection: FragmentRejected | None = None,
) -> Completion:
    """One provider call, with the failure mapping ``generation.py`` already fixed.

    Every branch here is that module's, deliberately: a second taxonomy for the
    same five failures would be a second set of ``error_code``s the interface has
    to learn. ``rejection`` is passed only so a refused *regeneration* is reported
    as an invalid fragment rather than as a spend failure, which is the
    distinction ``_budget_failure`` exists to make.
    """
    try:
        return await client.complete(request, spend_for(request, run_id))
    except BudgetRefusal as refusal:
        raise budget_failure(refusal, rejection) from refusal
    except AuthUnavailable as exc:
        raise ProductionFailure(
            "auth_unavailable",
            f"Tuyến LLM từ chối thông tin xác thực: {sanitized_reason(str(exc))}",
        ) from exc
    except ModelRefusal as exc:
        raise ProductionFailure(
            "invalid_model_output",
            f"Model từ chối sinh Analysis: {sanitized_reason(str(exc))}",
        ) from exc
    except LLMError as exc:
        raise ProductionFailure(
            "llm_transport_error",
            f"Tuyến LLM không trả lời được: {sanitized_reason(str(exc))}",
        ) from exc


def _tool_schemas() -> tuple[ToolSchema, ...]:
    """The two store tools, asked for by bundle rather than by name.

    Through the toolset name and the shared builder, so this lane offers what the
    bundle holds rather than a list copied into a caller — the failure the toolset
    table exists to prevent — and so there is still exactly one place that decides
    what a model was shown. Availability still applies: both tools are
    unconditional, and a build that somehow had neither would answer here with an
    empty tuple and produce exactly the one-shot Analysis.

    Imported inside the call rather than at module scope: ``definitions`` reaches
    the registry, the registry is populated by ``tools.register_all()`` at
    startup, and a module-level import would tie the import order of this lane to
    that of the tool surface.
    """
    from src.agent.definitions import get_tool_definitions

    return get_tool_definitions(SIGNALS_TOOLSET)


def _figure_in(result: Any) -> EvidenceFigure | None:
    """The figure a ``get_field`` result carries, or ``None`` for anything else.

    Read off the structured payload the executor already holds rather than by
    re-parsing the text: a second parse is a second chance to read the same
    answer differently. A failed call, a catalog listing, and a payload that is
    not a figure all answer ``None`` — the loop adds evidence and never guesses
    at it.
    """
    if not result.ok or not isinstance(result.payload, Mapping):
        return None
    field_id = result.payload.get("fieldId")
    if not isinstance(field_id, str) or field_id not in REGISTRY:
        return None
    try:
        health = Health(result.payload.get("health"))
    except ValueError:  # pragma: no cover - the tool builds this from the enum
        return None
    as_of = result.payload.get("asOf")
    return EvidenceFigure(
        field_id=field_id,
        label=str(result.payload.get("label") or field_id),
        value=result.payload.get("value"),
        unit=result.payload.get("unit"),
        kind=result.payload.get("kind"),
        source=result.payload.get("source"),
        interpretation=str(result.payload.get("interpretation") or ""),
        health=health,
        reason_code=result.payload.get("reasonCode"),
        reason=result.payload.get("reason"),
        as_of=None if as_of is None else date.fromisoformat(str(as_of)),
        sessions_used=result.payload.get("sessionsUsed"),
        window_days=result.payload.get("windowDays"),
        extras=result.payload.get("extras") or {},
    )


def _expanded(
    envelope: EvidenceEnvelope, figures: Sequence[EvidenceFigure]
) -> EvidenceEnvelope:
    """The seed with everything the loop fetched folded into its own axis.

    Appended to the section its namespace belongs to, which is what makes a
    fetched figure indistinguishable from a seeded one downstream: section
    health is derived from membership, so a substitute that answers where a
    refusal stood lifts the section it answers for.

    ``MAX_FIELDS_PER_AXIS`` is not applied. It bounds the *seed* — what every
    Analysis pays for before the model has said anything — and the whole purpose
    of the loop is to reach past it for the symbols that need it.

    No figure already in the envelope is replaced. The backend owns the evidence,
    and a second read of the same field arriving late is not a correction of the
    first: it is the same store answering the same question, and preferring
    either one over the other would be the backend editing its own snapshot.
    """
    if not figures:
        return envelope
    by_axis: dict[Axis, list[EvidenceFigure]] = {
        section.axis: list(section.figures) for section in envelope.sections
    }
    for figure in figures:
        by_axis.setdefault(axis_of(figure.field_id), []).append(figure)
    return replace(
        envelope,
        sections=tuple(
            EvidenceSection(axis=axis, figures=tuple(by_axis.get(axis, ())))
            for axis in AXIS_ORDER
        ),
    )


async def _record_round(
    session_opener: SessionOpener,
    run_id: int | str,
    round_index: int,
    calls: Sequence[ExecutorToolCall],
    outcome: ExecutionOutcome | None,
    started_at: datetime,
) -> None:
    """Write one round's trace, in the order the model issued the calls.

    ``seq`` comes from the issued order rather than from completion order: two
    reads dispatched together share a millisecond, and the question the trace
    answers is what the model asked for, not which query returned first.
    ``outcome`` is ``None`` for a round that timed out, where every call is
    recorded as one.

    A lost trace row is not a lost Analysis. The Analysis is what the reader is
    waiting for, and refusing to publish it because an audit insert failed would
    turn a bookkeeping problem into a missing artifact — so this logs loudly and
    returns.
    """
    rows = []
    for seq, call in enumerate(calls, start=1):
        result = None if outcome is None else _result_for(outcome, call.id)
        if result is None:
            status, error, latency, payload = "timeout", None, None, None
        else:
            status = "ok" if result.ok else _STATUS_BY_ERROR.get(
                result.error or "", "tool_error"
            )
            error = None if result.ok else sanitized_reason(result.text or "")[:500]
            latency = result.duration_ms
            payload = _trace_result(result)
        rows.append(
            AnalysisToolCall(
                run_id=int(run_id),
                round_index=round_index,
                seq=seq,
                tool_name=call.name[:64],
                tool_call_id=None if call.id is None else str(call.id)[:128],
                arguments=_jsonable_arguments(call.arguments),
                result=payload,
                status=status,
                error=error,
                latency_ms=latency,
                started_at=started_at,
            )
        )

    def write() -> None:
        with session_opener() as session:
            session.add_all(rows)
            # Committed here rather than left to whoever opened the session, the
            # same way the chat lane's trace writer does it: the trace is one
            # short transaction of its own, and a caller that hands over a plain
            # session factory closes without committing.
            session.commit()

    try:
        await asyncio.to_thread(write)
    except Exception as exc:  # noqa: BLE001 - an audit row is not the artifact
        logger.warning(
            "Could not record the tool trace for Analysis Run %s round %d: %s",
            run_id,
            round_index,
            exc,
        )


def _result_for(outcome: ExecutionOutcome, call_id: str) -> Any:
    for result in outcome.results:
        if result.call_id == call_id:
            return result
    return None


def _trace_result(result: Any) -> Any:
    """What is stored for one call: the structured payload where there is one.

    A handler that answered with prose, and a failed call whose only answer is
    the sentence saying why, are stored under ``text`` so the column always holds
    an object a reader can branch on.
    """
    if isinstance(result.payload, (Mapping, list)):
        try:
            json.dumps(result.payload, ensure_ascii=False, default=str)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            pass
        else:
            return result.payload
    text = result.text or ""
    if not text:
        return None
    return {"text": text[:MAX_TRACE_RESULT_CHARS]}


def _jsonable_arguments(raw: Any) -> dict[str, Any]:
    """The arguments as an object, whatever the route handed over.

    A route that sent something other than an arguments object is a route
    violating its contract, and the trace records what arrived rather than
    refusing to record the round.
    """
    if isinstance(raw, Mapping):
        return dict(raw)
    if raw is None:
        return {}
    return {"raw": str(raw)[:1_000]}


__all__ = [
    "ANALYSIS_THRESHOLDS",
    "LOOP_CONTRACT",
    "LOOP_PROMPT_VERSION",
    "LOOP_SYSTEM_PROMPT",
    "MAX_TOOL_ROUNDS",
    "MAX_TRACE_RESULT_CHARS",
    "ROUND_OUTPUT_TOKENS",
    "TOOL_TIMEOUT_SECONDS",
    "LoopOutcome",
    "generate_fragment_in_loop",
]
