"""What the registry refuses, what it caches, and what it tells layers above."""

from __future__ import annotations

import pytest

from src.agent import registry

from .agent_tool_world import echo, isolated_registry, stub_entry


@pytest.fixture(autouse=True)
def _registry():
    with isolated_registry():
        yield


def test_a_second_toolset_may_not_shadow_a_registered_name():
    registry.register(stub_entry("read_thing", toolset="alpha"))

    with pytest.raises(registry.ToolShadowError) as raised:
        registry.register(stub_entry("read_thing", toolset="beta"))

    assert raised.value.existing_toolset == "alpha"
    assert raised.value.new_toolset == "beta"
    assert registry.get("read_thing").toolset == "alpha"


def test_shadowing_is_possible_when_it_is_stated():
    registry.register(stub_entry("read_thing", toolset="alpha"))

    registry.register(stub_entry("read_thing", toolset="beta"), override=True)

    assert registry.get("read_thing").toolset == "beta"


def test_the_same_toolset_may_re_register_its_own_tool():
    registry.register(stub_entry("read_thing", toolset="alpha", description="first"))

    registry.register(stub_entry("read_thing", toolset="alpha", description="second"))

    assert registry.get("read_thing").description == "second"


def test_registration_and_removal_move_the_generation():
    first = registry.generation()

    registry.register(stub_entry("read_thing"))
    after_register = registry.generation()
    registry.deregister("read_thing")
    after_deregister = registry.generation()

    assert first < after_register < after_deregister
    assert registry.deregister("read_thing") is False
    assert registry.generation() == after_deregister


def test_an_availability_check_is_not_repeated_inside_its_window():
    probes: list[int] = []
    registry.register(
        stub_entry("gated", check_fn=lambda: bool(probes.append(1)) or True)
    )

    assert registry.is_available("gated", now=100.0) is True
    assert registry.is_available("gated", now=100.0 + registry.CHECK_TTL_SECONDS - 1) is True
    assert len(probes) == 1

    assert registry.is_available("gated", now=100.0 + registry.CHECK_TTL_SECONDS + 1) is True
    assert len(probes) == 2


def test_re_registering_a_tool_forgets_its_cached_verdict():
    registry.register(stub_entry("gated", check_fn=lambda: False))
    assert registry.is_available("gated", now=10.0) is False

    registry.register(stub_entry("gated", check_fn=lambda: True))

    assert registry.is_available("gated", now=10.0) is True


def test_a_raising_check_hides_only_its_own_tool():
    def broken() -> bool:
        raise RuntimeError("the probe is broken")

    registry.register(stub_entry("broken", check_fn=broken))
    registry.register(stub_entry("healthy"))

    assert registry.is_available("broken", now=0.0) is False
    assert registry.availability("broken", now=0.0)[1] is (
        registry.AvailabilityReason.CHECK_FAILED
    )
    assert [schema.name for schema in registry.definitions(now=0.0)] == ["healthy"]


def test_a_missing_environment_variable_withholds_the_tool(monkeypatch):
    monkeypatch.delenv("STOCK_MASSIVE_TEST_TOKEN", raising=False)
    registry.register(
        stub_entry("needs_token", requires_env=("STOCK_MASSIVE_TEST_TOKEN",))
    )

    assert registry.is_available("needs_token", now=0.0) is False

    monkeypatch.setenv("STOCK_MASSIVE_TEST_TOKEN", "present")

    assert registry.is_available("needs_token", now=1_000.0) is True


def test_definitions_follow_the_requested_order_and_skip_unknown_names():
    registry.register(stub_entry("one"))
    registry.register(stub_entry("two"))

    schemas = registry.definitions(["two", "missing", "one", "two"], now=0.0)

    assert [schema.name for schema in schemas] == ["two", "one"]


def test_a_declared_result_size_is_readable_by_the_budget():
    registry.register(stub_entry("big", max_result_size_chars=12_345))
    registry.register(stub_entry("plain"))

    assert registry.get_max_result_size("big") == 12_345
    assert registry.get_max_result_size("plain") is None
    assert registry.declared_result_sizes() == {"big": 12_345}


def test_a_registration_without_a_description_is_refused():
    with pytest.raises(ValueError):
        registry.register(stub_entry("silent", description="  "))


def test_legacy_or_unknown_metadata_defaults_conservatively():
    entry = stub_entry("legacy")

    assert entry.effect is registry.ToolEffect.UNKNOWN
    assert entry.idempotency is registry.ToolIdempotency.NON_IDEMPOTENT
    assert entry.access is registry.ToolAccess.NETWORK
    assert entry.content_trust is registry.ContentTrust.UNTRUSTED
    assert entry.concurrency is registry.ToolConcurrency.SERIALIZED
    assert entry.reads_external is True


def test_conflicting_trust_compatibility_fields_are_refused():
    with pytest.raises(ValueError, match="conflicting"):
        stub_entry(
            "conflict",
            reads_external=False,
            content_trust=registry.ContentTrust.UNTRUSTED,
        )


def test_availability_reasons_are_sanitized(monkeypatch):
    secret_name = "STOCK_MASSIVE_SECRET_TOKEN"
    monkeypatch.delenv(secret_name, raising=False)
    registry.register(stub_entry("missing", requires_env=(secret_name,)))

    available, reason, _ = registry.availability("missing", now=0.0)

    assert available is False
    assert reason is registry.AvailabilityReason.REQUIREMENTS_MISSING
    assert secret_name not in reason.value


# -- the two names every tool carries ------------------------------------------


class TestAToolNamesItselfTwice:
    """``name`` is what the model calls; ``display_name`` is what a person reads.

    Kept as a refusal in ``register`` rather than as a table somewhere else,
    because a table is a list somebody has to remember to extend and the tool
    that gets forgotten is the newest one. A real Turn showed fourteen rows
    reading ``get_field`` for exactly that reason.
    """

    def test_a_registration_with_no_reader_facing_name_is_refused(self):
        with isolated_registry():
            with pytest.raises(ValueError, match="display_name"):
                registry.register(
                    registry.ToolEntry(
                        name="nameless",
                        toolset="stub",
                        schema=registry.object_schema({}),
                        handler=echo,
                        description="the model can read this",
                    )
                )

    def test_a_blank_reader_facing_name_is_refused_too(self):
        with isolated_registry():
            with pytest.raises(ValueError, match="display_name"):
                registry.register(stub_entry("blank", display_name="   "))

    def test_every_tool_this_build_offers_declares_both_names(self):
        """The structural guarantee, over the real surface rather than a stub."""
        from src.agent import tools

        with isolated_registry():
            tools.register_all()
            entries = registry.entries()

            assert entries
            for item in entries:
                assert item.display_name.strip(), item.name
                # The two are for two audiences and are never the same string:
                # a rail row saying `get_field` tells a reader nothing, and a
                # model asked to call "Đọc chỉ báo" has nothing to call.
                assert item.display_name != item.name, item.name
