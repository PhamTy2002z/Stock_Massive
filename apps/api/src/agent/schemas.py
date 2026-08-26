"""The request and response shapes of the Alpha Desk transport (#85).

Thin by design.  The Turn's own vocabulary — its statuses, its terminal reasons,
its event envelope — is fixed in :mod:`src.agent.events` and
:mod:`src.alpha.models`, and restating any of it as a second enum here would
create two places that can disagree about what ``incomplete`` means.

A message's ``content`` is deliberately an open mapping rather than a model.
Its shape belongs to the lifecycle that writes it (``turns.assistant_message``),
and a second declaration of it here is a second thing to keep in step with the
client reading it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.agent.turns import MAX_USER_INPUT_BYTES
from src.alpha.models import FLAG_REASONS
from src.stocks.shared import validate_symbol


def _symbol(value: str) -> str:
    """Normalise one symbol, refusing a malformed one as a request error.

    ``validate_symbol`` raises a ``StockServiceError``, which the application
    answers with 502 — the right status for an upstream that misbehaved and the
    wrong one for a browser that sent ``"hp g"``. Re-raised as a ``ValueError``
    so pydantic answers 422.
    """
    try:
        return validate_symbol(value)
    except Exception as exc:  # noqa: BLE001 - narrowed to a request error below
        raise ValueError(str(exc)) from exc


class CreateThreadRequest(BaseModel):
    """A new Thread. Free-roaming, so it is not opened against a symbol."""

    title: str | None = Field(default=None, max_length=200)


class UpdateThreadRequest(BaseModel):
    """What the sidebar's per-Thread menu may change: its name and its pin.

    Both fields are optional and the router reads ``model_fields_set`` rather
    than the values, because an absent ``title`` and a ``null`` one are
    different requests: one leaves the name alone, the other clears it so the
    Thread falls back to its timestamped name.
    """

    title: str | None = Field(default=None, max_length=200)
    pinned: bool | None = Field(default=None)


class FlagMessageRequest(BaseModel):
    """One reason label, checked against the vocabulary the column declares.

    Validated against :data:`FLAG_REASONS` rather than restated as an enum
    here, for the reason this module's docstring gives: a second spelling of
    the four labels is a second place they can disagree, and a count would then
    be over a category the store cannot write.

    **There is no free-text field, and that is deliberate.** A comment box is a
    promise that somebody reads it, and v1 has no dispute workflow to read one.
    The label is what the ops query counts; the transcript and its Tool Call
    Trace are what a reviewer re-reads.
    """

    reason: str

    @field_validator("reason")
    @classmethod
    def _within_the_vocabulary(cls, value: str) -> str:
        if value not in FLAG_REASONS:
            raise ValueError(
                f"reason must be one of: {', '.join(FLAG_REASONS)}"
            )
        return value


class MessageFlagResponse(BaseModel):
    """A message's flag after a write. Both fields are set, or neither is."""

    message_id: int
    flagged_reason: str | None
    flagged_at: datetime | None


class MessageHelpfulResponse(BaseModel):
    """A message's positive mark after a write.

    One field and no reason, mirroring the column. ``helpful_at`` set is the
    mark; null is its absence — which is what ``DELETE`` answers with, rather
    than ``204``, so the caller can render the settled state from the response
    it already has.
    """

    message_id: int
    helpful_at: datetime | None


class MessageResponse(BaseModel):
    id: int
    seq: int
    role: str
    content: dict[str, Any]
    created_at: datetime
    # Carried on the transcript so a reopened Thread shows what was already
    # flagged, rather than an action that looks unpressed. Null on almost every
    # message.
    flagged_reason: str | None = None
    flagged_at: datetime | None = None
    # Carried for the same reason as the flag: an answer the reader already
    # marked helpful must come back marked.
    helpful_at: datetime | None = None


class ArtifactResponse(BaseModel):
    """One Study run, as the canvas panel fetches it.

    Immutable by design, which is what lets the browser cache it forever: the
    row is written once and re-opening a Thread renders it rather than
    recomputing. ``provenance`` carries the ``asOf`` that freeze is measured by.

    ``frames`` is the numbers themselves. This is the only route they travel,
    and the model is not on it.
    """

    id: uuid.UUID
    study_name: str
    study_version: int
    params: dict[str, Any]
    canvas_spec: dict[str, Any]
    frames: dict[str, Any]
    provenance: dict[str, Any]
    created_at: datetime


class ThreadResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    # Every symbol this Thread has touched. A Thread is never owned by one.
    symbols: list[str]
    # When the user pinned it, or null. The list arrives already ordered with
    # the pinned group first; this is carried so the sidebar can *label* that
    # group rather than have to sort it.
    pinned_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ThreadDetailResponse(ThreadResponse):
    messages: list[MessageResponse]


class ThreadListResponse(BaseModel):
    threads: list[ThreadResponse]


class CreateTurnRequest(BaseModel):
    """One user message, under an id the browser chose before it asked.

    ``turn_id`` is the idempotency key and arrives in the body rather than the
    path, because the path names the Thread the Turn is being created *in* and
    the Turn does not exist yet.
    """

    turn_id: uuid.UUID
    text: str = Field(min_length=1)
    # The symbols the user's message is about, as the surface understood them.
    # Part of the idempotency payload: the same id with a different set is a
    # different question.
    symbols: list[str] = Field(default_factory=list, max_length=10)
    # Retry creates a *new* Turn that points at the old one; the previous Turn,
    # its spend, its message and its traces stay immutable.
    retry_of_turn_id: uuid.UUID | None = None

    @field_validator("text")
    @classmethod
    def _within_the_input_cap(cls, value: str) -> str:
        # Checked here as well as in the lifecycle: refusing 8 KiB of UTF-8
        # before a row exists is the difference between a bad request and a
        # Turn that has to be cleaned up.
        if len(value.encode("utf-8")) > MAX_USER_INPUT_BYTES:
            raise ValueError("message exceeds the 8 KiB input cap")
        return value

    @field_validator("symbols")
    @classmethod
    def _normalise(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(_symbol(entry) for entry in value))


class TurnResponse(BaseModel):
    """What a Turn looks like to a caller that is not reading its stream."""

    id: uuid.UUID
    thread_id: uuid.UUID
    status: str
    terminal_reason: str | None
    request_message_id: int
    response_message_id: int | None
    retry_of_turn_id: uuid.UUID | None
    # Where the stream got to, so a client can tell a fresh Turn from one it has
    # already partly seen.
    last_event_seq: int
    cancel_requested: bool
    started_at: datetime
    finished_at: datetime | None


class CreatedTurnResponse(TurnResponse):
    # False when the id was already known: the same payload returns the Turn
    # that exists and starts nothing at all.
    created: bool


__all__ = [
    "ArtifactResponse",
    "CreateThreadRequest",
    "CreateTurnRequest",
    "CreatedTurnResponse",
    "FlagMessageRequest",
    "MessageFlagResponse",
    "MessageResponse",
    "ThreadDetailResponse",
    "ThreadListResponse",
    "ThreadResponse",
    "TurnResponse",
]
