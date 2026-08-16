"""Rendering, versioning and hashing the System Prompt Contract.

``docs/adr/0015`` makes the Contract the behavioural core and, in the same
breath, refuses to let it be an enforcement mechanism.  This module is what that
distinction looks like in code: it renders text and computes a hash, and it
contains no check that a model could be said to have passed.

Three things are proven here rather than asserted in prose.

**Nothing but four typed values can reach the prompt.**  :func:`render` accepts a
:class:`RuntimeContext` whose fields are an ``int``, a ``date``, a
:class:`MarketState` and a validated symbol.  There is no string field, so there
is no hole a figure, a Watchlist entry, a tool result or user prose could be
poured into — and :data:`_STATIC_TEXT` is built by concatenation with no
formatting call anywhere in the module.

**The prose is the version.**  :func:`contract_hash` hashes the section text
itself, so an edit that forgets to bump :data:`PROMPT_VERSION` still changes the
hash the Evidence Manifest records and the cache key derives from.

**The cacheable prefix is genuinely stable.**  Every section is identical for
every Turn; only the four values appended after the last one vary.
:func:`prefix` returns exactly the stable part, so a cache key built from it
cannot silently include today's Trading Day.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum

from src.stocks.shared import validate_symbol

from .sections import PROMPT_VERSION, SECTIONS, PromptSection


class MarketState(str, Enum):
    """The market's state as a short string, and the only one injected.

    An enum rather than free text, and that is the point: a string field here
    would be the one hole in an otherwise closed renderer, and the value is
    injected precisely because no tool can supply it.
    """

    CLOSED = "closed"
    PRE_OPEN = "pre_open"
    ATO = "ato"
    CONTINUOUS = "continuous"
    LUNCH_BREAK = "lunch_break"
    ATC = "atc"
    POST_CLOSE = "post_close"


class AnswerKind(str, Enum):
    """The three answer classes of ``docs/adr/0015``.

    Classified by the harness under the Contract. V1 adds no router model: a
    second call whose accuracy cannot be measured until the Eval Battery exists
    is a second call that cannot be defended.
    """

    ANALYSIS = "analysis"
    EDUCATION = "education"
    REFUSAL = "refusal"


@dataclass(frozen=True)
class RuntimeContext:
    """The complete set of what may be injected, and nothing else.

    Deliberately the same three trusted facts the Tool Catalog's
    ``ToolContext`` carries, plus market state — which is injected for the one
    reason given in section 7: without it the model calls yesterday's close
    "the current price", and no tool can catch that sentence.
    """

    user_id: int
    trading_day: date
    market_state: MarketState
    active_symbol: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, int) or isinstance(self.user_id, bool):
            raise TypeError("identity is injected as a user id, out of band")
        if not isinstance(self.trading_day, date):
            raise TypeError("trading_day must be a date")
        if not isinstance(self.market_state, MarketState):
            raise TypeError("market_state must be a MarketState")
        if self.active_symbol is not None:
            object.__setattr__(self, "active_symbol", validate_symbol(self.active_symbol))


@dataclass(frozen=True)
class AnswerEvidence:
    """What the harness observed during a Turn, in classification terms.

    Counts and flags the loop already has. Nothing here is a model assertion:
    the model cannot tell the harness that its own answer was an analysis.
    """

    model_refused: bool = False
    universe_refusals: int = 0
    grounded_tool_calls: int = 0


def _assert_no_formatting_hole(sections: Sequence[PromptSection]) -> None:
    """Refuse a section body that could be filled in later.

    The acceptance criterion is that no code path can interpolate a figure into
    the system prompt. Auditing the call sites proves that for today's code; a
    body with no brace in it proves it for tomorrow's, because there is nothing
    for a stray ``format`` call to fill.
    """
    for section in sections:
        if "{" in section.body or "}" in section.body:
            raise ValueError(
                f"section {section.key} contains a formatting hole; the Contract's "
                "prose describes shapes in words so that it cannot be filled in"
            )


_assert_no_formatting_hole(SECTIONS)


def _static_text(sections: Sequence[PromptSection] = SECTIONS) -> str:
    """Every section, in order, with no runtime value anywhere."""
    return "\n\n".join(f"## {section.title}\n\n{section.body}" for section in sections)


_STATIC_TEXT = _static_text()


def contract_hash(
    sections: Sequence[PromptSection] = SECTIONS,
    version: str = PROMPT_VERSION,
) -> str:
    """A stable hash of the version and the prose it names.

    Taken over the static text rather than a rendered prompt: a hash that moved
    with the Trading Day would void the cached prefix once a day and would tell
    an auditor nothing about which Contract produced an answer.
    """
    digest = hashlib.sha256()
    digest.update(version.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(_static_text(sections).encode("utf-8"))
    return digest.hexdigest()


PROMPT_HASH = contract_hash()


def prefix() -> str:
    """The part of the prompt that is identical for every Turn."""
    return _STATIC_TEXT


def render(context: RuntimeContext) -> str:
    """The whole system prompt: the stable prefix, then the four values.

    Byte-stable for the same version and the same context, because the only
    variable part is four values rendered from typed fields in a fixed order.
    """
    if not isinstance(context, RuntimeContext):
        raise TypeError("the system prompt renders only a RuntimeContext")
    lines = (
        f"- user_id: {context.user_id}",
        f"- trading_day: {context.trading_day.isoformat()}",
        f"- market_state: {context.market_state.value}",
        f"- active_symbol: {context.active_symbol or 'none'}",
    )
    return _STATIC_TEXT + "\n\n" + "\n".join(lines) + "\n"


def cache_key(model: str, tool_catalog_version: str) -> str:
    """The identity of a cacheable prefix, per ``docs/adr/0015``.

    Model, ``prompt_version`` and ``tool_catalog_version`` — and the prompt hash
    with them, so a prose edit that forgets the version bump still voids the
    cache. Caching never changes correctness or control flow; this key only
    decides whether a prefix may be reused.
    """
    return "|".join((model, PROMPT_VERSION, PROMPT_HASH, tool_catalog_version))


def classify_answer_kind(evidence: AnswerEvidence) -> AnswerKind:
    """Assign one of the three answer classes, deterministically.

    Ordered by the Contract's own precedence: a refusal outranks everything,
    grounded evidence makes an analysis, and what remains is education. No
    model call, and no branch that a model's own claim about its answer could
    enter.
    """
    if evidence.model_refused:
        return AnswerKind.REFUSAL
    if evidence.grounded_tool_calls > 0:
        return AnswerKind.ANALYSIS
    if evidence.universe_refusals > 0:
        return AnswerKind.REFUSAL
    return AnswerKind.EDUCATION


__all__ = [
    "PROMPT_HASH",
    "PROMPT_VERSION",
    "AnswerEvidence",
    "AnswerKind",
    "MarketState",
    "RuntimeContext",
    "cache_key",
    "classify_answer_kind",
    "contract_hash",
    "prefix",
    "render",
]
