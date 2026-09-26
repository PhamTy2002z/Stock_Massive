"""The figure check inside a Turn: one repair, then labels, and a ledger every time.

The loop is driven by a scripted route and one stub page read whose payload has
the shape ``fetch_url`` really returns, so the figure check sees a real source.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest

from .agent_tool_world import isolated_registry
from .test_agent_loop import (
    FakeClient,
    answer,
    config,
    entry,
    turn_request,
)
from src.agent import registry
from src.agent.evidence.grounding import LEDGER_VERSION
from src.agent.loop import AgentLoop, TurnStatus
from src.agent.prompt import RuntimeContext
from src.core.llm import Completion, LLMError, ToolCall, Usage

NOW = datetime(2026, 9, 26, 7, 0, tzinfo=timezone.utc)


async def _page(_context: registry.ToolContext, arguments) -> Any:
    url = str(arguments.get("url") or "https://cafef.vn/stb.chn")
    return {
        "url": url,
        "canonical_url": url,
        "title": "Sacombank công bố kết quả",
        "publisher": "cafef.vn",
        "source_class": "media",
        "content": "Tỷ lệ nợ xấu của Sacombank là 2,15% tại ngày 30/06/2026.",
        "retrieved_at": "2026-09-26T14:00:00+07:00",
        "content_sha256": "c" * 64,
        "publication": {"publishedAt": "2026-08-20T08:00:00+07:00"},
    }


@pytest.fixture(autouse=True)
def _world():
    with isolated_registry():
        registry.register(entry("web_search"))
        registry.register(entry("fetch_url", _page))
        for name in ("session_search", "recall_facts", "remember_fact"):
            registry.register(entry(name))
        yield


def reads_page() -> Completion:
    return Completion(
        model="m",
        tool_calls=(
            ToolCall(id="c1", name="fetch_url", arguments={"url": "https://cafef.vn/stb.chn"}, output_index=0),
        ),
        usage=Usage(input_tokens=10, output_tokens=5),
    )


def run(client: FakeClient):
    agent = AgentLoop(client=client, config=config(), clock=lambda: NOW)
    request = turn_request(
        user_text="Nợ xấu STB bao nhiêu?",
        runtime=RuntimeContext(today=date(2026, 9, 26), user_name="Ty"),
    )
    return agent.run(request, cancelled=lambda: False)


@pytest.mark.asyncio
async def test_an_invented_figure_is_sent_back_once_and_the_rewrite_is_kept():
    client = FakeClient(
        [
            reads_page(),
            answer("Nợ xấu của STB là 6,31%."),
            answer("Nợ xấu của STB là 2,15% tại ngày 30/06/2026."),
        ]
    )

    outcome = await run(client)

    assert outcome.status is TurnStatus.COMPLETE
    assert len(client.requests) == 3
    note = client.requests[2].messages[-1].content
    assert '"6,31%"' in note and "BẢN NHÁP" in note
    # The repair asks for prose, not for more tools.
    assert client.requests[2].tools == ()
    assert outcome.answer.startswith("Nợ xấu của STB là 2,15% [1 · 20/08/2026]")
    assert "6,31%" not in outcome.answer
    ledger = outcome.claim_ledger
    assert ledger["version"] == LEDGER_VERSION
    assert [claim["verdict"] for claim in ledger["claims"]] == ["single_source"]


@pytest.mark.asyncio
async def test_a_figure_still_unsupported_after_the_repair_is_labelled_not_removed():
    client = FakeClient(
        [
            reads_page(),
            answer("Nợ xấu của STB là 6,31%."),
            answer("Nợ xấu của STB là 6,30%."),
        ]
    )

    outcome = await run(client)

    assert len(client.requests) == 3
    assert "[chưa kiểm chứng]" in outcome.answer
    assert [claim["verdict"] for claim in outcome.claim_ledger["claims"]] == ["unsupported"]


@pytest.mark.asyncio
async def test_a_rewrite_that_makes_things_worse_keeps_the_draft():
    client = FakeClient(
        [
            reads_page(),
            answer("Nợ xấu 2,15%, CAR 8,49%."),
            answer("Nợ xấu 3,33%, CAR 8,49%, ROE 12,34%."),
        ]
    )

    outcome = await run(client)

    assert outcome.answer.startswith("Nợ xấu 2,15% [1 · 20/08/2026], CAR 8,49% [chưa kiểm chứng].")


@pytest.mark.asyncio
async def test_a_repair_the_route_cannot_answer_keeps_the_labelled_draft():
    client = FakeClient([reads_page(), answer("Nợ xấu của STB là 6,31%."), LLMError("down")])

    outcome = await run(client)

    assert outcome.status is TurnStatus.COMPLETE
    assert outcome.answer.startswith("Nợ xấu của STB là 6,31% [chưa kiểm chứng].")


@pytest.mark.asyncio
async def test_an_answer_whose_figures_all_check_out_costs_no_repair():
    client = FakeClient([reads_page(), answer("Nợ xấu 2,15% tại ngày 30/06/2026.")])

    outcome = await run(client)

    assert len(client.requests) == 2
    assert "[1 · 20/08/2026]" in outcome.answer
    assert "**Nguồn số liệu**" in outcome.answer


@pytest.mark.asyncio
async def test_an_answer_without_figures_still_leaves_a_ledger():
    client = FakeClient([answer("Chào bạn, bạn muốn tìm hiểu mã nào?")])

    outcome = await run(client)

    assert outcome.answer == "Chào bạn, bạn muốn tìm hiểu mã nào?"
    assert outcome.claim_ledger is not None
    assert outcome.claim_ledger["claims"] == []
