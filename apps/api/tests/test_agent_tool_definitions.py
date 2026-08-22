"""The one built tool list: what it caches, and what makes it rebuild."""

from __future__ import annotations

import pytest

from src.agent import definitions, registry, toolsets

from .agent_tool_world import isolated_registry, stub_entry


@pytest.fixture(autouse=True)
def _registry():
    with isolated_registry():
        yield


@pytest.fixture
def surface():
    """Two toolsets whose tools are all registered and all available."""
    registry.register(stub_entry("read_thing", toolset="reads"))
    registry.register(stub_entry("write_thing", toolset="writes"))
    table = {
        "reads": {"description": "reads", "tools": ("read_thing",)},
        "writes": {"description": "writes", "tools": ("write_thing",)},
    }
    toolsets.TOOLSETS.update(table)
    yield tuple(table)
    for name in table:
        toolsets.TOOLSETS.pop(name, None)
    toolsets.clear_memo()


def test_the_same_request_is_served_from_the_cache(surface):
    probes: list[int] = []
    registry.register(
        stub_entry(
            "read_thing",
            toolset="reads",
            check_fn=lambda: bool(probes.append(1)) or True,
        )
    )

    first = definitions.get_tool_definitions(["reads"], now=1_000.0)
    second = definitions.get_tool_definitions(["reads"], now=1_001.0)

    assert first == second
    assert [schema.name for schema in first] == ["read_thing"]
    assert len(probes) == 1


def test_a_new_registration_invalidates_the_built_list(surface):
    before = definitions.get_tool_definitions(["reads", "writes"], now=1_000.0)
    registry.register(stub_entry("read_more", toolset="reads"))
    toolsets.TOOLSETS["reads"] = {"description": "reads", "tools": ("read_thing", "read_more")}
    toolsets.clear_memo()

    after = definitions.get_tool_definitions(["reads", "writes"], now=1_000.0)

    assert [schema.name for schema in before] == ["read_thing", "write_thing"]
    assert [schema.name for schema in after] == ["read_thing", "read_more", "write_thing"]


def test_removing_a_tool_invalidates_the_built_list(surface):
    definitions.get_tool_definitions(["writes"], now=1_000.0)

    registry.deregister("write_thing")

    assert definitions.get_tool_definitions(["writes"], now=1_000.0) == ()


def test_a_gate_that_flips_is_picked_up_when_the_entry_expires(surface):
    enabled = {"value": False}
    registry.register(
        stub_entry("read_thing", toolset="reads", check_fn=lambda: enabled["value"])
    )

    assert definitions.get_tool_definitions(["reads"], now=1_000.0) == ()
    enabled["value"] = True
    assert definitions.get_tool_definitions(["reads"], now=1_005.0) == ()

    later = 1_000.0 + registry.CHECK_TTL_SECONDS + 1
    assert [
        schema.name for schema in definitions.get_tool_definitions(["reads"], now=later)
    ] == ["read_thing"]


def test_the_requested_order_is_the_order_the_model_reads(surface):
    forward = definitions.get_tool_definitions(["reads", "writes"], now=1_000.0)
    backward = definitions.get_tool_definitions(["writes", "reads"], now=1_000.0)

    assert [schema.name for schema in forward] == ["read_thing", "write_thing"]
    assert [schema.name for schema in backward] == ["write_thing", "read_thing"]


def test_the_cache_stays_bounded_as_combinations_pile_up():
    many = {}
    for index in range(MANY := definitions.MAX_CACHE_ENTRIES * 2):
        name = f"set_{index}"
        registry.register(stub_entry(f"tool_{index}", toolset=name))
        many[name] = {"description": name, "tools": (f"tool_{index}",)}
    toolsets.TOOLSETS.update(many)
    try:
        for index in range(MANY):
            definitions.get_tool_definitions([f"set_{index}"], now=1_000.0)

        assert definitions.cache_size() == definitions.MAX_CACHE_ENTRIES
    finally:
        for name in many:
            toolsets.TOOLSETS.pop(name, None)
        toolsets.clear_memo()


def test_no_toolsets_named_means_everything_this_build_offers(surface):
    schemas = definitions.get_tool_definitions(now=1_000.0)

    assert {schema.name for schema in schemas} == {"read_thing", "write_thing"}
