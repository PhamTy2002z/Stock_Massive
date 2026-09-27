"""Approval inside a Turn: allow once, always, deny, timeout, an app that cannot
draw the card, calls approved independently, and a connector switched off
while its call waits."""

from __future__ import annotations

import asyncio
import math
import time
import uuid
from datetime import date, datetime, timezone
from typing import Any

import pytest

from src.agent import registry
from src.agent.definitions import ResolvedToolSurface, with_overlay
from src.agent.executor import APPROVAL_REQUIRED, ToolCall, ToolExecutor
from src.agent.loop import AgentLoop, TurnRequest
from src.agent.prompt import RuntimeContext
from src.connectors.approvals import hub, make_approver
from src.connectors.overlay import CALL_TOOL, build_overlay
from src.core.llm import Completion, ToolCall as LLMToolCall, Usage

from .connector_world import connector_world
from .test_agent_loop import SESSION_MODEL, FakeClient, config

DB = "stockmassive_connectors_approvals_test"


@pytest.fixture(scope="module")
def world():
    with connector_world(DB) as built:
        yield built


class CardPublisher:
    """Records approval cards and answers each one the way a test says."""

    def __init__(self, turn_id: uuid.UUID, user_id: int, answers: dict[str, tuple[float, str]] | None = None):
        self.turn_id, self.user_id = turn_id, user_id
        self.answers = answers or {}
        self.requested: list[dict[str, Any]] = []
        self.resolved: list[tuple[str, str]] = []

    def approval_requested(self, card):
        self.requested.append(dict(card))
        answer = self.answers.get(card["tool"])
        if answer is not None:
            delay, decision = answer
            asyncio.get_running_loop().call_later(
                delay,
                lambda: hub.resolve(user_id=self.user_id, turn_id=self.turn_id, call_id=card["call_id"], decision=decision),
            )

    def approval_resolved(self, call_id, decision):
        self.resolved.append((call_id, decision))

    # The loop's own events, unused here.
    def content_delta(self, *args, **kwargs):
        pass

    def tool_call(self, payload):
        pass

    def progress(self, part):
        pass


async def _setup(world, *, mode="preloaded", approvals=True, timeout=5.0, answers=None):
    service = world.service()
    row = await service.add_custom(world.alice, name=f"Sổ tay {uuid.uuid4().hex[:4]}", url=world.server.url, header_value="Bearer s3cret")
    await service.set_tool_access(world.alice, mode)
    overlay = await build_overlay(world.alice, approvals_supported=approvals, service=service)
    turn_id = uuid.uuid4()
    publisher = CardPublisher(turn_id, world.alice, answers)
    approver = make_approver(
        overlay=overlay, publisher=publisher, turn_id=turn_id, user_id=world.alice,
        cancel_event=asyncio.Event(), service=service, timeout=timeout,
    )
    surface = with_overlay(
        ResolvedToolSurface(tools=(), registry_generation=0, expanded_names=(), expires_at=math.inf),
        overlay.offered,
        overlay.hidden,
    )
    executor = ToolExecutor(context=registry.ToolContext(user_id=world.alice), surface=surface, approver=approver)
    wires = {tool["name"]: tool["wire"] for tool in row.tools}
    return service, row, executor, publisher, wires


async def _run(executor, calls):
    await executor.approve(calls)
    return (await executor.run(calls)).results


@pytest.mark.asyncio
async def test_allow_once_runs_the_call_and_asks_again_next_time(world):
    service, row, executor, publisher, wires = await _setup(world, answers={"get_revenue": (0.05, "allow_once")})
    [result] = await _run(executor, [ToolCall(id="a1", name=wires["get_revenue"], arguments={"ticker": "VNM"})])
    assert result.ok, result.text
    assert publisher.requested[0]["connector"].startswith("Sổ tay")
    assert publisher.requested[0]["arguments_preview"] == '{"ticker": "VNM"}'
    assert publisher.resolved == [("a1", "allow_once")]
    reread, _ = await service.get(world.alice, row.id)
    assert "get_revenue" not in (reread.policies or {})
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_always_runs_the_call_and_keeps_allow_for_that_tool(world):
    service, row, executor, publisher, wires = await _setup(world, answers={"get_revenue": (0.05, "always")})
    [result] = await _run(executor, [ToolCall(id="b1", name=wires["get_revenue"], arguments={"ticker": "FPT"})])
    assert result.ok
    reread, _ = await service.get(world.alice, row.id)
    assert reread.policies["get_revenue"] == "allow"
    overlay = await build_overlay(world.alice, approvals_supported=True, service=service)
    rule = next(tool for tool in overlay.offered if tool.name == wires["get_revenue"]).permission_rules[0]
    assert rule.action.value == "allow"
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_deny_and_timeout_both_reach_the_model_as_approval_required(world):
    service, row, executor, publisher, wires = await _setup(world, timeout=0.2, answers={"get_revenue": (0.05, "deny")})
    denied, timed_out = await _run(
        executor,
        [
            ToolCall(id="c1", name=wires["get_revenue"], arguments={"ticker": "VNM"}),
            ToolCall(id="c2", name=wires["save_note"], arguments={"text": "ghi chú"}),
        ],
    )
    assert denied.error == APPROVAL_REQUIRED and "declined" in denied.text
    assert timed_out.error == APPROVAL_REQUIRED and "five minutes" in timed_out.text
    assert ("save_note", {"text": "ghi chú"}) not in world.server.calls
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_an_app_that_cannot_draw_the_card_is_refused_at_once(world):
    service, row, executor, publisher, wires = await _setup(world, approvals=False, timeout=30)
    started = time.monotonic()
    [result] = await _run(executor, [ToolCall(id="d1", name=wires["get_revenue"], arguments={"ticker": "VNM"})])
    assert time.monotonic() - started < 2
    assert result.error == APPROVAL_REQUIRED and "cannot show approval" in result.text
    assert publisher.requested == []
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_two_calls_in_one_round_are_approved_independently(world):
    service, row, executor, publisher, wires = await _setup(
        world, answers={"get_revenue": (0.15, "allow_once"), "save_note": (0.05, "deny")}
    )
    read, write = await _run(
        executor,
        [
            ToolCall(id="e1", name=wires["get_revenue"], arguments={"ticker": "HPG"}),
            ToolCall(id="e2", name=wires["save_note"], arguments={"text": "x"}),
        ],
    )
    assert {card["call_id"] for card in publisher.requested} == {"e1", "e2"}
    assert read.ok and write.error == APPROVAL_REQUIRED
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_always_is_refused_for_a_write(world):
    service, row, executor, publisher, wires = await _setup(world, timeout=0.5)
    task = asyncio.ensure_future(_run(executor, [ToolCall(id="f1", name=wires["save_note"], arguments={"text": "x"})]))
    while not publisher.requested:
        await asyncio.sleep(0.01)
    assert publisher.requested[0]["can_always"] is False
    with pytest.raises(PermissionError):
        hub.resolve(user_id=world.alice, turn_id=publisher.turn_id, call_id="f1", decision="always")
    # And nobody else can answer it.
    assert not hub.resolve(user_id=world.bob, turn_id=publisher.turn_id, call_id="f1", decision="allow_once")
    [result] = await task
    assert result.error == APPROVAL_REQUIRED
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("how", ["disable", "delete"])
async def test_switching_a_connector_off_settles_its_waiting_call(world, how):
    service, row, executor, publisher, wires = await _setup(world, timeout=30)
    task = asyncio.ensure_future(_run(executor, [ToolCall(id="g1", name=wires["get_revenue"], arguments={"ticker": "VNM"})]))
    while not publisher.requested:
        await asyncio.sleep(0.01)
    if how == "disable":
        await service.set_enabled(world.alice, row.id, False)
    else:
        await service.delete(world.alice, row.id)
    [result] = await asyncio.wait_for(task, 5)
    assert result.error == APPROVAL_REQUIRED and "switched off or removed" in result.text
    assert publisher.resolved == [("g1", "connector_off")]
    if how == "disable":
        await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_the_on_demand_pair_routes_approval_to_the_inner_tool(world):
    service, row, executor, publisher, wires = await _setup(world, mode="on_demand", answers={"get_revenue": (0.05, "allow_once")})
    call = ToolCall(id="h1", name=CALL_TOOL, arguments={"tool": wires["get_revenue"], "arguments": '{"ticker": "MWG"}'})
    [result] = await _run(executor, [call])
    assert result.ok, result.text
    assert publisher.requested[0]["tool"] == "get_revenue"
    unknown = ToolCall(id="h2", name=CALL_TOOL, arguments={"tool": "remember_fact", "arguments": "{}"})
    [refused] = await _run(executor, [unknown])
    assert refused.error == "unknown_tool"
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_waiting_for_the_reader_is_not_charged_to_the_turn_deadline(world):
    service, row, _, _, wires = await _setup(world)
    overlay = await build_overlay(world.alice, approvals_supported=True, service=service)
    turn_id = uuid.uuid4()
    publisher = CardPublisher(turn_id, world.alice, {"get_revenue": (0.8, "allow_once")})
    approver = make_approver(
        overlay=overlay, publisher=publisher, turn_id=turn_id, user_id=world.alice,
        cancel_event=asyncio.Event(), service=service, timeout=5,
    )
    client = FakeClient(
        [
            Completion(
                model=SESSION_MODEL,
                tool_calls=(LLMToolCall(id="t1", name=wires["get_revenue"], arguments={"ticker": "VNM"}),),
                usage=Usage(input_tokens=10, output_tokens=5),
            ),
            Completion(model=SESSION_MODEL, text="Theo sổ tay, doanh thu là 61.782 tỷ đồng.", usage=Usage(input_tokens=10, output_tokens=5)),
        ]
    )
    loop = AgentLoop(
        client=client,
        config=config(),
        toolsets=(),
        deadline_seconds=0.5,
        publisher=publisher,
        clock=lambda: datetime(2026, 9, 27, tzinfo=timezone.utc),
    )
    outcome = await loop.run(
        TurnRequest(
            thread_id=str(uuid.uuid4()),
            request_message_id=1,
            user_id=world.alice,
            user_text="Doanh thu VNM trong sổ tay?",
            runtime=RuntimeContext(today=date(2026, 9, 27), user_name="Alice"),
            turn_id=turn_id,
            connector_tools=overlay.offered,
            connector_hidden_tools=overlay.hidden,
            approver=approver,
        )
    )
    assert outcome.status.value == "complete", outcome.terminal_reason
    assert "[chưa kiểm chứng]" in outcome.answer
    assert [call.status.value for call in outcome.tool_calls] == ["ok"]
    await service.delete(world.alice, row.id)
