"""Public contract of the Intelligent Quant Tool Catalog."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest

from src.agent.tools.catalog import (
    MAX_TOOL_RESULT_BYTES,
    RECOVERY_HINTS,
    ToolCatalog,
    ToolContext,
    ToolResultTooLarge,
    ToolSpec,
    recovery_hint,
)
from src.agent.tools.fields import registered_field_schema, serialize_registered_field
from src.agent.tools.fields import REGISTERED_FIELD_VALUES_KEY
from src.core.provider_access import (
    ProviderSourceAccessForbidden,
    ensure_provider_source_allowed,
)


async def echo(_context: ToolContext, arguments: dict) -> dict:
    return {"echo": arguments.get("value")}


def spec(name: str = "echo") -> ToolSpec:
    return ToolSpec(
        name=name,
        description="Echo one stored value.",
        parameters={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        callable=echo,
    )


def context() -> ToolContext:
    return ToolContext(user_id=7, trading_day=date(2026, 8, 14), active_symbol="FPT")


def test_schemas_and_version_are_derived_from_the_same_registration():
    one = ToolCatalog((spec(),), trace_writer=lambda _trace: None)
    two = ToolCatalog((spec(), spec("second")), trace_writer=lambda _trace: None)

    assert [schema.name for schema in one.tool_schemas] == ["echo"]
    assert "user_id" not in str(one.tool_schemas[0].parameters)
    assert one.tool_catalog_version != two.tool_catalog_version


@pytest.mark.asyncio
async def test_unknown_tool_is_a_structured_result_and_a_trace():
    traces: list[dict] = []
    catalog = ToolCatalog((spec(),), trace_writer=traces.append)

    result = await catalog.dispatch(
        "missing",
        {},
        context(),
        call_id="call-9",
        thread_id="thread-1",
        request_message_id=11,
    )

    assert result == {
        "error": {
            "code": "unknown_tool",
            "tool_name": "missing",
            "available_tools": ["echo"],
        },
        # The refusal says what to do next, once, and the codes it may say it
        # for are a closed table (``RECOVERY_HINTS``).
        "hint": "call one of the tools this result lists as available",
    }
    assert traces[0]["status"] == "unknown_tool"
    assert traces[0]["request_message_id"] == 11
    # The route's own call id reaches the trace, which is what lets a citation
    # be joined to the row holding the result it names.
    assert traces[0]["tool_call_id"] == "call-9"


@pytest.mark.asyncio
async def test_result_budget_names_the_tool_and_serialized_size():
    async def too_large(_context: ToolContext, _arguments: dict) -> dict:
        return {"payload": "x" * MAX_TOOL_RESULT_BYTES}

    catalog = ToolCatalog(
        (
            ToolSpec(
                name="too_large",
                description="Return too much data.",
                parameters={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                callable=too_large,
            ),
        ),
        trace_writer=lambda _trace: None,
    )

    with pytest.raises(ToolResultTooLarge, match=r"too_large.*[0-9]+ bytes"):
        await catalog.dispatch("too_large", {}, context())


def test_only_signal_registry_fields_serialize_and_null_fpr_stays_in_schema():
    name = "volatility_regime.gk_variance_robust_z"

    schema = registered_field_schema(name)
    payload = serialize_registered_field(
        name,
        value=3.2,
        details={"sessions": 63, "not_registered_for_this_field": 999},
    )

    assert "false-positive rate" in schema["description"]
    assert "null_fpr" not in str(payload)
    assert payload["details"] == {"sessions": 63}
    with pytest.raises(KeyError):
        serialize_registered_field("unregistered.computation", value=1)

    catalog = ToolCatalog(
        (
            ToolSpec(
                name="registered_echo",
                description="Schema metadata test.",
                parameters={"type": "object", "properties": {}},
                callable=echo,
                registered_fields=(name,),
            ),
        ),
        trace_writer=lambda _trace: None,
    )
    assert "false-positive rate" in catalog.tool_schemas[0].description


@pytest.mark.asyncio
async def test_callable_cannot_smuggle_an_unregistered_computation():
    async def unregistered(_context: ToolContext, _arguments: dict) -> dict:
        return {REGISTERED_FIELD_VALUES_KEY: {"unregistered.value": object()}}

    catalog = ToolCatalog(
        (
            ToolSpec(
                name="unregistered",
                description="Must be refused.",
                parameters={"type": "object", "properties": {}},
                callable=unregistered,
            ),
        ),
        trace_writer=lambda _trace: None,
    )

    with pytest.raises(ValueError, match="undeclared registered fields"):
        await catalog.dispatch("unregistered", {}, context())


@pytest.mark.asyncio
async def test_store_only_dispatch_blocks_provider_access_even_inside_to_thread():
    touched: list[bool] = []

    def provider_source() -> None:
        ensure_provider_source_allowed()
        touched.append(True)

    async def reaches_provider(_context: ToolContext, _arguments: dict) -> dict:
        await asyncio.to_thread(provider_source)
        return {"unreachable": True}

    catalog = ToolCatalog(
        (
            ToolSpec(
                name="reaches_provider",
                description="Must be blocked.",
                parameters={"type": "object", "properties": {}},
                callable=reaches_provider,
            ),
        ),
        trace_writer=lambda _trace: None,
    )

    with pytest.raises(ProviderSourceAccessForbidden, match="store-only"):
        await catalog.dispatch("reaches_provider", {}, context())
    assert touched == []


# --- recovery hints -------------------------------------------------------


def test_a_result_that_answered_carries_no_hint():
    # A suggestion attached to a successful call is a prompt, and prompts belong
    # in the Contract where a version records them.
    assert recovery_hint({"symbol": "FPT", "close": 95.4}) is None
    assert recovery_hint({"reason": None, "items": []}) is None


def test_the_envelopes_own_refusal_outranks_a_refused_window_inside_it():
    both = {
        "reason": "not_in_universe",
        "suggestions": [],
        "window_health": {"refusal": "insufficient_history"},
    }

    assert recovery_hint(both) == RECOVERY_HINTS["not_in_universe"]
    # A result that answered as a whole, with one field it could not compute,
    # gets the hint about the field.
    window_only = {"symbol": "FPT", "window_health": {"refusal": "insufficient_history"}}
    assert "shorter than this field needs" in str(recovery_hint(window_only))


def test_a_refusal_code_with_nothing_useful_to_suggest_says_nothing():
    assert recovery_hint({"reason": "some_new_code_nobody_wrote_a_hint_for"}) is None


@pytest.mark.asyncio
async def test_a_hint_that_would_not_fit_is_dropped_rather_than_the_result():
    async def nearly_full(_context: ToolContext, _arguments: dict) -> dict:
        # A refusal whose envelope already fills the budget. The hint is the
        # garnish; the refusal is what the model needs.
        return {
            "reason": "web_unavailable",
            "detail": "x" * (MAX_TOOL_RESULT_BYTES - 100),
        }

    catalog = ToolCatalog(
        (
            ToolSpec(
                name="nearly_full",
                description="A refusal that barely fits.",
                parameters={"type": "object", "properties": {}},
                callable=nearly_full,
            ),
        ),
        trace_writer=lambda _trace: None,
    )

    result = await catalog.dispatch("nearly_full", {}, context())

    assert result["reason"] == "web_unavailable"
    assert "hint" not in result


@pytest.mark.asyncio
async def test_a_tools_own_hint_is_never_overwritten():
    async def opinionated(_context: ToolContext, _arguments: dict) -> dict:
        return {"reason": "web_unavailable", "hint": "ask the store instead"}

    catalog = ToolCatalog(
        (
            ToolSpec(
                name="opinionated",
                description="A tool that writes its own hint.",
                parameters={"type": "object", "properties": {}},
                callable=opinionated,
            ),
        ),
        trace_writer=lambda _trace: None,
    )

    result = await catalog.dispatch("opinionated", {}, context())

    assert result["hint"] == "ask the store instead"


def test_a_declared_result_budget_is_readable_as_the_registry_rung():
    declared = ToolCatalog(
        (
            spec("echo"),
            ToolSpec(
                name="bulky",
                description="Returns a lot.",
                parameters={"type": "object", "properties": {}},
                callable=echo,
                result_budget_bytes=MAX_TOOL_RESULT_BYTES,
            ),
        ),
        trace_writer=lambda _trace: None,
    )

    # Only what was declared. A tool that declared nothing is absent, which is
    # how it inherits the spillover default — including every MCP tool.
    assert declared.result_budgets == {"bulky": MAX_TOOL_RESULT_BYTES}
