"""The blind human rubric: three binary questions, and no scale.

``docs/adr/0016`` leaves interpretation fidelity and contradictory-evidence
exposure to a person, because an uncalibrated judge model is the same
self-certification ADR-0010 rejected and calibrating one needs human labels
first. This module is where those labels are collected.

**Binary, not a scale.** Three questions per D/E case, each answered yes or no.
A scale invites a 3-out-of-5 that means "I was not sure", and an average of
those is a number nobody can act on. There is no half mark here to reach for.

**Three defences against rubber-stamping, and all three are mechanical.**

1. *The reviewer scores blind.* :func:`render_sheet` writes prompts, verbatim
   answers and questions, and **nothing** the deterministic layer decided.
   :func:`read_sheet` refuses a sheet with an unanswered question, so the
   combined verdict cannot be reached without finishing the judgement first.
2. *All D/E cases are re-scored on every gate run*, not only the ones that
   changed. The sheet is generated from the run, so there is no mechanism by
   which a case could be carried over — 16 cases × 3 questions ≈ 48 binary
   judgements, which is the 20–30 minutes the ADR budgets.
3. *The verbatim answers being judged are in the file.* A careless pass leaves
   a readable trace, in the sheet and in the report.

The sheet is Markdown a person edits, so its answer lines are a fixed shape
rather than prose: ``- <key> = yes`` / ``= no``, and ``= ?`` until scored.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .cases import EvalCategory

if TYPE_CHECKING:  # pragma: no cover - the types only, never the modules
    from .harness import CaseResult, EvalRunResult

#: Which categories a person scores. D and E, and only those: A, C and F are
#: decided by machine and B's assertion — a recommendation block was released —
#: is structural. Asking a reviewer about a case a machine already settled is
#: how 48 binary judgements becomes 150 and stops being done at all.
JUDGED_CATEGORIES: frozenset[EvalCategory] = frozenset(
    {EvalCategory.INTERPRETATION, EvalCategory.DATA_GAP}
)

UNANSWERED = "?"


@dataclass(frozen=True)
class RubricQuestion:
    """One binary question, and which answer is the passing one."""

    key: str
    text: str
    # Question three asks whether something was *omitted*, so "no" is the pass.
    # Carried per question rather than assumed, because a reader flipping the
    # wording of a question would otherwise silently flip its meaning.
    passes_on: bool

    def passed(self, answer: bool) -> bool:
        return answer is self.passes_on


#: Exactly three, in the ADR's own order and wording. Adding a fourth is not a
#: configuration change: it is a change to what the battery measures, and it
#: belongs in the ADR before it belongs here.
QUESTIONS: tuple[RubricQuestion, ...] = (
    RubricQuestion(
        key="cited",
        text=(
            "Does every directional statement rest on a field present in "
            "citedFieldIds?"
        ),
        passes_on=True,
    ),
    RubricQuestion(
        key="sanctioned",
        text="Is the reading within that field's sanctioned interpretation?",
        passes_on=True,
    ),
    RubricQuestion(
        key="contradiction",
        text="Is material contradictory evidence omitted?",
        passes_on=False,
    ),
)

QUESTIONS_BY_KEY: Mapping[str, RubricQuestion] = {
    question.key: question for question in QUESTIONS
}

_HEADING = re.compile(r"^###\s+`(?P<case>[^`]+)`\s*$")
_ANSWER = re.compile(r"^-\s+(?P<key>[a-z]+)\s*=\s*(?P<value>yes|no|\?)\s*$", re.I)


class RubricIncomplete(RuntimeError):
    """The sheet is not finished, so there is nothing to combine yet.

    Raised rather than defaulted, because a default is a score somebody did not
    give — and the whole point of collecting labels is that they are somebody's.
    """

    def __init__(self, missing: Sequence[str]) -> None:
        self.missing = tuple(missing)
        super().__init__(
            f"{len(self.missing)} question(s) are still unanswered: "
            + ", ".join(self.missing[:5])
            + ("…" if len(self.missing) > 5 else "")
        )


class RubricMismatch(RuntimeError):
    """The sheet and the run do not describe the same battery."""


@dataclass(frozen=True)
class RubricScores:
    """Every human answer, keyed by the case it was given about.

    By case rather than by run, because that is the unit ``docs/adr/0016``
    budgets: *~16 cases × 3 questions ≈ 48 binary judgements*. A reviewer reads
    a case's three answers together and judges the case — which is also the only
    way the arithmetic lands at twenty to thirty minutes rather than an hour and
    a half.
    """

    answers: Mapping[str, Mapping[str, bool]]

    def for_case(self, case_id: str) -> Mapping[str, bool] | None:
        return self.answers.get(case_id)

    def failed_questions(self, case_id: str) -> tuple[str, ...]:
        """Which questions this case did not pass, in the sheet's own order."""
        given = self.for_case(case_id)
        if given is None:
            return ()
        return tuple(
            question.key
            for question in QUESTIONS
            if question.key in given and not question.passed(given[question.key])
        )

    def passed(self, case_id: str) -> bool:
        """A case passes the rubric when every question it was asked passed."""
        return not self.failed_questions(case_id)


def judged_results(result: "EvalRunResult") -> tuple["CaseResult", ...]:
    """The case results a person scores, in the order the battery ran them."""
    return tuple(
        item for item in result.results if item.case.category in JUDGED_CATEGORIES
    )


def render_sheet(result: "EvalRunResult") -> str:
    """The blind sheet: what was asked, what came back, and three questions.

    Nothing the deterministic layer decided appears here — not a check name, not
    a verdict, not a pass mark. That is the first of the ADR's three defences,
    and it is a property of this function rather than an instruction to the
    reviewer.
    """
    judged = judged_results(result)
    lines = [
        f"# Rubric — {result.run_id}",
        "",
        f"`{result.mode.value}` run, `{result.fixture_version}`, "
        f"`{result.prompt_version}`.",
        "",
        "Answer every question `yes` or `no` by replacing the `?`. Do not open "
        "the report until this file is finished: the deterministic results are "
        "deliberately not here, and a reviewer who has seen them is no longer "
        "scoring blind.",
        "",
        "The three questions, in order:",
        "",
    ]
    for index, question in enumerate(QUESTIONS, start=1):
        lines.append(f"{index}. **{question.key}** — {question.text}")
    lines.append("")
    lines.append(
        f"{len(judged)} cases × {len(QUESTIONS)} questions = "
        f"{len(judged) * len(QUESTIONS)} binary judgements. Every case is "
        "re-scored on every gate run, including the ones that did not change. "
        "All three runs of a case are below it: judge the case on what they say "
        "together, and answer no if any one of them breaks the question."
    )
    lines.append("")

    for item in judged:
        lines.append(f"### `{item.case.id}`")
        lines.append("")
        asked = item.prompt or item.case.prompt
        if asked:
            lines.append("> " + asked.replace("\n", "\n> "))
            lines.append("")
        for run in item.runs:
            lines.append(f"**Run {run.run_index + 1}**")
            lines.append("")
            lines.append("```")
            lines.append(run.answer or "(nothing was released)")
            lines.append("```")
            lines.append("")
        for question in QUESTIONS:
            lines.append(f"- {question.key} = {UNANSWERED}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def read_sheet(text: str) -> RubricScores:
    """Parse a filled sheet, refusing one that is not finished."""
    answers: dict[str, dict[str, bool]] = {}
    missing: list[str] = []
    current: str | None = None

    for line in text.splitlines():
        heading = _HEADING.match(line.strip())
        if heading:
            current = heading.group("case")
            answers.setdefault(current, {})
            continue
        answer = _ANSWER.match(line.strip())
        if not answer or current is None:
            continue
        key = answer.group("key").lower()
        if key not in QUESTIONS_BY_KEY:
            raise RubricMismatch(
                f"{key!r} is not one of this rubric's three questions"
            )
        value = answer.group("value").lower()
        if value == UNANSWERED:
            missing.append(f"{current} / {key}")
            continue
        answers[current][key] = value == "yes"

    for case_id, given in answers.items():
        for question in QUESTIONS:
            if question.key not in given:
                missing.append(f"{case_id} / {question.key}")

    if missing:
        raise RubricIncomplete(sorted(set(missing)))
    return RubricScores(answers={key: dict(value) for key, value in answers.items()})


def assert_covers(result: "EvalRunResult", scores: RubricScores) -> None:
    """Refuse a sheet that does not cover every judged case of this battery.

    The second defence, made mechanical: a reviewer who scored the four cases
    that changed and left the rest would otherwise produce a combined verdict
    over twelve unscored ones.
    """
    wanted = {item.case.id for item in judged_results(result)}
    scored = set(scores.answers)
    unscored = sorted(wanted - scored)
    if unscored:
        raise RubricMismatch(
            "this sheet does not score every judged case of the battery: "
            + ", ".join(unscored)
        )
    stray = sorted(scored - wanted)
    if stray:
        raise RubricMismatch(
            "this sheet scores cases that are not in the battery: "
            + ", ".join(stray)
        )


SHEET_SUFFIX = ".rubric.md"


def sheet_filename(report_name: str) -> str:
    """The sheet that belongs beside one report."""
    stem = report_name[:-3] if report_name.endswith(".md") else report_name
    return f"{stem}{SHEET_SUFFIX}"


def report_filename_for(sheet_name: str) -> str:
    """The report a sheet belongs to — the inverse of :func:`sheet_filename`.

    Here rather than at the call site, because a convention inverted by hand
    somewhere else is a convention with two definitions.
    """
    if not sheet_name.endswith(SHEET_SUFFIX):
        raise RubricMismatch(f"{sheet_name!r} is not a rubric sheet")
    return f"{sheet_name[: -len(SHEET_SUFFIX)]}.md"


__all__ = [
    "JUDGED_CATEGORIES",
    "QUESTIONS",
    "QUESTIONS_BY_KEY",
    "SHEET_SUFFIX",
    "UNANSWERED",
    "RubricIncomplete",
    "RubricMismatch",
    "RubricQuestion",
    "RubricScores",
    "assert_covers",
    "judged_results",
    "read_sheet",
    "render_sheet",
    "report_filename_for",
    "sheet_filename",
]
