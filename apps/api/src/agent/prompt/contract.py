"""Rendering, versioning and hashing the system prompt.

This module renders text and computes a hash. It contains no check a model could
be said to have passed: the prompt is what the model is told, never what the
harness enforces. Everything this harness actually enforces lives in
:mod:`src.agent.guardrails`, :mod:`src.agent.budget` and
:mod:`src.agent.untrusted`, because a rule stated only in prose is a rule that
holds until a page asks nicely.

Three properties are proven here rather than asserted.

**Almost nothing can reach the prompt.** :func:`render` accepts a
:class:`RuntimeContext` whose fields are a ``date``, a market status, and the
reader's own name, investing style and instructions, and :data:`_STATIC_TEXT` is
built by concatenation with no formatting call anywhere in the module. The name
and the instructions are the free-text values; both are sanitised on the way in
and the style is one of a fixed set of codes — see
:meth:`RuntimeContext.__post_init__`.

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
import logging
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from ..threat_patterns import INVISIBLE_CHARS, findings_in
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


#: The investing styles a reader can pick in Settings, by the code the prompt
#: prints. ``auth.schemas.InvestingStyle`` accepts exactly these; the CONTEXT
#: section says in words what each one means.
INVESTING_STYLES: tuple[str, ...] = ("long_term", "growth", "dividend", "swing", "learning")

#: How much of the reader's own instructions reaches the prompt — the same cap
#: the Settings form enforces, restated here because this is the gate that holds
#: whatever the row happens to contain.
MAX_INSTRUCTIONS_CHARS = 1500

_INVISIBLE = re.compile(f"[{INVISIBLE_CHARS}]")
#: Control characters, angle brackets and braces, and nothing else. Angle
#: brackets go because every delimiter this harness wraps content in is a tag —
#: ``untrusted_tool_result``, ``user_attachment`` — and a tag with no ``<`` cannot
#: open or close anything. Braces go so the rendered prompt keeps holding no
#: formatting hole anywhere, the property :func:`assert_no_formatting_hole`
#: proves for the prose.
_INSTRUCTIONS_UNSAFE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f<>{}]")

logger = logging.getLogger(__name__)


def sanitise_instructions(raw: str) -> str | None:
    """The reader's own instructions, as one line, or nothing at all.

    Wider than :func:`sanitise_name` because this field is prose by design, so
    punctuation stays. What cannot stay is anything that changes the *shape* of
    the prompt: a newline would let the value start a line of its own and pose
    as a runtime field, and a bracket could forge a wrapper tag. Invisible
    characters come out first, the same way ``threat_patterns.normalise`` folds
    them, so what is scanned is what the model reads.

    A match against the threat patterns drops the instructions for the Turn
    rather than editing them. A half-cleaned injection is still an injection, and
    the reader loses only a preference, never the answer. The finding names are
    logged and the text is not: it is the reader's own words.
    """
    folded = _INVISIBLE.sub("", unicodedata.normalize("NFKC", raw))
    cleaned = _NAME_SPACES.sub(" ", _INSTRUCTIONS_UNSAFE.sub(" ", folded)).strip()
    cleaned = cleaned[:MAX_INSTRUCTIONS_CHARS].strip()
    if not cleaned:
        return None
    findings = findings_in(cleaned)
    if findings:
        logger.warning(
            "custom instructions dropped for this Turn: %s", ", ".join(findings)
        )
        return None
    return cleaned


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
    Optional because most do not, and sanitised because a user writes it.

    ``investing_style`` and ``custom_instructions`` are the reader's own
    preferences from Settings, about how an answer is presented. They are data
    about the reader, never policy: the CONTEXT section says so to the model,
    and this class makes sure neither can carry more than that — the style is
    reduced to a known code or dropped, and the instructions go through
    :func:`sanitise_instructions`.

    ``memory_enabled`` is false when the reader switched memory off. It is said
    up front so the model can tell a reader asking to be remembered that it
    cannot, instead of learning it from a refused tool call it may never make
    and promising to remember anyway. The memory tools still refuse on their
    own, so the prompt is the courtesy and the handler is the guarantee.
    """

    today: date
    user_name: str | None = None
    market: MarketDay = field(default_factory=lambda: MarketDay(MarketPhase.UNKNOWN))
    investing_style: str | None = None
    custom_instructions: str | None = None
    memory_enabled: bool = True
    #: The names of the connectors this reader has switched on, when there are
    #: any. Here and not in a tool description: the on-demand tools are one fixed
    #: text for every reader so the cached head never moves, and without the names
    #: the model cannot know a connector the reader just named is there to search.
    #: Sanitised like ``user_name``, because the reader typed them.
    connectors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.today, date):
            raise TypeError("today must be a date")
        if not isinstance(self.market, MarketDay):
            raise TypeError("market must be a MarketDay")
        if not isinstance(self.memory_enabled, bool):
            raise TypeError("memory_enabled must be a bool")
        for name in ("user_name", "investing_style", "custom_instructions"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string when present")
        if self.user_name is not None:
            object.__setattr__(self, "user_name", sanitise_name(self.user_name))
        if self.investing_style not in INVESTING_STYLES:
            # A stale or hand-edited row degrades to no style rather than
            # printing a code the CONTEXT section never explained.
            object.__setattr__(self, "investing_style", None)
        if self.custom_instructions is not None:
            object.__setattr__(
                self,
                "custom_instructions",
                sanitise_instructions(self.custom_instructions),
            )
        object.__setattr__(
            self,
            "connectors",
            tuple(name for name in (sanitise_name(str(item)) for item in self.connectors) if name),
        )


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


#: Vietnamese weekday names, Monday first as ``date.weekday()`` counts. The date
#: alone left the model to work out the day of the week, and on 2026-09-27 it
#: called that Sunday "thứ Bảy" in three answers.
WEEKDAYS = ("Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật")


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
        f"- today: {context.today.isoformat()} ({WEEKDAYS[context.today.weekday()]})",
        f"- market_today: {phase}",
    ]
    if market.previous_trading_day is not None:
        lines.append(
            f"- previous_trading_day: {market.previous_trading_day.isoformat()}"
        )
    if context.user_name:
        lines.append(f"- user_name: {context.user_name}")
    if context.investing_style:
        lines.append(f"- investing_style: {context.investing_style}")
    if context.custom_instructions:
        lines.append(f"- user_instructions: {context.custom_instructions}")
    if not context.memory_enabled:
        lines.append("- memory: off")
    if context.connectors:
        # Named with the tool that reaches them, so a reader who says "dùng
        # DeepWiki" is answered from DeepWiki rather than from a web search.
        lines.append(
            f"- connectors: {', '.join(context.connectors)} "
            "(the reader's own connected tools; find them with search_connector_tools "
            "before searching the web)"
        )
    return _STATIC_TEXT + "\n\n" + "\n".join(lines) + "\n"


#: How a key spells the two shapes the system message comes in. Words rather
#: than a bare flag, because this string is read by a person looking at a call's
#: metadata and ``True`` at the end of a key says nothing about what it means.
_WITH_BODY = "body"
_WITHOUT_BODY = "no-body"


def cache_key(
    model: str, tool_signature: str, pack_identity: str, *, domain_body: bool
) -> str:
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
    next caller to skip the pack without noticing.

    ``domain_body`` finishes that sentence. The pack's body is carried by the
    Turns that reached for the domain and left out of the ones that did not, so
    the pack alone does not say which of the two prompts went out. Both are
    real, both are cacheable, and a key that could not tell them apart would
    name a prefix the request does not begin with. Keyword-only and required
    for the same reason as the pack: the caller has the answer in hand, and a
    default would be somewhere to lose it.

    Nothing calls this at runtime yet — prompt caching is off — so the strict
    signature costs two arguments today and prevents a silently wrong cache hit
    later.
    """
    return "|".join(
        (
            model,
            PROMPT_VERSION,
            PROMPT_HASH,
            tool_signature,
            pack_identity,
            _WITH_BODY if domain_body else _WITHOUT_BODY,
        )
    )


__all__ = [
    "INVESTING_STYLES",
    "MAX_INSTRUCTIONS_CHARS",
    "MAX_NAME_CHARS",
    "PROMPT_HASH",
    "PROMPT_VERSION",
    "RuntimeContext",
    "assert_no_formatting_hole",
    "cache_key",
    "contract_hash",
    "prefix",
    "render",
    "sanitise_instructions",
    "sanitise_name",
]
