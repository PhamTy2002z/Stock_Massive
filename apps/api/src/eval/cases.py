"""What one **Eval Case** is, and the registry the battery is read from.

An individual case is an ``Eval Case`` and is **never** called a probe.
``Capability Probe`` already means the boot-time LLM route contract test
(``src/core/llm/probe.py``), and two unrelated mechanisms sharing a word is how
an operator comes to read the wrong runbook during an incident.

This module holds the shape and the registry. The ~56 cases themselves are
seeded by the category tickets, and the registry is deliberately empty here
rather than pre-populated with placeholders: a battery that reports a category
total over cases nobody wrote is the same lie as one that drops cases and scores
anyway.

**Cases are seeded once.** After that the battery grows only through the flag
loop of ``docs/adr/0016`` — a flagged message confirmed as a genuine failure
becomes a new case, frozen with its fixture. Nobody adds cases to improve a
score, and :func:`register` exists so that adding one is a visible act in a
diff rather than a line appended to a list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.agent.prompt import AnswerKind

from .roles import FixtureRole


class EvalCategory(str, Enum):
    """The six categories of ``docs/adr/0016``, by their letters.

    The letters are the vocabulary the ADR, the report and the merge rule all
    use, so they are the value rather than a display name derived from one.
    """

    GROUNDING_CANARY = "A"
    FALSE_REFUSAL = "B"
    SCOPE = "C"
    INTERPRETATION = "D"
    DATA_GAP = "E"
    INJECTION = "F"

    @property
    def is_safety(self) -> bool:
        """Whether a rate is an acceptable answer for this category.

        A, C and F require 3/3: one leak is a leak, and a system prompt
        disclosed in one run out of three is not "92% safe".
        """
        return self in _SAFETY_CATEGORIES


_SAFETY_CATEGORIES = frozenset(
    {EvalCategory.GROUNDING_CANARY, EvalCategory.SCOPE, EvalCategory.INJECTION}
)


class EvalSurface(str, Enum):
    """The two surfaces the battery covers.

    The nightly Analysis is not exempt for having a schema: the model writes
    ``verdictLine``, ``thesis`` and a per-axis ``read``, so the artifact users
    read every day is free-form prose, and a schema proves shape rather than
    content.
    """

    TURN = "turn"
    ANALYSIS = "analysis"


@dataclass(frozen=True)
class AnalysisExpectation:
    """What the deterministic layer may decide about one Analysis-lane case.

    Its own type rather than more fields on :class:`Expectation`, because the
    two lanes share no field at all: an Analysis has no ``answer_kind``, no
    block structure and no refusal, and a Turn has no verdict and no axes. One
    flat expectation carrying both halves would leave every case with a set of
    fields that mean nothing for its surface — and an expectation field that
    means nothing is one that silently asserts nothing.
    """

    # Whether the pipeline must publish an Analysis for this seat. ``False`` is
    # the shape of a data-gap case: the deliberate bad symbols are in the
    # fixture so the pipeline refuses them by name, and an artifact produced
    # over evidence that should have been refused is exactly what fails.
    publishes: bool | None = None
    # Which failure code, when the case is about a specific refusal.
    failure_code: str | None = None
    # Field ids whose gap has to be **visible** in the published artifact. The
    # data-gap category is about exposure rather than absence: a figure the
    # backend could not read reaches the artifact ``refused`` with a reason, and
    # an artifact that quietly dropped it is one that looks whole.
    exposes_refused: tuple[str, ...] = ()


@dataclass(frozen=True)
class Expectation:
    """What the deterministic layer is entitled to decide about one case.

    Every field is optional and unset means *not asserted*. That is not laxity:
    interpretation fidelity and contradictory-evidence exposure are left to the
    human rubric on purpose (``docs/adr/0016``), and an expectation field for
    them would be an invitation to guess at what only a person can decide.
    """

    answer_kind: AnswerKind | None = None
    # Whether the Turn must refuse — either as an ``answer_kind`` of
    # ``refusal`` or as a Turn ending ``incomplete/grounding_failed``.
    refuses: bool | None = None
    # Category A: the figure the fixture marks unavailable must not reach the
    # screen. Asserted over the *displayed* text, because that is what a reader
    # would have seen.
    forbids_figures: bool = False
    # Category B: a legitimate question on a healthy symbol must produce a
    # recommendation block, not a hedge.
    requires_recommendation: bool = False
    # Which terminal reason, when the case is about a specific one.
    terminal_reason: str | None = None
    # The Analysis lane's half, unset on a Turn case and required on an
    # Analysis one — see :meth:`EvalCase.__post_init__`, which refuses the
    # mismatch rather than scoring a case whose surface and expectation
    # disagree about what is being measured.
    analysis: AnalysisExpectation | None = None


@dataclass(frozen=True)
class EvalCase:
    """One question, asked of one fixture seat, with one set of expectations."""

    id: str
    category: EvalCategory
    surface: EvalSurface
    # What the user types. Empty for an Analysis-lane case, whose input is the
    # symbol and the nightly pipeline rather than a message.
    prompt: str
    expectation: Expectation = field(default_factory=Expectation)
    # Which fixture seat the case is about, so a re-freeze that moves a symbol
    # moves the case with it. A case naming a ticker directly would be a case
    # that silently stops asking about the short-history symbol.
    role: FixtureRole | None = None
    # Free prose for the report, and for a reader deciding whether a failure is
    # the model's or the case's.
    intent: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("an Eval Case needs an id to fail under")
        if self.surface is EvalSurface.TURN and not self.prompt.strip():
            raise ValueError(f"{self.id}: a Turn case needs a prompt")
        if self.surface is EvalSurface.ANALYSIS and self.role is None:
            raise ValueError(f"{self.id}: an Analysis case needs a fixture seat")
        # A surface and an expectation that disagree is a case measuring
        # nothing: an Analysis case with no ``analysis`` expectation asserts
        # only the three lane checks and silently drops whatever it was written
        # for, and a Turn case carrying one asserts something no Turn produces.
        if self.surface is EvalSurface.ANALYSIS and self.expectation.analysis is None:
            raise ValueError(
                f"{self.id}: an Analysis case needs an AnalysisExpectation; "
                "without one it asserts nothing about what the pipeline produced"
            )
        if self.surface is EvalSurface.TURN and self.expectation.analysis is not None:
            raise ValueError(
                f"{self.id}: a Turn case carries no Analysis expectation"
            )


class DuplicateEvalCase(ValueError):
    """Two cases under one id, which would make a failure unattributable."""


_REGISTRY: dict[str, EvalCase] = {}


def register(*cases: EvalCase) -> tuple[EvalCase, ...]:
    """Seat cases in the battery, refusing a duplicate id."""
    for case in cases:
        if case.id in _REGISTRY:
            raise DuplicateEvalCase(
                f"{case.id} is already registered; a failure has to name exactly "
                "one case"
            )
        _REGISTRY[case.id] = case
    return cases


def battery() -> tuple[EvalCase, ...]:
    """Every registered case, in registration order.

    Unfiltered, and deliberately so. ``docs/adr/0016`` re-scores **all** D/E
    cases on every gate run rather than only the ones that changed, and a
    selector here would be the first thing reached for on a run that felt slow.
    """
    return tuple(_REGISTRY.values())


__all__ = [
    "AnalysisExpectation",
    "DuplicateEvalCase",
    "EvalCase",
    "EvalCategory",
    "EvalSurface",
    "Expectation",
    "battery",
    "register",
]
