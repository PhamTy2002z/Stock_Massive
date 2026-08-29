"""The versioned system prompt of a general assistant.

One canonical source, shared by every caller: :mod:`sections` holds the prose
and :mod:`contract` renders, versions and hashes it. There is no runtime editing
surface and no A/B mechanism — a prompt change is a source change, reviewed like
any other.
"""

from .contract import (
    MAX_NAME_CHARS,
    PROMPT_HASH,
    PROMPT_VERSION,
    RuntimeContext,
    assert_no_formatting_hole,
    cache_key,
    contract_hash,
    prefix,
    render,
    sanitise_name,
)
from .sections import SECTIONS, PromptSection

__all__ = [
    "MAX_NAME_CHARS",
    "PROMPT_HASH",
    "PROMPT_VERSION",
    "SECTIONS",
    "PromptSection",
    "RuntimeContext",
    "assert_no_formatting_hole",
    "cache_key",
    "contract_hash",
    "prefix",
    "render",
    "sanitise_name",
]
