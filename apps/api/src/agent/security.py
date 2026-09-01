"""Credential guards shared by outbound web calls and durable tool traces."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

from src.core.llm.errors import REDACTED, redact

from .threat_patterns import normalise

_SENSITIVE_FIELD = re.compile(
    r"(?i)^(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"id[_-]?token|client[_-]?secret|secret|password|passwd|key|token|"
    r"session|auth)$"
)


class SecretEgressBlocked(ValueError):
    """Credential-shaped data was refused before outbound I/O."""


def redact_trace_value(value: Any, *, field: str | None = None) -> Any:
    """Recursively remove credential values from the durable trace projection."""

    if field is not None and _SENSITIVE_FIELD.fullmatch(str(field)):
        return REDACTED
    if isinstance(value, Mapping):
        return {
            str(key): redact_trace_value(item, field=str(key))
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_trace_value(item) for item in value]
    if isinstance(value, str):
        return redact(value)
    return value


def contains_secret(text: str) -> bool:
    """Whether outbound text contains a credential, including encoded forms."""

    raw = str(text or "")
    folded = normalise(unquote(raw))
    if redact(folded) != folded:
        return True
    parsed = urlsplit(folded)
    return any(
        _SENSITIVE_FIELD.fullmatch(name) and bool(value)
        for name, value in parse_qsl(parsed.query, keep_blank_values=True)
    )


def refuse_secret_egress(text: str, *, label: str) -> None:
    """Fail before provider, DNS or socket I/O without echoing the secret."""

    if contains_secret(text):
        raise SecretEgressBlocked(
            f"{label} contains credential-shaped data and was refused"
        )


__all__ = [
    "SecretEgressBlocked",
    "contains_secret",
    "redact_trace_value",
    "refuse_secret_egress",
]
