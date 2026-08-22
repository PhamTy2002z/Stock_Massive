"""The tools this agent has, and the one call that installs them.

Registration is explicit rather than an import side effect: a module that
registers when it is imported registers differently depending on who imported it
first, and a test that imports one tool would inherit the others. So the process
calls :func:`register_all` once at startup, and everything else asks the registry.

Idempotent, because a reload path and a startup path both legitimately call it.
"""

from __future__ import annotations

from ..registry import ToolEntry
from .memory import register_memory_tools
from .web import register_web_tools


def register_all() -> tuple[ToolEntry, ...]:
    """Install every tool this build offers. Safe to call more than once."""
    return (*register_web_tools(), *register_memory_tools())


__all__ = ["register_all", "register_memory_tools", "register_web_tools"]
