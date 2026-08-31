"""The two verdicts a reader can leave on a message (#99).

Four endpoints over three columns, and the interesting part is everything they
deliberately are not.

```
POST   /api/v1/messages/{messageId}/flag   {"reason": "..."}  → the flag
DELETE /api/v1/messages/{messageId}/flag                      → the cleared pair
POST   /api/v1/messages/{messageId}/helpful                   → the mark
DELETE /api/v1/messages/{messageId}/helpful                   → the cleared mark
```

**The flag carries a reason and the mark does not.** The four labels are what
makes a dispute readable when the answers are reviewed; there is nothing to
categorise about an answer that worked, so the positive verdict is one stamp
and asks the reader nothing. That asymmetry is the whole difference between the
two halves of this file.

**It opens nothing.** No ticket is created, nobody is notified, no account is
suspended, and no background job is dispatched. v1 has no dispute workflow; the
value of the action is downstream and manual — a flagged message confirmed as a
genuine failure is a defect somebody reads the transcript for.

**Replay means re-reading what was written down, not reproducing the answer.**
The transcript message is kept indefinitely; the Tool Call Traces behind it
expire at 90 days, so a flag raised later is answerable from the prose alone.
That limit is stated rather than hidden: a trace can be re-read, not re-run.

**It hangs off the store, not off the desk service.** Flagging is not a Turn: it
admits nothing, spends nothing and reaches no model, so it takes the
``AgentPersistence`` dependency directly rather than the service that owns the
loop. A flag must remain possible on a transcript the model route is too broke
or too broken to add to.

**Ownership is verified here, and not only in the UI.** The store resolves the
message through an owner-scoped join, so another user's message is *not found*
rather than forbidden — a caller able to tell those two apart has already been
told that the id exists.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.agent.persistence import (
    AgentPersistence,
    MessageRecord,
    UnflaggableMessage,
)
from src.agent.schemas import (
    FlagMessageRequest,
    MessageFlagResponse,
    MessageHelpfulResponse,
)
from src.auth.dependencies import CurrentUser

router = APIRouter(prefix="/messages", tags=["alpha-desk"])


def get_store() -> AgentPersistence:
    """The store, as a dependency so a test can substitute it."""
    return AgentPersistence()


Store = Annotated[AgentPersistence, Depends(get_store)]

_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
)


def _flag(record: MessageRecord) -> MessageFlagResponse:
    return MessageFlagResponse(
        message_id=record.id,
        flagged_reason=record.flagged_reason,
        flagged_at=record.flagged_at,
    )


def _helpful(record: MessageRecord) -> MessageHelpfulResponse:
    return MessageHelpfulResponse(
        message_id=record.id, helpful_at=record.helpful_at
    )


@router.post("/{message_id}/flag", response_model=MessageFlagResponse)
async def flag_message(
    message_id: int,
    payload: FlagMessageRequest,
    current_user: CurrentUser,
    store: Store,
) -> MessageFlagResponse:
    """Mark one assistant message with one reason. Idempotent per message.

    Re-flagging replaces the reason rather than accumulating rows, which is what
    makes the missing ``message_flag`` table the right call: a message carries
    at most one reason, and a second press is the reader correcting themselves.
    """
    try:
        record = await store.flag_message(
            current_user.id, message_id, reason=payload.reason
        )
    except UnflaggableMessage as refused:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "not_an_assistant_message",
                "message": (
                    "Only an assistant message can be flagged. This action is "
                    "about what the system answered."
                ),
            },
        ) from refused
    if record is None:
        raise _NOT_FOUND
    return _flag(record)


@router.delete("/{message_id}/flag", response_model=MessageFlagResponse)
async def unflag_message(
    message_id: int,
    current_user: CurrentUser,
    store: Store,
) -> MessageFlagResponse:
    """Clear the flag. Both columns, never one of them.

    Answers with the cleared pair rather than ``204`` so the caller can render
    the message's settled state from the response it already has, the same way
    the flag itself does.
    """
    record = await store.unflag_message(current_user.id, message_id)
    if record is None:
        raise _NOT_FOUND
    return _flag(record)


@router.post("/{message_id}/helpful", response_model=MessageHelpfulResponse)
async def mark_message_helpful(
    message_id: int,
    current_user: CurrentUser,
    store: Store,
) -> MessageHelpfulResponse:
    """Mark one assistant message helpful. Idempotent per message.

    No body, because there is nothing to say: the mark is the whole of it. A
    second press on an already-marked message answers with the existing stamp
    rather than moving it, the same rule the flag follows.
    """
    try:
        record = await store.mark_helpful(current_user.id, message_id)
    except UnflaggableMessage as refused:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "not_an_assistant_message",
                "message": (
                    "Only an assistant message can be marked helpful. This "
                    "action is about what the system answered."
                ),
            },
        ) from refused
    if record is None:
        raise _NOT_FOUND
    return _helpful(record)


@router.delete("/{message_id}/helpful", response_model=MessageHelpfulResponse)
async def clear_message_helpful(
    message_id: int,
    current_user: CurrentUser,
    store: Store,
) -> MessageHelpfulResponse:
    """Take the mark back, answering with the cleared stamp."""
    record = await store.clear_helpful(current_user.id, message_id)
    if record is None:
        raise _NOT_FOUND
    return _helpful(record)


__all__ = ["router", "get_store"]
