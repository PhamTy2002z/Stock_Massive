"""Contracts for the generic web and memory tool surface."""

from __future__ import annotations

import asyncio
import json

import pytest

from src.agent import budget, definitions, executor, loop, registry, tools, toolsets, untrusted
from src.agent.executor import ToolCall, ToolExecutor
from src.agent.messages import STORE_KIND, TurnToolCall, summarise_call

from .agent_tool_world import isolated_registry, stub_entry


EXPECTED_CATALOG = {
    "web_search": ("web", registry.ToolEffect.READ, registry.ToolIdempotency.IDEMPOTENT, registry.ToolAccess.NETWORK, registry.ContentTrust.UNTRUSTED, registry.ToolConcurrency.PARALLEL_SAFE, registry.ToolPermission.ALLOW, 20.0),
    "fetch_url": ("web", registry.ToolEffect.READ, registry.ToolIdempotency.IDEMPOTENT, registry.ToolAccess.NETWORK, registry.ContentTrust.UNTRUSTED, registry.ToolConcurrency.PARALLEL_SAFE, registry.ToolPermission.ALLOW, 25.0),
    "session_search": ("memory", registry.ToolEffect.READ, registry.ToolIdempotency.IDEMPOTENT, registry.ToolAccess.STORE, registry.ContentTrust.TRUSTED_STRUCTURED, registry.ToolConcurrency.PARALLEL_SAFE, registry.ToolPermission.ALLOW, 10.0),
    "remember_fact": ("memory", registry.ToolEffect.WRITE, registry.ToolIdempotency.UNKNOWN, registry.ToolAccess.STORE, registry.ContentTrust.TRUSTED_STRUCTURED, registry.ToolConcurrency.SERIALIZED, registry.ToolPermission.ALLOW, 10.0),
    "recall_facts": ("memory", registry.ToolEffect.READ, registry.ToolIdempotency.IDEMPOTENT, registry.ToolAccess.STORE, registry.ContentTrust.TRUSTED_STRUCTURED, registry.ToolConcurrency.PARALLEL_SAFE, registry.ToolPermission.ALLOW, 10.0),
}


def test_all_shipped_tools_declare_a_complete_behavior_contract():
    with isolated_registry():
        tools.register_all()
        assert registry.names() == tuple(EXPECTED_CATALOG)
        for entry in registry.entries():
            assert (entry.toolset, entry.effect, entry.idempotency, entry.access, entry.content_trust, entry.concurrency, entry.permission, entry.timeout_seconds) == EXPECTED_CATALOG[entry.name]
            assert entry.contract_version == "1"
            assert entry.handler_identity.startswith("src.agent.tools.")
            assert entry.reads_external is (entry.content_trust is registry.ContentTrust.UNTRUSTED)
            # Every declared bound sits under the round's own backstop, or the
            # per-call limit could only ever fire by ending the whole Turn.
            assert 0 < entry.timeout_seconds < loop.TOOL_TIMEOUT_SECONDS


def test_shipped_schema_order_and_display_contract_are_locked():
    expected_runtime = {
        "web_search": ("Tìm trên web", True, 8_000, "query", False),
        "fetch_url": ("Đọc trang", True, 22_000, "url", False),
        "session_search": ("Tìm trong hội thoại trước", True, None, "query", False),
        "remember_fact": ("Ghi nhớ", True, None, "title", False),
        "recall_facts": ("Đọc lại ghi chú", True, None, "query", False),
    }
    with isolated_registry():
        tools.register_all()
        entries = registry.entries()
        assert [entry.as_schema().as_wire()["function"]["name"] for entry in entries] == list(EXPECTED_CATALOG)
        assert {entry.name: (entry.display_name, entry.is_async, entry.max_result_size_chars, entry.summary_detail_arg, entry.summarise is not None) for entry in entries} == expected_runtime


def test_every_offered_schema_survives_json_encoding():
    with isolated_registry():
        tools.register_all()
        surface = definitions.resolve_tool_surface(toolsets.CHAT_TOOLSETS, now=1_000.0)
        for name, resolved in surface.by_name.items():
            try:
                json.dumps(resolved.schema.as_wire())
            except TypeError as unwritable:  # pragma: no cover
                pytest.fail(f"{name} cannot go on the wire: {unwritable}")


def test_chat_selection_is_web_and_memory_only():
    from src.agent.domain import active_pack

    assert toolsets.CORE_TOOLSETS == ("web", "memory")
    assert active_pack().toolsets == ()
    assert toolsets.CHAT_TOOLSETS == toolsets.CORE_TOOLSETS
    assert toolsets.resolve_toolset(toolsets.CHAT_TOOLSETS) == tuple(EXPECTED_CATALOG)


@pytest.mark.asyncio
async def test_one_read_only_registration_flows_through_generic_consumers():
    async def read(_context, arguments):
        return {"value": arguments.get("value", "ok")}

    entry = registry.ToolEntry(
        name="hypothetical_read", toolset="hypothetical",
        schema=registry.object_schema({"value": {"type": "string"}}), handler=read,
        description="Read one hypothetical store value.", display_name="Đọc dữ liệu thử nghiệm",
        summary_detail_arg="value", reads_external=False, effect=registry.ToolEffect.READ,
        idempotency=registry.ToolIdempotency.IDEMPOTENT, access=registry.ToolAccess.STORE,
        content_trust=registry.ContentTrust.TRUSTED_STRUCTURED,
        concurrency=registry.ToolConcurrency.PARALLEL_SAFE, max_result_size_chars=2_000,
        permission=registry.ToolPermission.ALLOW, timeout_seconds=7.5,
    )
    written: list[dict] = []
    with isolated_registry():
        toolsets.TOOLSETS["hypothetical"] = {"description": "Test tool.", "tools": (entry.name,)}
        toolsets.clear_memo()
        try:
            registry.register(entry)
            surface = definitions.resolve_tool_surface("hypothetical", now=1_000.0)
            resolved = surface.by_name[entry.name]
            result = await ToolExecutor(context=registry.ToolContext(), surface=surface, availability=lambda _name: True, trace=written.append).run([ToolCall(id="call-1", name=entry.name, arguments={"value": "x"})])
            turn_budget = budget.TurnBudget(budget.BudgetThresholds(per_result_chars=10_000, per_turn_chars=20_000), registry_limits={entry.name: resolved.max_result_size_chars})
            call = TurnToolCall(id="call-1", name=entry.name, summary=summarise_call(entry.name, {"value": "x"}, resolved=resolved), resolved_tool=resolved)
            assert tuple(schema.name for schema in surface.offered_schemas) == (entry.name,)
            # The object, not an equal copy of it: the schema the executor
            # dispatches against and the schema the model was shown are the same
            # frozen declaration, so no round can be run against a second one.
            assert resolved.schema is surface.offered_schemas[0]
            assert result.results[0].ok is True
            assert (resolved.permission, resolved.timeout_seconds) == (registry.ToolPermission.ALLOW, 7.5)
            assert turn_budget.limit_for(entry.name) == 2_000
            assert call.summary == "Đọc dữ liệu thử nghiệm: x"
            assert call.as_wire()["kind"] == STORE_KIND
            assert untrusted.wrap_result(entry.name, "trusted structured result long enough to be wrapped otherwise", resolved=resolved) == "trusted structured result long enough to be wrapped otherwise"
            assert [(row["call_id"], row["tool"], row["ok"], row["dispatched"]) for row in written] == [("call-1", entry.name, True, True)]
        finally:
            toolsets.TOOLSETS.pop("hypothetical", None)
            toolsets.clear_memo()


def permissioned(name: str, **overrides) -> registry.ToolEntry:
    """One stub declaring the axes this file's dispatch tests turn on."""
    declared = {
        "access": registry.ToolAccess.STORE,
        "reads_external": False,
        "content_trust": registry.ContentTrust.TRUSTED_STRUCTURED,
        "effect": registry.ToolEffect.READ,
        "idempotency": registry.ToolIdempotency.IDEMPOTENT,
        "concurrency": registry.ToolConcurrency.PARALLEL_SAFE,
    }
    declared.update(overrides)
    return stub_entry(name, **declared)


@pytest.mark.asyncio
async def test_a_refused_call_settles_one_typed_result_and_spares_its_siblings():
    """Six ways a call ends badly, one batch, and an answer that still arrives.

    The point of the batch is the sibling: a refusal that took its neighbours
    with it would leave the model owed results it will never read, and a
    provider rejecting the conversation is how that failure shows up.
    """

    async def sleeper(_context, _arguments):
        await asyncio.sleep(5.0)

    async def broken(_context, _arguments):
        raise RuntimeError("this handler is broken")

    with isolated_registry():
        registry.register(permissioned("healthy"))
        registry.register(permissioned("denied", permission=registry.ToolPermission.DENY))
        registry.register(permissioned("needs_approval", permission=registry.ToolPermission.ASK))
        registry.register(permissioned("slow", handler=sleeper, timeout_seconds=0.05))
        registry.register(permissioned("broken", handler=broken))
        outcome = await ToolExecutor(context=registry.ToolContext()).run([
            ToolCall(id="ok", name="healthy", arguments={"value": "x"}),
            ToolCall(id="nobody", name="not_a_tool", arguments={}),
            ToolCall(id="garbled", name="healthy", arguments="{not json"),
            ToolCall(id="no", name="denied", arguments={}),
            ToolCall(id="ask", name="needs_approval", arguments={}),
            ToolCall(id="late", name="slow", arguments={}),
            ToolCall(id="raises", name="broken", arguments={}),
        ])
        settled = {result.call_id: result for result in outcome.results}

        assert len(outcome.results) == 7
        assert settled["ok"].ok is True
        assert [(result.error, result.dispatched) for result in outcome.results] == [
            (None, True),
            (executor.UNKNOWN_TOOL, False),
            (executor.INVALID_ARGUMENTS, False),
            (executor.PERMISSION_DENIED, False),
            (executor.PERMISSION_DENIED, False),
            (executor.TOOL_CALL_TIMEOUT, True),
            (executor.TOOL_FAILED, True),
        ]
        # The two refusals share a code because the model's next move is the
        # same, and differ in their text because the reasons are not: one route
        # is closed, the other is waiting on somebody.
        assert "not permitted" in settled["no"].text
        assert "agreed" in settled["ask"].text
        assert settled["late"].duration_ms >= 40


@pytest.mark.asyncio
async def test_a_handlers_own_timeout_is_a_failure_not_the_declared_bound():
    """A socket timeout is a ``TimeoutError`` too, and it is not this one.

    ``socket.timeout`` is the same class, so a wire that gave up in one second
    must not be reported as a call that spent its whole declared allowance —
    that sentence carries a number the model plans around, and it would be the
    wrong number.
    """

    async def wire_gave_up(_context, _arguments):
        raise TimeoutError("the socket timed out")

    with isolated_registry():
        registry.register(
            permissioned("impatient_wire", handler=wire_gave_up, timeout_seconds=30.0)
        )
        outcome = await ToolExecutor(context=registry.ToolContext()).run(
            [ToolCall(id="wire", name="impatient_wire", arguments={})]
        )
        (result,) = outcome.results
        assert (result.error, result.dispatched) == (executor.TOOL_FAILED, True)
        assert "30" not in result.text


@pytest.mark.asyncio
async def test_a_batch_reads_back_in_the_order_the_model_issued_it():
    """Parallel reads, a barrier and a refusal, in the model's own order."""
    with isolated_registry():
        registry.register(permissioned("read_one"))
        registry.register(permissioned("read_two"))
        registry.register(
            permissioned(
                "write_thing",
                effect=registry.ToolEffect.WRITE,
                concurrency=registry.ToolConcurrency.SERIALIZED,
            )
        )
        registry.register(permissioned("denied", permission=registry.ToolPermission.DENY))
        issued = [
            ToolCall(id="1", name="read_one", arguments={"value": "a"}),
            ToolCall(id="2", name="denied", arguments={}),
            ToolCall(id="3", name="write_thing", arguments={"value": "b"}),
            ToolCall(id="4", name="read_two", arguments={"value": "c"}),
        ]
        outcome = await ToolExecutor(context=registry.ToolContext()).run(issued)

        assert [result.call_id for result in outcome.results] == ["1", "2", "3", "4"]
        assert [result.tool_name for result in outcome.results] == [
            "read_one", "denied", "write_thing", "read_two"
        ]
        assert [result.ok for result in outcome.results] == [True, False, True, True]


class TestARegistrationStatesWhatItMayDoAndForHowLong:
    """Both are refused rather than defaulted, and refused at different points.

    Permission is refused by ``register`` because the missing field is a
    decision nobody made; a timeout that is not a duration is refused by the
    declaration itself, because there is no state of the world it describes.
    """

    def test_a_registration_that_does_not_say_whether_it_may_run_is_refused(self):
        with isolated_registry():
            with pytest.raises(ValueError, match="permission"):
                registry.register(stub_entry("undeclared", permission=None))

    @pytest.mark.parametrize("timeout", (0, -1.0, float("inf"), float("nan")))
    def test_a_timeout_that_is_not_a_duration_is_refused(self, timeout):
        with pytest.raises(ValueError, match="timeout_seconds"):
            stub_entry("unbounded", timeout_seconds=timeout)
