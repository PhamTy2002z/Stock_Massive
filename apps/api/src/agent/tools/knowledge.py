"""Deliberate, sourced memory across Turns without promoting external claims."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import date, datetime, time, timezone
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import text

from src.alpha.models import (
    KNOWLEDGE_KIND_OBSERVATION,
    KNOWLEDGE_KINDS,
    KNOWLEDGE_ORIGIN_EXTERNAL_SOURCE,
    KNOWLEDGE_ORIGINS,
    AgentKnowledge,
)
from src.core.database import sync_session_factory
from src.stocks.shared import validate_symbol

from .catalog import MAX_TOOL_RESULT_BYTES, ToolContext, ToolSpec, serialized_size
from .data import SessionFactory, _object_schema

MAX_FACTS = 5
MAX_TITLE_CHARS = 240
MAX_BODY_CHARS = 4_000
MAX_RECALLED_BODY_CHARS = 900


class KnowledgeTools:
    """Write only explicit memories and search them with source metadata intact."""

    def __init__(self, *, session_factory: SessionFactory = sync_session_factory) -> None:
        self._session_factory = session_factory

    def registrations(self) -> tuple[ToolSpec, ...]:
        return (
            ToolSpec(
                name="remember_fact",
                description=(
                    "Remember one useful fact across Turns. Use origin "
                    "'user_stated' for something the reader said about "
                    "themselves, such as risk appetite or investment horizon, "
                    "and leave source_url out; use 'external_source' with a "
                    "source_url for anything read from the web or a publisher, "
                    "and 'system_derived' for a conclusion this agent reached. "
                    "Set expires_at when the fact stops being worth quoting. "
                    "Saving it does not verify it; the result remains "
                    "external_claim evidence."
                ),
                parameters=_object_schema(
                    {
                        "title": {"type": "string", "minLength": 1, "maxLength": MAX_TITLE_CHARS},
                        "body": {"type": "string", "minLength": 1, "maxLength": MAX_BODY_CHARS},
                        "kind": {"type": "string", "enum": list(KNOWLEDGE_KINDS)},
                        "origin": {"type": "string", "enum": list(KNOWLEDGE_ORIGINS)},
                        "source_url": {"type": "string", "minLength": 1},
                        "as_of": {"type": "string"},
                        "expires_at": {"type": "string"},
                        "symbol": {"type": "string"},
                    },
                    ("title", "body"),
                ),
                callable=self.remember_fact,
            ),
            ToolSpec(
                name="recall_facts",
                description=(
                    "Search deliberately remembered facts with accent-insensitive "
                    "full-text and fuzzy title ranking, optionally narrowed to one "
                    "kind or origin. Expired facts are never returned. Results "
                    "remain external_claim and carry the origin that produced "
                    "them, so attribute them as previously recorded rather than "
                    "as stored market data."
                ),
                parameters=_object_schema(
                    {
                        "query": {"type": "string", "minLength": 1},
                        "symbol": {"type": "string"},
                        "kind": {"type": "string", "enum": list(KNOWLEDGE_KINDS)},
                        "origin": {"type": "string", "enum": list(KNOWLEDGE_ORIGINS)},
                        "limit": {"type": "integer", "minimum": 1, "maximum": MAX_FACTS},
                    },
                    ("query",),
                ),
                callable=self.recall_facts,
            ),
        )

    async def remember_fact(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(self._remember_fact, context, dict(arguments))

    def _remember_fact(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        title = str(arguments["title"]).strip()
        body = str(arguments["body"]).strip()
        if not title or len(title) > MAX_TITLE_CHARS:
            raise ValueError("title must be between 1 and 240 characters")
        if not body or len(body) > MAX_BODY_CHARS:
            raise ValueError("body must be between 1 and 4000 characters")
        kind = _choice(arguments.get("kind"), KNOWLEDGE_KINDS, "kind", KNOWLEDGE_KIND_OBSERVATION)
        origin = _choice(
            arguments.get("origin"),
            KNOWLEDGE_ORIGINS,
            "origin",
            KNOWLEDGE_ORIGIN_EXTERNAL_SOURCE,
        )
        raw_url = arguments.get("source_url")
        source_url = _source_url(str(raw_url)) if raw_url and str(raw_url).strip() else None
        # The database CHECK says the same thing; saying it here first turns a
        # constraint violation into an argument error the model can act on.
        if origin == KNOWLEDGE_ORIGIN_EXTERNAL_SOURCE and source_url is None:
            raise ValueError(
                "source_url is required when origin is external_source; use "
                "origin 'user_stated' for something the reader said"
            )
        symbol = arguments.get("symbol")
        normalized_symbol = validate_symbol(str(symbol)) if symbol else None
        retrieved_at = datetime.now(timezone.utc)
        as_of = _optional_instant(arguments.get("as_of"))
        expires_at = _optional_instant(arguments.get("expires_at"))
        source_name = (urlsplit(source_url).hostname or source_url) if source_url else None
        with self._session_factory() as session:
            row = AgentKnowledge(
                user_id=context.user_id,
                symbol=normalized_symbol,
                title=title,
                body=body,
                kind=kind,
                origin=origin,
                source_url=source_url,
                source_name=source_name,
                retrieved_at=retrieved_at,
                as_of=as_of,
                expires_at=expires_at,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return {
                "id": row.id,
                "remembered": True,
                "external_claim": _claim(row, body_limit=MAX_RECALLED_BODY_CHARS),
            }

    async def recall_facts(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(self._recall_facts, context, dict(arguments))

    def _recall_facts(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        query = str(arguments["query"]).strip()
        if not query:
            raise ValueError("query must not be blank")
        limit = min(MAX_FACTS, max(1, int(arguments.get("limit", MAX_FACTS))))
        symbol = arguments.get("symbol")
        normalized_symbol = validate_symbol(str(symbol)) if symbol else None
        kind = _choice(arguments.get("kind"), KNOWLEDGE_KINDS, "kind", None)
        origin = _choice(arguments.get("origin"), KNOWLEDGE_ORIGINS, "origin", None)
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
                      (knowledge.user_id = :user_id OR knowledge.user_id IS NULL)
                      AND (:symbol IS NULL OR knowledge.symbol = :symbol)
                      AND (:kind IS NULL OR knowledge.kind = :kind)
                      AND (:origin IS NULL OR knowledge.origin = :origin)
                      -- Expiry is enforced in SQL rather than left to the model
                      -- to read off a date: a fact past its usefulness is safer
                      -- absent than present behind a caveat an answer may drop.
                      AND (
                        knowledge.expires_at IS NULL
                        OR knowledge.expires_at > now()
                      )
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
                {
                    "query": query,
                    "user_id": context.user_id,
                    "symbol": normalized_symbol,
                    "kind": kind,
                    "origin": origin,
                    "limit": limit,
                },
            ).mappings()
            facts: list[Mapping[str, Any]] = []
            for row in rows:
                claim = {
                    "id": row["id"],
                    "title": row["title"],
                    "body": str(row["body"])[:MAX_RECALLED_BODY_CHARS],
                    "symbol": row["symbol"],
                    "kind": row["kind"],
                    "origin": row["origin"],
                    "source_url": row["source_url"],
                    "source": row["source_name"],
                    "retrieved_at": row["retrieved_at"].isoformat(),
                    "as_of": row["as_of"].isoformat() if row["as_of"] else None,
                    "expires_at": (
                        row["expires_at"].isoformat() if row["expires_at"] else None
                    ),
                    "claim_class": "external_claim",
                }
                candidate = {"query": query, "facts": [*facts, {"external_claim": claim}]}
                if serialized_size(candidate) <= MAX_TOOL_RESULT_BYTES:
                    facts.append({"external_claim": claim})
        return {
            "query": query,
            "facts": facts,
            "count": len(facts),
            "reason": None if facts else "no_remembered_facts",
        }


def _source_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("source_url must be an absolute http or https URL")
    if parsed.username or parsed.password:
        raise ValueError("source_url must not contain credentials")
    return value.strip()


def _choice(
    value: Any, allowed: tuple[str, ...], field: str, default: str | None
) -> str | None:
    """One of a closed vocabulary, or the default when the model said nothing.

    The sets are small and shared with the store, so an unrecognised value is
    rejected with the whole set in the message: the model's next attempt then
    has the vocabulary rather than another guess at it.
    """

    if value is None or not str(value).strip():
        return default
    candidate = str(value).strip()
    if candidate not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(allowed)}")
    return candidate


def _optional_instant(value: Any) -> datetime | None:
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.combine(date.fromisoformat(raw), time.min)
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc)


def _claim(row: AgentKnowledge, *, body_limit: int) -> Mapping[str, Any]:
    return {
        "title": row.title,
        "body": row.body[:body_limit],
        "symbol": row.symbol,
        "kind": row.kind,
        "origin": row.origin,
        "source_url": row.source_url,
        "source": row.source_name,
        "retrieved_at": row.retrieved_at.isoformat(),
        "as_of": row.as_of.isoformat() if row.as_of else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        # Persistence never promotes evidence: a fact the reader stated and a
        # fact read off a publisher are both external claims when recalled.
        "claim_class": "external_claim",
    }


__all__ = ["KnowledgeTools"]
