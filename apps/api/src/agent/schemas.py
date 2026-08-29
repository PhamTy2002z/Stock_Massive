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

from src.agent.attachments import MAX_IMAGES_PER_TURN
from src.agent.loop import CHAT_MODE, TurnMode
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
    """One Study run, as the Signal Desk panel fetches it.

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
    signal_desk_spec: dict[str, Any]
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


class AllowanceResponse(BaseModel):
    """One ceiling as the client draws it.

    ``limit`` is null for a ceiling a deployment turned off, which is not the
    same as a ceiling of zero and must not render as an exhausted meter. The
    client is expected to say "no limit" and draw nothing.
    """

    used: int
    limit: int | None
    resets_at: datetime | None


class CapabilitiesResponse(BaseModel):
    """What this deployment's route can do, as the surface needs to know it.

    Separate from :class:`UsageResponse` on purpose. That one is *"one account's
    consumption"* — a number that moves as a reader works. This is a property of
    the route the API was configured and measured against, identical for every
    account and unchanged until a deploy. Folding a capability into a
    consumption snapshot would give one payload two meanings, and a client
    polling for fresh spend figures would be polling for a constant.

    One field today. It is a record and not a bare boolean because the next
    thing the surface has to ask — which is what an entitlement is — belongs
    here beside it rather than at a second endpoint.
    """

    #: Whether the configured route reads images. When false the composer still
    #: accepts and stores them, and says plainly that the model will not see
    #: them: a picture silently ignored reads as a wrong answer.
    vision: bool


class UsageResponse(BaseModel):
    """What this account has consumed against its own ceilings.

    Spend is carried in micro-USD — the ledger's own integer unit — rather than
    as a rounded currency string, so the client owns the presentation and no
    rounding happens twice. It is an operating limit on generation, not an
    amount owed, and the interface is responsible for not implying a bill.
    """

    as_of: datetime
    turns_today: AllowanceResponse
    spend_today_micro_usd: AllowanceResponse
    spend_rolling_30d_micro_usd: AllowanceResponse


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
    # Which surface asked, and therefore what the Turn owes back. ``chat`` is
    # the default, so a client that has never heard of the Signal Desk sends
    # exactly what it sent before and gets exactly what it got before.
    #
    # The type comes from the loop rather than being spelled again here, for the
    # reason this module's docstring gives about the Turn's other vocabularies:
    # a second declaration of the two values is a second place they can
    # disagree. It is part of the idempotency payload — the same question asked
    # from the desk is a different request from the same question asked in chat,
    # because only one of them is owed a picture.
    mode: TurnMode = CHAT_MODE
    # What the reader attached, by id — the bytes were uploaded before this
    # request and are read from the store, so the same question asked twice
    # sends the same short list either time.
    #
    # Part of the idempotency payload, and it has to be: the same words with two
    # different pictures are two different questions, and a key that ignored the
    # pictures would answer the second with the first one's Turn.
    #
    # Capped at the per-Turn image ceiling. One number rather than two, because
    # the list can hold at most that many entries and therefore at most that
    # many images — a second cap on the images alone could only ever agree with
    # this one, and two numbers that must agree are one number and a bug.
    attachments: list[uuid.UUID] = Field(
        default_factory=list, max_length=MAX_IMAGES_PER_TURN
    )

    @field_validator("attachments")
    @classmethod
    def _each_attachment_once(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        # The same file twice is one file. Deduplicated rather than refused: a
        # double click is not a bad request, and sending an image twice would
        # charge the Turn for it twice.
        return list(dict.fromkeys(value))

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


class AttachmentResponse(BaseModel):
    """What an upload answers with: an id and what the file turned out to be.

    Never the bytes. Reading them is its own request, so a transcript loads at
    text weight and a picture is fetched by whoever looks at it — the same split
    ``ArtifactResponse`` makes for ``frames``.

    ``media_type`` is what the bytes were measured to be, which for an image is
    not necessarily what the client said. ``estimated_tokens`` is what this file
    will be charged against the Turn's ceilings, so a client can say so before
    the reader presses send.
    """

    id: uuid.UUID
    media_type: str
    filename: str
    byte_size: int
    estimated_tokens: int | None = None


class CreatedTurnResponse(TurnResponse):
    # False when the id was already known: the same payload returns the Turn
    # that exists and starts nothing at all.
    created: bool


__all__ = [
    "AllowanceResponse",
    "ArtifactResponse",
    "AttachmentResponse",
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
    "UsageResponse",
]
