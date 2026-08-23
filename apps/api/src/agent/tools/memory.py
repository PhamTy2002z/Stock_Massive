"""What this user said before, and what they asked to keep.

Three tools, one subject: the user's own conversation. ``session_search`` reads
the transcript, ``remember_fact`` writes one durable note, ``recall_facts`` reads
those notes back. None of them reads market data — that surface belongs to the
price board and the model does not consult it.

The boundary that matters is ownership. Both reads are scoped to the caller's own
rows in SQL rather than in Python: the model chooses the query text, and a filter
applied after the rows were selected is a filter one refactor away from leaking
somebody else's transcript. ``user_id`` arrives in the trusted context, never in
a tool argument, so there is nothing here for the model to name.

Full-text search is accent-insensitive through ``immutable_unaccent``, because
Vietnamese is written both ways and a user searching "chu tich" means "chủ tịch".
The transcript has no stored ``tsvector`` — ``agent_message.content`` is JSONB and
carries more than prose — so the vector is built per row inside a query already
narrowed to one user's threads by an indexed join, rather than by scanning the
whole table.

Every call opens one short transaction and closes it. A session held for the
length of a Turn is a connection held across model latency, which is how a pool
of five runs out with four users on the site.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import date, datetime, time, timezone
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.alpha.models import AgentKnowledge
from src.core.database import sync_session_factory

from ..registry import ToolContext, ToolEntry, object_schema, register

MAX_MATCHES = 8
MAX_FACTS = 5
MAX_TITLE_CHARS = 240
MAX_BODY_CHARS = 4_000
MAX_EXCERPT_CHARS = 600
MAX_RECALLED_BODY_CHARS = 900

TOOLSET = "memory"

#: A fact the user stated in conversation has no URL, and the column is not
#: nullable. This is what stands in for one, and it is deliberately not a
#: fake http URL: nothing downstream should be able to mistake it for a page
#: somebody could open.
CONVERSATION_SOURCE = "memory://conversation"

SessionFactory = Callable[[], Session]


class MemoryTools:
    """Read this user's transcript and keep the facts they asked to keep."""

    def __init__(self, *, session_factory: SessionFactory = sync_session_factory) -> None:
        self._session_factory = session_factory

    def entries(self) -> tuple[ToolEntry, ...]:
        return (
            ToolEntry(
                name="session_search",
                toolset=TOOLSET,
                description=(
                    "Search this user's earlier messages and answers by keyword. "
                    "Use it to recover something the conversation established before."
                ),
                schema=object_schema(
                    {
                        "query": {"type": "string", "minLength": 1},
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": MAX_MATCHES,
                        },
                    },
                    ("query",),
                ),
                handler=self.session_search,
                display_name="Tìm trong hội thoại trước",
                summary_detail_arg="query",
                # The user's own earlier words. Already in the trust position
                # the conversation gives them, so wrapping them would tell the
                # model to weigh what it was itself told a moment ago.
                reads_external=False,
            ),
            ToolEntry(
                name="remember_fact",
                toolset=TOOLSET,
                description=(
                    "Keep one durable note for this user across conversations. Use "
                    "it only for something worth remembering later, not for notes "
                    "about the current answer."
                ),
                schema=object_schema(
                    {
                        "title": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": MAX_TITLE_CHARS,
                        },
                        "body": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": MAX_BODY_CHARS,
                        },
                        "source_url": {
                            "type": "string",
                            "description": (
                                "Where the fact came from, if it came from a page."
                            ),
                        },
                        "as_of": {
                            "type": "string",
                            "description": "The date the fact is true as of, if known.",
                        },
                    },
                    ("title", "body"),
                ),
                handler=self.remember_fact,
                display_name="Ghi nhớ",
                summary_detail_arg="title",
                reads_external=False,
            ),
            ToolEntry(
                name="recall_facts",
                toolset=TOOLSET,
                description=(
                    "Search the notes this user asked to keep, by keyword. "
                    "Accent-insensitive."
                ),
                schema=object_schema(
                    {
                        "query": {"type": "string", "minLength": 1},
                        "limit": {"type": "integer", "minimum": 1, "maximum": MAX_FACTS},
                    },
                    ("query",),
                ),
                handler=self.recall_facts,
                display_name="Đọc lại ghi chú",
                summary_detail_arg="query",
                reads_external=False,
            ),
        )

    async def session_search(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(self._session_search, context, dict(arguments))

    def _session_search(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ValueError("query must not be blank")
        limit = min(MAX_MATCHES, max(1, int(arguments.get("limit", MAX_MATCHES))))
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
                      thread.title AS thread_title,
                      left(coalesce(message.content->>'text', ''), :excerpt) AS excerpt,
                      ts_rank(
                        to_tsvector(
                          'simple',
                          immutable_unaccent(coalesce(message.content->>'text', ''))
                        ),
                        search.terms
                      ) AS text_rank
                    FROM agent_message AS message
                    JOIN agent_thread AS thread ON thread.id = message.thread_id
                    CROSS JOIN search
                    WHERE
                      thread.user_id = :user_id
                      AND to_tsvector(
                        'simple',
                        immutable_unaccent(coalesce(message.content->>'text', ''))
                      ) @@ search.terms
                    ORDER BY text_rank DESC, message.created_at DESC, message.id DESC
                    LIMIT :limit
                    """
                ),
                {
                    "query": query,
                    "user_id": _owner(context),
                    "excerpt": MAX_EXCERPT_CHARS,
                    "limit": limit,
                },
            ).mappings()
            matches = [
                {
                    "thread_id": str(row["thread_id"]),
                    "thread_title": row["thread_title"],
                    "seq": row["seq"],
                    "role": row["role"],
                    "created_at": row["created_at"].isoformat(),
                    "excerpt": row["excerpt"],
                }
                for row in rows
            ]
        return {
            "query": query,
            "matches": matches,
            "count": len(matches),
            "reason": None if matches else "no_matching_messages",
        }

    async def remember_fact(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(self._remember_fact, context, dict(arguments))

    def _remember_fact(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        title = str(arguments.get("title") or "").strip()
        body = str(arguments.get("body") or "").strip()
        if not title or len(title) > MAX_TITLE_CHARS:
            raise ValueError(f"title must be between 1 and {MAX_TITLE_CHARS} characters")
        if not body or len(body) > MAX_BODY_CHARS:
            raise ValueError(f"body must be between 1 and {MAX_BODY_CHARS} characters")
        source_url, source_name = _source(arguments.get("source_url"))
        remembered_at = context.now or datetime.now(timezone.utc)
        as_of = _optional_instant(arguments.get("as_of"))
        with self._session_factory() as session:
            row = AgentKnowledge(
                user_id=_owner(context),
                title=title,
                body=body,
                source_url=source_url,
                source_name=source_name,
                retrieved_at=remembered_at,
                as_of=as_of,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return {
                "id": row.id,
                "remembered": True,
                "title": row.title,
                "source": row.source_name,
            }

    async def recall_facts(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(self._recall_facts, context, dict(arguments))

    def _recall_facts(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ValueError("query must not be blank")
        limit = min(MAX_FACTS, max(1, int(arguments.get("limit", MAX_FACTS))))
        with self._session_factory() as session:
            rows = session.execute(
                text(
                    """
                    WITH search AS (
                      SELECT
                        websearch_to_tsquery(
                          'simple', immutable_unaccent(:query)
                        ) AS terms,
                        immutable_unaccent(lower(:query)) AS normalized
                    )
                    SELECT
                      knowledge.*,
                      ts_rank(knowledge.tsv, search.terms) AS text_rank,
                      similarity(
                        immutable_unaccent(lower(knowledge.title)),
                        search.normalized
                      ) AS title_similarity
                    FROM agent_knowledge AS knowledge
                    CROSS JOIN search
                    WHERE
                      knowledge.user_id = :user_id
                      AND (
                        knowledge.tsv @@ search.terms
                        OR similarity(
                          immutable_unaccent(lower(knowledge.title)),
                          search.normalized
                        ) >= 0.15
                      )
                    ORDER BY
                      text_rank DESC,
                      title_similarity DESC,
                      knowledge.created_at DESC,
                      knowledge.id DESC
                    LIMIT :limit
                    """
                ),
                {"query": query, "user_id": _owner(context), "limit": limit},
            ).mappings()
            facts = [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "body": str(row["body"])[:MAX_RECALLED_BODY_CHARS],
                    "source": row["source_name"],
                    "source_url": row["source_url"],
                    "remembered_at": row["retrieved_at"].isoformat(),
                    "as_of": row["as_of"].isoformat() if row["as_of"] else None,
                }
                for row in rows
            ]
        return {
            "query": query,
            "facts": facts,
            "count": len(facts),
            "reason": None if facts else "no_remembered_facts",
        }


def _owner(context: ToolContext) -> int:
    """The user these three tools are about, or a refusal naming what is missing.

    ``ToolContext.user_id`` is optional because not every caller of the registry
    has a user: an Analysis is keyed by ``(symbol, trading_day)`` and belongs to
    nobody. These three tools do belong to somebody — every read is scoped to
    one user's own rows in SQL — so the condition is asserted here rather than
    assumed from the type. A refusal rather than a crash, because the executor
    turns a raising handler into a result the model can read, and "this tool
    needs a signed-in user" is exactly what it should read.

    Unreachable through the chat lane, which always has a user, and unreachable
    through the Analysis lane, which does not select the ``memory`` toolset at
    all. It is the third caller — the one nobody has written yet — that this is
    for.
    """
    if context.user_id is None:
        raise ValueError(
            "this tool reads one user's own conversation and there is no user in "
            "this context"
        )
    return context.user_id


def _source(value: Any) -> tuple[str, str]:
    """Where a remembered fact came from, validated if it claims to be a page."""
    raw = str(value or "").strip()
    if not raw:
        return CONVERSATION_SOURCE, "conversation"
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("source_url must be an absolute http or https URL")
    if parsed.username or parsed.password:
        raise ValueError("source_url must not contain credentials")
    return raw, parsed.hostname


def _optional_instant(value: Any) -> datetime | None:
    """A date or timestamp the model wrote, or ``None``.

    A bare date is read as midnight UTC rather than refused: "as of 2026-08-20"
    is the normal way a fact is dated, and refusing it would teach the model to
    stop dating facts at all.
    """
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.combine(date.fromisoformat(raw), time.min)
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc)


def register_memory_tools(**kwargs: Any) -> tuple[ToolEntry, ...]:
    """Register all three memory tools and hand the registrations back."""
    tools = MemoryTools(**kwargs)
    return tuple(register(entry) for entry in tools.entries())


__all__ = [
    "CONVERSATION_SOURCE",
    "MAX_BODY_CHARS",
    "MAX_FACTS",
    "MAX_MATCHES",
    "MAX_TITLE_CHARS",
    "MemoryTools",
    "TOOLSET",
    "register_memory_tools",
]
