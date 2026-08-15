"""Constructing one call's context, as a pure function outside the loop.

Trimming is the part of an agent harness most likely to be wrong in a way
nobody notices: it silently changes what the model saw, and a bug in it looks
exactly like the model being stupid.  So it lives here, as a function of a
transcript and a budget, with no I/O, no clock and no LLM — which makes every
trimming decision a unit test rather than a live experiment.

The ladder of ``docs/specs/0003`` §6, in order:

1. **Keep recent Turns intact.**  A Turn is emitted whole or not at all, and a
   tool result is never emitted without the call that asked for it.
2. **Replace old tool results with one line** — *called X with arguments Y*.
   This costs nothing in auditability, because ``agent_tool_call`` still holds
   every result whole; the transcript is a working context, not the record.
3. **Past a threshold, one model-written summary**, reused and never
   re-summarised.  Writing it needs a model call, so this function does not
   write it: it consumes one that already exists and *reports* when one is
   needed.

Rungs 2 and 3 interleave in one place the prose does not spell out.  A single
Turn can outgrow the ceiling on its own — eight rounds of parallel calls, each
result up to 4 KB — so the collapse in rung 2 is ordered by tool call, oldest
first, and reaches inside the most recent Turn only after every older Turn has
already been dropped.  Ordering it by Turn instead would leave the one case
that actually blows the budget with nothing left to give.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from src.core.llm.admission import TURN_CONTEXT_PER_CALL
from src.core.llm.protocol import Message, Role, ToolCall

# A deterministic approximation, and deliberately a pessimistic one. Vietnamese
# prose with diacritics tokenizes worse than English, and the ceiling this feeds
# is also enforced by admission (``turn_context_per_call``), where the penalty
# for undercounting is a refused call in the middle of a Turn.
CHARS_PER_TOKEN = 3
# What the wire format costs per message beyond its text: role, delimiters, and
# the ids on a tool block.
MESSAGE_OVERHEAD_TOKENS = 4

SUMMARY_LABEL = "Summary of the earlier Turns in this Thread:"


@dataclass(frozen=True)
class TranscriptToolCall:
    """One call the model made, with the result it was handed back.

    ``result`` is optional only so that a cancelled or in-flight call has a
    shape. Such a call is left out of the constructed context entirely — both
    halves of it — because half a tool exchange is a transcript the model has
    to guess at.
    """

    call_id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    result: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class TranscriptTurn:
    """One user message and everything that answered it."""

    user_text: str
    tool_calls: tuple[TranscriptToolCall, ...] = ()
    assistant_text: str | None = None

    @property
    def completed_calls(self) -> tuple[TranscriptToolCall, ...]:
        return tuple(call for call in self.tool_calls if call.result is not None)


@dataclass(frozen=True)
class Transcript:
    """Everything the constructor is allowed to see.

    A snapshot, already read from the store by the caller. Reading it here
    would put a database session inside the one function whose value is that it
    has none.
    """

    system_prompt: str
    turns: tuple[TranscriptTurn, ...] = ()
    # The cached ``role = 'summary'`` message, and how many leading Turns it
    # covers. Both come from persistence together; a summary whose span is
    # unknown could only be applied by guessing.
    summary: str | None = None
    summarised_turns: int = 0


@dataclass(frozen=True)
class ContextBudget:
    """The ceiling this function exists to meet, and how it gives ground."""

    max_tokens: int = TURN_CONTEXT_PER_CALL
    # Never dropped, and their tool results collapse last.
    keep_intact_turns: int = 2
    # Past this many live Turns, a summary is worth its call.
    summary_threshold_turns: int = 8


@dataclass(frozen=True)
class ConstructedContext:
    """The message list, and what it cost to fit.

    The counters are returned rather than logged because the caller has to act
    on one of them: ``summary_needed`` is the rung-3 trigger, and a function
    that stayed pure by hiding it would just move the decision somewhere
    untestable.
    """

    messages: tuple[Message, ...]
    estimated_tokens: int
    summary_used: bool = False
    summary_needed: bool = False
    # The half-open span of the original Transcript's Turns a summary should
    # now cover. ``from`` is where *new* material starts, which is exactly what
    # an existing summary already covers: the caller summarises only
    # ``turns[from:through]`` and carries the existing summary text forward
    # beside it. Reporting the whole span would make the caller re-summarise a
    # summary, which is the compounding drift rung 3 exists to avoid.
    summarise_from_turn: int = 0
    summarise_through_turn: int = 0
    turns_dropped: int = 0
    results_collapsed: int = 0


class ConstructedContextTooLarge(ValueError):
    """Even the protected Turns, fully collapsed, break the ceiling.

    Raised rather than trimmed past the ladder's last rung. Returning an
    over-budget context would hand admission a call it must refuse mid-Turn,
    and returning a silently mangled one is the failure this module exists to
    prevent.
    """

    def __init__(self, estimated_tokens: int, budget: int) -> None:
        super().__init__(
            f"the smallest constructible context is {estimated_tokens} tokens "
            f"against a ceiling of {budget}"
        )
        self.estimated_tokens = estimated_tokens
        self.budget = budget


def _compact(payload: Mapping[str, Any]) -> str:
    """One deterministic encoding, so the same inputs give the same bytes."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )


def estimate_tokens(message: Message) -> int:
    """What one message is charged, deterministically."""
    text = message.content or ""
    for call in message.tool_calls:
        text += call.name + _compact(call.arguments)
    if message.tool_call_id:
        text += message.tool_call_id
    return MESSAGE_OVERHEAD_TOKENS + -(-len(text) // CHARS_PER_TOKEN)


def _turn_messages(
    turn: TranscriptTurn,
    collapsed: frozenset[str],
) -> tuple[Message, ...]:
    """One whole Turn, with its call/result pairs kept together."""
    messages: list[Message] = [Message(role=Role.USER, content=turn.user_text)]
    calls = turn.completed_calls
    if calls:
        messages.append(
            Message(
                role=Role.ASSISTANT,
                tool_calls=tuple(
                    ToolCall(
                        id=call.call_id,
                        name=call.name,
                        arguments=dict(call.arguments),
                        output_index=index,
                    )
                    for index, call in enumerate(calls)
                ),
            )
        )
        for call in calls:
            if call.call_id in collapsed:
                content = f"called {call.name} with arguments {_compact(call.arguments)}"
            else:
                content = _compact(call.result or {})
            messages.append(
                Message(
                    role=Role.TOOL,
                    content=content,
                    tool_call_id=call.call_id,
                    name=call.name,
                )
            )
    if turn.assistant_text:
        messages.append(Message(role=Role.ASSISTANT, content=turn.assistant_text))
    return tuple(messages)


def _render(
    transcript: Transcript,
    turns: Sequence[TranscriptTurn],
    dropped: int,
    collapsed: frozenset[str],
) -> tuple[Message, ...]:
    """Assemble one candidate context.

    The system prompt is one block and the summary is another. Folding the
    summary into the prompt would put conversation content inside the artifact
    ADR-0015 forbids conversation content from entering.
    """
    messages: list[Message] = [
        Message(role=Role.SYSTEM, content=transcript.system_prompt)
    ]
    if transcript.summary:
        messages.append(
            Message(
                role=Role.SYSTEM,
                content=f"{SUMMARY_LABEL}\n{transcript.summary}",
            )
        )
    for turn in turns[dropped:]:
        messages.extend(_turn_messages(turn, collapsed))
    return tuple(messages)


def _reductions(
    turns: Sequence[TranscriptTurn],
    budget: ContextBudget,
) -> Iterator[tuple[int, frozenset[str]]]:
    """The ladder, as an ordered sequence of ``(turns dropped, collapsed)``."""
    protected = max(1, budget.keep_intact_turns)
    older = turns[: max(0, len(turns) - protected)]
    recent = turns[len(older) :]

    older_ids = [call.call_id for turn in older for call in turn.completed_calls]
    recent_ids = [call.call_id for turn in recent for call in turn.completed_calls]

    # 1. Everything intact.
    yield 0, frozenset()

    # 2. Old tool results collapse, oldest first.
    for taken in range(1, len(older_ids) + 1):
        yield 0, frozenset(older_ids[:taken])

    all_older = frozenset(older_ids)

    # 3. Whole Turns leave, oldest first; the protected ones never do.
    for dropped in range(1, len(older) + 1):
        yield dropped, all_older

    # 4. Last resort: the protected Turns' own results collapse, oldest first.
    for taken in range(1, len(recent_ids) + 1):
        yield len(older), all_older | frozenset(recent_ids[:taken])


def build_messages(
    transcript: Transcript,
    budget: ContextBudget | None = None,
) -> ConstructedContext:
    """Construct one call's messages under the constructed-context ceiling.

    Pure: the same transcript and the same budget give the same list, every
    time. The ceiling is met here and nowhere else, which is why the ladder is
    exhaustive rather than best-effort.
    """
    budget = budget or ContextBudget()
    # A summary without a span could only be applied by guessing which Turns it
    # replaced, so an unaccompanied span is ignored rather than trusted.
    covered = transcript.summarised_turns if transcript.summary else 0
    live = tuple(transcript.turns[covered:])

    smallest = 0
    for dropped, collapsed in _reductions(live, budget):
        messages = _render(transcript, live, dropped, collapsed)
        tokens = sum(estimate_tokens(message) for message in messages)
        smallest = tokens
        if tokens <= budget.max_tokens:
            return ConstructedContext(
                messages=messages,
                estimated_tokens=tokens,
                summary_used=transcript.summary is not None,
                summary_needed=(
                    dropped > 0 or len(live) > budget.summary_threshold_turns
                ),
                summarise_from_turn=covered,
                summarise_through_turn=covered + dropped,
                turns_dropped=dropped,
                results_collapsed=len(collapsed),
            )

    raise ConstructedContextTooLarge(smallest, budget.max_tokens)


__all__ = [
    "CHARS_PER_TOKEN",
    "MESSAGE_OVERHEAD_TOKENS",
    "SUMMARY_LABEL",
    "ConstructedContext",
    "ConstructedContextTooLarge",
    "ContextBudget",
    "Transcript",
    "TranscriptToolCall",
    "TranscriptTurn",
    "build_messages",
    "estimate_tokens",
]
