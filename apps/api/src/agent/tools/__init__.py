"""The tools this agent has, and the one call that installs them.

Registration is explicit rather than an import side effect: a module that
registers when it is imported registers differently depending on who imported it
first, and a test that imports one tool would inherit the others. So the process
calls :func:`register_all` once at startup, and everything else asks the registry.

Idempotent, because a reload path and a startup path both legitimately call it.
"""

from __future__ import annotations

from ..registry import ToolEntry
from .compute import register_compute_tool
from .evidence import register_evidence_tool
from .memory import register_memory_tools
from .price_check import register_price_check_tool
from .query import register_query_tools
from .signals import register_signal_tools
from .studies import register_study_tools
from .web import register_web_tools


def register_all() -> tuple[ToolEntry, ...]:
    """Install every tool this build offers. Safe to call more than once.

    Every tool, not every tool a conversation may call. Registration is what
    makes a name dispatchable at all; whether a given caller is *offered* one is
    decided by which toolsets it selects (``toolsets.py``).
    """
    return (
        *register_web_tools(),
        # After the two web tools, so the registry's order matches the order the
        # ``web`` bundle expands to — the same reason the query tools sit after
        # the price check below.
        *register_evidence_tool(),
        *register_memory_tools(),
        *register_signal_tools(),
        *register_price_check_tool(),
        # After the price check, so the registry's order matches the order the
        # ``signals`` bundle expands to. Two orders that disagree are two
        # contracts a test has to state separately, and the resolved-surface
        # cache keys on one of them.
        *register_query_tools(),
        *register_study_tools(),
        *register_compute_tool(),
    )


__all__ = [
    "register_all",
    "register_compute_tool",
    "register_evidence_tool",
    "register_memory_tools",
    "register_price_check_tool",
    "register_query_tools",
    "register_signal_tools",
    "register_study_tools",
    "register_web_tools",
]
