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

#: The bundles that belong to no domain: they answer questions about anything,
#: so every pack gets them and no pack declares them. The split is the whole
#: point of a pack — what is left over after these is what makes this deployment
#: about one subject rather than another, and that remainder is
#: ``active_pack().toolsets``.
CORE_TOOLSETS: tuple[str, ...] = ("web", "memory")

TOOLSETS: dict[str, Toolset] = {
    "web": {
        "description": (
            "Search the open web, read one public page, and put figures read "
            "off a page onto the Signal Desk."
        ),
        "tools": (
            "web_search",
            "fetch_url",
            # In this bundle and not one of its own because it is about the web:
            # it reads a page this Turn already fetched and nothing else, and a
            # deployment without the web has nothing for it to check against.
            "frame_from_evidence",
        ),
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
            "Read this system's own store: one registered Signal Field as a "
            "figure or a series, a table of many symbols across many periods, a "
            "comparison of symbols on several fields — and check a price "
            "published elsewhere against the exchange that would have had to "
            "produce it."
        ),
        "tools": (
            "list_fields",
            "get_field",
            "get_series",
            "check_price_claim",
            # The table half of the same plane, added with the analysis
            # compiler. In this bundle and not one of their own because they
            # read exactly what the four above read — this system's store, under
            # the same Universe and closed-session rules — and a bundle is a
            # statement about *what a tool reads*, not about what shape it
            # returns.
            "query",
            "compare_fields",
        ),
    },
    # A Study answers what a figure cannot: a shape rather than a number. The
    # bundle is separate from ``signals`` because the two are different kinds of
    # read — one returns a number the model puts in a sentence, the other
    # returns a picture the model never sees and a reader does.
    "studies": {
        "description": (
            "Run a named, versioned analysis recipe over this system's own "
            "store, or compose a Signal Desk out of numbers already gathered, and "
            "draw either as a panel the reader can open."
        ),
        "tools": (
            "list_studies",
            "run_study",
            "render_signal_desk",
            # The calculation axis of the same plane. Here rather than in
            # ``signals`` because it reads no store table: its inputs are frames
            # this Turn already made, which is what a Study's own ``compute``
            # does, one step later.
            "compute",
        ),
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
#: ``studies`` since a conversation gained a Signal Desk to draw on. Both are written
#: down rather than defaulted: a fifth bundle added tomorrow does not reach a
#: conversation until this tuple says so.
#:
#: It is also :data:`CORE_TOOLSETS` followed by what the active pack declares,
#: and ``_check_the_selection_matches_the_pack`` refuses the import when it
#: stops being. Written down *and* held to the pack: the tuple a reader sees is
#: the real one, and swapping the pack cannot leave it behind saying the last
#: domain's name.
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


class ChatSelectionDisagreesWithPackError(ValueError):
    """The written-down selection and the active pack no longer say the same thing.

    Both properties above are kept, and this is what keeps them from being in
    tension. The selection stays *written down* — a reader of this file sees the
    real tuple, and a bundle registered for another lane still does not reach a
    conversation until this tuple names it. What it can no longer do is drift
    from the domain it is supposed to be the selection *for*.

    Raised at import rather than logged, on the same reasoning as
    ``_check_the_chat_selection_holds``: a deployment whose selection has drifted
    from its pack is a deployment handing the model a tool surface nobody
    approved, and one loud failure on the way up is cheaper than that served
    quietly. The message names both sides because the fix is always to change
    one of them and the reader has to know which.
    """

    def __init__(self, selection: Sequence[str], expected: Sequence[str]) -> None:
        super().__init__(
            f"CHAT_TOOLSETS is {tuple(selection)!r} but the active pack makes it "
            f"{tuple(expected)!r}; edit CHAT_TOOLSETS in agent/toolsets.py or the "
            "toolsets the pack declares in agent/domain/, so the two agree"
        )
        self.selection = tuple(selection)
        self.expected = tuple(expected)


def _check_the_selection_matches_the_pack() -> None:
    """Refuse to import a chat selection that has drifted from the active pack.

    Imported inside the function, not at module scope, and it is worth being
    exact about what that buys and what it does not. It buys one thing: by the
    time this runs, on the last executable line of the module, ``toolsets`` is
    fully defined — so a future ``domain`` that reached back for ``TOOLSETS`` or
    ``resolve_toolset`` would find them, where a module-scope import would have
    handed it a half-built module. It does **not** make this module independent
    of the domain: importing ``toolsets`` now transitively imports
    ``agent.domain`` and, through the pack, ``stocks.universe`` and
    ``stocks.signals.issues``. A cycle running the other way — something under
    ``stocks`` importing ``toolsets`` — would still break, and the reason it
    cannot today is that nothing under ``stocks`` or ``core`` imports
    ``src.agent`` at all. That is the edge to not add.

    Raising here rather than logging is the same trade ``_check_the_chat_
    selection_holds`` already makes: a deployment whose selection has drifted
    from its pack hands the model a tool surface nobody approved, and one loud
    failure on the way up is cheaper than that served quietly.
    """
    from .domain import active_pack

    expected = (*CORE_TOOLSETS, *active_pack().toolsets)
    if CHAT_TOOLSETS != expected:
        raise ChatSelectionDisagreesWithPackError(CHAT_TOOLSETS, expected)


_check_the_chat_selection_holds()
_check_the_selection_matches_the_pack()


__all__ = [
    "CHAT_TOOLSETS",
    "CORE_TOOLS",
    "CORE_TOOLSETS",
    "ChatSelectionDisagreesWithPackError",
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
