"""Scaffolding shared by the tool-layer tests.

The registry is process-wide, which is right for a process and wrong for a test
suite: one file's tools would be visible to the next file's assertions. So every
test that touches it borrows it through :func:`isolated_registry`, which empties
it before and after and takes the schema cache with it.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from src.agent import definitions, registry, toolsets


@contextmanager
def isolated_registry() -> Iterator[None]:
    """A registry holding nothing but what this test puts in it."""
    registry.clear()
    definitions.clear_cache()
    toolsets.clear_memo()
    try:
        yield
    finally:
        registry.clear()
        definitions.clear_cache()
        toolsets.clear_memo()


async def echo(_context: registry.ToolContext, arguments: Mapping[str, Any]) -> Any:
    """A handler that returns what it was called with."""
    return dict(arguments)


def stub_entry(name: str, *, toolset: str = "stub", **overrides: Any) -> registry.ToolEntry:
    """One registration intentionally exercising conservative policy defaults."""
    fields: dict[str, Any] = {
        "name": name,
        "toolset": toolset,
        "schema": registry.object_schema({"value": {"type": "string"}}),
        "handler": echo,
        "description": f"stub tool {name}",
        # The registry refuses a registration with no reader-facing name, which
        # is the point of that field: a tool cannot reach a screen as its own id.
        "display_name": f"Stub {name}",
    }
    fields.update(overrides)
    return registry.ToolEntry(**fields)


__all__ = ["echo", "isolated_registry", "stub_entry"]
