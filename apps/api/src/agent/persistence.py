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
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.alpha.models import AgentMessage, AgentThread, AgentToolCall
from src.core.database import sync_session_factory
from src.stocks.shared import validate_symbol

SessionFactory = Callable[[], Session]
MAX_SEQUENCE_RETRIES = 20
TOOL_CALL_RETENTION_DAYS = 90


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


def _thread_id(value: uuid.UUID | str) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


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
        return await asyncio.to_thread(self._read_thread, user_id, _thread_id(thread_id))

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
            self._delete_thread, user_id, _thread_id(thread_id)
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
            _thread_id(thread_id),
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
        for attempt in range(MAX_SEQUENCE_RETRIES):
            with self._session_factory() as session:
                try:
                    thread = session.execute(
                        select(AgentThread).where(AgentThread.id == thread_id)
                    ).scalar_one_or_none()
                    if thread is None:
                        raise LookupError(f"Thread {thread_id} does not exist")
                    current = session.execute(
                        select(func.max(AgentMessage.seq)).where(
                            AgentMessage.thread_id == thread_id
                        )
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
                    session.commit()
                    return _message_record(message)
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
        thread_id = _thread_id(trace["thread_id"])
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
