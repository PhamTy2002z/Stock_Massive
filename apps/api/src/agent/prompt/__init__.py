"""The versioned System Prompt Contract (``docs/adr/0015``).

One canonical source, shared by every provider adapter: :mod:`sections` holds
the prose and :mod:`contract` renders, versions and hashes it. There is no
runtime editing surface and no A/B mechanism — a Contract change is a source
change, reviewed and gated like any other.
"""

from .contract import (
    PROMPT_HASH,
    PROMPT_VERSION,
    AnswerEvidence,
    AnswerKind,
    MarketState,
    RuntimeContext,
    cache_key,
    classify_answer_kind,
    contract_hash,
    prefix,
    render,
)
from .sections import SECTIONS, PromptSection

__all__ = [
    "PROMPT_HASH",
    "PROMPT_VERSION",
    "SECTIONS",
    "AnswerEvidence",
    "AnswerKind",
    "MarketState",
    "PromptSection",
    "RuntimeContext",
    "cache_key",
    "classify_answer_kind",
    "contract_hash",
    "prefix",
    "render",
]
