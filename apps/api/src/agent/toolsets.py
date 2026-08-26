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
    # Selected by both lanes now. It was the Analysis lane's alone while the
    # chat surface's whole boundary was that it read none of this system's data
    # (``1e7b936``); what changed is that these tools carry a figure's health and
    # its asOf with it, so a conversation using one can say what session it is
    # from and under what condition. The two lanes get two signatures out of one
    # registration — see ``tools/signals.py``.
    "signals": {
        "description": (
            "Read one registered Signal Field out of this system's own store — "
            "as one figure or as a series across sessions — and check a price "
            "published elsewhere against the exchange that would have had to "
            "produce it."
        ),
        "tools": (
            "list_fields",
            "get_field",
            "get_series",
            "check_price_claim",
        ),
    },
    # A Study answers what a figure cannot: a shape rather than a number. The
    # bundle is separate from ``signals`` because the two are different kinds of
    # read — one returns a number the model puts in a sentence, the other
    # returns a picture the model never sees and a reader does.
    "studies": {
        "description": (
            "Run a named, versioned analysis recipe over this system's own "
            "store, or compose a canvas out of numbers already gathered, and "
            "draw either as a panel the reader can open."
        ),
        "tools": ("list_studies", "run_study", "render_canvas"),
    },
}


#: What a conversation may reach for, and the only selection the chat lane makes.
#:
#: A list of *toolset names* rather than of tools, which is the distinction this
#: module's opening paragraph is about: the members of a bundle move when a
#: capability is switched on, and this does not. It is written down because the
#: alternative is a default of "everything registered", and the day a bundle was
#: added for another lane that default would hand it to every Turn without a
#: single line changing.
#:
#: ``signals`` is here as of the reversal recorded in ``tools/signals.py``, and
#: ``studies`` since a conversation gained a canvas to draw on. Both are written
#: down rather than defaulted: a fifth bundle added tomorrow does not reach a
#: conversation until this tuple says so.
CHAT_TOOLSETS: tuple[str, ...] = ("web", "memory", "signals", "studies")


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
_MEMO_CATALOGUE_IDENTITY: tuple[object, ...] | None = None


def _catalogue_identity(catalogue: Mapping[str, Toolset]) -> tuple[object, ...]:
    return (
        CORE_TOOLS,
        *(
            (
                name,
                tuple(toolset.get("includes", ())),
                tuple(toolset.get("tools", ())),
            )
            for name, toolset in catalogue.items()
        ),
    )


def resolve_toolset(
    names: Sequence[str] | str,
    *,
    toolsets: Mapping[str, Toolset] | None = None,
) -> tuple[str, ...]:
    """Every tool the named toolsets offer, deduplicated, order preserved.

    :data:`CORE_TOOLS` comes first so the prompt prefix does not move when a
    Turn selects a different bundle.
    """
    global _MEMO_CATALOGUE_IDENTITY
    catalogue = TOOLSETS if toolsets is None else toolsets
    # The module-level memo is only valid for the module's own table; a caller
    # passing its own catalogue gets a fresh expansion.
    if toolsets is None:
        identity = _catalogue_identity(catalogue)
        if identity != _MEMO_CATALOGUE_IDENTITY:
            _MEMO.clear()
            _MEMO_CATALOGUE_IDENTITY = identity
        memo = _MEMO
    else:
        memo = {}
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
    global _MEMO_CATALOGUE_IDENTITY
    _MEMO.clear()
    _MEMO_CATALOGUE_IDENTITY = None


def expansion_identity(names: Sequence[str] | str) -> tuple[str, ...]:
    """Ordered membership identity used by resolved-surface cache keys."""
    return resolve_toolset(names)


def describe(name: str, *, toolsets: Mapping[str, Toolset] | None = None) -> str:
    """What one toolset is for, as the prompt introduces it."""
    catalogue = TOOLSETS if toolsets is None else toolsets
    toolset = catalogue.get(name)
    if toolset is None:
        raise UnknownToolsetError(name, tuple(catalogue))
    return toolset.get("description", "")


def known_toolsets(*, toolsets: Mapping[str, Toolset] | None = None) -> tuple[str, ...]:
    return tuple(TOOLSETS if toolsets is None else toolsets)


def _check_the_chat_selection_holds() -> None:
    """Refuse to import a chat selection naming a bundle nobody registered.

    A misspelled name here is the worst kind of wrong: the chat lane would offer
    the model fewer tools than the deployment has, and from the outside that
    reads as a model choosing not to call anything rather than as a typo.

    This used to also refuse ``signals``, on the boundary ``1e7b936`` drew. That
    refusal is gone deliberately and not by omission — the reason is in
    ``tools/signals.py`` and in the commit that moved it. What still holds is
    that the selection is *written down*: a bundle added for another lane does
    not reach a conversation until this tuple names it.
    """
    unknown = [name for name in CHAT_TOOLSETS if name not in TOOLSETS]
    if unknown:
        raise UnknownToolsetError(unknown[0], tuple(TOOLSETS))


_check_the_chat_selection_holds()


__all__ = [
    "CHAT_TOOLSETS",
    "CORE_TOOLS",
    "TOOLSETS",
    "Toolset",
    "ToolsetCycleError",
    "UnknownToolsetError",
    "clear_memo",
    "describe",
    "expansion_identity",
    "known_toolsets",
    "resolve_toolset",
]
