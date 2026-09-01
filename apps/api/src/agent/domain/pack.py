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
from dataclasses import dataclass

from ..prompt.contract import assert_no_formatting_hole
from ..prompt.sections import PromptSection


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


__all__ = ["DomainPack", "DomainPackInvalid"]
