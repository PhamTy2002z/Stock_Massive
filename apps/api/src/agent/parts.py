"""The typed parts a Turn produces beside its prose: progress, and a question.

A Turn already publishes two things a reader can see: the answer, delta by
delta, and one row per tool call. What it never published is what the *loop*
did — which lane it was routed to, that it asked the model and got an answer,
that it gave up transcript and asked again, that it ran out of rounds. Those
facts existed only in this process's log, so a reader watching a long Turn saw a
spinner, and an operator reading a finished one could not tell a Turn that
compressed twice from a Turn that sailed through.

A progress part is that audit trail, and three rules keep it honest.

**One part per real event.** Every part is emitted at the moment the loop does
the thing it names, from the code that does it. There is no timer, no
progress bar and no stage that a Turn is declared to have entered because some
wall clock said so: a made-up stage is worse than no stage, because it looks
exactly like a measurement.

**Content-light, by an allowlist.** :data:`PROGRESS_FIELDS` names every key each
kind may carry, and :func:`progress_payload` drops everything else. The values
are codes and numbers this harness wrote — a lane name, a bounded counter, a
tool-call id — and never a page's text, a tool result or a sentence from the
model. Progress travels on a channel the browser renders, so a payload a web
page could influence would be an injection path onto that channel, and the
allowlist is what makes the absence structural rather than remembered.

**It does not duplicate ``tool.call``.** What a call asked, what it returned and
which sources it found already live on that channel and in the Tool Call Trace.
A ``tool_round`` part therefore carries the *shape* of the round — how many
calls, how much of the external allowance is spent, which call ids — and refers
to the other channel for the rest.

Nothing here reaches the model. Progress is written for a reader and for an
operator; the transcript the next call is built from is assembled by
``messages.build_messages`` out of prose and tool results, and there is no field
on it a part could arrive through.

A **question part** is the second kind, and it is a different animal: progress
narrates a Turn, and a question *ends* one. When the harness cannot discover
something it needs — a horizon, a cost basis, what the reader is deciding — it
asks, and the asking terminates the Turn like any other terminal. There is no
suspended Turn waiting for a tap: the ask and the answer are two Turns of a
conversation, so nothing has to be kept alive between them and nothing is lost
if the reader never taps at all.

Two rules follow from that, and they are why this part validates instead of
dropping. A malformed progress part must never be the thing that ends a Turn, so
:func:`progress_payload` drops what it cannot carry; a malformed question has no
safe fallback, because a card with no answerable option is a dead end the reader
cannot leave — so :class:`QuestionPart` refuses to exist. And the part carries no
state: what the reader did with it changes after the terminal transaction has
committed, so the outcome lives on a row (``agent_question``) and the part stays
the immutable thing that was asked.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ProgressKind(str, Enum):
    """The seven loop events a Turn reports progress for.

    A closed set, and closed for the same reason the payload keys are an
    allowlist: a kind nobody named is a kind nobody decided was fit for a
    screen. A new one is added by the code that has a new real event to report.
    """

    #: Which ceilings this Turn was given, and the machine reason it was.
    LANE_SELECTED = "lane_selected"
    #: The Turn's asking of the model: running, then how that asking ended.
    MODEL_ATTEMPT = "model_attempt"
    #: One round of tools dispatched, by shape rather than by content.
    TOOL_ROUND = "tool_round"
    #: A bounded recovery the loop actually performed.
    RECOVERY = "recovery"
    #: The guardrail ladder stopped the tool loop; the Turn still answers.
    TOOLS_HALTED = "tools_halted"
    #: The last round the lane allows; the model is told so and answers.
    ROUNDS_EXHAUSTED = "rounds_exhausted"
    #: The Turn ran out of the wall clock its lane gave it.
    DEADLINE = "deadline"


#: The lifecycle of one Turn's asking of the model.
#:
#: ``cancelled`` is the reader stopping the Turn: whatever the model had already
#: said is what they keep, no further attempt will be made, and where the stop
#: arrived mid-call the asking that was in flight was itself torn down rather
#: than waited out. It is a status of the attempt rather than a kind of its own
#: because the question a reader asks of the timeline is the same one — *what
#: happened when this Turn asked the model* — and four answers to it belong on
#: one line.
ATTEMPT_RUNNING = "running"
ATTEMPT_COMPLETED = "completed"
ATTEMPT_ERROR = "error"
ATTEMPT_CANCELLED = "cancelled"

ATTEMPT_STATUSES: frozenset[str] = frozenset(
    {ATTEMPT_RUNNING, ATTEMPT_COMPLETED, ATTEMPT_ERROR, ATTEMPT_CANCELLED}
)

#: The three bounded recoveries the loop owns, under the names
#: ``core/llm/recovery.py`` gives the two it is handed and the loop gives the one
#: it decides on its own.
RECOVERY_COMPRESS = "compress"
RECOVERY_LOWER_OUTPUT_CAP = "lower_output_cap"
RECOVERY_EMPTY_NUDGE = "empty_nudge"

RECOVERY_ACTIONS: frozenset[str] = frozenset(
    {RECOVERY_COMPRESS, RECOVERY_LOWER_OUTPUT_CAP, RECOVERY_EMPTY_NUDGE}
)

#: What each kind of part is allowed to carry, and nothing more.
#:
#: Read by :func:`progress_payload`, which is the only way a payload is built.
#: The shapes are deliberately small: a counter and its bound rather than the
#: route's message, a list of call ids rather than the queries behind them.
PROGRESS_FIELDS: Mapping[ProgressKind, tuple[str, ...]] = {
    ProgressKind.LANE_SELECTED: ("lane", "reason"),
    ProgressKind.MODEL_ATTEMPT: ("status", "terminal_reason"),
    ProgressKind.TOOL_ROUND: ("calls", "external_used", "call_ids"),
    ProgressKind.RECOVERY: ("action", "attempt", "bound"),
    ProgressKind.TOOLS_HALTED: ("reason",),
    ProgressKind.ROUNDS_EXHAUSTED: ("rounds",),
    #: The Turn's own wall clock ran out. Nothing to say beyond that it did:
    #: which lane granted the clock is on the ``lane_selected`` part, and how
    #: far the Turn got is the rest of the trail.
    ProgressKind.DEADLINE: (),
}

#: The keys one part carries on the wire, in the order they are written.
#:
#: Named here rather than in the transport so that the publisher restating a
#: part and the checkpoint persisting one cannot disagree about its shape.
PROGRESS_WIRE_FIELDS = ("seq", "kind", "round", "payload", "at")

#: How long a code may be. No name, reason or status this harness writes comes
#: near it, so a longer string is prose that reached the wrong channel — dropped
#: rather than truncated, because a cut sentence still puts a page's words in
#: front of the reader and additionally makes them look like a code.
MAX_CODE_CHARS = 120


def _admissible(kind: ProgressKind, key: str, value: Any) -> bool:
    """Whether one value is the kind of thing a part may carry.

    Codes, numbers and flags, plus the one list of codes ``call_ids`` is. A
    mapping or a nested object is refused outright: the way a page's text would
    arrive here is inside somebody's structured payload, and there is no reason
    for a part to carry one.
    """
    if isinstance(value, str):
        if len(value) > MAX_CODE_CHARS:
            logger.warning(
                "Dropped %r from a %s progress part: %d characters is prose, not a code",
                key,
                kind.value,
                len(value),
            )
            return False
        return True
    if value is None or isinstance(value, (bool, int, float)):
        return True
    if isinstance(value, (list, tuple)):
        return all(
            isinstance(entry, str) and len(entry) <= MAX_CODE_CHARS for entry in value
        )
    logger.warning(
        "Dropped %r from a %s progress part: %s is not a code or a number",
        key,
        kind.value,
        type(value).__name__,
    )
    return False


def progress_payload(kind: ProgressKind, **fields: Any) -> dict[str, Any]:
    """One part's payload, holding only what its kind declared.

    An unknown *kind* is refused, because there is no shape to fall back to and
    a part nobody declared has no business on a rendered channel. An unknown
    *key* is dropped and logged instead of raising: a progress part is an
    account of a Turn and must never be the thing that ends one, and a caller
    that passed a key nobody allowlisted has a bug the log names loudly.

    The kind is resolved through the enum rather than looked up as it arrived,
    because :class:`ProgressKind` is a string enum: a bare string that happens to
    match would otherwise sail through here and fail later, where the part is
    written to the wire.
    """
    try:
        kind = ProgressKind(kind)
    except ValueError as error:
        raise ValueError(f"{kind!r} is not a progress kind") from error
    allowed = PROGRESS_FIELDS[kind]
    payload: dict[str, Any] = {}
    for key, value in fields.items():
        if key not in allowed:
            logger.warning(
                "Dropped %r from a %s progress part: it is not an allowed field",
                key,
                kind.value,
            )
            continue
        if not _admissible(kind, key, value):
            continue
        payload[key] = list(value) if isinstance(value, (list, tuple)) else value
    return payload


@dataclass(frozen=True)
class ProgressPart:
    """One loop event, numbered within its Turn.

    ``seq`` is the part's ordinal in this Turn and not the publisher's event
    sequence. The two count different things — a Turn publishes deltas and tool
    calls between its parts — and a reader ordering the trail wants the parts'
    own order, which survives being read back off a checkpoint where no event
    sequence exists.

    ``round`` is the tool round the event happened in, so a part reads against
    the calls and the narration of the same round. ``at`` is the loop's clock,
    UTC and ISO, because the one thing a reader cannot recover from the order
    alone is how long a Turn sat inside a single step.
    """

    seq: int
    kind: ProgressKind
    round: int
    payload: Mapping[str, Any]
    at: str

    def as_wire(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "kind": self.kind.value,
            "round": self.round,
            "payload": dict(self.payload),
            "at": self.at,
        }


def wire_parts(parts: Sequence[ProgressPart]) -> tuple[dict[str, Any], ...]:
    """A Turn's parts as the checkpoint and the outcome carry them."""
    return tuple(part.as_wire() for part in parts)


# -- a question, and what became of it ------------------------------------


#: The four outcomes of one asking, in the order they can be reached.
#:
#: ``pending`` is written by the terminal transaction that asked. The other three
#: are ends: the reader chose (``answered``), the reader declined and the work
#: runs on stated assumptions (``skipped``), or the reader typed into the
#: composer instead of touching the card and the next Turn made the question moot
#: (``superseded``). A resolved question is never reopened — a second answer to a
#: question that has already branched the work would be a different question.
#:
#: They are not on the part. The part is what was asked and never changes; these
#: change after the terminal transaction has committed, which is precisely why
#: they live on a row of their own.
QUESTION_PENDING = "pending"
QUESTION_ANSWERED = "answered"
QUESTION_SKIPPED = "skipped"
QUESTION_SUPERSEDED = "superseded"

QUESTION_STATES: tuple[str, ...] = (
    QUESTION_PENDING,
    QUESTION_ANSWERED,
    QUESTION_SKIPPED,
    QUESTION_SUPERSEDED,
)

#: A question offers two to four choices, and the bound is not cosmetic. One
#: choice is not a question, and a list long enough to need scrolling is a form —
#: the discipline is that an unanswerable question should have been research
#: instead.
MIN_QUESTION_OPTIONS = 2
MAX_QUESTION_OPTIONS = 4

#: How long each piece of a question may be. The prompt is a sentence a reader
#: answers in one glance, a label is a button, and an id is a code the client
#: posts back. Past these a card stops being a card, so the part is refused
#: rather than truncated: a cut prompt asks something other than what was meant.
MAX_QUESTION_PROMPT_CHARS = 400
MAX_QUESTION_LABEL_CHARS = 120
MAX_QUESTION_DETAIL_CHARS = 300
MAX_QUESTION_OPTION_ID_CHARS = 64

#: The choice that is always offered. Skipping is not cancelling: the work runs
#: on default assumptions and prints them, which is what keeps a question card
#: from ever being a door the reader has to open.
DEFAULT_SKIP_LABEL = "Bỏ qua — dùng giả định mặc định"

#: The keys one question carries on the wire, in the order they are written.
#:
#: Named here rather than in the transport for the reason the progress fields
#: are: the publisher restating a question, the row persisting one and the client
#: drawing one must not be able to disagree about its shape.
QUESTION_WIRE_FIELDS = (
    "question_id",
    "prompt",
    "options",
    "multi_select",
    "skip_label",
)


def _bounded(what: str, value: Any, limit: int) -> str:
    """One piece of a question: a non-empty string inside its own ceiling."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"a question's {what} must be a non-empty string")
    if len(value) > limit:
        raise ValueError(
            f"a question's {what} is {len(value)} characters; the ceiling is {limit}"
        )
    return value


@dataclass(frozen=True)
class QuestionOption:
    """One choice, as data rather than as rendered text.

    ``id`` is what the client posts back and what the row stores, so it is a
    stable code and never the label: a reader's choice has to stay readable after
    somebody rewords the button.

    ``detail`` is the one line under the label — why this choice, or what it
    assumes. Optional, because most choices are self-explanatory and a card of
    explained buttons is a card nobody reads.
    """

    id: str
    label: str
    detail: str | None = None

    def __post_init__(self) -> None:
        _bounded("option id", self.id, MAX_QUESTION_OPTION_ID_CHARS)
        _bounded("option label", self.label, MAX_QUESTION_LABEL_CHARS)
        if self.detail is not None:
            _bounded("option detail", self.detail, MAX_QUESTION_DETAIL_CHARS)

    def as_wire(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "detail": self.detail}


@dataclass(frozen=True)
class QuestionPart:
    """One asking, immutable, and the whole of what a card is drawn from.

    ``question_id`` is a UUID and is also the primary key of the row that records
    what became of it. One identifier rather than two: a client answering a card
    posts the id it was drawn with, and a second key would be a second thing that
    can point at the wrong question.

    ``multi_select`` is carried from the first version even though no surface
    offers it yet. It is a fact about the *question* — whether choosing two
    answers is coherent — and a flag added later would have to be guessed at for
    every question already stored.
    """

    question_id: str
    prompt: str
    options: tuple[QuestionOption, ...]
    multi_select: bool = False
    skip_label: str = DEFAULT_SKIP_LABEL

    def __post_init__(self) -> None:
        try:
            uuid.UUID(str(self.question_id))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError(
                f"{self.question_id!r} is not a question id; it is the primary key "
                "of the row that records the outcome and has to be a UUID"
            ) from error
        _bounded("prompt", self.prompt, MAX_QUESTION_PROMPT_CHARS)
        _bounded("skip label", self.skip_label, MAX_QUESTION_LABEL_CHARS)
        # Coerced rather than demanded as a tuple: a caller building options in a
        # list is the ordinary case, and a frozen part holding a mutable list
        # would be frozen in name only.
        object.__setattr__(self, "options", tuple(self.options))
        if not MIN_QUESTION_OPTIONS <= len(self.options) <= MAX_QUESTION_OPTIONS:
            raise ValueError(
                f"a question offers {MIN_QUESTION_OPTIONS} to "
                f"{MAX_QUESTION_OPTIONS} options; this one has {len(self.options)}"
            )
        if len(set(self.option_ids)) != len(self.options):
            # Two options under one id would make an answer ambiguous at exactly
            # the moment it is supposed to settle something.
            raise ValueError("a question's option ids must be distinct")

    @property
    def option_ids(self) -> tuple[str, ...]:
        return tuple(option.id for option in self.options)

    def as_wire(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "prompt": self.prompt,
            "options": [option.as_wire() for option in self.options],
            "multi_select": self.multi_select,
            "skip_label": self.skip_label,
        }


def question_option_ids(payload: Mapping[str, Any]) -> tuple[str, ...]:
    """The ids a stored question was written with, read back off its payload.

    The one reader of a persisted question's options, so that "is this a choice
    this question offered" has a single answer wherever it is asked — the store
    validating an answer, and anything later that has to render one.
    """
    options = payload.get("options") or ()
    if not isinstance(options, Sequence) or isinstance(options, (str, bytes)):
        return ()
    return tuple(
        str(option["id"])
        for option in options
        if isinstance(option, Mapping) and option.get("id")
    )


__all__ = [
    "ATTEMPT_CANCELLED",
    "ATTEMPT_COMPLETED",
    "ATTEMPT_ERROR",
    "ATTEMPT_RUNNING",
    "ATTEMPT_STATUSES",
    "DEFAULT_SKIP_LABEL",
    "MAX_CODE_CHARS",
    "MAX_QUESTION_DETAIL_CHARS",
    "MAX_QUESTION_LABEL_CHARS",
    "MAX_QUESTION_OPTIONS",
    "MAX_QUESTION_OPTION_ID_CHARS",
    "MAX_QUESTION_PROMPT_CHARS",
    "MIN_QUESTION_OPTIONS",
    "PROGRESS_FIELDS",
    "PROGRESS_WIRE_FIELDS",
    "QUESTION_ANSWERED",
    "QUESTION_PENDING",
    "QUESTION_SKIPPED",
    "QUESTION_STATES",
    "QUESTION_SUPERSEDED",
    "QUESTION_WIRE_FIELDS",
    "RECOVERY_ACTIONS",
    "RECOVERY_COMPRESS",
    "RECOVERY_EMPTY_NUDGE",
    "RECOVERY_LOWER_OUTPUT_CAP",
    "ProgressKind",
    "ProgressPart",
    "QuestionOption",
    "QuestionPart",
    "progress_payload",
    "question_option_ids",
    "wire_parts",
]
