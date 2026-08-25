"""The one built tool list: what it caches, and what makes it rebuild."""

from __future__ import annotations

from collections import OrderedDict
from threading import Event, Thread, current_thread

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


def test_surface_owns_schema_policy_lookup_and_availability(surface):
    resolved = definitions.resolve_tool_surface(["reads", "writes"], now=1_000.0)

    assert resolved.expanded_names == ("read_thing", "write_thing")
    assert tuple(resolved.by_name) == resolved.expanded_names
    assert resolved.offered_schemas == tuple(
        tool.schema for tool in resolved.tools if tool.available
    )
    assert resolved.unavailable_reasons == {}
    with pytest.raises(TypeError):
        resolved.by_name["other"] = resolved.tools[0]


def test_frozen_sequence_schemas_keep_exact_strict_wire_projection(surface):
    entry = stub_entry(
        "read_thing",
        toolset="reads",
        schema=registry.object_schema(
            {"value": {"type": ["string", "number"]}},
        ),
    )
    registry.register(entry)

    resolved = definitions.resolve_tool_surface("reads", now=1_000.0)

    assert resolved.by_name["read_thing"].schema.as_wire() == entry.as_schema().as_wire()


def test_surface_keeps_handler_and_policy_atomic_after_re_registration(surface):
    async def replacement(_context, _arguments):
        return "replacement"

    before = definitions.resolve_tool_surface(["reads"], now=1_000.0)
    registry.register(
        stub_entry(
            "read_thing",
            toolset="reads",
            handler=replacement,
            effect=registry.ToolEffect.WRITE,
        )
    )
    after = definitions.resolve_tool_surface(["reads"], now=1_000.0)

    assert before.by_name["read_thing"].handler is not replacement
    assert before.by_name["read_thing"].effect is registry.ToolEffect.UNKNOWN
    assert after.by_name["read_thing"].handler is replacement
    assert after.by_name["read_thing"].effect is registry.ToolEffect.WRITE
    assert before.registry_generation != after.registry_generation


def test_resolved_schema_is_detached_from_later_declaration_mutation(surface):
    resolved = definitions.resolve_tool_surface(["reads"], now=1_000.0)
    declared = registry.get("read_thing")
    assert declared is not None

    declared.schema["properties"]["value"]["type"] = "integer"

    assert resolved.by_name["read_thing"].schema.parameters["properties"]["value"][
        "type"
    ] == "string"
    with pytest.raises(TypeError):
        resolved.by_name["read_thing"].schema.parameters["type"] = "array"
    with pytest.raises(TypeError):
        resolved.by_name["read_thing"].schema.parameters["properties"]["value"][
            "type"
        ] = "number"
    with pytest.raises((AttributeError, TypeError)):
        resolved.by_name["read_thing"].schema.parameters["required"].append("other")
    with pytest.raises(TypeError):
        list.append(
            resolved.by_name["read_thing"].schema.parameters["required"],
            "other",
        )


def test_registry_mutation_during_probe_retries_to_one_atomic_generation():
    async def old_handler(_context, _arguments):
        return "old"

    async def new_handler(_context, _arguments):
        return "new"

    def replace_during_probe():
        registry.register(
            stub_entry(
                "probe",
                toolset="reads",
                handler=new_handler,
                check_fn=lambda: False,
            )
        )
        return True

    registry.register(
        stub_entry(
            "probe",
            toolset="reads",
            handler=old_handler,
            check_fn=replace_during_probe,
        )
    )
    toolsets.TOOLSETS["reads"] = {
        "description": "reads",
        "tools": ("probe",),
    }
    try:
        resolved = definitions.resolve_tool_surface("reads", now=1_000.0)
        tool = resolved.by_name["probe"]

        assert resolved.registry_generation == registry.generation()
        assert tool.handler is new_handler
        assert tool.available is False
        assert tool.unavailable_reason is registry.AvailabilityReason.CHECK_REFUSED
        assert definitions.resolve_tool_surface("reads", now=1_001.0) is resolved
    finally:
        toolsets.TOOLSETS.pop("reads", None)
        toolsets.clear_memo()


def test_concurrent_generation_eviction_cannot_break_a_cache_hit(surface, monkeypatch):
    initial = definitions.resolve_tool_surface("reads", now=1_000.0)
    reader_at_move = Event()
    release_reader = Event()
    replacement_stored = Event()
    reader_errors: list[BaseException] = []

    class PausingCache(OrderedDict):
        def __setitem__(self, key, value):
            super().__setitem__(key, value)
            if key[0] != initial.registry_generation:
                replacement_stored.set()

        def move_to_end(self, key, last=True):
            if (
                current_thread().name == "surface-reader"
                and key[0] == initial.registry_generation
            ):
                reader_at_move.set()
                assert release_reader.wait(2.0)
            super().move_to_end(key, last=last)

    monkeypatch.setattr(definitions, "_CACHE", PausingCache(definitions._CACHE))

    def read_cached_surface():
        try:
            definitions.resolve_tool_surface("reads", now=1_001.0)
        except BaseException as exc:  # noqa: BLE001 - assertion captures the race
            reader_errors.append(exc)

    reader = Thread(target=read_cached_surface, name="surface-reader")
    reader.start()
    assert reader_at_move.wait(2.0)

    registry.register(stub_entry("read_thing", toolset="reads", description="new"))
    builder = Thread(
        target=lambda: definitions.resolve_tool_surface("reads", now=1_001.0),
        name="surface-builder",
    )
    builder.start()
    replacement_stored.wait(0.25)
    release_reader.set()
    reader.join(2.0)
    builder.join(2.0)

    assert not reader.is_alive()
    assert not builder.is_alive()
    assert replacement_stored.is_set()
    assert reader_errors == []


def test_toolset_only_membership_mutation_cannot_serve_a_stale_surface():
    registry.register(stub_entry("first", toolset="reads"))
    registry.register(stub_entry("second", toolset="reads"))
    toolsets.TOOLSETS["reads"] = {"description": "reads", "tools": ("first",)}
    try:
        before = definitions.resolve_tool_surface(["reads"], now=1_000.0)
        toolsets.TOOLSETS["reads"] = {
            "description": "reads",
            "tools": ("second",),
        }
        after = definitions.resolve_tool_surface(["reads"], now=1_000.0)

        assert before.expanded_names == ("first",)
        assert after.expanded_names == ("second",)
        assert before is not after
    finally:
        toolsets.TOOLSETS.pop("reads", None)
        toolsets.clear_memo()


def test_unavailable_and_missing_names_are_sanitized_without_hiding_siblings():
    registry.register(
        stub_entry("hidden", toolset="reads", check_fn=lambda: False)
    )
    registry.register(stub_entry("visible", toolset="reads"))
    toolsets.TOOLSETS["reads"] = {
        "description": "reads",
        "tools": ("hidden", "missing", "visible"),
    }
    try:
        resolved = definitions.resolve_tool_surface(["reads"], now=1_000.0)

        assert [schema.name for schema in resolved.offered_schemas] == ["visible"]
        assert resolved.unavailable_reasons == {
            "hidden": registry.AvailabilityReason.CHECK_REFUSED,
            "missing": registry.AvailabilityReason.NOT_REGISTERED,
        }
    finally:
        toolsets.TOOLSETS.pop("reads", None)
        toolsets.clear_memo()


def test_surface_identity_is_stable_and_contains_no_callable_repr(surface):
    first = definitions.resolve_tool_surface(["reads", "writes"], now=1_000.0)
    second = definitions.resolve_tool_surface(["reads", "writes"], now=1_001.0)
    wire = first.identity_payload()

    assert first is second
    assert first.identity_digest == second.identity_digest
    assert "0x" not in str(wire)
    assert "handler" not in wire["tools"][0]
    assert wire["tools"][0]["handler_identity"].endswith(".echo")
