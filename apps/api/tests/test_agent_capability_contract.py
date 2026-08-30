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
    "frame_from_evidence": (
        "web",
        registry.ToolEffect.READ,
        registry.ToolIdempotency.IDEMPOTENT,
        # The store, not the network. Nothing is fetched: the page it checks
        # against is read out of the Tool Call Trace, which is the only copy the
        # answer was written from.
        registry.ToolAccess.STORE,
        registry.ContentTrust.TRUSTED_STRUCTURED,
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
    "get_series": (
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
    "query": (
        "signals",
        registry.ToolEffect.READ,
        registry.ToolIdempotency.IDEMPOTENT,
        registry.ToolAccess.STORE,
        registry.ContentTrust.TRUSTED_STRUCTURED,
        registry.ToolConcurrency.PARALLEL_SAFE,
    ),
    "compare_fields": (
        "signals",
        registry.ToolEffect.READ,
        registry.ToolIdempotency.IDEMPOTENT,
        registry.ToolAccess.STORE,
        registry.ContentTrust.TRUSTED_STRUCTURED,
        registry.ToolConcurrency.PARALLEL_SAFE,
    ),
    "list_studies": (
        "studies",
        registry.ToolEffect.READ,
        registry.ToolIdempotency.IDEMPOTENT,
        registry.ToolAccess.STORE,
        registry.ContentTrust.TRUSTED_STRUCTURED,
        registry.ToolConcurrency.SERIALIZED,
    ),
    # ``run_study`` writes a row and can reach a provider, and is still declared
    # a store read: what it hands the model is arithmetic this deployment
    # performed, and the row it writes is the answer being kept rather than
    # anything a reader already holds changing.
    "run_study": (
        "studies",
        registry.ToolEffect.READ,
        registry.ToolIdempotency.IDEMPOTENT,
        registry.ToolAccess.STORE,
        registry.ContentTrust.TRUSTED_STRUCTURED,
        registry.ToolConcurrency.SERIALIZED,
    ),
    "render_signal_desk": (
        "studies",
        registry.ToolEffect.READ,
        registry.ToolIdempotency.IDEMPOTENT,
        registry.ToolAccess.STORE,
        registry.ContentTrust.TRUSTED_STRUCTURED,
        registry.ToolConcurrency.SERIALIZED,
    ),
    # Serialized rather than parallel-safe, and it is the only tool here whose
    # reason is a resource rather than an ordering: every call spawns a process
    # allowed half a gigabyte, and a round issuing six at once is six of those
    # at once.
    "compute": (
        "studies",
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
        "frame_from_evidence": ("Lấy số từ trang đã đọc", False, 8_000, None, True),
        "session_search": ("Tìm trong hội thoại trước", True, None, "query", False),
        "remember_fact": ("Ghi nhớ", True, None, "title", False),
        "recall_facts": ("Đọc lại ghi chú", True, None, "query", False),
        "list_fields": ("Xem danh mục chỉ báo", True, 32_000, None, True),
        "get_field": ("Đọc chỉ báo", False, 32_000, None, True),
        "get_series": ("Đọc chuỗi chỉ báo", False, 32_000, None, True),
        "check_price_claim": ("Kiểm mức giá", False, 4_000, None, True),
        "query": ("Đọc bảng dữ liệu", False, 32_000, None, True),
        "compare_fields": ("So sánh chỉ báo", False, 32_000, None, True),
        "list_studies": ("Xem danh mục phân tích", True, 32_000, None, True),
        "run_study": ("Chạy phân tích", False, 32_000, None, True),
        "render_signal_desk": ("Vẽ signal_desk", False, 32_000, None, True),
        "compute": ("Tính trên số đã đọc", False, 8_000, None, True),
    }
    with isolated_registry():
        tools.register_all()
        entries = registry.entries()
        schemas = [entry.as_schema().as_wire() for entry in entries]

        # Moves whenever the wire schemas do — including when a Study is
        # registered, because ``run_study`` carries the catalog in its own
        # parameters and description. That is the design (``agent/tools/
        # studies.py``): a Study added later changes the tool signature the
        # resolved-surface cache keys on and changes nothing in the prompt. So
        # this is updated in the same commit as the Study, deliberately.
        #
        # Moved on 2026-08-29 as well, for ``fetch_url``'s new optional
        # ``looking_for``: a page is now returned as the passages matching what
        # the caller said it was after, so the argument is part of the wire
        # schema and the model has to be told the field means something.
        #
        # Moved again on 2026-08-30 for ``query`` and ``compare_fields``: the
        # store's own tables became readable as a table, which is two new wire
        # schemas rather than a change to an existing one. Moved a second time
        # the same day, in code review: ``window`` gained a maximum and ``items``
        # a maxItems, because a ceiling checked only on the built frame is a
        # ceiling that protects the model's context and not the process. Moved a second time
        # the same day, on review: ``window`` gained a maximum and ``items`` a
        # maxItems, so a request too large to answer is refused at the boundary
        # instead of after the read.
        #
        # Moved a third time on 2026-08-30 for ``compute`` and
        # ``frame_from_evidence``: the calculation axis and the evidence axis
        # registered, which is two more new wire schemas rather than a change to
        # an existing one.
        #
        # Moved a fourth time on 2026-08-30 for the board grammar:
        # ``render_signal_desk`` went from a title and a flat list of blocks to
        # a board — a KPI strip, sections, captions with cell references, an
        # appendix. One schema replaced, none added.
        assert hashlib.sha256(
            json.dumps(
                schemas,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest() == "be5b995fec13fb685542f24b8fb2b90ef7861a48ea1ba7836cd31cbdaa97b71b"
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


def test_every_offered_schema_survives_the_json_encoder():
    """The resolved surface is what the route is sent, and it is frozen.

    Freezing turns nested mappings into ``mappingproxy`` and lists into tuples,
    neither of which the JSON encoder can write. Asking the entries directly
    would not see it: only a resolved declaration is frozen, so the check has to
    go through the same surface the loop calls with.
    """

    with isolated_registry():
        tools.register_all()
        surface = definitions.resolve_tool_surface(
            toolsets.CHAT_TOOLSETS, now=1_000.0
        )

        for name, resolved in surface.by_name.items():
            try:
                json.dumps(resolved.schema.as_wire())
            except TypeError as unwritable:  # pragma: no cover - failure text
                pytest.fail(f"{name} cannot go on the wire: {unwritable}")


def test_lane_selection_and_order_are_explicit_and_do_not_share_authority():
    assert toolsets.CHAT_TOOLSETS == ("web", "memory", "signals", "studies")
    assert toolsets.resolve_toolset(toolsets.CHAT_TOOLSETS) == tuple(EXPECTED_CATALOG)
    assert toolsets.resolve_toolset("signals") == (
        "list_fields",
        "get_field",
        "get_series",
        "check_price_claim",
        "query",
        "compare_fields",
    )
    assert toolsets.resolve_toolset("studies") == (
        "list_studies",
        "run_study",
        "render_signal_desk",
        "compute",
    )

    # Added 2026-08-29: the selection above is still written down and still the
    # only one the chat lane makes, and it now also has an author. The two
    # halves are ``CORE_TOOLSETS`` — the bundles that belong to no subject — and
    # whatever the active domain pack declares. Neither half may be inferred:
    # this asserts the *sum*, and ``toolsets`` refuses to import when the sum
    # stops holding, so the tuple above cannot be left behind naming the last
    # domain after a pack swap.
    from src.agent.domain import active_pack

    assert toolsets.CORE_TOOLSETS == ("web", "memory")
    assert active_pack().toolsets == ("signals", "studies")
    assert toolsets.CHAT_TOOLSETS == (
        *toolsets.CORE_TOOLSETS,
        *active_pack().toolsets,
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
