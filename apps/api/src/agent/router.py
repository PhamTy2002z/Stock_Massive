"""The three endpoints that put a Turn on the wire, and the Threads behind them.

The surface is fixed:

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
whose scope ends only when the response does.  The async pool is 15 connections;
one held per Turn would cap concurrency at 15 and make the sixteenth wait thirty
seconds to fail.

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

import base64
import logging
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import StreamingResponse
# Starlette's, not FastAPI's subclass: ``request.form()`` yields the former, and
# an ``isinstance`` against the latter would never match.
from starlette.datastructures import UploadFile

from src.agent.messages import TranscriptTurn, TurnAttachment
from src.agent.persistence import (
    MessageRecord,
    QuestionAlreadyResolved,
    QuestionOptionInvalid,
    QuestionRecord,
    SummaryRecord,
    ThreadRecord,
    ThreadView,
    TurnPayloadConflict,
    TurnRecord,
    latest_summary,
)
from src.agent.domain.trading_calendar import market_day
from src.agent.prompt import RuntimeContext
from src.agent.schemas import (
    AllowanceResponse,
    AnswerQuestionRequest,
    AttachmentResponse,
    CreatedTurnResponse,
    CreateThreadRequest,
    CapabilitiesResponse,
    CreateTurnRequest,
    MessageResponse,
    QuestionResponse,
    ThreadDetailResponse,
    ThreadListResponse,
    ThreadResponse,
    TurnResponse,
    UpdateThreadRequest,
    UsageResponse,
)
from src.agent.service import AlphaDeskService, alpha_desk
from src.agent.usage import Allowance, read_usage
from src.agent.sse import frames
from src.agent.attachments import (
    IMAGE_TYPES,
    MAX_ATTACHMENT_BYTES,
    AttachmentRefused,
    AttachmentStore,
    StoredAttachment,
    assert_within_turn_budget,
    serving_headers,
)
from src.auth.dependencies import CurrentUser
from src.core.ratelimit import heavy_rate_limit
from src.auth.models import User
from src.auth.security import TokenError, decode_access_token
from src.auth.service import get_user_by_id
from src.core.database import async_session_factory

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

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


def attachment_store() -> AttachmentStore:
    """The store, as a dependency so a test can point it at its own session.

    Beside ``Desk`` rather than beside the upload endpoint, because the Turn
    endpoint above it needs the same store: an alias declared after its first
    use resolves to the bare class and FastAPI reads that as a response field.
    """
    return AttachmentStore()


Attachments = Annotated[AttachmentStore, Depends(attachment_store)]


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


def _applicable_summary(
    summary: SummaryRecord | None, history: Sequence[TranscriptTurn]
) -> SummaryRecord | None:
    """The summary this Turn may apply, or ``None`` when it may apply none.

    A summary is applied by dropping the leading Turns it covers, so one whose
    span reaches the whole of a Thread would leave the constructor with nothing
    to build from. The compactor never writes such a row — it will not touch the
    protected tail — and this is the reading end refusing to act on one anyway:
    the two counts come from the same rows but are computed by different code,
    and the cost of them disagreeing is a Thread that renders as its own summary.
    """
    if summary is None or summary.summarised_turns >= len(history):
        return None
    return summary


def history_of(messages: Sequence[MessageRecord]) -> tuple[TranscriptTurn, ...]:
    """The Thread so far, as the context constructor reads it.

    A user message opens a Turn and the assistant message that follows closes
    it, so the pairing is by order rather than by a foreign key — which is also
    what makes an interrupted Turn with no answer render as a Turn that asked
    and got nothing, instead of silently swallowing the question.

    Tool calls are deliberately absent: ``build_messages`` trims older Turns to
    their prose, and re-reading every trace of every earlier Turn to throw it
    away is a query per Turn for nothing.

    Their **names** do come back, in ``tool_names``, and neither half of that
    sentence contradicts the one above it. No extra query: the names are already
    on the assistant row this loop is reading, written there by
    ``turns.assistant_message``. And nothing is sent to the model that was not
    sent before — ``build_messages`` reads ``tool_calls`` and never
    ``tool_names``. What the names buy is one question a later Turn asks of an
    earlier one and could not answer: has this thread already reached for the
    domain, so that a follow-up which calls nothing still gets the domain's half
    of the prompt.

    **Attachments come back as metadata and never as bytes**, and that single
    line is two ceilings at once. Dropping them entirely would lose an earlier
    Turn's file from the model's view while the surface still draws a chip for
    it — the interface asserting something the model does not have. Loading them
    whole would send every image again on every later question, so a Thread
    where ten questions each carried a picture would put ten pictures in the
    tenth request. What survives is the placeholder: the model knows a file was
    there and knows it can no longer see it, which is a thing it can say instead
    of a thing it has to guess.
    """
    turns: list[TranscriptTurn] = []
    for record in messages:
        text = str(record.content.get("text") or "")
        if record.role == "user":
            turns.append(
                TranscriptTurn(
                    user_text=text,
                    attachments=tuple(
                        TurnAttachment.from_payload(entry)
                        for entry in record.content.get("attachments") or ()
                    ),
                )
            )
        elif record.role == "assistant" and turns:
            last = turns[-1]
            if last.assistant_text is None:
                turns[-1] = TranscriptTurn(
                    user_text=last.user_text,
                    tool_calls=last.tool_calls,
                    assistant_text=text,
                    attachments=last.attachments,
                    # Skipping anything without a name rather than trusting the
                    # shape: these rows were written by every version of this
                    # message builder there has ever been, and a Turn from
                    # before the field existed must read as a Turn that called
                    # nothing, not raise.
                    tool_names=tuple(
                        str(call["name"])
                        for call in record.content.get("tool_calls") or ()
                        if isinstance(call, Mapping) and call.get("name")
                    ),
                    # The key is written only by a Turn that asked, so its
                    # presence is the whole test — a message from before cards
                    # existed reads as a Turn that did not ask, not as one whose
                    # asking was lost.
                    asked=bool(record.content.get("question")),
                )
    return tuple(turns)


# -- authentication for the long response ----------------------------------


async def streaming_user_id(request: Request) -> int:
    """Resolve the caller, and close the session before anything streams.

    Deliberately not ``Depends(get_current_user)``. A dependency that opens a
    database session keeps it until the *response* ends, and this response ends
    when the Turn does — up to ten minutes later. No session is held across a
    streaming Turn.
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
        # A summary row is the harness talking to itself about a Thread the
        # reader can still scroll: none of the Turns behind it were deleted, so
        # drawing it would show the conversation twice, once compressed. It stays
        # where the context constructor reads it and out of what a screen draws.
        messages=[
            _message(message)
            for message in view.messages
            if message.role != "summary"
        ],
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

    Cascades to its messages, its traces and its Turns. It is not reversible and there is no archive: the menu asks the
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
    """The three trusted values, and nothing else, for one Turn.

    The date is read in Vietnam rather than in UTC: a Turn opened at 00:30 local
    time is asked on a day that is still yesterday in UTC, and "today" is the
    reader's day or it is no use to them.

    The trading status is derived from that same local date, and here rather
    than inside the prompt module, which renders text and owns no calendar. It
    is the one place the two can be read together, so it is the one place they
    cannot disagree about which day is being described.

    The name is the only user-supplied string that reaches the system prompt, so
    it is the whole attack surface of this function. ``RuntimeContext`` sanitises
    it; passing it through untouched here is deliberate, because a second
    cleaning rule beside that one is how the two come to disagree.
    """
    today = datetime.now(VN_TZ).date()
    return RuntimeContext(
        today=today,
        user_name=user.full_name,
        market=market_day(today),
    )


async def _resolve_attachments(
    store: AttachmentStore, user_id: int, ids: Sequence[uuid.UUID]
) -> tuple[TurnAttachment, ...]:
    """Read what the reader attached, in the order they attached it.

    404 for an id that is not there and 404 for an id that belongs to somebody
    else — the same answer, deliberately. Two answers would make this endpoint a
    way to learn which ids exist.

    Bytes are loaded here, at the one point where they are about to become a
    content part. The ceiling that makes that affordable is the count already
    applied by the schema.
    """
    resolved: list[TurnAttachment] = []
    metas: list[StoredAttachment] = []
    for attachment_id in ids:
        stored = await store.read(user_id, attachment_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="Attachment not found")
        meta = stored.meta
        metas.append(meta)
        is_image = meta.media_type in IMAGE_TYPES
        resolved.append(
            TurnAttachment(
                id=meta.id,
                filename=meta.filename,
                media_type=meta.media_type,
                byte_size=meta.byte_size,
                estimated_tokens=meta.estimated_tokens,
                data=(
                    base64.b64encode(stored.content).decode("ascii")
                    if is_image
                    else None
                ),
                # Decoded here rather than in the message layer: what the bytes
                # are is a fact about the row, and a mojibake file should read as
                # a mojibake file rather than raise inside context construction.
                text=(
                    None if is_image else stored.content.decode("utf-8", errors="replace")
                ),
            )
        )
    # The sum, not the count. The schema already capped the count, and the count
    # was derived from an average image — three full-desktop captures sit inside
    # it and past the budget.
    assert_within_turn_budget(metas)
    return tuple(resolved)


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
    store: Attachments,
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

    # Read and checked before the lifecycle is entered: a refusal here must not
    # leave a Turn behind, and the reader is told which file to drop while they
    # can still drop it.
    try:
        attachments = await _resolve_attachments(
            store, current_user.id, payload.attachments
        )
    except AttachmentRefused as refused:
        raise HTTPException(
            status_code=refused.status_code,
            detail={"reason": refused.reason, "message": str(refused)},
        ) from refused

    history = history_of(view.messages)
    summary = _applicable_summary(latest_summary(view.messages), history)

    try:
        handle = await desk.turns.create(
            user_id=current_user.id,
            thread_id=thread_id,
            turn_id=payload.turn_id,
            user_text=payload.text,
            runtime=_runtime(current_user),
            symbols=payload.symbols,
            history=history,
            summary=None if summary is None else summary.text,
            summarised_turns=0 if summary is None else summary.summarised_turns,
            retry_of_turn_id=payload.retry_of_turn_id,
            attachments=attachments,
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


# -- the account's own allowance ------------------------------------------------


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def read_capabilities(desk: Desk) -> CapabilitiesResponse:
    """What the configured route can do.

    Read off the same ``LLMRoute`` the loop reads, so the answer the surface
    draws and the behaviour the context constructor takes cannot disagree — the
    alternative is a composer that promises pixels to a route the probe never
    measured.

    Behind the session like every other route here, but the answer is a
    deployment fact and not an account one: it is identical for every caller and
    constant until a deploy.
    """
    return CapabilitiesResponse(vision=desk.config.route.vision)


@router.get("/usage", response_model=UsageResponse)
async def read_usage_endpoint(current_user: CurrentUser) -> UsageResponse:
    """What this account has consumed against its ceilings.

    Read-only, and scoped to the caller: the user id comes from the resolved
    session and is never accepted as a parameter, so there is no shape of this
    request that reads another account's ledger.

    It exists because the refusals it explains are otherwise invisible until
    they happen. ``user_turn_starts_daily`` and ``user_spend_daily`` are decided
    from the same windows and the same charge expression this reads (see
    ``agent/usage.py``), so the number here is the number that will refuse the
    next Turn — not an estimate of it.
    """
    snapshot = await read_usage(current_user.id)
    return UsageResponse(
        as_of=snapshot.as_of,
        turns_today=_allowance(snapshot.turns_today),
        spend_today_micro_usd=_allowance(snapshot.spend_today_micro_usd),
        spend_rolling_30d_micro_usd=_allowance(snapshot.spend_rolling_30d_micro_usd),
    )


def _allowance(value: Allowance) -> AllowanceResponse:
    return AllowanceResponse(
        used=value.used,
        limit=value.limit,
        resets_at=value.resets_at,
    )


# -- cancel ----------------------------------------------------------------


# -- attachments -----------------------------------------------------------


@router.post(
    "/attachments",
    response_model=AttachmentResponse,
    status_code=201,
    dependencies=[Depends(heavy_rate_limit)],
)
async def upload_attachment(
    request: Request,
    current_user: CurrentUser,
    store: Attachments,
) -> AttachmentResponse:
    """Take one file in, and answer with an id.

    **This endpoint needs its own ceilings.** Every other ``POST`` here is
    bounded by LLM admission, and this one calls no model, so it goes through no
    such gate. What bounds it: the ``Content-Length`` check below, the per-file
    and per-user ceilings in ``agent/attachments.py``, and the heavy limiter.

    The limiter is keyed by IP, and behind the Next proxy every reader shares
    one — the same fact that keeps ``subscribe`` off it. It is here anyway, as a
    blunt stop on a runaway loop from one origin; the ceiling that actually
    binds *per reader* is the row-and-byte quota, which is keyed by user.

    **Why the file is not a declared body parameter.** FastAPI parses the body
    before it solves any dependency, so with ``file: UploadFile = File(...)``
    the multipart form is already spooled and validated by the time this
    function — or any ``Depends`` guarding it — could say no, and a request past
    the ceiling comes back 422 having been received in full. Reading the form
    here, after the header check, is what makes the ceiling arrive first. The
    cost is that the multipart shape is documented in this docstring rather than
    in the schema.

    ``Content-Length`` is a claim, so it is used only to refuse early and is
    never believed afterwards: the real length is measured on the bytes.
    """
    declared_length = request.headers.get("content-length")
    if declared_length and declared_length.isdigit():
        # Multipart framing costs a little over the file itself, hence the slack.
        if int(declared_length) > MAX_ATTACHMENT_BYTES + 8 * 1024:
            raise HTTPException(
                status_code=413,
                detail={
                    "reason": "file_too_large",
                    "message": f"past the {MAX_ATTACHMENT_BYTES} byte ceiling",
                },
            )

    form = await request.form()
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        raise HTTPException(
            status_code=422,
            detail={"reason": "missing_file", "message": "expected a `file` part"},
        )

    data = await upload.read()
    try:
        stored = await store.store(
            current_user.id,
            declared_type=(upload.content_type or "").split(";")[0].strip(),
            filename=upload.filename or "",
            data=data,
        )
    except AttachmentRefused as refusal:
        raise HTTPException(
            status_code=refusal.status_code,
            detail={"reason": refusal.reason, "message": str(refusal)},
        ) from refusal

    return AttachmentResponse(
        id=stored.id,
        media_type=stored.media_type,
        filename=stored.filename,
        byte_size=stored.byte_size,
        estimated_tokens=stored.estimated_tokens,
    )


@router.get("/attachments/{attachment_id}")
async def read_attachment_bytes(
    attachment_id: uuid.UUID,
    current_user: CurrentUser,
    store: Attachments,
) -> Response:
    """The bytes, for the reader who uploaded them.

    Somebody else's attachment is *not found* rather than forbidden: a caller
    who could tell the two apart has been told that an id exists.

    The two text types have no magic bytes, so anything at all can arrive under
    one of them. They are handed back as an opaque download with sniffing
    refused — see ``attachments.serving_headers`` for why that is the defence
    rather than a stricter whitelist.
    """
    found = await store.read(current_user.id, attachment_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    media_type, headers = serving_headers(found.meta.media_type, found.meta.filename)
    # Written once and never updated, so a client may hold it as long as it likes.
    headers["Cache-Control"] = "private, max-age=31536000, immutable"
    return Response(content=found.content, media_type=media_type, headers=headers)


# -- resolving a question --------------------------------------------------


_QUESTION_NOT_FOUND = HTTPException(status_code=404, detail="Question not found")


def _question(record: QuestionRecord) -> QuestionResponse:
    return QuestionResponse(
        id=record.id,
        state=record.state,
        selected_option_ids=(
            None
            if record.selected_option_ids is None
            else list(record.selected_option_ids)
        ),
        resolved_at=record.resolved_at,
    )


def _resolved(record: QuestionRecord | None) -> QuestionResponse:
    """One answer for a question that is not there and one that is not yours.

    404 for both, deliberately: a caller who could tell them apart has been told
    that an id exists. The same rule every other row in this surface follows.
    """
    if record is None:
        raise _QUESTION_NOT_FOUND
    return _question(record)


@router.post("/questions/{question_id}/answer", response_model=QuestionResponse)
async def answer_question(
    question_id: uuid.UUID,
    payload: AnswerQuestionRequest,
    current_user: CurrentUser,
    desk: Desk,
) -> QuestionResponse:
    """Record the reader's choice. Idempotent, and it starts nothing.

    A question ended its Turn, so answering one does not resume anything: the
    reply is a new Turn the reader sends, and this endpoint's whole job is to
    write down what they chose so that Turn — and a reopened Thread — can see it.

    Three refusals, and each says something different. 404 is a question that is
    not this reader's; 422 is an option the card never offered, or several on a
    single-select question; 409 is a question already resolved *differently*,
    because the work has continued from the first answer and the way to change
    course is another Turn. Re-sending the same choice is none of those and
    answers 200 with the row unchanged.
    """
    try:
        record = await desk.store.answer_question(
            current_user.id, question_id, payload.selected_option_ids
        )
    except QuestionOptionInvalid as invalid:
        raise HTTPException(
            status_code=422,
            detail={"reason": "option_not_offered", "message": str(invalid)},
        ) from invalid
    except QuestionAlreadyResolved as resolved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "question_already_resolved",
                "message": (
                    "That question is already settled. Ask again in a new message "
                    "to change course."
                ),
            },
        ) from resolved
    return _resolved(record)


@router.post("/questions/{question_id}/skip", response_model=QuestionResponse)
async def skip_question(
    question_id: uuid.UUID,
    current_user: CurrentUser,
    desk: Desk,
) -> QuestionResponse:
    """Record that the reader declined to choose. No body, and no dead end.

    Skipping is a decision with an outcome, not a cancellation: the work runs on
    default assumptions and prints them. Idempotent on the same terms as an
    answer, and 409 if the question was already resolved another way.
    """
    try:
        record = await desk.store.skip_question(current_user.id, question_id)
    except QuestionAlreadyResolved as resolved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "question_already_resolved",
                "message": (
                    "That question is already settled. Ask again in a new message "
                    "to change course."
                ),
            },
        ) from resolved
    return _resolved(record)


@router.post("/turns/{turn_id}/cancel", response_model=TurnResponse)
async def cancel_turn(
    turn_id: uuid.UUID,
    current_user: CurrentUser,
    desk: Desk,
) -> TurnResponse:
    """Idempotent, and it dispatches nothing.

    A second cancel returns the same answer, stamps nothing a second time and
    cannot change a terminal reason that is already written. A read-only call
    already in flight is allowed to finish; its
    trace is kept and its result is simply not fed into another round.

    **Retry is not this endpoint.** A retry is a new Turn carrying
    ``retry_of_turn_id``, and a network reconnection is neither.
    """
    record = await desk.turns.cancel(current_user.id, turn_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Turn not found")
    return TurnResponse(**_turn(record))


__all__ = ["router", "desk", "history_of", "streaming_user_id"]
