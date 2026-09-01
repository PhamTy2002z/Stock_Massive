"""Typed capability/resource permission rules.

Permission answers one question only: whether policy permits a capability on a
resource. It is not availability (the deployment kill switch), approval (a
person's answer), authorization (which tenant owns a row), or sandboxing (where
code runs). Keeping those questions separate prevents one green check from
silently standing in for another.

Rules are ordered and the last matching rule wins. No match denies. That makes
an omitted resource a closed boundary instead of an implicit grant, while still
letting a declaration start broad and add a narrow exception deliberately.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from fnmatch import fnmatchcase
from typing import Iterable


class ToolPermission(str, Enum):
    """The three outcomes a permission rule may declare."""

    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class AuthorizationDenied(ValueError):
    """Trusted caller context cannot authorize access to the requested scope."""


@dataclass(frozen=True)
class PermissionRule:
    """One ordered rule over a capability name and resource string."""

    capability: str
    resource: str
    action: ToolPermission

    def __post_init__(self) -> None:
        capability = str(self.capability).strip()
        resource = str(self.resource).strip()
        if not capability:
            raise ValueError("a permission rule needs a capability pattern")
        if not resource:
            raise ValueError("a permission rule needs a resource pattern")
        object.__setattr__(self, "capability", capability)
        object.__setattr__(self, "resource", resource)
        object.__setattr__(self, "action", ToolPermission(self.action))


@dataclass(frozen=True)
class PermissionDecision:
    """The evaluated action and the rule that supplied it, if any."""

    action: ToolPermission
    reason: str
    rule: PermissionRule | None = None


class PermissionPolicy:
    """Immutable ordered rules with deny-by-default evaluation."""

    def __init__(self, rules: Iterable[PermissionRule]) -> None:
        self.rules = tuple(rules)

    def evaluate(self, capability: str, resource: str) -> PermissionDecision:
        matched: PermissionRule | None = None
        for rule in self.rules:
            if fnmatchcase(capability, rule.capability) and fnmatchcase(
                resource, rule.resource
            ):
                matched = rule
        if matched is None:
            return PermissionDecision(
                ToolPermission.DENY,
                "no_matching_rule",
            )
        return PermissionDecision(matched.action, "matched_rule", matched)

    def may_allow(self, capability: str) -> bool:
        """Whether any resource could be allowed by this declaration.

        Used only to decide whether a schema can be useful to the model. The
        dispatch path always evaluates the real resource again.
        """

        # Walk in evaluation order backwards. A final all-resource rule
        # shadows every earlier resource rule; a narrow final deny still leaves
        # the earlier allow useful for other resources.
        for rule in reversed(self.rules):
            if not fnmatchcase(capability, rule.capability):
                continue
            if rule.resource == "*":
                return rule.action is ToolPermission.ALLOW
            if rule.action is ToolPermission.ALLOW:
                return True
        return False


@dataclass
class TurnPermissionState:
    """Content-light state for hard cross-origin write protection."""

    untrusted_content_seen: bool = False

    def observe_untrusted_content(self) -> None:
        self.untrusted_content_seen = True


__all__ = [
    "AuthorizationDenied",
    "PermissionDecision",
    "PermissionPolicy",
    "PermissionRule",
    "ToolPermission",
    "TurnPermissionState",
]
