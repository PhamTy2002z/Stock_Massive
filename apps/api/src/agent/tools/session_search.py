"""Read earlier conversations back out of the store, without a model in the loop.

One registration covers four questions because they are one question asked with
different amounts of knowledge: *where did we discuss this*, *what did we say
around here*, *what was that whole thread*, *what have we talked about lately*.
The mode is inferred from which arguments arrive rather than named by a `mode`
parameter — a parameter the model would have to keep consistent with the rest of
the call, and would sometimes get wrong while the arguments said otherwise.

Nothing here calls an LLM. Summarising a search result costs a model call on the
path to *finding* something, and a summary can be wrong in ways the excerpt it
replaced cannot; the excerpt is served verbatim and clipped instead.

Every excerpt is an ``external_claim``. It is this system's own store, but what
it holds is prose — the reader's and an earlier answer's — and a figure quoted
back out of a transcript is no more verified than it was the first time
(``grounding.py::EvidenceSource``). Access is scoped by joining ``agent_thread``:
``agent_message`` deliberately carries no ``user_id``, and the thread is where
ownership lives.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import text

from src.core.database import sync_session_factory

from .catalog import (
    MAX_TOOL_RESULT_BYTES,
    ToolContext,
    ToolDataAccess,
    ToolSpec,
    serialized_size,
)
from .data import SessionFactory, _object_schema

#: The refusal every mode shares when the store holds nothing to show.
NO_MATCHING_MESSAGES = "no_matching_messages"

MAX_MESSAGES = 8
MAX_THREADS = 8
#: Messages either side of an anchor. Small on purpose: the point of an anchor
#: is that the model already knows where to look, so the window is context and
#: not a second search.
ANCHOR_RADIUS = 3
#: Where an excerpt is cut. Long enough to carry a claim with its qualifier,
#: short enough that the 4KB result cap is reached by several excerpts rather
#: than by one.
MAX_EXCERPT_CHARS = 600


class SessionSearchTools:
    """Search and replay this user's transcripts, bounded and without an LLM."""

    def __init__(self, *, session_factory: SessionFactory = sync_session_factory) -> None:
        self._session_factory = session_factory

    def registrations(self) -> tuple[ToolSpec, ...]:
        return (
            ToolSpec(
                name="session_search",
                description=(
                    "Look back at this reader's earlier conversations before "
                    "asking them to repeat themselves. Pass query to search "
                    "every thread; add thread_id to search inside one; pass "
                    "thread_id with anchor for the messages around that seq; "
                    "pass thread_id alone for its recent messages; pass nothing "
                    "for the recent threads. Excerpts are prose from the "
                    "transcript and remain external_claim, so re-check any "
                    "figure before quoting it."
                ),
                parameters=_object_schema(
                    {
                        "query": {"type": "string", "minLength": 1},
                        "thread_id": {"type": "string", "minLength": 1},
                        "anchor": {"type": "integer", "minimum": 0},
                        "limit": {"type": "integer", "minimum": 1, "maximum": MAX_MESSAGES},
                    },
                ),
                callable=self.session_search,
                data_access=ToolDataAccess.STORE_ONLY,
            ),
        )

    async def session_search(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(self._session_search, context, dict(arguments))

    def _session_search(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        raw_query = arguments.get("query")
        query = str(raw_query).strip() if raw_query is not None else ""
        thread_id = _optional_thread_id(arguments.get("thread_id"))
        anchor = _optional_anchor(arguments.get("anchor"))
        limit = min(MAX_MESSAGES, max(1, int(arguments.get("limit", MAX_MESSAGES))))

        if query:
            return self._search(context, query=query, thread_id=thread_id, limit=limit)
        if thread_id is not None and anchor is not None:
            return self._window(context, thread_id=thread_id, anchor=anchor)
        if thread_id is not None:
            return self._thread(context, thread_id=thread_id, limit=limit)
        return self._recent_threads(context, limit=limit)

    def _search(
        self, context: ToolContext, *, query: str, thread_id: str | None, limit: int
    ) -> Mapping[str, Any]:
        with self._session_factory() as session:
            rows = session.execute(
                text(
                    """
                    WITH search AS (
                      SELECT websearch_to_tsquery(
                        'simple', immutable_unaccent(:query)
                      ) AS terms
                    )
                    SELECT
                      message.thread_id,
                      message.seq,
                      message.role,
                      message.created_at,
                      message.content ->> 'text' AS excerpt,
                      ts_rank(message.tsv, search.terms) AS text_rank
                    FROM agent_message AS message
                    JOIN agent_thread AS thread ON thread.id = message.thread_id
                    CROSS JOIN search
                    WHERE
                      thread.user_id = :user_id
                      AND (
                        CAST(:thread_id AS uuid) IS NULL
                        OR message.thread_id = CAST(:thread_id AS uuid)
                      )
                      AND message.tsv @@ search.terms
                    ORDER BY
                      text_rank DESC,
                      message.created_at DESC,
                      message.seq DESC
                    LIMIT :limit
                    """
                ),
                {
                    "query": query,
                    "user_id": context.user_id,
                    "thread_id": thread_id,
                    "limit": limit,
                },
            ).mappings()
            messages = _pack(rows, base={"mode": "search", "query": query})
        return _messages_envelope(
            {"mode": "search", "query": query, "thread_id": thread_id}, messages
        )

    def _window(
        self, context: ToolContext, *, thread_id: str, anchor: int
    ) -> Mapping[str, Any]:
        with self._session_factory() as session:
            rows = session.execute(
                text(
                    """
                    SELECT
                      message.thread_id,
                      message.seq,
                      message.role,
                      message.created_at,
                      message.content ->> 'text' AS excerpt
                    FROM agent_message AS message
                    JOIN agent_thread AS thread ON thread.id = message.thread_id
                    WHERE
                      thread.user_id = :user_id
                      AND message.thread_id = CAST(:thread_id AS uuid)
                      AND message.seq BETWEEN :low AND :high
                    ORDER BY message.seq
                    """
                ),
                {
                    "user_id": context.user_id,
                    "thread_id": thread_id,
                    "low": anchor - ANCHOR_RADIUS,
                    "high": anchor + ANCHOR_RADIUS,
                },
            ).mappings()
            messages = _pack(rows, base={"mode": "window"})
        return _messages_envelope(
            {"mode": "window", "thread_id": thread_id, "anchor": anchor}, messages
        )

    def _thread(
        self, context: ToolContext, *, thread_id: str, limit: int
    ) -> Mapping[str, Any]:
        with self._session_factory() as session:
            # The newest messages are the ones worth replaying, but they read in
            # the order they were written, so the bound is applied before the
            # ordering is put back.
            rows = session.execute(
                text(
                    """
                    SELECT * FROM (
                      SELECT
                        message.thread_id,
                        message.seq,
                        message.role,
                        message.created_at,
                        message.content ->> 'text' AS excerpt
                      FROM agent_message AS message
                      JOIN agent_thread AS thread ON thread.id = message.thread_id
                      WHERE
                        thread.user_id = :user_id
                        AND message.thread_id = CAST(:thread_id AS uuid)
                      ORDER BY message.seq DESC
                      LIMIT :limit
                    ) AS recent
                    ORDER BY seq
                    """
                ),
                {"user_id": context.user_id, "thread_id": thread_id, "limit": limit},
            ).mappings()
            messages = _pack(rows, base={"mode": "thread"})
        return _messages_envelope({"mode": "thread", "thread_id": thread_id}, messages)

    def _recent_threads(self, context: ToolContext, *, limit: int) -> Mapping[str, Any]:
        with self._session_factory() as session:
            rows = session.execute(
                text(
                    """
                    SELECT
                      thread.id AS thread_id,
                      thread.title,
                      thread.updated_at,
                      count(message.id) AS message_count
                    FROM agent_thread AS thread
                    LEFT JOIN agent_message AS message
                      ON message.thread_id = thread.id
                    WHERE thread.user_id = :user_id
                    GROUP BY thread.id, thread.title, thread.updated_at
                    ORDER BY thread.updated_at DESC, thread.id
                    LIMIT :limit
                    """
                ),
                {"user_id": context.user_id, "limit": min(MAX_THREADS, limit)},
            ).mappings()
            threads: list[Mapping[str, Any]] = []
            for row in rows:
                entry = {
                    "thread_id": str(row["thread_id"]),
                    "title": row["title"],
                    "updated_at": row["updated_at"].isoformat(),
                    "message_count": int(row["message_count"]),
                }
                candidate = {"mode": "recent_threads", "threads": [*threads, entry]}
                if serialized_size(candidate) <= MAX_TOOL_RESULT_BYTES:
                    threads.append(entry)
        return {
            "mode": "recent_threads",
            "threads": threads,
            "count": len(threads),
            "reason": None if threads else NO_MATCHING_MESSAGES,
        }


def _pack(
    rows: Any, *, base: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    """Take rows until the next one would push the result past the cap."""

    messages: list[Mapping[str, Any]] = []
    for row in rows:
        excerpt = str(row["excerpt"] or "").strip()
        if not excerpt:
            continue
        claim = {
            "thread_id": str(row["thread_id"]),
            "seq": int(row["seq"]),
            "role": row["role"],
            "created_at": row["created_at"].isoformat(),
            "excerpt": excerpt[:MAX_EXCERPT_CHARS],
            "claim_class": "external_claim",
        }
        candidate = {**base, "messages": [*messages, {"external_claim": claim}]}
        if serialized_size(candidate) <= MAX_TOOL_RESULT_BYTES:
            messages.append({"external_claim": claim})
    return messages


def _messages_envelope(
    header: Mapping[str, Any], messages: Sequence[Mapping[str, Any]]
) -> Mapping[str, Any]:
    """One shape for the three message modes, refusing the same way when empty.

    A thread belonging to somebody else lands here as an empty result, which is
    the point: the join found nothing, so the refusal cannot distinguish a
    thread that is not this reader's from one that does not exist.
    """

    return {
        **header,
        "messages": list(messages),
        "count": len(messages),
        "reason": None if messages else NO_MATCHING_MESSAGES,
    }


def _optional_thread_id(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    try:
        return str(UUID(raw))
    except ValueError as exc:
        raise ValueError("thread_id must be a UUID") from exc


def _optional_anchor(value: Any) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    anchor = int(value)
    if anchor < 0:
        raise ValueError("anchor must not be negative")
    return anchor


__all__ = ["SessionSearchTools", "NO_MATCHING_MESSAGES"]
