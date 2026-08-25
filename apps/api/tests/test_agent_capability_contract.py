"""Cross-owner contract locked before capability consumers are migrated."""

from __future__ import annotations

import hashlib
import json

import pytest

from src.agent import budget, definitions, registry, tools, toolsets, untrusted
from src.agent.executor import ToolCall, ToolExecutor
from src.agent.messages import STORE_KIND, TurnToolCall, summarise_call

from .agent_tool_world import isolated_registry


EXPECTED_CATALOG = {
    "web_search": (
        "web",
        registry.ToolEffect.READ,
        registry.ToolIdempotency.IDEMPOTENT,
        registry.ToolAccess.NETWORK,
        registry.ContentTrust.UNTRUSTED,
        registry.ToolConcurrency.PARALLEL_SAFE,
    ),
    "fetch_url": (
        "web",
        registry.ToolEffect.READ,
        registry.ToolIdempotency.IDEMPOTENT,
        registry.ToolAccess.NETWORK,
        registry.ContentTrust.UNTRUSTED,
        registry.ToolConcurrency.PARALLEL_SAFE,
    ),
    "session_search": (
        "memory",
        registry.ToolEffect.READ,
        registry.ToolIdempotency.IDEMPOTENT,
        registry.ToolAccess.STORE,
        registry.ContentTrust.TRUSTED_STRUCTURED,
        registry.ToolConcurrency.PARALLEL_SAFE,
    ),
    "remember_fact": (
        "memory",
        registry.ToolEffect.WRITE,
        registry.ToolIdempotency.UNKNOWN,
        registry.ToolAccess.STORE,
        registry.ContentTrust.TRUSTED_STRUCTURED,
        registry.ToolConcurrency.SERIALIZED,
    ),
    "recall_facts": (
        "memory",
        registry.ToolEffect.READ,
        registry.ToolIdempotency.IDEMPOTENT,
        registry.ToolAccess.STORE,
        registry.ContentTrust.TRUSTED_STRUCTURED,
        registry.ToolConcurrency.PARALLEL_SAFE,
    ),
    "list_fields": (
        "signals",
        registry.ToolEffect.READ,
        registry.ToolIdempotency.IDEMPOTENT,
        registry.ToolAccess.STORE,
        registry.ContentTrust.TRUSTED_STRUCTURED,
        registry.ToolConcurrency.SERIALIZED,
    ),
    "get_field": (
        "signals",
        registry.ToolEffect.READ,
        registry.ToolIdempotency.IDEMPOTENT,
        registry.ToolAccess.STORE,
        registry.ContentTrust.TRUSTED_STRUCTURED,
        registry.ToolConcurrency.SERIALIZED,
    ),
    "check_price_claim": (
        "signals",
        registry.ToolEffect.READ,
        registry.ToolIdempotency.IDEMPOTENT,
        registry.ToolAccess.STORE,
        registry.ContentTrust.TRUSTED_STRUCTURED,
        registry.ToolConcurrency.SERIALIZED,
    ),
}


def test_all_shipped_tools_declare_one_complete_current_behavior_contract():
    with isolated_registry():
        tools.register_all()

        assert registry.names() == tuple(EXPECTED_CATALOG)
        for entry in registry.entries():
            assert (
                entry.toolset,
                entry.effect,
                entry.idempotency,
                entry.access,
                entry.content_trust,
                entry.concurrency,
            ) == EXPECTED_CATALOG[entry.name]
            assert entry.contract_version == "1"
            assert entry.handler_identity.startswith("src.agent.tools.")
            assert entry.reads_external is (
                entry.content_trust is registry.ContentTrust.UNTRUSTED
            )


def test_shipped_schema_bytes_order_output_and_display_are_locked():
    expected_runtime = {
        "web_search": ("Tìm trên web", True, 8_000, "query", False),
        "fetch_url": ("Đọc trang", True, 22_000, "url", False),
        "session_search": ("Tìm trong hội thoại trước", True, None, "query", False),
        "remember_fact": ("Ghi nhớ", True, None, "title", False),
        "recall_facts": ("Đọc lại ghi chú", True, None, "query", False),
        "list_fields": ("Xem danh mục chỉ báo", True, 32_000, None, True),
        "get_field": ("Đọc chỉ báo", False, 32_000, None, True),
        "check_price_claim": ("Kiểm mức giá", False, 4_000, None, True),
    }
    with isolated_registry():
        tools.register_all()
        entries = registry.entries()
        schemas = [entry.as_schema().as_wire() for entry in entries]

        assert hashlib.sha256(
            json.dumps(
                schemas,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest() == "492ce59feb54827f2863ba29ffc383bb6fa022a663dcdc0ba9a0f40a056d3502"
        assert {
            entry.name: (
                entry.display_name,
                entry.is_async,
                entry.max_result_size_chars,
                entry.summary_detail_arg,
                entry.summarise is not None,
            )
            for entry in entries
        } == expected_runtime


def test_lane_selection_and_order_are_explicit_and_do_not_share_authority():
    assert toolsets.CHAT_TOOLSETS == ("web", "memory", "signals")
    assert toolsets.resolve_toolset(toolsets.CHAT_TOOLSETS) == tuple(EXPECTED_CATALOG)
    assert toolsets.resolve_toolset("signals") == (
        "list_fields",
        "get_field",
        "check_price_claim",
    )


@pytest.mark.asyncio
async def test_one_read_only_registration_flows_through_every_generic_consumer():
    async def read(_context, arguments):
        return {"value": arguments.get("value", "ok")}

    entry = registry.ToolEntry(
        name="hypothetical_read",
        toolset="hypothetical",
        schema=registry.object_schema({"value": {"type": "string"}}),
        handler=read,
        description="Read one hypothetical store value.",
        display_name="Đọc dữ liệu thử nghiệm",
        summary_detail_arg="value",
        reads_external=False,
        effect=registry.ToolEffect.READ,
        idempotency=registry.ToolIdempotency.IDEMPOTENT,
        access=registry.ToolAccess.STORE,
        content_trust=registry.ContentTrust.TRUSTED_STRUCTURED,
        concurrency=registry.ToolConcurrency.PARALLEL_SAFE,
        max_result_size_chars=2_000,
    )

    with isolated_registry():
        toolsets.TOOLSETS["hypothetical"] = {
            "description": "One intentionally selected read-only tool.",
            "tools": (entry.name,),
        }
        toolsets.clear_memo()
        try:
            registry.register(entry)
            surface = definitions.resolve_tool_surface("hypothetical", now=1_000.0)
            resolved = surface.by_name[entry.name]
            result = await ToolExecutor(
                context=registry.ToolContext(),
                surface=surface,
                availability=lambda _name: True,
            ).run([ToolCall(id="call-1", name=entry.name, arguments={"value": "x"})])
            turn_budget = budget.TurnBudget(
                budget.BudgetThresholds(
                    per_result_chars=10_000,
                    per_turn_chars=20_000,
                ),
                registry_limits={entry.name: resolved.max_result_size_chars},
            )
            call = TurnToolCall(
                id="call-1",
                name=entry.name,
                summary=summarise_call(
                    entry.name, {"value": "x"}, resolved=resolved
                ),
                resolved_tool=resolved,
            )

            assert tuple(schema.name for schema in surface.offered_schemas) == (
                entry.name,
            )
            assert result.results[0].ok is True
            assert turn_budget.limit_for(entry.name) == 2_000
            assert call.summary == "Đọc dữ liệu thử nghiệm: x"
            assert call.as_wire()["kind"] == STORE_KIND
            assert untrusted.wrap_result(
                entry.name,
                "trusted structured result long enough to be wrapped otherwise",
                resolved=resolved,
            ) == "trusted structured result long enough to be wrapped otherwise"
        finally:
            toolsets.TOOLSETS.pop("hypothetical", None)
            toolsets.clear_memo()
