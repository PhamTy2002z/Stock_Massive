"""The three endpoints that put a Turn on the wire, and the Threads behind them.

``docs/adr/0013`` fixes the surface:

```
POST /api/alpha-desk/threads/{threadId}/turns    → admit, create, return turnId
GET  /api/alpha-desk/turns/{turnId}/events       → same-origin EventSource
POST /api/alpha-desk/turns/{turnId}/cancel       → authenticated, idempotent
```

Four properties are worth reading the code for.

**An admission failure never opens a stream.**  Admission is asked before a row
exists and answers with an ordinary status — 429 for an exhausted user
allowance, 503 for exhausted service budget or a full semaphore — because a
refusal folded into the stream is a refusal the client has to parse, and it
would make the idempotency key arrive at the same moment as the work.

**No database session is held across the streaming response.**  The subscribe
endpoint authenticates and resolves ownership through its own short session and
closes it *before* the response begins, rather than through ``Depends(get_db)``
whose scope ends only when the response does.  The async pool is 15 connections
(``docs/specs/0003`` §10.5); one held per Turn would cap concurrency at 15 and
make the sixteenth wait thirty seconds to fail.

**Ownership is verified here, not at the proxy.**  Next owns cookies and
forwards a bearer token, and that is all it is: every one of create, subscribe,
snapshot and cancel resolves the user itself and reads the Turn through an
owner-scoped join, so a Turn under another user's Thread is not found rather
than forbidden.

**Subscription is not a Turn start.**  It passes through its own per-user and
per-Turn limiter and never through the IP-based ``heavy`` one: behind the Next
proxy every user shares one IP, so the first reconnect burst would rate-limit
everybody at once.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse

from src.agent.messages import TranscriptTurn
from src.agent.persistence import (
    MessageRecord,
    ThreadRecord,
    ThreadView,
    TurnPayloadConflict,
    TurnRecord,
)
from src.agent.prompt import RuntimeContext
from src.agent.schemas import (
    ArtifactResponse,
    CreatedTurnResponse,
    CreateThreadRequest,
    CreateTurnRequest,
    MessageResponse,
    ThreadDetailResponse,
    ThreadListResponse,
    ThreadResponse,
    TurnResponse,
    UpdateThreadRequest,
)
from src.agent.service import AlphaDeskService, alpha_desk
from src.agent.sse import frames
from src.auth.dependencies import CurrentUser
from src.auth.models import User
from src.auth.security import TokenError, decode_access_token
from src.auth.service import get_user_by_id
from src.core.database import async_session_factory
from src.stocks.providers.normalize import VN_TZ

logger = logging.getLogger(__name__)

router = APIRouter(tags=["alpha-desk"])

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)

# What every SSE response carries. ``no-transform`` is the load-bearing half of
# the cache header: a proxy permitted to transform the body is a proxy permitted
# to buffer it, and a buffered event stream is a stream that arrives at the end.
STREAM_HEADERS = {
    "Cache-Control": "no-store, no-transform",
    # nginx buffers proxied responses by default and would hold every event
    # until the Turn finished. Harmless where no nginx is in the path.
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def desk() -> AlphaDeskService:
    """The process's service, as a dependency so a test can override it."""
    return alpha_desk()


Desk = Annotated[AlphaDeskService, Depends(desk)]


# -- reading the transcript ------------------------------------------------


def _thread(record: ThreadRecord) -> ThreadResponse:
    return ThreadResponse(
        id=record.id,
        title=record.title,
        symbols=list(record.symbols),
        pinned_at=record.pinned_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _message(record: MessageRecord) -> MessageResponse:
    return MessageResponse(
        id=record.id,
        seq=record.seq,
        role=record.role,
        content=dict(record.content),
        created_at=record.created_at,
        # A reopened Thread has to show what was already flagged, or the action
        # looks unpressed and the reader presses it a second time (#99).
        flagged_reason=record.flagged_reason,
        flagged_at=record.flagged_at,
        helpful_at=record.helpful_at,
    )


def _turn(record: TurnRecord) -> dict:
    return {
        "id": record.id,
        "thread_id": record.thread_id,
        "status": record.status,
        "terminal_reason": record.terminal_reason,
        "request_message_id": record.request_message_id,
        "response_message_id": record.response_message_id,
        "retry_of_turn_id": record.retry_of_turn_id,
        "last_event_seq": record.last_event_seq,
        "cancel_requested": record.cancel_requested_at is not None,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
    }


def history_of(messages: Sequence[MessageRecord]) -> tuple[TranscriptTurn, ...]:
    """The Thread so far, as the context constructor reads it.

    A user message opens a Turn and the assistant message that follows closes
    it, so the pairing is by order rather than by a foreign key — which is also
    what makes an interrupted Turn with no answer render as a Turn that asked
    and got nothing, instead of silently swallowing the question.

    Tool calls are deliberately absent: ``build_messages`` trims older Turns to
    their prose, and re-reading every trace of every earlier Turn to throw it
    away is a query per Turn for nothing.
    """
    turns: list[TranscriptTurn] = []
    for record in messages:
        text = str(record.content.get("text") or "")
        if record.role == "user":
            turns.append(TranscriptTurn(user_text=text))
        elif record.role == "assistant" and turns:
            last = turns[-1]
            if last.assistant_text is None:
                turns[-1] = TranscriptTurn(
                    user_text=last.user_text,
                    tool_calls=last.tool_calls,
                    assistant_text=text,
                )
    return tuple(turns)


# -- authentication for the long response ----------------------------------


async def streaming_user_id(request: Request) -> int:
    """Resolve the caller, and close the session before anything streams.

    Deliberately not ``Depends(get_current_user)``. A dependency that opens a
    database session keeps it until the *response* ends, and this response ends
    when the Turn does — up to ten minutes later. ``docs/specs/0003`` §10.5 is
    explicit that no session is held across a streaming Turn.
    """
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _UNAUTHORIZED
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (TokenError, KeyError, TypeError, ValueError):
        raise _UNAUTHORIZED

    async with async_session_factory() as session:
        user = await get_user_by_id(session, user_id)
        # Read inside the scope: the instance is detached once the session
        # closes, and touching an expired attribute afterwards raises.
        active = user is not None and bool(user.is_active)
        identity = None if user is None else int(user.id)
    if not active or identity is None:
        raise _UNAUTHORIZED
    return identity


StreamingUser = Annotated[int, Depends(streaming_user_id)]


# -- Threads ---------------------------------------------------------------


@router.post(
    "/threads",
    response_model=ThreadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_thread(
    payload: CreateThreadRequest,
    current_user: CurrentUser,
    desk: Desk,
) -> ThreadResponse:
    """Open a Thread. It belongs to a user, never to a symbol."""
    desk.assert_enabled()
    return _thread(await desk.store.create_thread(current_user.id, payload.title))


@router.get("/threads", response_model=ThreadListResponse)
async def list_threads(current_user: CurrentUser, desk: Desk) -> ThreadListResponse:
    """This user's Threads, most recently touched first."""
    records = await desk.store.list_threads(current_user.id)
    return ThreadListResponse(threads=[_thread(record) for record in records])


@router.get("/threads/{thread_id}", response_model=ThreadDetailResponse)
async def read_thread(
    thread_id: uuid.UUID,
    current_user: CurrentUser,
    desk: Desk,
) -> ThreadDetailResponse:
    """One Thread and its canonical transcript.

    The transcript is the only thing a reopened Thread renders. A draft belongs
    to a running Turn and reaches the client through the stream; it is never
    part of the canonical history.
    """
    view = await desk.store.read_thread(current_user.id, thread_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return ThreadDetailResponse(
        **_thread(view).model_dump(),
        messages=[_message(message) for message in view.messages],
    )


@router.patch("/threads/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: uuid.UUID,
    payload: UpdateThreadRequest,
    current_user: CurrentUser,
    desk: Desk,
) -> ThreadResponse:
    """Rename a Thread or pin it — the two things the sidebar menu writes.

    Which fields were *sent* decides what is written, so a pin carries no title
    and a rename does not silently unpin. An unknown Thread and another user's
    Thread answer the same 404: a caller who could tell them apart has been
    told an id exists.
    """
    desk.assert_enabled()
    sent = payload.model_fields_set
    record = await desk.store.update_thread(
        current_user.id,
        thread_id,
        title=payload.title if "title" in sent else ...,
        # `pinned: null` is not a third state. The field is a boolean the menu
        # toggles, and a null in it means the same as leaving it out.
        pinned=payload.pinned if "pinned" in sent and payload.pinned is not None else ...,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return _thread(record)


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: uuid.UUID,
    current_user: CurrentUser,
    desk: Desk,
) -> Response:
    """Delete a Thread and everything hanging off it.

    Cascades to its messages, its traces and its Turns (`docs/specs/0003`
    §10.6). It is not reversible and there is no archive: the menu asks the
    user to confirm, and this route is what that confirmation runs.

    A Thread that is not this user's answers 404 rather than 403, for the same
    reason the read route does.
    """
    desk.assert_enabled()
    if not await desk.store.delete_thread(current_user.id, thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -- creating a Turn -------------------------------------------------------


def _runtime(user: User) -> RuntimeContext:
    """The two trusted values, and nothing else, for one Turn.

    The date is read in Vietnam rather than in UTC: a Turn opened at 00:30 local
    time is asked on a day that is still yesterday in UTC, and "today" is the
    reader's day or it is no use to them.

    The name is the only user-supplied string that reaches the system prompt, so
    it is the whole attack surface of this function. ``RuntimeContext`` sanitises
    it; passing it through untouched here is deliberate, because a second
    cleaning rule beside that one is how the two come to disagree.
    """
    return RuntimeContext(
        today=datetime.now(VN_TZ).date(),
        user_name=user.full_name,
    )


@router.post(
    "/threads/{thread_id}/turns",
    response_model=CreatedTurnResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_turn(
    thread_id: uuid.UUID,
    payload: CreateTurnRequest,
    current_user: CurrentUser,
    desk: Desk,
    response: Response,
) -> CreatedTurnResponse:
    """Admit, commit, then start. Never any other order.

    Admission comes first because a refusal must not leave a row behind. The
    Thread is read next, both to prove ownership and to take the history *before*
    this Turn's own user message joins it. Only then does the lifecycle commit
    the message and the ``agent_turn`` row and start execution — a crash between
    the commit and the task start is recoverable as an incomplete Turn rather
    than as an invisible or duplicated request.
    """
    desk.assert_enabled()
    view: ThreadView | None = await desk.store.read_thread(current_user.id, thread_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Asked once the Thread is known to exist and to be this user's, so a
    # stranger's id cannot be used to probe how busy the service is.
    await desk.admission.admit(user_id=current_user.id)

    try:
        handle = await desk.turns.create(
            user_id=current_user.id,
            thread_id=thread_id,
            turn_id=payload.turn_id,
            user_text=payload.text,
            runtime=_runtime(current_user),
            symbols=payload.symbols,
            history=history_of(view.messages),
            retry_of_turn_id=payload.retry_of_turn_id,
        )
    except TurnPayloadConflict as conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "turn_id_reused",
                "message": (
                    "That Turn id already exists with different content. A Turn id "
                    "is an idempotency key and cannot be reused for a new question."
                ),
            },
        ) from conflict
    except LookupError as missing:
        # The Thread was read a moment ago, so this is a deletion that raced the
        # create. Still a 404: the Thread genuinely is not there.
        raise HTTPException(status_code=404, detail="Thread not found") from missing

    if not handle.created:
        # The same id and payload resolves to the Turn that already exists, and
        # started nothing. 200 rather than 201, because nothing was created.
        response.status_code = status.HTTP_200_OK
    return CreatedTurnResponse(**_turn(handle.turn), created=handle.created)


# -- the stream ------------------------------------------------------------


@router.get("/turns/{turn_id}/events")
async def turn_events(
    turn_id: uuid.UUID,
    user_id: StreamingUser,
    desk: Desk,
    request: Request,
) -> StreamingResponse:
    """Attach to a Turn. Start nothing, and stop nothing by leaving.

    ``Last-Event-ID`` needs no filtering here, and that is a property of the
    replay contract rather than an omission: a snapshot *restates* everything up
    to ``through_seq`` instead of replaying it, so a reconnecting client replaces
    its projection wholesale and then receives only ``seq > through_seq``. There
    is no window in which an event is in neither half — registration and
    snapshot capture are atomic with respect to the publisher.
    """
    desk.subscriptions.check_user(user_id)
    subscriber = await desk.turns.subscribe(user_id, turn_id)
    if subscriber is None:
        raise HTTPException(status_code=404, detail="Turn not found")
    try:
        # Counted here rather than above, because a window keyed by Turn may
        # only be spent by the Turn's owner. The subscriber is already
        # registered with the publisher by this point, so a refusal closes it
        # instead of leaving a queue nobody drains.
        desk.subscriptions.check_turn(turn_id)
    except Exception:
        subscriber.close()
        raise

    last_event_id = request.headers.get("Last-Event-ID")
    if last_event_id:
        logger.info(
            "Turn %s reattached from event %s; serving a snapshot through %d",
            turn_id,
            last_event_id,
            subscriber.through_seq,
        )
    return StreamingResponse(
        frames(subscriber),
        media_type="text/event-stream",
        headers=STREAM_HEADERS,
    )


@router.get("/turns/{turn_id}", response_model=TurnResponse)
async def read_turn(
    turn_id: uuid.UUID,
    current_user: CurrentUser,
    desk: Desk,
) -> TurnResponse:
    """One Turn's current state, for a client that has not opened a stream."""
    record = await desk.store.read_turn(current_user.id, turn_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Turn not found")
    return TurnResponse(**_turn(record))


# -- cancel ----------------------------------------------------------------


# -- one canvas ------------------------------------------------------------


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def read_artifact(
    artifact_id: uuid.UUID,
    current_user: CurrentUser,
    desk: Desk,
) -> ArtifactResponse:
    """The numbers behind one canvas, for the reader whose answer produced it.

    The one route ``frames`` travels. It is a separate request from the
    transcript on purpose: a heatmap is thousands of cells and a conversation
    scrolls, so the text loads at text weight and the picture is fetched by
    whoever opens the panel.

    **Immutable, so the client may cache it forever.** The row is written once
    and never updated; re-opening a Thread renders what was frozen rather than
    recomputing against a store that has moved on.

    An artifact under another user's Thread is *not found* rather than
    forbidden, exactly as a Turn is: a caller who could tell the two apart has
    been told an id exists.
    """
    record = await desk.store.read_artifact(current_user.id, artifact_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return ArtifactResponse(
        id=record.id,
        study_name=record.study_name,
        study_version=record.study_version,
        params=dict(record.params),
        canvas_spec=dict(record.canvas_spec),
        frames=dict(record.frames),
        provenance=dict(record.provenance),
        created_at=record.created_at,
    )


@router.post("/turns/{turn_id}/cancel", response_model=TurnResponse)
async def cancel_turn(
    turn_id: uuid.UUID,
    current_user: CurrentUser,
    desk: Desk,
) -> TurnResponse:
    """Idempotent, and it dispatches nothing.

    A second cancel returns the same answer, stamps nothing a second time and
    cannot change a terminal reason that is already written. A read-only call
    already in flight is allowed to finish as ``docs/adr/0008`` requires; its
    trace is kept and its result is simply not fed into another round.

    **Retry is not this endpoint.** A retry is a new Turn carrying
    ``retry_of_turn_id``, and a network reconnection is neither.
    """
    record = await desk.turns.cancel(current_user.id, turn_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Turn not found")
    return TurnResponse(**_turn(record))


__all__ = ["router", "desk", "history_of", "streaming_user_id"]
