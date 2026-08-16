"""Deliberate, sourced memory across Turns without promoting external claims."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import date, datetime, time, timezone
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import text

from src.alpha.models import AgentKnowledge
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
                    "Remember one useful sourced fact across Turns. Saving it does "
                    "not verify it; the result remains external_claim evidence."
                ),
                parameters=_object_schema(
                    {
                        "title": {"type": "string", "minLength": 1, "maxLength": MAX_TITLE_CHARS},
                        "body": {"type": "string", "minLength": 1, "maxLength": MAX_BODY_CHARS},
                        "source_url": {"type": "string", "minLength": 1},
                        "as_of": {"type": "string"},
                        "symbol": {"type": "string"},
                    },
                    ("title", "body", "source_url"),
                ),
                callable=self.remember_fact,
            ),
            ToolSpec(
                name="recall_facts",
                description=(
                    "Search deliberately remembered facts with accent-insensitive "
                    "full-text and fuzzy title ranking. Results remain external_claim."
                ),
                parameters=_object_schema(
                    {
                        "query": {"type": "string", "minLength": 1},
                        "symbol": {"type": "string"},
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
        source_url = _source_url(str(arguments["source_url"]))
        symbol = arguments.get("symbol")
        normalized_symbol = validate_symbol(str(symbol)) if symbol else None
        retrieved_at = datetime.now(timezone.utc)
        as_of = _optional_instant(arguments.get("as_of"))
        source_name = urlsplit(source_url).hostname or source_url
        with self._session_factory() as session:
            row = AgentKnowledge(
                user_id=context.user_id,
                symbol=normalized_symbol,
                title=title,
                body=body,
                source_url=source_url,
                source_name=source_name,
                retrieved_at=retrieved_at,
                as_of=as_of,
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
                    "source_url": row["source_url"],
                    "source": row["source_name"],
                    "retrieved_at": row["retrieved_at"].isoformat(),
                    "as_of": row["as_of"].isoformat() if row["as_of"] else None,
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
        "source_url": row.source_url,
        "source": row.source_name,
        "retrieved_at": row.retrieved_at.isoformat(),
        "as_of": row.as_of.isoformat() if row.as_of else None,
        "claim_class": "external_claim",
    }


__all__ = ["KnowledgeTools"]
