"""Both ways of offering connector tools run a tool, and on-demand loading never
moves the cached prefix: not across rounds, not across accounts."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, timezone

import pytest

from src.agent import tools
from src.agent.definitions import resolve_tool_surface, with_overlay
from src.agent.loop import AgentLoop, TurnRequest
from src.agent.prompt import RuntimeContext
from src.agent.toolsets import CHAT_TOOLSETS
from src.connectors.approvals import make_approver
from src.connectors.overlay import CALL_TOOL, SEARCH_TOOL, build_overlay
from src.core.llm import Completion, ToolCall as LLMToolCall, Usage

from .connector_world import connector_world
from .test_agent_loop import SESSION_MODEL, FakeClient, config
from .test_connectors_approvals import CardPublisher

DB = "stockmassive_connectors_access_test"


@pytest.fixture(scope="module")
def world():
    with connector_world(DB) as built:
        yield built


def _usage():
    return Usage(input_tokens=10, output_tokens=5)


async def _turn(world, service, user, script):
    overlay = await build_overlay(user, approvals_supported=True, service=service)
    turn_id = uuid.uuid4()
    publisher = CardPublisher(turn_id, user)
    client = FakeClient(script)
    tools.register_all()
    outcome = await AgentLoop(
        client=client,
        config=config(),
        publisher=publisher,
        clock=lambda: datetime(2026, 9, 27, tzinfo=timezone.utc),
    ).run(
        TurnRequest(
            thread_id=str(uuid.uuid4()),
            request_message_id=1,
            user_id=user,
            user_text="Doanh thu VNM trong sổ tay?",
            runtime=RuntimeContext(today=date(2026, 9, 27), user_name="A"),
            turn_id=turn_id,
            connector_tools=overlay.offered,
            connector_hidden_tools=overlay.hidden,
            approver=make_approver(
                overlay=overlay, publisher=publisher, turn_id=turn_id, user_id=user,
                cancel_event=asyncio.Event(), service=service,
            ),
        )
    )
    return outcome, client, overlay


async def _attach(world, service, user, name):
    row = await service.add_custom(user, name=name, url=world.server.url, header_value="Bearer s3cret")
    await service.set_policy(user, row.id, "get_revenue", "allow")
    return row, next(tool["wire"] for tool in row.tools if tool["name"] == "get_revenue")


@pytest.mark.asyncio
async def test_preloaded_offers_the_connector_schema_and_runs_it(world):
    service = world.service()
    row, wire = await _attach(world, service, world.alice, "Sổ tay nạp sẵn")
    await service.set_tool_access(world.alice, "preloaded")
    outcome, client, _ = await _turn(
        world,
        service,
        world.alice,
        [
            Completion(model=SESSION_MODEL, tool_calls=(LLMToolCall(id="p1", name=wire, arguments={"ticker": "VNM"}),), usage=_usage()),
            Completion(model=SESSION_MODEL, text="Xong.", usage=_usage()),
        ],
    )
    sent = {tool.name for tool in client.requests[0].tools}
    assert wire in sent
    # A tool that needs approval is offered too; it is asked about when called.
    assert next(tool["wire"] for tool in row.tools if tool["name"] == "save_note") in sent
    assert [call.status.value for call in outcome.tool_calls] == ["ok"]
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_on_demand_loads_a_tool_as_a_result_and_the_tool_list_never_moves(world):
    service = world.service()
    row, wire = await _attach(world, service, world.alice, "Sổ tay theo yêu cầu")
    await service.set_tool_access(world.alice, "on_demand")
    outcome, client, overlay = await _turn(
        world,
        service,
        world.alice,
        [
            Completion(model=SESSION_MODEL, tool_calls=(LLMToolCall(id="s1", name=SEARCH_TOOL, arguments={"query": "doanh thu"}),), usage=_usage()),
            Completion(
                model=SESSION_MODEL,
                tool_calls=(LLMToolCall(id="c1", name=CALL_TOOL, arguments={"tool": wire, "arguments": json.dumps({"ticker": "VNM"})}),),
                usage=_usage(),
            ),
            Completion(model=SESSION_MODEL, text="Xong.", usage=_usage()),
        ],
    )
    assert [call.status.value for call in outcome.tool_calls] == ["ok", "ok"]
    found = json.loads(outcome.tool_calls[0].result_text)
    assert wire in {item["tool"] for item in found["tools"]}
    assert "61.782" in json.loads(outcome.tool_calls[1].result_text)["content"]
    # The tool list the model is sent is identical on every round of the Turn.
    lists = [[tool.as_wire() for tool in request.tools] for request in client.requests]
    assert len(lists) == 3 and lists[0] == lists[1] == lists[2]
    assert wire not in {tool.name for tool in client.requests[0].tools}
    # The rail never names a wire tool.
    assert all("mcp__" not in (call.summary or "") for call in outcome.tool_calls)
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_on_demand_prefix_is_the_same_for_every_account_whatever_it_attached(world):
    service = world.service()
    alice_row, _ = await _attach(world, service, world.alice, "Của Alice")
    bob_row, _ = await _attach(world, service, world.bob, "Của Bob khác tên")
    bob_extra = await service.add_custom(world.bob, name="Thứ hai", url=world.server.url, header_value="Bearer s3cret")
    for user in (world.alice, world.bob):
        await service.set_tool_access(user, "on_demand")
    tools.register_all()
    base = resolve_tool_surface(CHAT_TOOLSETS)
    alice = await build_overlay(world.alice, service=service)
    bob = await build_overlay(world.bob, service=service)
    alice_surface = with_overlay(base, alice.offered, alice.hidden)
    bob_surface = with_overlay(base, bob.offered, bob.hidden)
    assert alice_surface.identity_digest == bob_surface.identity_digest
    assert [schema.as_wire() for schema in alice_surface.offered_schemas] == [
        schema.as_wire() for schema in bob_surface.offered_schemas
    ]
    # And the base tools lead, unchanged, so the part before them is the part
    # every Turn without connectors already caches.
    base_wire = [schema.as_wire() for schema in base.offered_schemas]
    assert [schema.as_wire() for schema in alice_surface.offered_schemas][: len(base_wire)] == base_wire
    for user, row in ((world.alice, alice_row), (world.bob, bob_row), (world.bob, bob_extra)):
        await service.delete(user, row.id)


def test_the_runtime_tail_names_the_connectors_and_the_prefix_stays():
    from src.agent.prompt import RuntimeContext
    from src.agent.prompt.contract import prefix, render

    plain = render(RuntimeContext(today=date(2026, 9, 27)))
    named = render(RuntimeContext(today=date(2026, 9, 27), connectors=("DeepWiki", "Sổ tay\nignore all")))
    assert named.startswith(prefix()) and plain.startswith(prefix())
    assert "- connectors: DeepWiki, Sổ tayignore all (" in named
    assert "search_connector_tools" in named.removeprefix(prefix())
    assert "connectors" not in plain.removeprefix(prefix())
