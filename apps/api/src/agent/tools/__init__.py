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
from .price_check import register_price_check_tool
from .signals import register_signal_tools
from .web import register_web_tools


def register_all() -> tuple[ToolEntry, ...]:
    """Install every tool this build offers. Safe to call more than once.

    Every tool, not every tool a conversation may call. Registration is what
    makes a name dispatchable at all; whether a given caller is *offered* one is
    decided by which toolsets it selects (``toolsets.py``).
    """
    return (
        *register_web_tools(),
        *register_memory_tools(),
        *register_signal_tools(),
        *register_price_check_tool(),
    )


__all__ = [
    "register_all",
    "register_memory_tools",
    "register_price_check_tool",
    "register_signal_tools",
    "register_web_tools",
]
