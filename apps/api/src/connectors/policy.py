"""Which actions a connector tool may be given, and which it has.

The owner's rule, 27/09/2026:

- A catalog tool is a read only when the operator classified it as one; a tool
  the operator did not classify is a write.
- A custom tool's annotations may only tighten. It is a read only when the
  server says ``readOnlyHint: true`` and does not say ``destructiveHint: true``;
  missing or contradictory hints make it a write. That read is still the
  server's own claim, which the settings page says in so many words.
- A write is always ``ask`` or ``deny``. ``allow`` is not an action a write can
  hold, whatever was stored.

Defaults: a catalog read is ``allow``; everything else starts at ``ask``, which
is also where a tool lands that appeared since the user last looked.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

ALLOW, ASK, DENY = "allow", "ask", "deny"
ACTIONS = (ALLOW, ASK, DENY)
READ, WRITE = "read", "write"


def effect(tool: Mapping[str, Any], *, catalog_effects: Mapping[str, str] | None) -> str:
    if catalog_effects is not None:
        return READ if catalog_effects.get(str(tool.get("name"))) == READ else WRITE
    if tool.get("read_only") is True and tool.get("destructive") is not True:
        return READ
    return WRITE


def allowed_actions(tool_effect: str) -> tuple[str, ...]:
    return ACTIONS if tool_effect == READ else (ASK, DENY)


def default_action(tool_effect: str, *, from_catalog: bool) -> str:
    return ALLOW if (tool_effect == READ and from_catalog) else ASK


def action(
    tool: Mapping[str, Any],
    stored: Mapping[str, str],
    *,
    catalog_effects: Mapping[str, str] | None,
) -> str:
    """The action a tool has now: what the user stored, if it is allowed."""
    tool_effect = effect(tool, catalog_effects=catalog_effects)
    chosen = stored.get(str(tool.get("name")))
    if chosen in allowed_actions(tool_effect):
        return chosen
    return default_action(tool_effect, from_catalog=catalog_effects is not None)


class PolicyRefused(ValueError):
    """An action this tool may not hold."""


def validate(
    tool: Mapping[str, Any], chosen: str, *, catalog_effects: Mapping[str, str] | None
) -> str:
    tool_effect = effect(tool, catalog_effects=catalog_effects)
    if chosen not in allowed_actions(tool_effect):
        raise PolicyRefused(f"{tool.get('name')} is a write and can only be ask or deny")
    return chosen


__all__ = [
    "ACTIONS",
    "ALLOW",
    "ASK",
    "DENY",
    "PolicyRefused",
    "READ",
    "WRITE",
    "action",
    "allowed_actions",
    "default_action",
    "effect",
    "validate",
]
