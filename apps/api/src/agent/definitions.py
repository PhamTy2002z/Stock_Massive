"""The single point that builds the tool list sent to the model.

Every other layer asks here, and that is the whole design: two places building
this list is two places that can disagree about what the model was offered,
which is the one disagreement a trace cannot resolve afterwards.

The work itself is cheap but not free — expand the toolsets, ask the registry
which of those tools are available, assemble the schemas — and it happens on
every round of every Turn. So it is cached, and the cache has to answer two
different staleness questions:

* **A tool appeared or left.** The registry's generation counter changes, and a
  generation is part of the key, so the old entry can never be served.
* **A gate flipped without any registration changing** — an API key arrives, a
  feature flag is switched. Nothing bumps the generation, so the entry carries
  its own short expiry instead: it lives exactly as long as the registry trusts
  one availability verdict, and rebuilding it re-probes.

The cache is bounded. Keys are combinations of toolset names, which is a small
set today and an unbounded one the moment toolsets become per-user, so it evicts
least-recently-used rather than growing.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Sequence

from src.core.llm import ToolSchema

from . import registry
from .toolsets import TOOLSETS, resolve_toolset

#: How many distinct toolset combinations stay cached. Well above the handful a
#: deployment uses, low enough that the cache cannot become the leak.
MAX_CACHE_ENTRIES = 32

_CacheKey = tuple[int, tuple[str, ...]]

_CACHE: OrderedDict[_CacheKey, tuple[float, tuple[ToolSchema, ...]]] = OrderedDict()


def get_tool_definitions(
    toolsets: Sequence[str] | str | None = None, *, now: float | None = None
) -> tuple[ToolSchema, ...]:
    """The schemas for these toolsets, availability applied, order stable.

    ``toolsets=None`` means every toolset this build knows, which is what a
    Turn with no narrower configuration gets. ``now`` is a monotonic reading,
    injectable so a test can age the cache rather than sleep.
    """
    selected = _selection(toolsets)
    instant = time.monotonic() if now is None else float(now)
    key: _CacheKey = (registry.generation(), selected)
    cached = _CACHE.get(key)
    if cached is not None and instant < cached[0]:
        _CACHE.move_to_end(key)
        return cached[1]
    schemas = registry.definitions(resolve_toolset(selected), now=instant)
    _CACHE[key] = (instant + registry.CHECK_TTL_SECONDS, schemas)
    _CACHE.move_to_end(key)
    _evict(key)
    return schemas


def _selection(toolsets: Sequence[str] | str | None) -> tuple[str, ...]:
    if toolsets is None:
        return tuple(TOOLSETS)
    if isinstance(toolsets, str):
        return (toolsets,)
    # Deduplicated but not sorted: the order the caller asked in is the order
    # the model reads, and reordering it would move the cacheable prefix.
    seen: list[str] = []
    for name in toolsets:
        if name not in seen:
            seen.append(name)
    return tuple(seen)


def _evict(current: _CacheKey) -> None:
    """Drop entries from superseded generations first, then the oldest."""
    generation = current[0]
    for key in [key for key in _CACHE if key[0] != generation]:
        del _CACHE[key]
    while len(_CACHE) > MAX_CACHE_ENTRIES:
        _CACHE.popitem(last=False)


def clear_cache() -> None:
    """Forget every built list. For tests and for a deliberate rebuild."""
    _CACHE.clear()


def cache_size() -> int:
    return len(_CACHE)


__all__ = ["MAX_CACHE_ENTRIES", "cache_size", "clear_cache", "get_tool_definitions"]
