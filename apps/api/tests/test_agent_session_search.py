"""Earlier conversations come back by argument shape alone, and without an LLM."""

from __future__ import annotations

import ast
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.agent.tools import session_search as session_search_module
from src.agent.tools.catalog import ToolContext, recovery_hint
from src.agent.tools.session_search import NO_MATCHING_MESSAGES, SessionSearchTools
from src.alpha.models import AgentMessage, AgentThread
from src.auth.models import User
from src.core.database import Base
from src.core.llm import client as llm_client

from .eval_store import create_database, drop_database

SESSION_SEARCH_DB = "stockmassive_session_search_test"

BANKING_THREAD = uuid4()
MACRO_THREAD = uuid4()
STRANGER_THREAD = uuid4()

BANKING_MESSAGES = (
    (1, "user", "Tôi muốn xem cổ phiếu FPT có tăng trưởng tốt không"),
    (2, "assistant", "FPT có tăng trưởng doanh thu ổn định trong bốn quý gần nhất."),
    (3, "user", "Còn ngành thép thì sao"),
    (4, "assistant", "Nhóm thép biến động mạnh hơn phần còn lại của thị trường."),
    (5, "user", "Cảm ơn, tạm thời vậy đã"),
)


@pytest.fixture(scope="module")
def session_world():
    url = create_database(SESSION_SEARCH_DB)
    engine = create_engine(url, future=True)
    Base.metadata.create_all(
        engine,
        tables=[User.__table__, AgentThread.__table__, AgentMessage.__table__],
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with factory() as session:
        owner = User(email="owner@example.com", hashed_password="x")
        stranger = User(email="stranger@example.com", hashed_password="x")
        session.add_all([owner, stranger])
        session.commit()
        owner_id, stranger_id = owner.id, stranger.id

        session.add_all(
            [
                AgentThread(
                    id=BANKING_THREAD,
                    user_id=owner_id,
                    title="Cổ phiếu và tăng trưởng",
                    updated_at=datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc),
                ),
                AgentThread(
                    id=MACRO_THREAD,
                    user_id=owner_id,
                    title="Vĩ mô",
                    updated_at=datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc),
                ),
                AgentThread(
                    id=STRANGER_THREAD,
                    user_id=stranger_id,
                    title="Riêng tư",
                    updated_at=datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc),
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                AgentMessage(
                    thread_id=BANKING_THREAD, seq=seq, role=role, content={"text": text}
                )
                for seq, role, text in BANKING_MESSAGES
            ]
        )
        session.add_all(
            [
                AgentMessage(
                    thread_id=MACRO_THREAD,
                    seq=1,
                    role="user",
                    content={"text": "Lãi suất điều hành ảnh hưởng thế nào"},
                ),
                AgentMessage(
                    thread_id=STRANGER_THREAD,
                    seq=1,
                    role="user",
                    content={"text": "Cổ phiếu nào đang tăng trưởng nhanh nhất"},
                ),
            ]
        )
        session.commit()

    yield SessionSearchTools(session_factory=factory), owner_id, stranger_id
    engine.dispose()
    drop_database(SESSION_SEARCH_DB)


@pytest.fixture()
def owner_context(session_world):
    _tools, owner_id, _stranger_id = session_world
    return ToolContext(user_id=owner_id, trading_day=date(2026, 8, 20))


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["co phieu", "cổ phiếu", "tang truong", "tăng trưởng"])
async def test_vietnamese_matches_with_or_without_diacritics(
    session_world, owner_context, query
):
    tools, _owner_id, _stranger_id = session_world

    result = await tools.session_search(owner_context, {"query": query})

    assert result["mode"] == "search"
    assert result["reason"] is None
    assert result["count"] >= 1
    excerpts = [message["external_claim"]["excerpt"] for message in result["messages"]]
    assert any("cổ phiếu" in text or "tăng trưởng" in text for text in excerpts)
    # Every hit is one of this reader's, never the stranger's identical wording.
    assert {message["external_claim"]["thread_id"] for message in result["messages"]} <= {
        str(BANKING_THREAD),
        str(MACRO_THREAD),
    }


@pytest.mark.asyncio
async def test_an_excerpt_stays_an_external_claim(session_world, owner_context):
    tools, _owner_id, _stranger_id = session_world

    result = await tools.session_search(owner_context, {"query": "tang truong"})

    claim = result["messages"][0]["external_claim"]
    assert claim["claim_class"] == "external_claim"
    assert set(claim) == {
        "thread_id",
        "seq",
        "role",
        "created_at",
        "excerpt",
        "claim_class",
    }


@pytest.mark.asyncio
async def test_a_query_with_a_thread_searches_inside_that_thread(
    session_world, owner_context
):
    tools, _owner_id, _stranger_id = session_world

    result = await tools.session_search(
        owner_context, {"query": "tang truong", "thread_id": str(MACRO_THREAD)}
    )

    assert result["thread_id"] == str(MACRO_THREAD)
    assert result["count"] == 0
    assert result["reason"] == NO_MATCHING_MESSAGES


@pytest.mark.asyncio
async def test_an_anchor_returns_the_window_around_it(session_world, owner_context):
    tools, _owner_id, _stranger_id = session_world

    result = await tools.session_search(
        owner_context, {"thread_id": str(BANKING_THREAD), "anchor": 5}
    )

    assert result["mode"] == "window"
    # Radius three, read forwards, and clipped by what the thread actually holds.
    assert [message["external_claim"]["seq"] for message in result["messages"]] == [2, 3, 4, 5]


@pytest.mark.asyncio
async def test_a_thread_alone_replays_it_in_written_order(session_world, owner_context):
    tools, _owner_id, _stranger_id = session_world

    result = await tools.session_search(
        owner_context, {"thread_id": str(BANKING_THREAD)}
    )

    assert result["mode"] == "thread"
    assert [message["external_claim"]["seq"] for message in result["messages"]] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert [message["external_claim"]["role"] for message in result["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
        "user",
    ]


@pytest.mark.asyncio
async def test_no_arguments_lists_the_recent_threads(session_world, owner_context):
    tools, _owner_id, _stranger_id = session_world

    result = await tools.session_search(owner_context, {})

    assert result["mode"] == "recent_threads"
    assert [thread["thread_id"] for thread in result["threads"]] == [
        str(MACRO_THREAD),
        str(BANKING_THREAD),
    ]
    assert [thread["message_count"] for thread in result["threads"]] == [1, 5]
    assert [thread["title"] for thread in result["threads"]] == [
        "Vĩ mô",
        "Cổ phiếu và tăng trưởng",
    ]


@pytest.mark.asyncio
async def test_another_readers_thread_is_indistinguishable_from_one_that_is_absent(
    session_world, owner_context
):
    tools, _owner_id, _stranger_id = session_world

    borrowed = await tools.session_search(
        owner_context, {"thread_id": str(STRANGER_THREAD)}
    )
    invented = await tools.session_search(owner_context, {"thread_id": str(uuid4())})

    assert borrowed["messages"] == []
    assert borrowed["reason"] == NO_MATCHING_MESSAGES
    assert invented["reason"] == borrowed["reason"]


@pytest.mark.asyncio
async def test_the_empty_refusal_carries_a_recovery_hint(session_world, owner_context):
    tools, _owner_id, _stranger_id = session_world

    result = await tools.session_search(
        owner_context, {"query": "khong co tu nao nhu the nay"}
    )

    assert result["reason"] == NO_MATCHING_MESSAGES
    assert recovery_hint(result) is not None


@pytest.mark.asyncio
async def test_a_malformed_thread_id_is_refused_before_the_query(
    session_world, owner_context
):
    tools, _owner_id, _stranger_id = session_world

    with pytest.raises(ValueError, match="thread_id must be a UUID"):
        await tools.session_search(owner_context, {"thread_id": "not-a-uuid"})


def test_the_module_cannot_reach_the_llm_layer():
    """Structural half of the zero-cost promise: there is no import to reach it by."""

    tree = ast.parse(Path(session_search_module.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")

    assert [name for name in imported if name.startswith("src.core.llm")] == []


@pytest.mark.asyncio
async def test_every_mode_completes_with_the_llm_chokepoints_booby_trapped(
    session_world, owner_context, monkeypatch
):
    """Behavioural half: both ways to reach a model raise, and all four modes answer."""

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("session_search must not call an LLM")

    monkeypatch.setattr(llm_client, "build_client", _forbidden)
    monkeypatch.setattr(llm_client.ReservedLLMClient, "complete", _forbidden)

    tools, _owner_id, _stranger_id = session_world
    results = [
        await tools.session_search(owner_context, {"query": "co phieu"}),
        await tools.session_search(
            owner_context, {"thread_id": str(BANKING_THREAD), "anchor": 3}
        ),
        await tools.session_search(owner_context, {"thread_id": str(BANKING_THREAD)}),
        await tools.session_search(owner_context, {}),
    ]

    assert [result["mode"] for result in results] == [
        "search",
        "window",
        "thread",
        "recent_threads",
    ]
    assert all(result["count"] > 0 for result in results)
