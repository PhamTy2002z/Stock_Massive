"""The typed parts a Turn produces beside its prose, starting with progress.

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
"""

from __future__ import annotations

import logging
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
#: ``cancelled`` is the reader stopping the Turn: no further attempt will be
#: made, and whatever the model had already said is what they keep. It is a
#: status of the attempt rather than a kind of its own because the question a
#: reader asks of the timeline is the same one — *what happened when this Turn
#: asked the model* — and four answers to it belong on one line.
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


__all__ = [
    "ATTEMPT_CANCELLED",
    "ATTEMPT_COMPLETED",
    "ATTEMPT_ERROR",
    "ATTEMPT_RUNNING",
    "ATTEMPT_STATUSES",
    "MAX_CODE_CHARS",
    "PROGRESS_FIELDS",
    "PROGRESS_WIRE_FIELDS",
    "RECOVERY_ACTIONS",
    "RECOVERY_COMPRESS",
    "RECOVERY_EMPTY_NUDGE",
    "RECOVERY_LOWER_OUTPUT_CAP",
    "ProgressKind",
    "ProgressPart",
    "progress_payload",
    "wire_parts",
]
