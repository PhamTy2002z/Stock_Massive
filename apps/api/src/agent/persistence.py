"""Short-lived persistence operations for Threads and Tool Call Traces.

Every public method is async for the agent path, but the work runs in a thread
over the repository's synchronous SQLAlchemy factory.  A method owns exactly
one short transaction; a Turn never owns a database session.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, TypeVar

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.alpha.models import (
    ACTIVE_TURN_STATUSES,
    TURN_ADMITTED,
    TURN_COMPLETE,
    TURN_INCOMPLETE,
    TURN_RUNNING,
    AgentMessage,
    AgentThread,
    AgentToolCall,
    AgentTurn,
)
from src.core.database import sync_session_factory
from src.stocks.shared import validate_symbol

T = TypeVar("T")
SessionFactory = Callable[[], Session]
MessageBuilder = Callable[["TurnRecord"], Mapping[str, Any] | None]
MAX_SEQUENCE_RETRIES = 20
TOOL_CALL_RETENTION_DAYS = 90

# The stable reason a Turn frozen by the startup sweep carries. V1 never resumes
# execution after a restart, so this is a terminal reason and not a state a
# later pass reconsiders.
INTERRUPTED_REASON = "interrupted_restart"


@dataclass(frozen=True)
class MessageRecord:
    id: int
    thread_id: uuid.UUID
    seq: int
    role: str
    content: Mapping[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class ThreadRecord:
    id: uuid.UUID
    user_id: int
    title: str | None
    symbols: tuple[str, ...]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ThreadView(ThreadRecord):
    messages: tuple[MessageRecord, ...]


@dataclass(frozen=True)
class ToolCallRecord:
    id: int
    thread_id: uuid.UUID
    request_message_id: int
    tool_name: str
    arguments: Mapping[str, Any]
    result: Mapping[str, Any] | None
    status: str
    error: str | None
    latency_ms: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    started_at: datetime


@dataclass(frozen=True)
class TurnRecord:
    """One row of the lifecycle table, as the service layer reads it."""

    id: uuid.UUID
    thread_id: uuid.UUID
    request_message_id: int
    response_message_id: int | None
    retry_of_turn_id: uuid.UUID | None
    status: str
    terminal_reason: str | None
    cancel_requested_at: datetime | None
    started_at: datetime
    finished_at: datetime | None
    last_event_seq: int
    draft_content: Mapping[str, Any] | None

    @property
    def is_terminal(self) -> bool:
        return self.status not in ACTIVE_TURN_STATUSES


@dataclass(frozen=True)
class TurnCreation:
    """The Turn the create transaction settled on, and whether it is new.

    ``created`` is what tells a caller whether to start execution. A resubmitted
    id returns the Turn that already exists and starts nothing — which is the
    whole point of an idempotency key on a flaky network.
    """

    turn: TurnRecord
    created: bool


class TurnPayloadConflict(ValueError):
    """The same Turn id was submitted with a different payload.

    Separate from "not found" on purpose: a client that reuses an id for new
    text has a bug, and answering it with the earlier Turn's content would be a
    silently wrong answer rather than a loud one. A6 maps this to ``409``.
    """

    def __init__(self, turn_id: uuid.UUID) -> None:
        super().__init__(
            f"Turn {turn_id} already exists with a different payload; a Turn id is "
            "an idempotency key and cannot be reused for new input"
        )
        self.turn_id = turn_id


def _uuid(value: uuid.UUID | str) -> uuid.UUID:
    """Coerce a Thread or Turn identifier, both of which arrive as either."""
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _turn_record(row: AgentTurn) -> TurnRecord:
    return TurnRecord(
        id=row.id,
        thread_id=row.thread_id,
        request_message_id=row.request_message_id,
        response_message_id=row.response_message_id,
        retry_of_turn_id=row.retry_of_turn_id,
        status=row.status,
        terminal_reason=row.terminal_reason,
        cancel_requested_at=row.cancel_requested_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        last_event_seq=int(row.last_event_seq or 0),
        draft_content=(
            dict(row.draft_content) if row.draft_content is not None else None
        ),
    )


def _thread_record(row: AgentThread) -> ThreadRecord:
    return ThreadRecord(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        symbols=tuple(row.symbols or ()),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _message_record(row: AgentMessage) -> MessageRecord:
    return MessageRecord(
        id=row.id,
        thread_id=row.thread_id,
        seq=row.seq,
        role=row.role,
        content=dict(row.content),
        created_at=row.created_at,
    )


def _trace_record(row: AgentToolCall) -> ToolCallRecord:
    return ToolCallRecord(
        id=row.id,
        thread_id=row.thread_id,
        request_message_id=row.request_message_id,
        tool_name=row.tool_name,
        arguments=dict(row.arguments),
        result=dict(row.result) if row.result is not None else None,
        status=row.status,
        error=row.error,
        latency_ms=row.latency_ms,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        started_at=row.started_at,
    )


def _insert_message(
    session: Session,
    thread_id: uuid.UUID,
    role: str,
    content: Mapping[str, Any],
    symbols: Sequence[str],
) -> AgentMessage:
    """Append one transcript row inside the caller's transaction.

    Takes a session rather than opening one, because the terminal transaction of
    a Turn has to write the assistant message and the Turn's terminal fields
    together or not at all.
    """
    thread = session.execute(
        select(AgentThread).where(AgentThread.id == thread_id)
    ).scalar_one_or_none()
    if thread is None:
        raise LookupError(f"Thread {thread_id} does not exist")
    current = session.execute(
        select(func.max(AgentMessage.seq)).where(AgentMessage.thread_id == thread_id)
    ).scalar_one()
    message = AgentMessage(
        thread_id=thread_id,
        seq=(current or 0) + 1,
        role=role,
        content=dict(content),
    )
    held = list(thread.symbols or ())
    for symbol in symbols:
        if symbol not in held:
            held.append(symbol)
    thread.symbols = held
    thread.updated_at = datetime.now(timezone.utc)
    session.add(message)
    session.flush()
    return message


class AgentPersistence:
    """The complete read/write surface for ticket #74."""

    def __init__(self, session_factory: SessionFactory = sync_session_factory) -> None:
        self._session_factory = session_factory

    async def create_thread(self, user_id: int, title: str | None = None) -> ThreadRecord:
        return await asyncio.to_thread(self._create_thread, user_id, title)

    def _create_thread(self, user_id: int, title: str | None) -> ThreadRecord:
        with self._session_factory() as session:
            row = AgentThread(
                id=uuid.uuid4(),
                user_id=user_id,
                title=title,
                symbols=[],
            )
            session.add(row)
            session.commit()
            return _thread_record(row)

    async def list_threads(self, user_id: int) -> tuple[ThreadRecord, ...]:
        return await asyncio.to_thread(self._list_threads, user_id)

    def _list_threads(self, user_id: int) -> tuple[ThreadRecord, ...]:
        with self._session_factory() as session:
            rows = session.execute(
                select(AgentThread)
                .where(AgentThread.user_id == user_id)
                .order_by(
                    AgentThread.updated_at.desc(),
                    AgentThread.created_at.desc(),
                    AgentThread.id.desc(),
                )
            ).scalars()
            return tuple(_thread_record(row) for row in rows)

    async def read_thread(
        self, user_id: int, thread_id: uuid.UUID | str
    ) -> ThreadView | None:
        return await asyncio.to_thread(self._read_thread, user_id, _uuid(thread_id))

    def _read_thread(self, user_id: int, thread_id: uuid.UUID) -> ThreadView | None:
        with self._session_factory() as session:
            row = session.execute(
                select(AgentThread).where(
                    AgentThread.id == thread_id,
                    AgentThread.user_id == user_id,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            messages = session.execute(
                select(AgentMessage)
                .where(AgentMessage.thread_id == thread_id)
                .order_by(AgentMessage.seq.asc())
            ).scalars()
            base = _thread_record(row)
            return ThreadView(
                **base.__dict__,
                messages=tuple(_message_record(message) for message in messages),
            )

    async def delete_thread(self, user_id: int, thread_id: uuid.UUID | str) -> bool:
        return await asyncio.to_thread(
            self._delete_thread, user_id, _uuid(thread_id)
        )

    def _delete_thread(self, user_id: int, thread_id: uuid.UUID) -> bool:
        with self._session_factory() as session:
            result = session.execute(
                delete(AgentThread).where(
                    AgentThread.id == thread_id,
                    AgentThread.user_id == user_id,
                )
            )
            session.commit()
            return bool(result.rowcount)

    async def append_message(
        self,
        thread_id: uuid.UUID | str,
        *,
        role: str,
        content: Mapping[str, Any],
        symbols: Sequence[str] = (),
    ) -> MessageRecord:
        if role not in {"user", "assistant", "summary"}:
            raise ValueError(f"unsupported transcript role: {role}")
        normalized = tuple(dict.fromkeys(validate_symbol(symbol) for symbol in symbols))
        return await asyncio.to_thread(
            self._append_message,
            _uuid(thread_id),
            role,
            dict(content),
            normalized,
        )

    def _append_message(
        self,
        thread_id: uuid.UUID,
        role: str,
        content: Mapping[str, Any],
        symbols: Sequence[str],
    ) -> MessageRecord:
        def write(session: Session) -> MessageRecord:
            message = _insert_message(session, thread_id, role, content, symbols)
            session.commit()
            return _message_record(message)

        return self._with_sequence_retry(write)

    def _with_sequence_retry(self, work: Callable[[Session], T]) -> T:
        """Run one transaction, retrying the ``UNIQUE(thread_id, seq)`` race.

        The retry lives here rather than in each caller because ``seq`` is
        allocated inside the writing transaction by design (``docs/specs/0003``
        §10.2), so every writer of a transcript row races the same way and none
        of them should have to remember it.
        """
        for attempt in range(MAX_SEQUENCE_RETRIES):
            with self._session_factory() as session:
                try:
                    return work(session)
                except IntegrityError:
                    session.rollback()
                    if attempt + 1 == MAX_SEQUENCE_RETRIES:
                        raise
        raise RuntimeError("sequence allocation retries were exhausted")

    async def threads_discussing(
        self, user_id: int, symbol: str
    ) -> tuple[ThreadRecord, ...]:
        normalized = validate_symbol(symbol)
        return await asyncio.to_thread(self._threads_discussing, user_id, normalized)

    def _threads_discussing(
        self, user_id: int, symbol: str
    ) -> tuple[ThreadRecord, ...]:
        with self._session_factory() as session:
            rows = session.execute(
                select(AgentThread)
                .where(
                    AgentThread.user_id == user_id,
                    AgentThread.symbols.contains([symbol]),
                )
                .order_by(AgentThread.updated_at.desc())
            ).scalars()
            return tuple(_thread_record(row) for row in rows)

    async def record_tool_call(self, trace: Mapping[str, Any]) -> ToolCallRecord:
        return await asyncio.to_thread(self._record_tool_call, dict(trace))

    def _record_tool_call(self, trace: Mapping[str, Any]) -> ToolCallRecord:
        thread_id = _uuid(trace["thread_id"])
        request_message_id = int(trace["request_message_id"])
        with self._session_factory() as session:
            anchor = session.execute(
                select(AgentMessage).where(AgentMessage.id == request_message_id)
            ).scalar_one_or_none()
            if (
                anchor is None
                or anchor.thread_id != thread_id
                or anchor.role != "user"
            ):
                raise ValueError(
                    "a Tool Call Trace must anchor to a user message in its Thread"
                )
            row = AgentToolCall(
                thread_id=thread_id,
                request_message_id=request_message_id,
                tool_name=str(trace["tool_name"]),
                arguments=dict(trace.get("arguments") or {}),
                result=(
                    dict(trace["result"])
                    if trace.get("result") is not None
                    else None
                ),
                status=str(trace["status"]),
                error=str(trace["error"])[:500] if trace.get("error") else None,
                latency_ms=trace.get("latency_ms"),
                prompt_tokens=trace.get("prompt_tokens"),
                completion_tokens=trace.get("completion_tokens"),
                started_at=trace.get("started_at", datetime.now(timezone.utc)),
            )
            session.add(row)
            session.commit()
            return _trace_record(row)

    async def traces_for_request(
        self, request_message_id: int
    ) -> tuple[ToolCallRecord, ...]:
        return await asyncio.to_thread(self._traces_for_request, request_message_id)

    def _traces_for_request(
        self, request_message_id: int
    ) -> tuple[ToolCallRecord, ...]:
        with self._session_factory() as session:
            rows = session.execute(
                select(AgentToolCall)
                .where(AgentToolCall.request_message_id == request_message_id)
                .order_by(AgentToolCall.started_at.asc(), AgentToolCall.id.asc())
            ).scalars()
            return tuple(_trace_record(row) for row in rows)

    async def tool_tokens_for_request(self, request_message_id: int) -> int:
        return await asyncio.to_thread(self._tool_tokens_for_request, request_message_id)

    def _tool_tokens_for_request(self, request_message_id: int) -> int:
        with self._session_factory() as session:
            total = session.execute(
                select(
                    func.coalesce(
                        func.sum(
                            func.coalesce(AgentToolCall.prompt_tokens, 0)
                            + func.coalesce(AgentToolCall.completion_tokens, 0)
                        ),
                        0,
                    )
                ).where(AgentToolCall.request_message_id == request_message_id)
            ).scalar_one()
            return int(total)

    # -- the Turn lifecycle (#81) -----------------------------------------

    async def create_turn(
        self,
        *,
        user_id: int,
        thread_id: uuid.UUID | str,
        turn_id: uuid.UUID | str,
        user_text: str,
        symbols: Sequence[str] = (),
        retry_of_turn_id: uuid.UUID | str | None = None,
    ) -> TurnCreation:
        """Commit the user message and the Turn, before anything is executed."""
        normalized = tuple(dict.fromkeys(validate_symbol(symbol) for symbol in symbols))
        return await asyncio.to_thread(
            self._create_turn,
            user_id,
            _uuid(thread_id),
            _uuid(turn_id),
            user_text,
            normalized,
            None if retry_of_turn_id is None else _uuid(retry_of_turn_id),
        )

    def _create_turn(
        self,
        user_id: int,
        thread_id: uuid.UUID,
        turn_id: uuid.UUID,
        user_text: str,
        symbols: Sequence[str],
        retry_of_turn_id: uuid.UUID | None,
    ) -> TurnCreation:
        # The whole payload, compared as one value rather than field by field.
        # An idempotency key that only checks the text would return the earlier
        # Turn for a request that differed in the symbols it declared — the same
        # id answering a different question, which is what the key exists to
        # make impossible.
        payload: dict[str, Any] = {"text": user_text}
        if symbols:
            payload["symbols"] = list(symbols)

        def write(session: Session) -> TurnCreation:
            existing = self._owned_turn(session, user_id, turn_id)
            if existing is not None:
                request = session.get(AgentMessage, existing.request_message_id)
                stored = dict(request.content or {}) if request is not None else None
                if stored != payload or existing.thread_id != thread_id:
                    raise TurnPayloadConflict(turn_id)
                if existing.retry_of_turn_id != retry_of_turn_id:
                    raise TurnPayloadConflict(turn_id)
                return TurnCreation(turn=_turn_record(existing), created=False)

            thread = session.execute(
                select(AgentThread).where(
                    AgentThread.id == thread_id,
                    AgentThread.user_id == user_id,
                )
            ).scalar_one_or_none()
            if thread is None:
                raise LookupError(f"Thread {thread_id} does not exist")

            message = _insert_message(session, thread_id, "user", payload, symbols)
            turn = AgentTurn(
                id=turn_id,
                thread_id=thread_id,
                request_message_id=message.id,
                retry_of_turn_id=retry_of_turn_id,
                status=TURN_ADMITTED,
                last_event_seq=0,
            )
            session.add(turn)
            session.commit()
            return TurnCreation(turn=_turn_record(turn), created=True)

        return self._with_sequence_retry(write)

    @staticmethod
    def _owned_turn(
        session: Session, user_id: int, turn_id: uuid.UUID
    ) -> AgentTurn | None:
        """The Turn, but only if this user owns the Thread it belongs to.

        Ownership is a join rather than a column: ``agent_turn`` has no
        ``user_id`` and should not grow one, because the Thread already answers
        the question and two answers can disagree.
        """
        return session.execute(
            select(AgentTurn)
            .join(AgentThread, AgentThread.id == AgentTurn.thread_id)
            .where(AgentTurn.id == turn_id, AgentThread.user_id == user_id)
        ).scalar_one_or_none()

    async def read_turn(
        self, user_id: int, turn_id: uuid.UUID | str
    ) -> TurnRecord | None:
        return await asyncio.to_thread(self._read_turn, user_id, _uuid(turn_id))

    def _read_turn(self, user_id: int, turn_id: uuid.UUID) -> TurnRecord | None:
        with self._session_factory() as session:
            row = self._owned_turn(session, user_id, turn_id)
            return None if row is None else _turn_record(row)

    async def mark_turn_running(self, turn_id: uuid.UUID | str) -> None:
        """Leave ``admitted`` at the moment the Turn commits to dispatching."""
        await asyncio.to_thread(self._mark_turn_running, _uuid(turn_id))

    def _mark_turn_running(self, turn_id: uuid.UUID) -> None:
        with self._session_factory() as session:
            row = session.get(AgentTurn, turn_id)
            if row is None or row.status != TURN_ADMITTED:
                return
            row.status = TURN_RUNNING
            session.commit()

    async def checkpoint_turn(
        self,
        turn_id: uuid.UUID | str,
        draft: Mapping[str, Any],
        *,
        last_event_seq: int | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._checkpoint_turn, _uuid(turn_id), dict(draft), last_event_seq
        )

    def _checkpoint_turn(
        self,
        turn_id: uuid.UUID,
        draft: Mapping[str, Any],
        last_event_seq: int | None,
    ) -> None:
        with self._session_factory() as session:
            row = session.get(AgentTurn, turn_id)
            if row is None or row.status not in ACTIVE_TURN_STATUSES:
                # A terminal Turn is frozen. A checkpoint arriving after the
                # terminal transaction is a race, not a correction, and applying
                # it would put a half-written answer back on a finished Turn.
                return
            row.draft_content = dict(draft)
            if last_event_seq is not None:
                row.last_event_seq = last_event_seq
            session.commit()

    async def request_turn_cancel(
        self, user_id: int, turn_id: uuid.UUID | str
    ) -> TurnRecord | None:
        """Record the cancel request; idempotent, and never a second stamp."""
        return await asyncio.to_thread(
            self._request_turn_cancel, user_id, _uuid(turn_id)
        )

    def _request_turn_cancel(
        self, user_id: int, turn_id: uuid.UUID
    ) -> TurnRecord | None:
        with self._session_factory() as session:
            row = self._owned_turn(session, user_id, turn_id)
            if row is None:
                return None
            if row.cancel_requested_at is None and row.status in ACTIVE_TURN_STATUSES:
                row.cancel_requested_at = datetime.now(timezone.utc)
                session.commit()
            return _turn_record(row)

    async def finish_turn(
        self,
        turn_id: uuid.UUID | str,
        *,
        status: str,
        terminal_reason: str | None,
        message: Mapping[str, Any] | None = None,
        symbols: Sequence[str] = (),
        draft: Mapping[str, Any] | None = None,
        last_event_seq: int | None = None,
    ) -> TurnRecord:
        """The one terminal transaction (#81).

        The canonical assistant message, ``status``, ``terminal_reason``,
        ``response_message_id`` and ``finished_at`` are written together. Before
        it commits the transcript holds no half-written answer at all — the same
        invariant that makes a row in ``analysis`` mean *complete*.
        """
        if status in ACTIVE_TURN_STATUSES:
            raise ValueError(f"{status} is not a terminal Turn status")
        if status != TURN_COMPLETE and not terminal_reason:
            raise ValueError("a non-complete Turn must carry a terminal reason")
        normalized = tuple(dict.fromkeys(validate_symbol(symbol) for symbol in symbols))
        return await asyncio.to_thread(
            self._finish_turn,
            _uuid(turn_id),
            status,
            terminal_reason,
            None if message is None else dict(message),
            normalized,
            None if draft is None else dict(draft),
            last_event_seq,
        )

    def _finish_turn(
        self,
        turn_id: uuid.UUID,
        status: str,
        terminal_reason: str | None,
        message: Mapping[str, Any] | None,
        symbols: Sequence[str],
        draft: Mapping[str, Any] | None,
        last_event_seq: int | None,
    ) -> TurnRecord:
        def write(session: Session) -> TurnRecord:
            row = session.get(AgentTurn, turn_id)
            if row is None:
                raise LookupError(f"Turn {turn_id} does not exist")
            if row.status not in ACTIVE_TURN_STATUSES:
                # Already terminal: the startup sweep and a late finishing task
                # can both arrive here, and the first terminal state wins.
                return _turn_record(row)
            if message is not None:
                written = _insert_message(
                    session, row.thread_id, "assistant", message, symbols
                )
                row.response_message_id = written.id
            if draft is not None:
                row.draft_content = dict(draft)
            if last_event_seq is not None:
                row.last_event_seq = last_event_seq
            row.status = status
            row.terminal_reason = terminal_reason
            row.finished_at = datetime.now(timezone.utc)
            session.commit()
            return _turn_record(row)

        return self._with_sequence_retry(write)

    async def freeze_interrupted_turns(
        self, message_builder: MessageBuilder | None = None
    ) -> tuple[TurnRecord, ...]:
        """Freeze every Turn a crash or a deploy left active.

        Called once at startup. V1 never resumes execution: replaying a
        non-deterministic model against a store that has moved would produce a
        plausible continuation, and an honest ``incomplete`` carrying everything
        that actually ran is worth more than that.

        ``message_builder`` turns one frozen draft into the canonical assistant
        message, in the same transaction that freezes the Turn. It is a callback
        rather than logic here because what a useful incomplete message looks
        like — its blocks, its Risk Notice, its Evidence Manifest — is the
        lifecycle's business, and this module's business is the transaction.
        """
        return await asyncio.to_thread(self._freeze_interrupted_turns, message_builder)

    def _freeze_interrupted_turns(
        self, message_builder: MessageBuilder | None
    ) -> tuple[TurnRecord, ...]:
        return self._with_sequence_retry(
            lambda session: self._freeze(session, message_builder)
        )

    @staticmethod
    def _freeze(
        session: Session, message_builder: MessageBuilder | None
    ) -> tuple[TurnRecord, ...]:
        """Freeze every active Turn in one transaction, message included.

        Runs under :meth:`_with_sequence_retry` like every other writer of a
        transcript row: the sweep appends assistant messages, so it races the
        same ``UNIQUE(thread_id, seq)`` as the Turn that is still finishing in
        another process during a rolling deploy.
        """
        rows = list(
            session.execute(
                select(AgentTurn).where(AgentTurn.status.in_(ACTIVE_TURN_STATUSES))
            ).scalars()
        )
        frozen: list[TurnRecord] = []
        for row in rows:
            message = (
                None if message_builder is None else message_builder(_turn_record(row))
            )
            if message is not None:
                written = _insert_message(
                    session, row.thread_id, "assistant", message, ()
                )
                row.response_message_id = written.id
            row.status = TURN_INCOMPLETE
            row.terminal_reason = INTERRUPTED_REASON
            row.finished_at = datetime.now(timezone.utc)
            frozen.append(_turn_record(row))
        if frozen:
            session.commit()
        return tuple(frozen)


__all__ = [
    "ACTIVE_TURN_STATUSES",
    "INTERRUPTED_REASON",
    "TURN_ADMITTED",
    "TURN_COMPLETE",
    "TURN_INCOMPLETE",
    "TURN_RUNNING",
    "AgentPersistence",
    "MessageRecord",
    "ThreadRecord",
    "ThreadView",
    "ToolCallRecord",
    "TurnCreation",
    "TurnPayloadConflict",
    "TurnRecord",
]
