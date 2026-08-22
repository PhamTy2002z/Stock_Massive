"""The user's own transcript and their own notes, and nobody else's.

Runs against a throwaway Postgres database beside whatever ``DATABASE_URL``
points at, for the same reason the eval tests do: the search is full-text with
accent folding, which is Postgres behaviour and cannot be proven against SQLite.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.agent.registry import ToolContext
from src.agent.tools.memory import CONVERSATION_SOURCE, MemoryTools
from src.alpha.models import AgentKnowledge, AgentMessage, AgentThread
from src.auth.models import User
from src.core.database import Base

from .eval_store import create_database, drop_database

MEMORY_DB = "stockmassive_memory_test"

# What the transcript search is proven against: one Vietnamese sentence with
# diacritics, one without, and one belonging to somebody else.
OWN_MESSAGES = (
    ("user", "Lãi suất điều hành có giảm trong tháng này không?"),
    ("assistant", "Ngân hàng Nhà nước giữ nguyên lãi suất điều hành."),
    ("user", "Cảm ơn, còn tỷ giá thì sao?"),
)
STRANGER_MESSAGE = "Lãi suất của tôi là chuyện riêng."


@pytest.fixture(scope="module")
def memory_world():
    url = create_database(MEMORY_DB)
    engine = create_engine(url, future=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        connection.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION public.immutable_unaccent(text)
                RETURNS text
                LANGUAGE sql
                IMMUTABLE
                PARALLEL SAFE
                STRICT
                AS $$ SELECT public.unaccent('public.unaccent', $1) $$
                """
            )
        )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            AgentThread.__table__,
            AgentMessage.__table__,
            AgentKnowledge.__table__,
        ],
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with factory() as session:
        owner = User(email="owner@example.com", hashed_password="x")
        stranger = User(email="stranger@example.com", hashed_password="x")
        session.add_all([owner, stranger])
        session.commit()
        own_thread = AgentThread(id=uuid.uuid4(), user_id=owner.id, title="Rates")
        other_thread = AgentThread(id=uuid.uuid4(), user_id=stranger.id, title="Private")
        session.add_all([own_thread, other_thread])
        session.commit()
        for seq, (role, body) in enumerate(OWN_MESSAGES, start=1):
            session.add(
                AgentMessage(
                    thread_id=own_thread.id, seq=seq, role=role, content={"text": body}
                )
            )
        session.add(
            AgentMessage(
                thread_id=other_thread.id,
                seq=1,
                role="user",
                content={"text": STRANGER_MESSAGE},
            )
        )
        session.commit()
        owner_id, stranger_id = owner.id, stranger.id
    yield MemoryTools(session_factory=factory), owner_id, stranger_id
    engine.dispose()
    drop_database(MEMORY_DB)


@pytest.mark.asyncio
async def test_the_transcript_search_finds_this_users_own_messages(memory_world):
    tools, owner_id, _ = memory_world

    found = await tools.session_search(
        ToolContext(user_id=owner_id), {"query": "lãi suất"}
    )

    assert found["count"] == 2
    assert {match["role"] for match in found["matches"]} == {"user", "assistant"}
    assert all(match["thread_title"] == "Rates" for match in found["matches"])


@pytest.mark.asyncio
async def test_the_transcript_search_ignores_diacritics(memory_world):
    tools, owner_id, _ = memory_world

    found = await tools.session_search(
        ToolContext(user_id=owner_id), {"query": "ty gia"}
    )

    assert found["count"] == 1
    assert "tỷ giá" in found["matches"][0]["excerpt"]


@pytest.mark.asyncio
async def test_the_transcript_search_never_reaches_another_users_thread(memory_world):
    tools, _, stranger_id = memory_world

    mine = await tools.session_search(
        ToolContext(user_id=stranger_id), {"query": "lãi suất"}
    )

    assert mine["count"] == 1
    assert mine["matches"][0]["excerpt"] == STRANGER_MESSAGE


@pytest.mark.asyncio
async def test_a_query_matching_nothing_says_so(memory_world):
    tools, owner_id, _ = memory_world

    found = await tools.session_search(
        ToolContext(user_id=owner_id), {"query": "chứng khoán phái sinh"}
    )

    assert found["matches"] == []
    assert found["reason"] == "no_matching_messages"


@pytest.mark.asyncio
async def test_a_blank_transcript_query_is_refused(memory_world):
    tools, owner_id, _ = memory_world

    with pytest.raises(ValueError, match="must not be blank"):
        await tools.session_search(ToolContext(user_id=owner_id), {"query": " "})


@pytest.mark.asyncio
async def test_a_fact_from_the_conversation_needs_no_url(memory_world):
    tools, owner_id, _ = memory_world
    context = ToolContext(user_id=owner_id)

    remembered = await tools.remember_fact(
        context,
        {"title": "Kỳ nghỉ của người dùng", "body": "Người dùng nghỉ phép tháng chín."},
    )
    recalled = await tools.recall_facts(context, {"query": "ky nghi"})

    assert remembered["remembered"] is True
    assert remembered["source"] == "conversation"
    assert recalled["count"] == 1
    assert recalled["facts"][0]["source_url"] == CONVERSATION_SOURCE


@pytest.mark.asyncio
async def test_a_fact_from_a_page_keeps_where_it_came_from(memory_world):
    tools, owner_id, _ = memory_world
    context = ToolContext(user_id=owner_id)

    await tools.remember_fact(
        context,
        {
            "title": "Chủ tịch Masan",
            "body": "Nguyễn Đăng Quang giữ chức Chủ tịch Hội đồng quản trị.",
            "source_url": "https://example.com/masan/leadership",
            "as_of": "2026-08-17",
        },
    )
    recalled = await tools.recall_facts(context, {"query": "chu tich masan"})

    fact = recalled["facts"][0]
    assert fact["source"] == "example.com"
    assert fact["source_url"] == "https://example.com/masan/leadership"
    assert fact["as_of"].startswith("2026-08-17")


@pytest.mark.asyncio
async def test_a_source_url_that_is_not_a_page_is_refused(memory_world):
    tools, owner_id, _ = memory_world

    with pytest.raises(ValueError, match="absolute http or https URL"):
        await tools.remember_fact(
            ToolContext(user_id=owner_id),
            {"title": "t", "body": "b", "source_url": "file:///etc/passwd"},
        )


@pytest.mark.asyncio
async def test_a_stranger_cannot_recall_this_users_notes(memory_world):
    tools, owner_id, stranger_id = memory_world
    await tools.remember_fact(
        ToolContext(user_id=owner_id),
        {"title": "Số tài khoản", "body": "Ghi chú riêng của người dùng."},
    )

    recalled = await tools.recall_facts(
        ToolContext(user_id=stranger_id), {"query": "so tai khoan"}
    )

    assert recalled["facts"] == []
    assert recalled["reason"] == "no_remembered_facts"


@pytest.mark.asyncio
async def test_an_empty_title_is_refused_before_a_row_is_written(memory_world):
    tools, owner_id, _ = memory_world

    with pytest.raises(ValueError, match="title must be"):
        await tools.remember_fact(
            ToolContext(user_id=owner_id), {"title": "  ", "body": "something"}
        )
