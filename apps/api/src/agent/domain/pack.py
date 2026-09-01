"""What one domain declares about itself, and nothing about any domain.

A :class:`DomainPack` is a *declaration*: the set of facts that make this
harness answer questions about Vietnamese equities rather than about anything
else, gathered in one frozen object instead of spread across a tuple in
``toolsets``, a callable in ``tools/signals``, and prose in ``prompt/sections``.
The point is not tidiness. It is that a second domain becomes a second file
rather than a second pass over every table that happens to name a stock.

Two properties of this module are load-bearing rather than stylistic.

**It imports no domain runtime or toolsets.** A
frame that knew the shape of the thing it frames would have to be edited to hold
the next one, which is the whole failure this file exists to prevent. That is
The pack carries prose and toolset names only; executable capabilities stay in
the harness registry.

**It reads nothing.** No settings, no session, no environment. A declaration
that consulted its environment would answer differently in a test than in
production, and every contract test written against it would be measuring the
machine it ran on.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from ..prompt.contract import assert_no_formatting_hole
from ..prompt.sections import PromptSection

#: Why a question got the body when nothing in it decided either way.
#:
#: Ambiguity resolves towards carrying the playbook. The two ways of being wrong
#: do not cost the same: a market question answered without the domain's rules
#: is answered worse, while a greeting that carries them is a few hundred tokens
#: nobody reads.
BODY_DEFAULT_REASON = "default"


class DomainPackInvalid(ValueError):
    """A pack that cannot be admitted, refused at import rather than at serve.

    Raised from ``__post_init__``, so a malformed pack takes the process down on
    the way up. The alternative — a pack that imports and then serves a Turn
    with no toolsets — reads from the outside as a model that chose to call
    nothing, which is the same misreading ``UnknownToolsetError`` exists to
    prevent one layer down.
    """


@dataclass(frozen=True)
class DomainPack:
    """One domain: what it can reach for, what it knows, and how it says no.

    Frozen on purpose. The active pack is process-level state today (see
    ``__init__.py``), and process-level state that can be mutated is state two
    requests can disagree about.
    """

    #: Stable identifier. Goes into :attr:`identity`, so it is part of what a
    #: cached prompt prefix is keyed by.
    name: str

    #: Bumped by hand, in the same commit as the prose it names — the same
    #: convention as ``PROMPT_VERSION``. Hand-written so a reader of the diff
    #: sees it; hashed into :attr:`identity` so forgetting to bump it still
    #: voids a cache rather than serving yesterday's body.
    version: str

    #: Toolset *names*, not tools. Whether a name is registered is
    #: ``toolsets``' question, not this module's — a pack that could check would
    #: be a pack that imports the table it is meant to be independent of.
    toolsets: tuple[str, ...] = ()

    #: How the domain's tools are used and how their refusals read: the half of
    #: the prompt only a Turn that reaches for this domain pays for. The other
    #: half — who the assistant is, what it may not be talked out of, how a tool
    #: is used at all — stays in ``prompt/sections`` and goes out with every
    #: Turn. Optional because a pack may be declared before its prose is written,
    #: not because a pack is expected to stay wordless.
    prompt_sections: tuple[PromptSection, ...] = ()

    #: How something tradable in this domain is written, as a regular expression
    #: source rather than a compiled pattern — a pack stays a declaration of
    #: strings, and ``re`` caches the compilation anyway.
    #:
    #: Matched against the question as typed, so case carries meaning: a ticker
    #: is shouted and ordinary prose is not. Deliberately loose at the edges,
    #: because every shape it over-matches costs the body and nothing else.
    symbol_shape: str = ""

    #: Words that put a question inside this domain, casefolded and matched as
    #: substrings for the reason :mod:`..lanes` matches its own that way: they
    #: are written the way a reader types them, and no diacritic folding means a
    #: reader who types without tone marks lands on the default, which carries
    #: the body rather than dropping it.
    topic_markers: tuple[str, ...] = ()

    #: Words that put a question outside *every* domain — about the assistant
    #: rather than about a market. The only evidence strong enough to withhold
    #: the body, and only when nothing above has already claimed the question.
    off_topic_markers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DomainPackInvalid(
                "a pack needs a name; it is what selects it and what keys its "
                "cached prompt prefix"
            )
        if not self.version.strip():
            raise DomainPackInvalid(
                f"pack {self.name!r} needs a version; without one a prose change "
                "cannot be told apart from the prose before it"
            )
        # The same gate the core prose passes at import (``prompt/contract``).
        # A pack's body reaches the model in the same conversation as the core,
        # so a brace in it is the same hole in the same wall — and refusing it
        # here means a malformed body cannot be shipped, rather than cannot be
        # noticed.
        assert_no_formatting_hole(self.prompt_sections)
        if self.symbol_shape:
            # Compiled here and thrown away: what the call site needs is that the
            # source is a pattern at all. A pack whose shape does not compile
            # would raise on its first question instead of on the way up, and
            # ``body_reason`` has no failure mode to report it with — it answers
            # every question, including the ones asked before anyone looked.
            try:
                re.compile(self.symbol_shape)
            except re.error as error:
                raise DomainPackInvalid(
                    f"pack {self.name!r} declares a symbol shape that is not a "
                    f"regular expression: {error}"
                ) from error

    @property
    def body_text(self) -> str:
        """The pack's prose as one string, in declared order.

        The unit of everything downstream: what gets appended to a call once a
        Turn has reached for this domain, what its token cost is measured on,
        and what its :attr:`identity` hashes. One string for all three, on
        purpose — a cost measured on text that differs from the text that ships
        is a budget that is wrong by however much the two differ, and a hash
        taken over a third variant voids nothing when the shipped text changes.

        Headings included, in the layout ``contract._static_text`` already uses
        for the core sections. Two reasons, and the second is the load-bearing
        one: a body that arrives without headings reads to a model as a
        continuation of whatever preceded it rather than as its own material,
        and a title edited with no version bump has to move this string or it
        moves the prompt without moving anything that keys a cache.
        """
        return "\n\n".join(
            f"## {section.title}\n\n{section.body}"
            for section in self.prompt_sections
        )

    @property
    def body_tokens(self) -> int:
        """What appending :attr:`body_text` to a call actually costs.

        Measured with ``messages.estimate_tokens`` — the same function the
        budget, the admission ceiling and the trimming ladder read — rather than
        approximated, because the loop reserves room for this text before it
        builds the context. A reservation that is smaller than the message it
        stands for is a context built believing it has room it does not, and the
        request goes out over a ceiling the transcript was already trimmed
        against.

        Imported inside the property rather than at module scope. ``messages``
        imports nothing from here, so there is no cycle to break; what the local
        import buys is that a pack stays importable by anything that wants to
        read a declaration without pulling in the transcript machinery.
        """
        from ..messages import estimate_tokens
        from ...core.llm.protocol import Message, Role

        return estimate_tokens(Message(role=Role.SYSTEM, content=self.body_text))

    def body_reason(self, question: str) -> tuple[bool, str]:
        """Whether this question is one the pack has anything to say about.

        The pack answers it rather than the loop, because every rule involved is
        a fact about the domain — what its instruments look like, what its
        readers call things — and a loop that held those rules would be a loop a
        second domain has to come back and edit. The loop keeps the half that is
        about the Turn: which lane funded it.

        The answer travels with the reason it was reached, the way
        ``lanes.route_reason`` does, so a Turn that ran without the playbook can
        say which word cost it one instead of having the question re-read after
        the fact.

        **The order of the three tests is the policy.** A symbol or a topic word
        claims the question outright; only a question nothing has claimed is
        allowed to be disowned. So "cách bạn hoạt động khi tôi hỏi về cổ phiếu"
        keeps the body, while "bạn là ai" does not — the same words, and the
        difference is that one of them names the domain.

        Pure and first-match, which is what makes it testable: no clock, no
        settings, no store, and a tuple rather than a set on either vocabulary so
        the reason names the same word on every run.
        """
        # One line rather than a reader's newlines, so a pasted block is read as
        # the sentence it is. Written out here instead of borrowed from
        # ``lanes``: the two fold text for their own reasons, and a shared helper
        # would make one of them move whenever the other's policy changed.
        text = " ".join(question.split())
        folded = text.casefold()
        if self.symbol_shape:
            found = re.search(self.symbol_shape, text)
            if found is not None:
                return True, f"symbol:{found.group()}"
        for marker in self.topic_markers:
            if marker in folded:
                return True, f"topic:{marker}"
        for marker in self.off_topic_markers:
            if marker in folded:
                return False, f"off_topic:{marker}"
        return True, BODY_DEFAULT_REASON

    @property
    def identity(self) -> str:
        """What makes two packs the same pack, for a cache to key on.

        Covers the hand-written version *and* the prose, for the reason
        ``contract.contract_hash`` covers the prose under ``PROMPT_VERSION``:
        somebody will edit a body and not bump a number, and the cheap fix is to
        not depend on them remembering.
        """
        digest = hashlib.sha256()
        for part in (
            self.name,
            self.version,
            "\x1f".join(self.toolsets),
            self.body_text,
        ):
            digest.update(part.encode("utf-8"))
            digest.update(b"\x1e")
        return digest.hexdigest()


__all__ = ["BODY_DEFAULT_REASON", "DomainPack", "DomainPackInvalid"]
