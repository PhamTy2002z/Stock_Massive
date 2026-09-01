"""Small transport-level symbol normalization with no market-data dependency."""

from __future__ import annotations

import re

_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,19}$")


def normalize_symbol(value: str) -> str:
    normalised = value.strip().upper()
    if not _SYMBOL.fullmatch(normalised):
        raise ValueError(
            "symbol must contain 1-20 letters, digits, dots, underscores, or hyphens"
        )
    return normalised


__all__ = ["normalize_symbol"]
