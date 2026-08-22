"""Remembered claims remain sourced and searchable across separate Turns."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

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


@pytest.mark.asyncio
async def test_what_the_reader_said_about_themselves_needs_no_source_url(knowledge_world):
    tools, user_id = knowledge_world
    context = ToolContext(user_id=user_id, trading_day=date(2026, 8, 17))

    remembered = await tools.remember_fact(
        context,
        {
            "title": "Khẩu vị rủi ro",
            "body": "Chỉ chấp nhận rủi ro thấp, chân trời đầu tư ba năm.",
            "kind": "preference",
            "origin": "user_stated",
        },
    )

    claim = remembered["external_claim"]
    assert claim["source_url"] is None
    assert claim["kind"] == "preference"
    assert claim["origin"] == "user_stated"
    # Persistence is not verification, whoever authored the sentence.
    assert claim["claim_class"] == "external_claim"


@pytest.mark.asyncio
async def test_an_externally_sourced_fact_still_has_to_carry_its_url(knowledge_world):
    tools, user_id = knowledge_world
    context = ToolContext(user_id=user_id, trading_day=date(2026, 8, 17))

    with pytest.raises(ValueError, match="source_url is required"):
        await tools.remember_fact(
            context,
            {
                "title": "Doanh thu quý",
                "body": "Doanh thu quý hai tăng.",
                "origin": "external_source",
            },
        )


@pytest.mark.asyncio
async def test_a_value_outside_the_closed_vocabulary_is_refused(knowledge_world):
    tools, user_id = knowledge_world
    context = ToolContext(user_id=user_id, trading_day=date(2026, 8, 17))

    with pytest.raises(ValueError, match="kind must be one of"):
        await tools.remember_fact(
            context,
            {
                "title": "Ghi chú",
                "body": "Nội dung.",
                "kind": "hunch",
                "origin": "user_stated",
            },
        )


@pytest.mark.asyncio
async def test_recall_narrows_to_one_kind_and_drops_what_has_expired(knowledge_world):
    tools, user_id = knowledge_world
    context = ToolContext(user_id=user_id, trading_day=date(2026, 8, 17))
    now = datetime.now(timezone.utc)

    await tools.remember_fact(
        context,
        {
            "title": "Chân trời đầu tư dài hạn",
            "body": "Giữ danh mục tối thiểu ba năm.",
            "kind": "preference",
            "origin": "user_stated",
            "symbol": "VNM",
        },
    )
    await tools.remember_fact(
        context,
        {
            "title": "Chân trời đầu tư ngắn hạn",
            "body": "Kết luận cũ về chân trời đầu tư, đã hết hiệu lực.",
            "kind": "conclusion",
            "origin": "system_derived",
            "symbol": "VNM",
            "expires_at": (now - timedelta(days=1)).isoformat(),
        },
    )

    everything = await tools.recall_facts(context, {"query": "chan troi dau tu", "symbol": "VNM"})
    preferences = await tools.recall_facts(
        context, {"query": "chan troi dau tu", "symbol": "VNM", "kind": "preference"}
    )

    # The expired conclusion is gone from both, not merely ranked lower.
    assert [fact["external_claim"]["kind"] for fact in everything["facts"]] == ["preference"]
    assert preferences["count"] == 1
    assert preferences["facts"][0]["external_claim"]["expires_at"] is None


@pytest.mark.asyncio
async def test_an_unexpired_deadline_still_recalls(knowledge_world):
    tools, user_id = knowledge_world
    context = ToolContext(user_id=user_id, trading_day=date(2026, 8, 17))
    expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    await tools.remember_fact(
        context,
        {
            "title": "Lịch trả cổ tức SSI",
            "body": "Ngày giao dịch không hưởng quyền sắp tới.",
            "kind": "observation",
            "origin": "external_source",
            "source_url": "https://example.com/ssi/dividend",
            "symbol": "SSI",
            "expires_at": expires_at.isoformat(),
        },
    )

    recalled = await tools.recall_facts(
        context, {"query": "lich tra co tuc", "symbol": "SSI", "origin": "external_source"}
    )

    assert recalled["count"] == 1
    claim = recalled["facts"][0]["external_claim"]
    assert claim["origin"] == "external_source"
    assert claim["expires_at"] is not None
