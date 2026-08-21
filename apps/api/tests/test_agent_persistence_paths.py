"""Thread, transcript, and Tool Call Trace behavior through the public store."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date

import pytest
from sqlalchemy import delete, select

from src.agent.persistence import (
    THREAD_TITLE_LENGTH,
    AgentPersistence,
    thread_title_from,
)
from src.agent.tools import ToolCatalog, ToolContext
from src.alpha.models import AgentThread, Analysis
from src.auth.models import User
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory

SYMBOL = "PATHS"


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture
def owner():
    email = f"paths-{uuid.uuid4().hex}@example.com"
    with get_sync_db() as session:
        user = User(email=email, hashed_password="x")
        session.add(user)
        session.flush()
        user_id = user.id

    yield user_id

    with get_sync_db() as session:
        session.execute(delete(AgentThread).where(AgentThread.user_id == user_id))
        session.execute(delete(User).where(User.id == user_id))
        session.execute(delete(Analysis).where(Analysis.symbol == SYMBOL))


def persistence() -> AgentPersistence:
    return AgentPersistence(session_factory=sync_session_factory)


@pytest.mark.asyncio
async def test_thread_lifecycle_keeps_an_unrelated_shared_analysis(owner):
    store = persistence()
    older = await store.create_thread(owner, title="Older")
    newer = await store.create_thread(owner, title="Newer")
    message = await store.append_message(
        older.id,
        role="user",
        content={"text": "Phân tích PATHS"},
        symbols=(SYMBOL,),
    )
    await store.record_tool_call(
        {
            "thread_id": older.id,
            "request_message_id": message.id,
            "tool_name": "get_analysis",
            "arguments": {"symbol": SYMBOL},
            "result": {"found": False},
            "status": "ok",
            "error": None,
            "latency_ms": 2,
        }
    )
    with get_sync_db() as session:
        session.add(
            Analysis(
                symbol=SYMBOL,
                trading_day=date(2026, 8, 14),
                verdict="watch",
                payload={"stable": True},
                schema_version=7,
            )
        )

    listed = await store.list_threads(owner)
    loaded = await store.read_thread(owner, older.id)
    discussing = await store.threads_discussing(owner, SYMBOL)

    assert [item.id for item in listed] == [older.id, newer.id]
    assert [item.seq for item in loaded.messages] == [1]
    assert loaded.symbols == (SYMBOL,)
    assert [item.id for item in discussing] == [older.id]

    assert await store.delete_thread(owner, older.id) is True
    assert await store.read_thread(owner, older.id) is None
    assert await store.traces_for_request(message.id) == ()
    with get_sync_db() as session:
        assert session.execute(
            select(Analysis).where(Analysis.symbol == SYMBOL)
        ).scalar_one().schema_version == 7


@pytest.mark.asyncio
async def test_concurrent_writers_receive_distinct_gapless_sequences(owner):
    store = persistence()
    thread = await store.create_thread(owner)

    messages = await asyncio.gather(
        *(
            store.append_message(
                thread.id,
                role="user" if index == 0 else "assistant",
                content={"index": index},
            )
            for index in range(8)
        )
    )
    loaded = await store.read_thread(owner, thread.id)

    assert sorted(item.seq for item in messages) == list(range(1, 9))
    assert [item.seq for item in loaded.messages] == list(range(1, 9))


@pytest.mark.asyncio
async def test_each_trace_survives_independently_and_cost_is_summed(owner):
    store = persistence()
    thread = await store.create_thread(owner)
    request = await store.append_message(
        thread.id, role="user", content={"text": "two calls"}
    )

    for index in range(2):
        await store.record_tool_call(
            {
                "thread_id": thread.id,
                "request_message_id": request.id,
                "tool_name": f"tool_{index}",
                "arguments": {"index": index},
                "result": {"index": index},
                "status": "ok",
                "error": None,
                "latency_ms": index + 1,
                "prompt_tokens": 10 + index,
                "completion_tokens": 2 + index,
            }
        )

    traces = await store.traces_for_request(request.id)

    assert [trace.tool_name for trace in traces] == ["tool_0", "tool_1"]
    assert [trace.result for trace in traces] == [{"index": 0}, {"index": 1}]
    assert await store.tool_tokens_for_request(request.id) == 26


@pytest.mark.asyncio
async def test_a_spilled_result_is_noted_on_its_trace_and_still_readable_whole(owner):
    store = persistence()
    thread = await store.create_thread(owner)
    request = await store.append_message(
        thread.id, role="user", content={"text": "one big call"}
    )
    whole = {"symbol": "FPT", "rows": [{"close": 90.0 + day} for day in range(30)]}
    await store.record_tool_call(
        {
            "thread_id": thread.id,
            "request_message_id": request.id,
            "tool_name": "get_price_series",
            "tool_call_id": "call_0",
            "arguments": {"symbol": "FPT"},
            "result": whole,
            "status": "ok",
            "error": None,
        }
    )

    updated = await store.record_spillover(request.id, {"call_0": 18_682})

    (trace,) = await store.traces_for_request(request.id)
    assert updated == 1
    assert trace.tool_call_id == "call_0"
    assert trace.spilled_bytes == 18_682
    # The model saw a preview; the record kept the whole of it, addressable by
    # the same id the model cites in an evidence reference.
    assert await store.tool_result(request.id, "call_0") == whole
    # And not through another Turn's request: the scope is the anchor, not the id.
    assert await store.tool_result(request.id + 1_000, "call_0") is None


@pytest.mark.asyncio
async def test_a_spill_for_a_call_nobody_traced_changes_nothing(owner):
    store = persistence()
    thread = await store.create_thread(owner)
    request = await store.append_message(
        thread.id, role="user", content={"text": "no traces"}
    )

    assert await store.record_spillover(request.id, {"call_0": 4_096}) == 0
    assert await store.record_spillover(request.id, {}) == 0


@pytest.mark.asyncio
async def test_catalog_unknown_tool_is_persisted_with_usage(owner):
    store = persistence()
    thread = await store.create_thread(owner)
    request = await store.append_message(
        thread.id, role="user", content={"text": "call missing"}
    )
    catalog = ToolCatalog((), trace_writer=store.record_tool_call)

    await catalog.dispatch(
        "missing",
        {},
        ToolContext(user_id=owner, trading_day=date(2026, 8, 14)),
        thread_id=thread.id,
        request_message_id=request.id,
        prompt_tokens=13,
        completion_tokens=5,
    )

    (trace,) = await store.traces_for_request(request.id)
    assert trace.status == "unknown_tool"
    assert trace.prompt_tokens == 13
    assert trace.completion_tokens == 5


@pytest.mark.asyncio
async def test_the_opening_question_names_the_thread(owner):
    store = persistence()
    thread = await store.create_thread(owner)

    await store.create_turn(
        user_id=owner,
        thread_id=thread.id,
        turn_id=uuid.uuid4(),
        user_text="  Vì sao PATHS bị hạ điểm\n phiên hôm qua?  ",
    )

    named = await store.read_thread(owner, uuid.UUID(str(thread.id)))
    assert named is not None
    assert named.title == "Vì sao PATHS bị hạ điểm phiên hôm qua?"


@pytest.mark.asyncio
async def test_a_later_question_does_not_rename_the_thread(owner):
    store = persistence()
    thread = await store.create_thread(owner)

    for text in ("Câu hỏi đầu", "Câu hỏi sau"):
        await store.create_turn(
            user_id=owner,
            thread_id=thread.id,
            turn_id=uuid.uuid4(),
            user_text=text,
        )

    named = await store.read_thread(owner, uuid.UUID(str(thread.id)))
    assert named is not None
    assert named.title == "Câu hỏi đầu"


@pytest.mark.asyncio
async def test_a_thread_the_user_named_keeps_that_name(owner):
    store = persistence()
    thread = await store.create_thread(owner, title="Sổ tay phiên chiều")

    await store.create_turn(
        user_id=owner,
        thread_id=thread.id,
        turn_id=uuid.uuid4(),
        user_text="Phân tích PATHS giúp tôi",
    )

    named = await store.read_thread(owner, uuid.UUID(str(thread.id)))
    assert named is not None
    assert named.title == "Sổ tay phiên chiều"


def test_a_long_question_is_cut_at_a_word_with_an_ellipsis():
    title = thread_title_from(
        "Vì sao nhóm ngân hàng vẫn giữ được đà tăng trong khi thanh khoản "
        "toàn thị trường giảm mạnh?"
    )
    assert title is not None
    assert len(title) <= THREAD_TITLE_LENGTH + 1
    assert title.endswith("…")
    assert not title.endswith(" …")


def test_a_blank_question_names_nothing():
    assert thread_title_from("   \n  ") is None
