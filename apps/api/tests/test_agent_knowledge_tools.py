"""Remembered claims remain sourced and searchable across separate Turns."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.agent.tools.catalog import ToolContext
from src.agent.tools.knowledge import KnowledgeTools
from src.alpha.models import AgentKnowledge
from src.auth.models import User
from src.core.database import Base

from .eval_store import create_database, drop_database

KNOWLEDGE_DB = "stockmassive_knowledge_test"


@pytest.fixture(scope="module")
def knowledge_world():
    url = create_database(KNOWLEDGE_DB)
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine, tables=[User.__table__, AgentKnowledge.__table__])
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with factory() as session:
        user = User(email="knowledge@example.com", hashed_password="x")
        session.add(user)
        session.commit()
        user_id = user.id
    yield KnowledgeTools(session_factory=factory), user_id
    engine.dispose()
    drop_database(KNOWLEDGE_DB)


@pytest.mark.asyncio
async def test_remember_then_recall_without_diacritics_in_another_turn(knowledge_world):
    tools, user_id = knowledge_world
    context = ToolContext(user_id=user_id, trading_day=date(2026, 8, 17))

    remembered = await tools.remember_fact(
        context,
        {
            "title": "Chủ tịch Masan",
            "body": "Nguyễn Đăng Quang giữ chức Chủ tịch Hội đồng quản trị.",
            "source_url": "https://example.com/masan/leadership",
            "as_of": "2026-08-17",
            "symbol": "MSN",
        },
    )
    recalled = await tools.recall_facts(
        context, {"query": "chu tich masan", "symbol": "MSN"}
    )

    assert remembered["remembered"] is True
    assert recalled["count"] == 1
    claim = recalled["facts"][0]["external_claim"]
    assert claim["claim_class"] == "external_claim"
    assert claim["source_url"] == "https://example.com/masan/leadership"
    assert claim["as_of"].startswith("2026-08-17")


@pytest.mark.asyncio
async def test_a_different_user_cannot_recall_private_memory(knowledge_world):
    tools, _user_id = knowledge_world
    other = ToolContext(user_id=999_999, trading_day=date(2026, 8, 17))

    recalled = await tools.recall_facts(other, {"query": "chu tich masan"})

    assert recalled["facts"] == []
