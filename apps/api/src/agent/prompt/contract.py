"""Rendering, versioning and hashing the system prompt.

This module renders text and computes a hash. It contains no check a model could
be said to have passed: the prompt is what the model is told, never what the
harness enforces. Everything this harness actually enforces lives in
:mod:`src.agent.guardrails`, :mod:`src.agent.budget` and
:mod:`src.agent.untrusted`, because a rule stated only in prose is a rule that
holds until a page asks nicely.

Three properties are proven here rather than asserted.

**Almost nothing can reach the prompt.** :func:`render` accepts a
:class:`RuntimeContext` whose fields are a ``date`` and one optional short name,
and :data:`_STATIC_TEXT` is built by concatenation with no formatting call
anywhere in the module. The name is the one free-text value, and it is sanitised
on the way in — see :meth:`RuntimeContext.__post_init__`.

**The prose is the version.** :func:`contract_hash` hashes the section text
itself, so an edit that forgets to bump :data:`PROMPT_VERSION` still changes the
hash.

**The cacheable prefix is genuinely stable.** Every section is identical for
every Turn; only the values appended after the last one vary. :func:`prefix`
returns exactly the stable part, so a cache key built from it cannot silently
include today's date.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from .sections import PROMPT_VERSION, SECTIONS, PromptSection

#: How much of a user-supplied name is carried into the prompt. Long enough for
#: a real Vietnamese full name, short enough that the field cannot become a
#: second prompt.
MAX_NAME_CHARS = 64

#: Everything a name may keep: letters (including Vietnamese diacritics),
#: digits, spaces and the three punctuation marks names actually use. Anything
#: else — newlines, angle brackets, quotes, the delimiters this harness wraps
#: untrusted content in — is dropped rather than escaped, because a name has no
#: legitimate use for them.
_NAME_UNSAFE = re.compile(r"[^\w .'\-]", re.UNICODE)
_NAME_SPACES = re.compile(r"\s+")


def sanitise_name(raw: str) -> str | None:
    """A display name reduced to something that cannot act as an instruction.

    The threat here is small but real: the name is the only user-controlled
    string in the prompt, and a user who writes instructions into it is
    steering their own answers rather than anybody else's. Sanitising is still
    worth its four lines, because the *shape* of the prompt — one line per
    value — is what a reader and a cache key both depend on, and a newline in a
    name breaks that shape for free.
    """
    cleaned = _NAME_SPACES.sub(" ", _NAME_UNSAFE.sub("", raw)).strip()
    return cleaned[:MAX_NAME_CHARS].strip() or None


class MarketPhase(str, Enum):
    """Whether the Vietnamese equity market trades on a given calendar day.

    ``UNKNOWN`` is a first-class answer rather than a failure. The holiday table
    behind it covers named years, and a phase that quietly degraded to "open"
    outside them would reintroduce exactly the confident wrong label this value
    exists to prevent.
    """

    OPEN = "open"
    CLOSED_WEEKEND = "closed_weekend"
    CLOSED_HOLIDAY = "closed_holiday"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MarketDay:
    """One day's trading status, as the harness will state it to the model.

    ``holiday`` names the occasion and is set only for
    :attr:`MarketPhase.CLOSED_HOLIDAY`. ``previous_trading_day`` is the session
    the price boards are actually showing while the market is shut — the single
    fact whose absence let a stale board be narrated as today — and is left
    ``None`` whenever it cannot be derived with certainty.

    Both are harness constants rather than user or web input, so neither goes
    through :func:`sanitise_name`; :func:`render` still keeps them on their own
    lines so the shape of the tail cannot be broken by a value.
    """

    phase: MarketPhase
    holiday: str | None = None
    previous_trading_day: date | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.phase, MarketPhase):
            raise TypeError("phase must be a MarketPhase")
        if self.holiday is not None and self.phase is not MarketPhase.CLOSED_HOLIDAY:
            raise ValueError("only a holiday closure names a holiday")
        if self.phase is MarketPhase.OPEN and self.previous_trading_day is not None:
            raise ValueError(
                "an open day has no previous session to point at: the boards it "
                "shows are its own, and naming yesterday here would relabel them"
            )


@dataclass(frozen=True)
class RuntimeContext:
    """The complete set of what may be injected, and nothing else.

    Three values, and each is here because no tool can supply it.

    ``today`` is the calendar date in the user's own timezone. Without it the
    model cannot resolve the word "today" in a question, and it cannot tell
    whether a page it just fetched is describing this week or last year.

    A date and never a timestamp: a clock here would change the prompt on every
    Turn and void the cacheable prefix, and it would invite precision about a
    minute that nothing behind the answer has.

    ``market`` is whether ``today`` is a session at all. It belongs beside the
    date for the same reason the date does — nothing the model can call will
    tell it — and it is carried as a value rather than looked up here so that
    this module keeps rendering text and knows no calendar. It defaults to
    :attr:`MarketPhase.UNKNOWN` rather than to ``None``: a caller who forgets it
    makes the model verify the session, which is the safe direction, and there
    is no silent state in which the prompt simply says nothing about trading.

    ``user_name`` is what to call the reader, when the account carries a name.
    Optional because most do not, and sanitised because it is the one field a
    user writes.
    """

    today: date
    user_name: str | None = None
    market: MarketDay = field(default_factory=lambda: MarketDay(MarketPhase.UNKNOWN))

    def __post_init__(self) -> None:
        if not isinstance(self.today, date):
            raise TypeError("today must be a date")
        if not isinstance(self.market, MarketDay):
            raise TypeError("market must be a MarketDay")
        if self.user_name is not None:
            if not isinstance(self.user_name, str):
                raise TypeError("user_name must be a string when present")
            object.__setattr__(self, "user_name", sanitise_name(self.user_name))


def assert_no_formatting_hole(sections: Sequence[PromptSection]) -> None:
    """Refuse a section body that could be filled in later.

    Auditing the call sites proves for today's code that nothing interpolates
    into the prompt; a body with no brace in it proves the same for tomorrow's,
    because there is nothing for a stray ``format`` call to fill.

    Public because it has two callers rather than one: the core below, and a
    domain pack validating the body it appends to a call
    (``agent/domain/pack.py``). A pack's prose reaches the model in the same
    conversation as the core, so it goes through the same gate — and a gate two
    modules call while wearing an underscore is a name that lies about its
    reach.
    """
    for section in sections:
        if "{" in section.body or "}" in section.body:
            raise ValueError(
                f"section {section.key} contains a formatting hole; the prose "
                "describes shapes in words so that it cannot be filled in"
            )


assert_no_formatting_hole(SECTIONS)


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
    with the date would void the cached prefix once a day and would tell an
    auditor nothing about which prompt produced an answer.
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
    """The whole system prompt: the stable prefix, then the Turn's values.

    Byte-stable for the same version and the same context, because the only
    variable part is rendered from typed fields in a fixed order.
    """
    if not isinstance(context, RuntimeContext):
        raise TypeError("the system prompt renders only a RuntimeContext")
    market = context.market
    phase = market.phase.value
    if market.holiday:
        phase = f"{phase} ({market.holiday})"
    lines = [
        f"- today: {context.today.isoformat()}",
        f"- market_today: {phase}",
    ]
    if market.previous_trading_day is not None:
        lines.append(
            f"- previous_trading_day: {market.previous_trading_day.isoformat()}"
        )
    if context.user_name:
        lines.append(f"- user_name: {context.user_name}")
    return _STATIC_TEXT + "\n\n" + "\n".join(lines) + "\n"


def cache_key(model: str, tool_signature: str, pack_identity: str) -> str:
    """The identity of a cacheable prefix.

    Model, version and the prompt hash — the hash so that a prose edit which
    forgets the version bump still voids the cache — plus whatever the caller
    uses to identify the tool list, because the schemas travel in the same
    cacheable head of the request as the prompt. Caching never changes
    correctness or control flow; this key only decides whether a prefix may be
    reused.

    ``pack_identity`` is required rather than defaulted, and the requirement is
    the point. Since the prompt came apart into a core and a domain body, two
    Turns on the same model with the same tools are *not* the same prompt when
    they run under different packs, and a default here would be a place for the
    next caller to skip the pack without noticing. Nothing calls this at
    runtime yet — prompt caching is off — so the strict signature costs one
    argument today and prevents a silently wrong cache hit later.
    """
    return "|".join(
        (model, PROMPT_VERSION, PROMPT_HASH, tool_signature, pack_identity)
    )


__all__ = [
    "MAX_NAME_CHARS",
    "PROMPT_HASH",
    "PROMPT_VERSION",
    "RuntimeContext",
    "assert_no_formatting_hole",
    "cache_key",
    "contract_hash",
    "prefix",
    "render",
    "sanitise_name",
]
