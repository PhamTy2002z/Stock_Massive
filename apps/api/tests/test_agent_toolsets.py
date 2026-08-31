"""What a toolset name expands to, including the ones built from others."""

from __future__ import annotations

import pytest

from src.agent import toolsets


@pytest.fixture(autouse=True)
def _memo():
    toolsets.clear_memo()
    yield
    toolsets.clear_memo()


def test_the_shipped_toolsets_hold_the_five_tools_and_nothing_else():
    resolved = toolsets.resolve_toolset(["web", "memory"])

    assert resolved == (
        "web_search",
        "fetch_url",
        "session_search",
        "remember_fact",
        "recall_facts",
    )


def test_one_name_may_be_passed_without_a_sequence():
    assert toolsets.resolve_toolset("web") == (
        "web_search",
        "fetch_url",
    )


def test_an_include_is_expanded_recursively_and_deduplicated():
    table = {
        "leaf": {"tools": ("a", "b")},
        "middle": {"tools": ("c",), "includes": ("leaf",)},
        "root": {"tools": ("b", "d"), "includes": ("middle", "leaf")},
    }

    assert toolsets.resolve_toolset(["root"], toolsets=table) == ("a", "b", "c", "d")


def test_a_deep_diamond_resolves_without_re_expanding_its_shared_branches():
    # Without a memo this table expands 2**depth times; the assertion that
    # matters is that the call returns at all.
    depth = 24
    table: dict[str, dict[str, tuple[str, ...]]] = {"level_0": {"tools": ("tool_0",)}}
    for level in range(1, depth + 1):
        table[f"level_{level}"] = {
            "tools": (f"tool_{level}",),
            "includes": (f"level_{level - 1}", f"level_{level - 1}"),
        }

    resolved = toolsets.resolve_toolset([f"level_{depth}"], toolsets=table)

    assert resolved == tuple(f"tool_{level}" for level in range(depth + 1))


def test_an_expansion_is_remembered_across_calls():
    first = toolsets.resolve_toolset(["web"])

    second = toolsets.resolve_toolset(["web"])

    assert first == second
    # The memo is what makes the second call free; asking for it directly is how
    # a regression that drops it becomes visible.
    assert toolsets._MEMO["web"] == (
        "web_search",
        "fetch_url",
    )


def test_an_unknown_toolset_is_refused_rather_than_resolving_to_nothing():
    with pytest.raises(toolsets.UnknownToolsetError):
        toolsets.resolve_toolset(["web", "typo"])


def test_a_cycle_is_refused():
    table = {
        "a": {"tools": ("one",), "includes": ("b",)},
        "b": {"tools": ("two",), "includes": ("a",)},
    }

    with pytest.raises(toolsets.ToolsetCycleError):
        toolsets.resolve_toolset(["a"], toolsets=table)


def test_core_tools_lead_the_resolved_list(monkeypatch):
    monkeypatch.setattr(toolsets, "CORE_TOOLS", ("always_here",))

    assert toolsets.resolve_toolset(["web"])[0] == "always_here"


def test_a_toolset_describes_itself_for_the_prompt():
    assert "open web" in toolsets.describe("web")
    with pytest.raises(toolsets.UnknownToolsetError):
        toolsets.describe("typo")
