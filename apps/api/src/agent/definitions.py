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

import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from threading import RLock
from types import MappingProxyType
from typing import Any

from src.core.llm import ToolSchema

from . import registry
from .toolsets import TOOLSETS, expansion_identity

#: How many distinct toolset combinations stay cached. Well above the handful a
#: deployment uses, low enough that the cache cannot become the leak.
MAX_CACHE_ENTRIES = 32

_CacheKey = tuple[int, tuple[str, ...]]


@dataclass(frozen=True)
class ResolvedToolSurface:
    """One ordered, immutable capability snapshot for a task."""

    tools: tuple[registry.ResolvedTool, ...]
    registry_generation: int
    expanded_names: tuple[str, ...]
    expires_at: float
    missing: tuple[tuple[str, registry.AvailabilityReason], ...] = ()
    offered_schemas: tuple[ToolSchema, ...] = field(init=False)
    by_name: Mapping[str, registry.ResolvedTool] = field(init=False, compare=False)
    unavailable_reasons: Mapping[str, registry.AvailabilityReason] = field(
        init=False, compare=False
    )

    def __post_init__(self) -> None:
        lookup = {tool.name: tool for tool in self.tools}
        unavailable = {
            tool.name: (
                tool.unavailable_reason or registry.AvailabilityReason.CHECK_REFUSED
            )
            for tool in self.tools
            if not tool.available
        }
        unavailable.update(self.missing)
        object.__setattr__(
            self,
            "offered_schemas",
            tuple(tool.schema for tool in self.tools if tool.available),
        )
        object.__setattr__(self, "by_name", MappingProxyType(lookup))
        object.__setattr__(
            self, "unavailable_reasons", MappingProxyType(unavailable)
        )

    def identity_payload(self) -> dict[str, Any]:
        """Deterministic policy identity with no callables, secrets, or expiry."""
        return {
            "resolver_version": "resolved-tool-surface@1",
            "expanded_names": list(self.expanded_names),
            "tools": [
                {
                    "name": tool.name,
                    "toolset": tool.toolset,
                    "schema": tool.schema.as_wire(),
                    "available": tool.available,
                    "unavailable_reason": (
                        None
                        if tool.unavailable_reason is None
                        else tool.unavailable_reason.value
                    ),
                    "effect": tool.effect.value,
                    "idempotency": tool.idempotency.value,
                    "access": tool.access.value,
                    "content_trust": tool.content_trust.value,
                    "concurrency": tool.concurrency.value,
                    "contract_version": tool.contract_version,
                    "handler_identity": tool.handler_identity,
                    "is_async": tool.is_async,
                    "max_result_size_chars": tool.max_result_size_chars,
                    "display_name": tool.display_name,
                    "summary_detail_arg": tool.summary_detail_arg,
                    "summarise_identity": tool.summarise_identity,
                }
                for tool in self.tools
            ],
            "missing": [[name, reason.value] for name, reason in self.missing],
        }

    @property
    def identity_digest(self) -> str:
        wire = json.dumps(
            self.identity_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(wire).hexdigest()


_CACHE: OrderedDict[_CacheKey, ResolvedToolSurface] = OrderedDict()
_CACHE_LOCK = RLock()


def resolve_tool_surface(
    toolsets: Sequence[str] | str | None = None, *, now: float | None = None
) -> ResolvedToolSurface:
    """Resolve declarations, availability, policy, and schemas exactly once."""
    selected = _selection(toolsets)
    instant = time.monotonic() if now is None else float(now)
    for _ in range(registry.MAX_RESOLUTION_RETRIES):
        expanded = expansion_identity(selected)
        generation = registry.generation()
        key: _CacheKey = (generation, expanded)
        with _CACHE_LOCK:
            cached = _CACHE.get(key)
            if cached is not None and instant < cached.expires_at:
                _CACHE.move_to_end(key)
                return cached

        resolved: list[registry.ResolvedTool] = []
        missing: list[tuple[str, registry.AvailabilityReason]] = []
        for name in expanded:
            tool = registry.resolve(name, now=instant)
            if tool is None:
                missing.append((name, registry.AvailabilityReason.NOT_REGISTERED))
            else:
                resolved.append(tool)
        if (
            registry.generation() != generation
            or expansion_identity(selected) != expanded
        ):
            continue
        expires_at = min(
            (tool.availability_expires_at for tool in resolved),
            default=instant + registry.CHECK_TTL_SECONDS,
        )
        surface = ResolvedToolSurface(
            tools=tuple(resolved),
            registry_generation=generation,
            expanded_names=expanded,
            expires_at=expires_at,
            missing=tuple(missing),
        )
        with _CACHE_LOCK:
            _CACHE[key] = surface
            _CACHE.move_to_end(key)
            _evict()
        return surface
    raise RuntimeError("tool registry changed repeatedly while resolving a surface")


def get_tool_definitions(
    toolsets: Sequence[str] | str | None = None, *, now: float | None = None
) -> tuple[ToolSchema, ...]:
    """The schemas for these toolsets, availability applied, order stable.

    ``toolsets=None`` means every toolset this build knows, which is what a
    Turn with no narrower configuration gets. ``now`` is a monotonic reading,
    injectable so a test can age the cache rather than sleep.
    """
    return resolve_tool_surface(toolsets, now=now).offered_schemas


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


def _evict() -> None:
    """Drop entries from superseded generations first, then the oldest."""
    generation = max((key[0] for key in _CACHE), default=registry.generation())
    for key in [key for key in _CACHE if key[0] != generation]:
        del _CACHE[key]
    while len(_CACHE) > MAX_CACHE_ENTRIES:
        _CACHE.popitem(last=False)


def clear_cache() -> None:
    """Forget every built list. For tests and for a deliberate rebuild."""
    with _CACHE_LOCK:
        _CACHE.clear()


def cache_size() -> int:
    with _CACHE_LOCK:
        return len(_CACHE)


__all__ = [
    "MAX_CACHE_ENTRIES",
    "ResolvedToolSurface",
    "cache_size",
    "clear_cache",
    "get_tool_definitions",
    "resolve_tool_surface",
]
