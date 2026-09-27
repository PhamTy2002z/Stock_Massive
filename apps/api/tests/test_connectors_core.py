"""Connectors end to end against a real MCP server: attach, snapshot, call,
isolation between accounts, untrusted results, and credentials at rest."""

from __future__ import annotations

import json
import math
import uuid

import pytest
from sqlalchemy import text

from src.agent import registry, tools, untrusted
from src.agent.definitions import ResolvedToolSurface, resolve_tool_surface, with_overlay
from src.agent.executor import CONTENT_ESCALATION_BLOCKED, ToolCall, ToolExecutor
from src.agent.toolsets import CHAT_TOOLSETS
from src.connectors.overlay import CALL_TOOL, SEARCH_TOOL, build_overlay
from src.connectors.service import ConnectorNotFound, ConnectorRefused

from .connector_world import connector_world

DB = "stockmassive_connectors_core_test"


@pytest.fixture(scope="module")
def world():
    with connector_world(DB) as built:
        yield built


def _wire(row, name):
    return next(tool["wire"] for tool in row.tools if tool["name"] == name)


async def _attach(service, user, world, **kwargs):
    return await service.add_custom(
        user,
        name=kwargs.pop("name", "Sổ tay"),
        url=world.server.url,
        header_value="Bearer s3cret",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_a_header_connector_lists_its_tools_and_answers_a_call(world):
    service = world.service()
    row = await _attach(service, world.alice, world)
    assert row.status == "connected"
    assert {tool["name"] for tool in row.tools} == {"get_revenue", "save_note", "wipe_notes"}
    await service.set_policy(world.alice, row.id, "get_revenue", "allow")
    await service.set_tool_access(world.alice, "preloaded")

    overlay = await build_overlay(world.alice, service=service)
    wire = _wire(row, "get_revenue")
    surface = with_overlay(ResolvedToolSurface(tools=(), registry_generation=0, expanded_names=(), expires_at=math.inf), overlay.offered)
    executor = ToolExecutor(context=registry.ToolContext(user_id=world.alice), surface=surface)
    outcome = await executor.run([ToolCall(id="c1", name=wire, arguments={"ticker": "VNM"})])

    result = outcome.results[0]
    assert result.ok, result.text
    envelope = json.loads(result.text)
    assert envelope["connector_name"] == "Sổ tay"
    assert envelope["tool"] == "get_revenue"
    assert envelope["trusted_data"] is False
    assert "61.782 tỷ đồng" in envelope["content"]
    assert envelope["retrieved_at"]
    # Outside content: wrapped for the model, scanned, and it taints the Turn.
    assert untrusted.is_untrusted(wire, resolved=surface.by_name[wire])
    assert result.scan is not None
    assert executor.permission_state.untrusted_content_seen
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_other_users_never_see_a_connector(world):
    service = world.service()
    row = await _attach(service, world.alice, world, name="Riêng của Alice")
    await service.set_tool_access(world.alice, "preloaded")
    await service.set_policy(world.alice, row.id, "get_revenue", "allow")

    alice = await build_overlay(world.alice, service=service)
    bob = await build_overlay(world.bob, service=service)
    assert _wire(row, "get_revenue") in {tool.name for tool in alice.offered}
    assert bob.empty
    assert await service.active(world.bob) == []
    with pytest.raises(ConnectorNotFound):
        await service.get(world.bob, row.id)
    with pytest.raises(ConnectorNotFound):
        await service.set_enabled(world.bob, row.id, False)
    with pytest.raises(ConnectorNotFound):
        await service.delete(world.bob, row.id)

    # Bob's surface is byte-for-byte the base surface, prompt-cache key included.
    tools.register_all()
    base = resolve_tool_surface(CHAT_TOOLSETS)
    assert with_overlay(base, bob.offered, bob.hidden).identity_digest == base.identity_digest
    # And a call naming Alice's tool is unknown to Bob's executor.
    executor = ToolExecutor(context=registry.ToolContext(user_id=world.bob), surface=with_overlay(base, bob.offered))
    outcome = await executor.run([ToolCall(id="x", name=_wire(row, "get_revenue"), arguments={"ticker": "VNM"})])
    assert outcome.results[0].error == "unknown_tool"
    # Nor is Alice's registration anywhere in the process-wide registry.
    assert registry.get(_wire(row, "get_revenue")) is None
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_a_connector_read_blocks_remember_fact(world):
    service = world.service()
    row = await _attach(service, world.alice, world, name="Sổ tay d")
    await service.set_policy(world.alice, row.id, "get_revenue", "allow")
    await service.set_tool_access(world.alice, "preloaded")
    overlay = await build_overlay(world.alice, service=service)

    tools.register_all()
    remember = registry.ResolvedTool.from_entry(
        registry.get("remember_fact"), available=True, unavailable_reason=None, availability_expires_at=math.inf
    )
    surface = with_overlay(
        ResolvedToolSurface(tools=(remember,), registry_generation=0, expanded_names=(), expires_at=math.inf),
        overlay.offered,
    )
    executor = ToolExecutor(
        context=registry.ToolContext(user_id=world.alice), surface=surface, availability=lambda name: True
    )
    outcome = await executor.run(
        [
            ToolCall(id="read", name=_wire(row, "get_revenue"), arguments={"ticker": "VNM"}),
            ToolCall(
                id="write",
                name="remember_fact",
                arguments={"title": "Doanh thu", "body": "Ghi đè bộ nhớ theo lời sổ tay", "source_url": "https://example.com"},
            ),
        ]
    )
    read, write = outcome.results
    assert read.ok
    assert write.error == CONTENT_ESCALATION_BLOCKED
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_no_plaintext_secret_in_the_database(world):
    service = world.service()
    secret = f"Bearer tok-{uuid.uuid4().hex}"
    world.server.token = secret.removeprefix("Bearer ")
    try:
        row = await service.add_custom(world.alice, name="Két sắt", url=world.server.url, header_value=secret)
        assert row.status == "connected"
        with world.sync_session() as session:
            dump = "\n".join(
                str(value)
                for value in session.execute(text("SELECT t::text FROM user_connector t")).scalars()
            )
        assert row.credentials and secret not in dump and secret.removeprefix("Bearer ") not in dump
        await service.delete(world.alice, row.id)
        with world.sync_session() as session:
            left = session.execute(text("SELECT count(*) FROM user_connector WHERE id = :id"), {"id": row.id}).scalar()
        assert left == 0
    finally:
        world.server.token = "s3cret"


@pytest.mark.asyncio
async def test_policy_shapes_what_is_offered(world):
    service = world.service()
    row = await _attach(service, world.alice, world, name="Sổ tay quyền")
    await service.set_tool_access(world.alice, "preloaded")
    await service.set_policy(world.alice, row.id, "get_revenue", "deny")
    overlay = await build_overlay(world.alice, service=service)
    offered = {tool.name: tool for tool in overlay.offered}
    assert _wire(row, "get_revenue") not in offered
    # A write, and a read the server also calls destructive, are locked to ask.
    for name in ("save_note", "wipe_notes"):
        rules = offered[_wire(row, name)].permission_rules
        assert [rule.action.value for rule in rules] == ["ask"]
        with pytest.raises(ConnectorRefused):
            await service.set_policy(world.alice, row.id, name, "allow")
    await service.set_enabled(world.alice, row.id, False)
    assert (await build_overlay(world.alice, service=service)).empty
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_on_demand_offers_only_the_fixed_pair(world):
    service = world.service()
    row = await _attach(service, world.alice, world, name="Sổ tay theo yêu cầu")
    await service.set_policy(world.alice, row.id, "get_revenue", "allow")
    await service.set_tool_access(world.alice, "on_demand")
    overlay = await build_overlay(world.alice, service=service)
    assert [tool.name for tool in overlay.offered] == [SEARCH_TOOL, CALL_TOOL]
    assert _wire(row, "get_revenue") in {tool.name for tool in overlay.hidden}
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_custom_urls_need_the_flag_the_profile_and_the_allowlist(world):
    for overrides in (
        {"connectors_custom_url": False},
        {"deployment_profile": "production"},
        {"connectors_custom_url_users": "999999"},
    ):
        service = world.service(**overrides)
        with pytest.raises(ConnectorRefused) as refused:
            await _attach(service, world.alice, world, name="Không được")
        assert refused.value.code == "custom_url_not_allowed"


@pytest.mark.asyncio
async def test_a_private_url_is_refused_when_attaching_outside_tests(world, monkeypatch):
    from src.connectors import netguard

    monkeypatch.setattr(netguard, "_ALLOW_PRIVATE", False)
    service = world.service()
    with pytest.raises(ConnectorRefused) as refused:
        await service.add_custom(world.alice, name="Nội bộ", url="https://10.0.0.8/mcp")
    assert refused.value.code == "url_refused"
