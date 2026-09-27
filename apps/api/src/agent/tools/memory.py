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

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.alpha.models import AgentKnowledge
from src.auth.models import User
from src.auth.schemas import UserPreferences
from src.core.database import sync_session_factory

from ..registry import (
    ContentTrust,
    ToolAccess,
    ToolConcurrency,
    ToolContext,
    ToolEffect,
    ToolEntry,
    ToolIdempotency,
    ToolPermission,
    object_schema,
    register,
)
from ..permissions import AuthorizationDenied

#: What one call of any of these tools may take. They are single statements
#: against this deployment's own database, so a call still running after this
#: is not slow, it is stuck.
STORE_TIMEOUT_SECONDS = 10.0

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

#: The reason a note tool gives when the reader switched memory off. A result,
#: not a failure: nothing went wrong, and a failure would count toward the
#: guardrail that stops a tool which keeps breaking. The MEMORY section tells
#: the model what to do with it.
MEMORY_DISABLED = "memory_disabled"
_DISABLED_MESSAGE = (
    "The user turned memory off in Settings, so notes are neither kept nor read. "
    "Do not call this tool again in this Turn."
)


def _memory_disabled(session: Session, user_id: int) -> bool:
    """Whether this reader switched the note tools off.

    Asked per call, inside the call's own transaction, rather than decided when
    the Turn's tool surface is built. Taking the tools off the surface would be
    the stronger form, and it needs the reader's preferences where the surface
    is resolved — the Turn runner and the loop — which is a wider change than a
    switch warrants. Here the gate sits on the one path every call takes, keyed
    by the trusted ``user_id``, and reads the stored row the way ``/auth/me``
    does, so the two cannot disagree about what the switch says.
    """
    stored = session.execute(
        select(User.preferences).where(User.id == user_id)
    ).scalar_one_or_none()
    return not UserPreferences.from_stored(stored).memory_enabled


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
                    "Search this user's own earlier messages by keyword. "
                    "Use it when the user refers to something said before that is "
                    "not in the visible conversation, before asking them to repeat "
                    "it. It is not a source of current market data."
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
                display_name="Search earlier conversation",
                summary_detail_arg="query",
                # The user's own earlier words, and only those: the search reads
                # user-role rows alone. Already in the trust position the
                # conversation gives them, so wrapping them would tell the
                # model to weigh what it was itself told a moment ago. An
                # earlier *answer* is not the user's word — it may repeat what
                # a page said — and grounding exempts this tool's figures as
                # the reader's own, so answers must not come back through it.
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                access=ToolAccess.STORE,
                content_trust=ContentTrust.TRUSTED_STRUCTURED,
                concurrency=ToolConcurrency.PARALLEL_SAFE,
                permission=ToolPermission.ALLOW,
                resource_arg="query",
                timeout_seconds=STORE_TIMEOUT_SECONDS,
                contract_version="1",
            ),
            ToolEntry(
                name="remember_fact",
                toolset=TOOLSET,
                description=(
                    "Keep one durable note for this user across conversations. This "
                    "is the only tool that writes. Use it when the user asks you "
                    "to remember something, or states a lasting preference or "
                    "constraint such as their horizon or risk tolerance. Do not "
                    "use it for market figures that go stale, or for notes about "
                    "the current answer."
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
                display_name="Remember",
                summary_detail_arg="title",
                effect=ToolEffect.WRITE,
                idempotency=ToolIdempotency.UNKNOWN,
                access=ToolAccess.STORE,
                content_trust=ContentTrust.TRUSTED_STRUCTURED,
                concurrency=ToolConcurrency.SERIALIZED,
                # A write, and still allowed: what it writes is this user's own
                # note in this user's own scope, which is the thing they asked
                # for. Permission is declared here so that judgement is a line
                # somebody can read and change, not an absence.
                permission=ToolPermission.ALLOW,
                resource_arg="title",
                timeout_seconds=STORE_TIMEOUT_SECONDS,
                contract_version="1",
            ),
            ToolEntry(
                name="recall_facts",
                toolset=TOOLSET,
                description=(
                    "Search the notes this user asked to keep, by keyword. "
                    "Accent-insensitive. Use it when an answer could depend on the "
                    "user's stated preferences or constraints, before asking them "
                    "again."
                ),
                schema=object_schema(
                    {
                        "query": {"type": "string", "minLength": 1},
                        "limit": {"type": "integer", "minimum": 1, "maximum": MAX_FACTS},
                    },
                    ("query",),
                ),
                handler=self.recall_facts,
                display_name="Recall notes",
                summary_detail_arg="query",
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                access=ToolAccess.STORE,
                content_trust=ContentTrust.TRUSTED_STRUCTURED,
                concurrency=ToolConcurrency.PARALLEL_SAFE,
                permission=ToolPermission.ALLOW,
                resource_arg="query",
                timeout_seconds=STORE_TIMEOUT_SECONDS,
                contract_version="1",
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
        owner = _owner(context)
        with self._session_factory() as session:
            # The transcript is memory too: a reader who switched memory off
            # is not searched across conversations either.
            if _memory_disabled(session, owner):
                return {
                    "query": query,
                    "matches": [],
                    "count": 0,
                    "reason": MEMORY_DISABLED,
                    "message": _DISABLED_MESSAGE,
                }
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
                      AND message.role = 'user'
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
                    "user_id": owner,
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
        owner = _owner(context)
        with self._session_factory() as session:
            if _memory_disabled(session, owner):
                return {
                    "remembered": False,
                    "reason": MEMORY_DISABLED,
                    "message": _DISABLED_MESSAGE,
                }
            row = AgentKnowledge(
                user_id=owner,
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
        owner = _owner(context)
        with self._session_factory() as session:
            if _memory_disabled(session, owner):
                return {
                    "query": query,
                    "facts": [],
                    "count": 0,
                    "reason": MEMORY_DISABLED,
                    "message": _DISABLED_MESSAGE,
                }
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
                {"query": query, "user_id": owner, "limit": limit},
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
        raise AuthorizationDenied(
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
    "MEMORY_DISABLED",
    "MemoryTools",
    "TOOLSET",
    "register_memory_tools",
]
