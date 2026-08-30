"""A score for how much of this board is picture, and what it is missing.

The grammar says whether a board is *legal*. This says whether it is *good*, and
the two are separated because they have different consequences: an illegal board
is refused, a poor one is stored with its score beside it. A model that drew one
chart and three paragraphs has answered the question and answered it badly, and
throwing that away would leave the reader with nothing at all.

**Every threshold here is a guess with a date on it.** They were written before
any distribution of real boards existed, which is precisely the mistake this
project has made before and named: a ceiling set from an intuition becomes a
ceiling nobody revisits. They are constants, in one place, and phase 09 of the
plan that introduced them resets each from the first fifty boards.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .contracts import BoardSection, CaptionBlock, VisualBlock
from .grammar import Violation

#: How much of a board has to be picture rather than prose.
#:
#: **Provisional — reset from the distribution of the first fifty boards
#: (phase 09).** A guess, and knowingly one: the surface is a panel beside an
#: answer that is already prose, so a board that repeats the answer in captions
#: has spent the reader's attention twice.
MIN_VISUAL_RATIO = 0.7

#: How many characters of caption a whole board may carry.
#:
#: **Provisional — reset from the distribution of the first fifty boards
#: (phase 09).**
MAX_NARRATIVE_CHARS = 1_200

#: How many different kinds of picture a board should hold.
#:
#: **Provisional — reset from the distribution of the first fifty boards
#: (phase 09).** Two, because a board of four identical charts is a table drawn
#: four times.
MIN_WIDGET_KINDS = 2


@dataclass(frozen=True)
class Report:
    """The score, the measurements behind it, and what it flagged."""

    score: float
    visual_ratio: float
    narrative_chars: int
    kpi_count: int
    widget_kinds: int
    violations: tuple[Violation, ...]

    @property
    def passed(self) -> bool:
        return not self.violations

    def to_payload(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 3),
            "visualRatio": round(self.visual_ratio, 3),
            "narrativeChars": self.narrative_chars,
            "kpiCount": self.kpi_count,
            "widgetKinds": self.widget_kinds,
            "violations": [violation.to_payload() for violation in self.violations],
        }


def score(
    sections: Sequence[BoardSection], kpi_count: int
) -> Report:
    """Measure the board a reader will see, and name what it falls short on.

    The *compiled* sections, not the model's plan. The two differ by the pictures
    the server added — a comparison earns the bars beside it — and scoring the
    plan would mark a board down for a chart that is on it.
    """
    visuals = 0
    captions = 0
    narrative = 0
    kinds: set[str] = set()
    for section in sections:
        for block in section.blocks:
            if isinstance(block, VisualBlock):
                visuals += 1
                kinds.add(block.widget)
            elif isinstance(block, CaptionBlock):
                captions += 1
                narrative += len(block.template)

    blocks = visuals + captions
    ratio = 1.0 if blocks == 0 else visuals / blocks

    violations: list[Violation] = []
    if ratio < MIN_VISUAL_RATIO:
        violations.append(
            Violation(
                "visual_ratio_low",
                "sections",
                f"{visuals} of {blocks} blocks are pictures, under the "
                f"{MIN_VISUAL_RATIO:.0%} a board is expected to be",
            )
        )
    if narrative > MAX_NARRATIVE_CHARS:
        violations.append(
            Violation(
                "narrative_too_long",
                "sections",
                f"{narrative} characters of caption against a limit of "
                f"{MAX_NARRATIVE_CHARS}",
            )
        )
    if len(kinds) < MIN_WIDGET_KINDS and visuals > 1:
        violations.append(
            Violation(
                "widget_kinds_thin",
                "sections",
                f"{len(kinds)} kind of picture across {visuals} visuals; a board "
                "that draws one thing repeatedly is a table",
            )
        )

    # One point per rule met, scaled to a fraction, so a board that fails one of
    # three still reads as two thirds of a board rather than as a failure.
    checks = 3
    return Report(
        score=(checks - len(violations)) / checks,
        visual_ratio=ratio,
        narrative_chars=narrative,
        kpi_count=kpi_count,
        widget_kinds=len(kinds),
        violations=tuple(violations),
    )


__all__ = [
    "MAX_NARRATIVE_CHARS",
    "MIN_VISUAL_RATIO",
    "MIN_WIDGET_KINDS",
    "Report",
    "score",
]
