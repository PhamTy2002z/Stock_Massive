"""Named bundles of tools, and what one name expands to.

A Turn is configured with toolset *names*, never with a tool list: the surface a
deployment offers changes when a capability is switched on, and a list copied
into a caller is a list that goes stale where nobody looks. Expansion is
recursive through ``includes`` so a bundle can be composed of other bundles
without repeating their members.

Two things are decided here rather than left to callers.

**Unknown names are refused.** A misspelled toolset that silently expanded to
nothing would present the model with no tools at all and read, from the outside,
as a model that chose not to call anything.

**Expansion is memoised.** It runs on every round of every Turn, and its answer
only changes when this module changes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypedDict


class Toolset(TypedDict, total=False):
    """One bundle: what it is for, what it holds, what it pulls in."""

    description: str
    tools: tuple[str, ...]
    includes: tuple[str, ...]


#: Offered to every Turn regardless of which toolsets it selected. Empty on
#: purpose: nothing this agent can do is unconditional — web reads need an API
#: key and a feature flag, memory needs a signed-in user — so a tool that
#: bypassed selection would be a tool that bypassed its own gate too.
CORE_TOOLS: tuple[str, ...] = ()

TOOLSETS: dict[str, Toolset] = {
    "web": {
        "description": "Search the open web and read one public page.",
        "tools": ("web_search", "fetch_url"),
    },
    "memory": {
        "description": (
            "Search this user's own conversations and the facts they asked to keep."
        ),
        "tools": ("session_search", "remember_fact", "recall_facts"),
    },
}


class UnknownToolsetError(KeyError):
    """A toolset name nobody registered."""

    def __init__(self, name: str, known: Sequence[str]) -> None:
        super().__init__(
            f"unknown toolset {name!r}; known toolsets are {', '.join(sorted(known))}"
        )
        self.name = name


class ToolsetCycleError(ValueError):
    """A toolset includes itself, directly or through another.

    Raised rather than quietly resolving to what could be reached: a cycle means
    the table is wrong, and a surface silently missing half its tools is the
    hardest version of that to notice.
    """

    def __init__(self, name: str, ancestry: Sequence[str]) -> None:
        super().__init__(
            f"toolset {name!r} includes itself through {' -> '.join((*ancestry, name))}"
        )
        self.name = name


_MEMO: dict[str, tuple[str, ...]] = {}


def resolve_toolset(
    names: Sequence[str] | str,
    *,
    toolsets: Mapping[str, Toolset] | None = None,
) -> tuple[str, ...]:
    """Every tool the named toolsets offer, deduplicated, order preserved.

    :data:`CORE_TOOLS` comes first so the prompt prefix does not move when a
    Turn selects a different bundle.
    """
    catalogue = TOOLSETS if toolsets is None else toolsets
    # The module-level memo is only valid for the module's own table; a caller
    # passing its own catalogue gets a fresh expansion.
    memo = _MEMO if toolsets is None else {}
    wanted = (names,) if isinstance(names, str) else tuple(names)
    resolved: list[str] = list(CORE_TOOLS)
    for name in wanted:
        for tool in _expand(name, catalogue, memo, ()):
            if tool not in resolved:
                resolved.append(tool)
    return tuple(resolved)


def _expand(
    name: str,
    catalogue: Mapping[str, Toolset],
    memo: dict[str, tuple[str, ...]],
    ancestry: tuple[str, ...],
) -> tuple[str, ...]:
    if name in memo:
        return memo[name]
    if name in ancestry:
        raise ToolsetCycleError(name, ancestry)
    toolset = catalogue.get(name)
    if toolset is None:
        raise UnknownToolsetError(name, tuple(catalogue))
    collected: list[str] = []
    for included in toolset.get("includes", ()):
        for tool in _expand(included, catalogue, memo, (*ancestry, name)):
            if tool not in collected:
                collected.append(tool)
    for tool in toolset.get("tools", ()):
        if tool not in collected:
            collected.append(tool)
    # Every name is memoised, not only the ones asked for directly: a table
    # where two bundles include a third would otherwise expand it twice, and a
    # deeper table expands exponentially.
    expanded = tuple(collected)
    memo[name] = expanded
    return expanded


def clear_memo() -> None:
    """Forget every expansion. For a table that changed, and for tests."""
    _MEMO.clear()


def describe(name: str, *, toolsets: Mapping[str, Toolset] | None = None) -> str:
    """What one toolset is for, as the prompt introduces it."""
    catalogue = TOOLSETS if toolsets is None else toolsets
    toolset = catalogue.get(name)
    if toolset is None:
        raise UnknownToolsetError(name, tuple(catalogue))
    return toolset.get("description", "")


def known_toolsets(*, toolsets: Mapping[str, Toolset] | None = None) -> tuple[str, ...]:
    return tuple(TOOLSETS if toolsets is None else toolsets)


__all__ = [
    "CORE_TOOLS",
    "TOOLSETS",
    "Toolset",
    "ToolsetCycleError",
    "UnknownToolsetError",
    "clear_memo",
    "describe",
    "known_toolsets",
    "resolve_toolset",
]
