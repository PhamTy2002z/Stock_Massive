"""One Turn's transcript, and the context constructed from it.

A pure function of a transcript and a budget, with no I/O, no clock and no LLM.
Trimming is the part of an agent harness most likely to be wrong in a way nobody
notices — it silently changes what the model saw, and a bug in it looks exactly
like the model being stupid — so every trimming decision here is a unit test
rather than a live experiment.

Its own module rather than a section of the loop because two callers meet here.
The loop constructs the context it sends; the transport reads a Thread out of the
store and hands it over as :class:`TranscriptTurn`. A type both of them name is a
shared boundary, and putting it inside the loop would make the transport import
the loop to describe a row it read from a table.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.core.llm import ContentSegment, Message, Role, ToolCall
from src.core.llm.admission import TURN_CONTEXT_PER_CALL

from . import registry
from .untrusted import wrap_result

#: What a tool call went and read, as the surface is told it. Two values, and the
#: distinction is the one the evidence boundary is built on: a figure out of this
#: system's store has a date and a health and reads the same tomorrow, and a page
#: has none of those. A surface that drew them alike would be undoing in pixels
#: what ``untrusted.py`` does in the message.
EXTERNAL_KIND = "external"
STORE_KIND = "store"


#: The two things a piece of a Turn's prose can be.
#:
#: ``answer`` is the reply. ``thought`` is a sentence written on the way to it,
#: in a round that went on to call tools — it belongs to the timeline of what
#: happened rather than to what was concluded.
#:
#: Here rather than in the transport, for the reason ``ToolCallStatus`` is here:
#: the loop produces these and the transport streams them, and the loop names
#: the shape of the transport rather than importing its module.
ANSWER = "answer"
THOUGHT = "thought"


class ToolCallStatus(str, Enum):
    """The three states the interactive surface renders a tool call in."""

    RUNNING = "running"
    OK = "ok"
    ERROR = "error"


#: How each tool is described on screen, and which one of its arguments may
#: appear beside the description.
#:
#: An allowlist of both halves rather than a rendering of the argument object,
#: for two reasons. The sentence is what the reader sees, and the interactive
#: surface renders it verbatim rather than composing one — so it has to read as
#: Vietnamese prose here or nowhere. And an argument nobody named is an argument
#: nobody reviewed for a screen: a tool added later shows its name and nothing
#: else until somebody decides what of it is fit to show.
MAX_SUMMARY_CHARS = 120

#: The hard ceiling on a whole rail row, for the tools that compose their own.
#: A row is one line in a narrow panel; past this it is truncated by the layout
#: anyway, and the cap is here so that is decided once rather than by whichever
#: tool wrote the longest sentence.
MAX_SUMMARY_ROW_CHARS = 200

# A deterministic approximation, and deliberately a pessimistic one. Vietnamese
# prose with diacritics tokenizes worse than English, and the ceiling this feeds
# is also enforced by admission, where the penalty for undercounting is a
# refused call in the middle of a Turn.
CHARS_PER_TOKEN = 3
# What the wire format costs per message beyond its text: role, delimiters, and
# the ids on a tool block.
MESSAGE_OVERHEAD_TOKENS = 4

SUMMARY_LABEL = "Summary of the earlier turns in this conversation:"


def _compact(payload: Mapping[str, Any]) -> str:
    """One deterministic encoding, so the same inputs give the same bytes."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )


@dataclass(frozen=True)
class TurnToolCall:
    """One tool call of a Turn: what the model asked, and what came back.

    One type rather than two, and the reason is that a second one would drift.
    The same record answers three readers: the transcript the next round is
    constructed from, the ``tool.call`` payload the interactive surface renders,
    and the Tool Call Trace row. Splitting them means three places that can
    disagree about whether a call succeeded.

    ``result_text`` is the *whole* result as the tool returned it. What the model
    is shown is derived from it at construction time, because the per-Turn output
    budget can ask a result gathered three rounds ago to give ground now
    (``budget.py`` rung three) — so the trimmed form is never stored here.
    """

    id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    status: ToolCallStatus = ToolCallStatus.RUNNING
    result_text: str | None = None
    #: A short user-facing line: the tool and the one argument worth naming.
    #: Never the result body, and never the reason it failed — that is ``error``,
    #: which travels beside it so a surface can say *why* without the summary
    #: having to be rewritten into an apology.
    summary: str = ""
    error: str | None = None
    #: The guardrail ladder's warning about this call, when it warned. Carried
    #: to the model *outside* the untrusted wrapper, because it is the harness
    #: talking and must not read as part of a page.
    guidance: str | None = None
    duration_ms: int = 0
    dispatched: bool = True
    #: Which round of the tool loop asked for this call, counting from zero.
    #:
    #: Carried so the surface can group a round's calls under one line — the
    #: model asks for several searches at once, and five rows that all appeared
    #: in the same instant read as five separate decisions rather than as the
    #: one decision it was. Grouping by arrival time would guess at that; the
    #: round is the fact.
    round: int = 0
    #: The part of this call's result that is fit to put on a screen.
    #:
    #: Distinct from ``result_text``, which is the whole result and belongs to
    #: the model and the trace. This is a short, already-flattened projection —
    #: title, link, source, one snippet — built by :func:`display_results` from
    #: text the web tools ran through ``visible_text`` and therefore stripped of
    #: markup. Empty for every tool that has nothing worth showing.
    results: tuple[Mapping[str, Any], ...] = ()
    #: What this call actually yielded, for the calls where "it ran" and "it
    #: answered" are different facts.
    #:
    #: ``status`` cannot carry this. A store read that comes back saying the
    #: store has nothing to say is a successful call — the tool worked, the
    #: question was well formed, and the answer is that there is no figure — so
    #: it is ``ok``, and it was drawn and recorded exactly like a call that
    #: returned a number. Measured over the trace: of 151 ``get_field`` calls,
    #: 94 carried a figure, 42 carried a refusal and 15 said the symbol was
    #: outside the Universe, and all 151 were stored as ``ok``. That is a third
    #: of the evidence path invisible to anyone reading either the rail or the
    #: table.
    #:
    #: ``None`` for every tool with nothing to classify, which is the default: a
    #: tool added later says nothing here until somebody decides what its
    #: outcomes are.
    outcome: str | None = None
    #: The route's own opaque token for the reasoning behind this call, when the
    #: route issued one. Held for the length of the Turn and no longer: a route
    #: that demands it back demands it for the rounds of the Turn it is
    #: answering, and a closed Turn in the history is accepted without it.
    signature: str | None = None

    @property
    def finished(self) -> bool:
        return self.status is not ToolCallStatus.RUNNING

    def as_wire(self) -> dict[str, Any]:
        """The ``tool.call`` payload of the SSE contract, and nothing else.

        ``error`` is here because ``status`` alone cannot answer the question a
        reader actually has. Three of the reasons a call ends in ``error`` are
        not failures at all — the Turn spent its external-call allowance, the
        round asked for more calls than it may dispatch, the tool loop was
        halted — and every one of those was refused by this deployment before
        anything was dispatched. Sending only ``error`` as a status draws them
        exactly like a tool that broke, and only one of the two is worth
        retrying.

        The reason is a stable code, not a sentence: the surface owns the words,
        the same way it already owns the words for ``terminal_reason``.
        """
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "summary": self.summary,
            "error": self.error,
            "round": self.round,
            "results": [dict(item) for item in self.results],
            "result_count": len(self.results),
            # Which kind of evidence this call went and got. Read off the same
            # declaration the untrusted wrapper reads, so a surface cannot draw a
            # read of this system's own store the way it draws a stranger's page
            # — the distinction the whole evidence boundary rests on. A name the
            # registry does not hold reads as external, conservatively, exactly
            # as it does for the wrapper.
            "kind": EXTERNAL_KIND if registry.reads_external(self.name) else STORE_KIND,
            "outcome": self.outcome,
        }


def summarise_call(name: str, arguments: Mapping[str, Any]) -> str:
    """The one line a reader is shown about a tool call.

    The whole sentence, in the reader's language, because the interactive
    surface renders it verbatim: a client that described a call would be
    guessing at what it was for, and the guess is what the reader would
    believe.

    It says what was *asked*, and it never changes once the call has been
    announced. What came back is the call's status, which the surface shows
    beside it, and a failure code belongs in the trace rather than in a sentence
    somebody reads.

    **Built from the registration, not from a table here.** Every tool declares
    the phrase a person reads (``ToolEntry.display_name``) beside the name the
    model calls, and ``register`` refuses a blank one. This function used to keep
    its own mapping of five tool names, which is why the three tools added after
    it was written showed a reader ``get_field`` — the same defect, in the same
    shape, that ``untrusted.py`` had with its frozenset of two.

    A name the registry does not hold falls back to itself. That is a tool
    nobody registered, so there is no declared phrase to use and inventing one
    would be this function guessing; it happens in a process whose tool surface
    has not been installed, and a raw name there is a symptom worth seeing.
    """
    entry = registry.get(name)
    if entry is None:
        return name
    if entry.summarise is not None:
        # A tool whose row cannot be built from one argument builds its own.
        return entry.summarise(arguments)[:MAX_SUMMARY_ROW_CHARS]
    if entry.summary_detail_arg is None:
        return entry.display_name
    value = arguments.get(entry.summary_detail_arg)
    detail = value.strip() if isinstance(value, str) else ""
    if not detail:
        return entry.display_name
    return f"{entry.display_name}: {detail[:MAX_SUMMARY_CHARS]}"


#: How much of one result's snippet is sent to a screen.
#:
#: Shorter than the ``MAX_SNIPPET_CHARS`` the model reads, because the two are
#: doing different jobs: the model reads a snippet to decide whether the page is
#: worth fetching, and the reader reads it to recognise a source they already
#: half-know. A card is two lines tall either way, so the rest of it would be
#: bytes on the wire that no layout has room for.
DISPLAY_SNIPPET_CHARS = 280

#: The most results one call may put on screen, whatever the tool returned.
#:
#: A ceiling on this side as well as on the tool's, so raising ``MAX_RESULTS``
#: to widen what the *model* reads cannot silently make every Turn's event
#: stream several times larger.
MAX_DISPLAY_RESULTS = 10


def display_results(name: str, payload: Any) -> tuple[Mapping[str, Any], ...]:
    """The part of one tool's result that may be put on a screen.

    Separate from ``result_text`` on purpose. ``result_text`` is the whole
    result: it belongs to the model, which is told to treat it as data, and to
    the Tool Call Trace, which nobody renders. What comes back from here is a
    short projection with four named fields and no body — the fields a reader
    needs to recognise a source and click it.

    Four properties make that projection safe to render, and all four are
    already true of what the web tools return rather than being asserted here:

    * the text has been through ``visible_text``, so it is the *visible* text of
      an HTML document with tags and scripts discarded, not markup;
    * every field is a string, flattened here, so no nested object from a
      provider reaches a component that would have to walk it;
    * the snippet is cut to :data:`DISPLAY_SNIPPET_CHARS` and the list to
      :data:`MAX_DISPLAY_RESULTS`, so one enormous answer cannot become one
      enormous frame;
    * the surface labels the whole block as outside content, which is where that
      label belongs — a wrapper *inside* the payload would be a string a page
      could forge.

    A tool with nothing worth showing returns nothing, which is the default: a
    tool added later shows a row and no results until somebody decides what of
    it is fit for a screen.
    """
    if not isinstance(payload, Mapping):
        return ()
    if name == "web_search":
        raw = payload.get("results")
        if not isinstance(raw, Sequence) or isinstance(raw, str):
            return ()
        return tuple(
            _display_item(item)
            for item in raw[:MAX_DISPLAY_RESULTS]
            if isinstance(item, Mapping)
        )
    if name == "fetch_url":
        # A page read is one result, and it is only worth a row once it has a
        # page: a refusal carries a ``reason`` and no title, and a card with an
        # empty heading tells the reader less than no card at all.
        if not payload.get("title") and not payload.get("url"):
            return ()
        return (_display_item(payload),)
    return ()


#: What a call yielded, where that is a different question from whether it ran.
#:
#: Three values, and the middle one is the one this exists for. Kept short and
#: stable because they are stored in a column and grouped by in a query, and
#: because a surface holds one sentence per value the way it already does for a
#: **Signal Issue**.
OUTCOME_VALUE = "value"
OUTCOME_NO_VALUE = "no_value"
OUTCOME_CANNOT_READ = "cannot_read"

#: Every tool whose result carries a figure that may be absent. Named rather
#: than sniffed from the payload shape: a tool answering with a ``value`` key
#: that is legitimately null would otherwise be reported as having refused.
_FIGURE_TOOLS = frozenset({"get_field"})


def outcome_of(name: str, payload: Any) -> str | None:
    """What one call yielded, or ``None`` where the question does not apply.

    Read off the structured payload rather than the result text, for the reason
    :func:`display_results` is: the executor is holding the object, and a second
    parse is a second chance to read it differently from the first.

    A refusal keeps the **Signal Issue** that caused it, not a flat "nothing".
    The whole value of separating these is that ``insufficient_cross_section``
    and ``market_cap_absent`` are different operational facts with different
    fixes, and folding them into one word rebuilds the blind spot one level up.
    """
    if name not in _FIGURE_TOOLS or not isinstance(payload, Mapping):
        return None
    if payload.get("error"):
        # The tool declined the question itself — a symbol outside the Universe,
        # a call opened for another one. It never reached the store.
        return OUTCOME_CANNOT_READ
    if "value" not in payload:
        return None
    if payload.get("value") is not None:
        return OUTCOME_VALUE
    code = payload.get("reasonCode")
    return f"{OUTCOME_NO_VALUE}:{code}" if code else OUTCOME_NO_VALUE


def _display_item(item: Mapping[str, Any]) -> Mapping[str, Any]:
    """One result flattened to the four strings a card is built from."""
    return {
        "title": _display_text(item.get("title"), 240),
        "url": _display_text(item.get("url"), 2048),
        "source": _display_text(item.get("source"), 120),
        "snippet": _display_text(item.get("snippet"), DISPLAY_SNIPPET_CHARS),
    }


def _display_text(value: Any, limit: int) -> str:
    """A single-line string of at most ``limit`` characters.

    Newlines collapse rather than survive: these strings are put in a card that
    is two lines tall, and a snippet carrying its own line breaks would either
    blow the card open or be silently clipped mid-paragraph.
    """
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def shown_result(call: TurnToolCall) -> str:
    """What the model reads for one finished call, in the one place it is built.

    Two decisions live here rather than at the three call sites that would
    otherwise each need them. Outside content is wrapped and its delimiter
    defanged (``untrusted.py``) — at the message layer, because a prompt cannot
    enforce a wrapper and an attacker can forge a closing tag. And the
    guardrail's warning is appended *after* the wrapper closes, so a page cannot
    be mistaken for the harness or the harness for a page.
    """
    body = wrap_result(call.name, call.result_text or "", source=_source_of(call))
    if call.guidance:
        return f"{body}\n\n{call.guidance}" if body else call.guidance
    return body


def _source_of(call: TurnToolCall) -> str:
    """The label the untrusted wrapper names as the origin of this content."""
    for key in ("url", "query"):
        value = call.arguments.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return call.name


@dataclass(frozen=True)
class TranscriptTurn:
    """One user message and everything that answered it."""

    user_text: str
    tool_calls: tuple[TurnToolCall, ...] = ()
    assistant_text: str | None = None

    @property
    def completed_calls(self) -> tuple[TurnToolCall, ...]:
        """Only the finished ones.

        A call still running is left out of the constructed context entirely —
        both halves of it — because half a tool exchange is a transcript the
        model has to guess at, and most routes reject it outright.
        """
        return tuple(call for call in self.tool_calls if call.finished)


@dataclass(frozen=True)
class Transcript:
    """Everything the constructor is allowed to see.

    A snapshot, already read from the store by the caller. Reading it here would
    put a database session inside the one function whose value is having none.
    """

    system_prompt: str
    #: Where the stable part of ``system_prompt`` ends, when the caller knows.
    #: Only a caller holding ``prompt.prefix()`` can say which part is which, so
    #: the boundary arrives here rather than being guessed at by string surgery.
    #: ``None`` means the whole prompt travels as one block.
    system_prefix: str | None = None
    turns: tuple[TranscriptTurn, ...] = ()
    # The cached summary, and how many leading Turns it covers. Both come from
    # persistence together; a summary whose span is unknown could only be
    # applied by guessing.
    summary: str | None = None
    summarised_turns: int = 0


@dataclass(frozen=True)
class ContextBudget:
    """The ceiling the constructor exists to meet, and how it gives ground."""

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
    turns_dropped: int = 0
    results_collapsed: int = 0


class ConstructedContextTooLarge(ValueError):
    """Even the protected Turns, fully collapsed, break the ceiling.

    Raised rather than trimmed past the ladder's last rung. Returning an
    over-budget context would hand admission a call it must refuse mid-Turn, and
    returning a silently mangled one is the failure this constructor exists to
    prevent.
    """

    def __init__(self, estimated_tokens: int, budget: int) -> None:
        super().__init__(
            f"the smallest constructible context is {estimated_tokens} tokens "
            f"against a ceiling of {budget}"
        )
        self.estimated_tokens = estimated_tokens
        self.budget = budget


def estimate_tokens(message: Message) -> int:
    """What one message is charged, deterministically."""
    text = message.content or ""
    for call in message.tool_calls:
        text += call.name + _compact(call.arguments)
    if message.tool_call_id:
        text += message.tool_call_id
    return MESSAGE_OVERHEAD_TOKENS + -(-len(text) // CHARS_PER_TOKEN)


def _system_message(transcript: Transcript) -> Message:
    """The system prompt, carrying its cache boundary when one is known.

    The segments describe the same string the message already holds —
    ``Message`` refuses any other arrangement — so a route that does not speak
    ``cache_control`` sees exactly the prompt it saw before, and the token
    estimate is unchanged either way.
    """
    prompt = transcript.system_prompt
    stable = transcript.system_prefix
    if not stable or not prompt.startswith(stable) or len(stable) == len(prompt):
        return Message(role=Role.SYSTEM, content=prompt)
    return Message(
        role=Role.SYSTEM,
        content=prompt,
        segments=(
            ContentSegment(stable, cache_breakpoint=True),
            ContentSegment(prompt[len(stable) :]),
        ),
    )


def _turn_messages(
    turn: TranscriptTurn, collapsed: frozenset[str]
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
                        id=call.id,
                        name=call.name,
                        arguments=dict(call.arguments),
                        output_index=index,
                        signature=call.signature,
                    )
                    for index, call in enumerate(calls)
                ),
            )
        )
        for call in calls:
            if call.id in collapsed:
                body = f"called {call.name} with arguments {_compact(call.arguments)}"
            else:
                body = shown_result(call)
            messages.append(
                Message(
                    role=Role.TOOL,
                    content=body,
                    tool_call_id=call.id,
                    name=call.name,
                )
            )
    if turn.assistant_text:
        messages.append(Message(role=Role.ASSISTANT, content=turn.assistant_text))
    return tuple(messages)


def _render_messages(
    transcript: Transcript,
    turns: Sequence[TranscriptTurn],
    dropped: int,
    collapsed: frozenset[str],
) -> tuple[Message, ...]:
    """Assemble one candidate context.

    The system prompt is one message and the summary is another. Folding the
    summary into the prompt would put conversation content inside the artifact
    whose whole property is that conversation content cannot enter it — and it
    would move the cacheable prefix once per Turn.
    """
    messages: list[Message] = [_system_message(transcript)]
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
    turns: Sequence[TranscriptTurn], budget: ContextBudget
) -> Iterator[tuple[int, frozenset[str]]]:
    """The ladder, as an ordered sequence of ``(turns dropped, collapsed)``.

    Rungs two and three interleave in one place the description does not spell
    out. A single Turn can outgrow the ceiling on its own — four rounds of
    parallel calls, each result up to its own cap — so the collapse is ordered
    by tool call, oldest first, and reaches inside the most recent Turn only
    after every older Turn has already been dropped. Ordering it by Turn instead
    would leave the one case that actually blows the budget with nothing left to
    give.
    """
    protected = max(1, budget.keep_intact_turns)
    older = turns[: max(0, len(turns) - protected)]
    recent = turns[len(older) :]

    older_ids = [call.id for turn in older for call in turn.completed_calls]
    recent_ids = [call.id for turn in recent for call in turn.completed_calls]

    # 1. Everything intact.
    yield 0, frozenset()

    # 2. Old tool results collapse to one line, oldest first.
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
    transcript: Transcript, budget: ContextBudget | None = None
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
        messages = _render_messages(transcript, live, dropped, collapsed)
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
                turns_dropped=dropped,
                results_collapsed=len(collapsed),
            )

    raise ConstructedContextTooLarge(smallest, budget.max_tokens)


__all__ = [
    "ANSWER",
    "CHARS_PER_TOKEN",
    "DISPLAY_SNIPPET_CHARS",
    "MAX_DISPLAY_RESULTS",
    "MAX_SUMMARY_CHARS",
    "MESSAGE_OVERHEAD_TOKENS",
    "OUTCOME_CANNOT_READ",
    "OUTCOME_NO_VALUE",
    "OUTCOME_VALUE",
    "SUMMARY_LABEL",
    "THOUGHT",
    "ConstructedContext",
    "ConstructedContextTooLarge",
    "ContextBudget",
    "ToolCallStatus",
    "Transcript",
    "TranscriptTurn",
    "TurnToolCall",
    "build_messages",
    "display_results",
    "estimate_tokens",
    "outcome_of",
    "shown_result",
    "summarise_call",
]
