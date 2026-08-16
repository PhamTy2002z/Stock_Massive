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
   which a case could be carried over — roughly 16 cases × 3 runs × 3
   questions, which is the 20–30 minutes the ADR budgets.
3. *The verbatim answers being judged are in the file.* A careless pass leaves
   a readable trace, in the sheet and in the report.

The sheet is Markdown a person edits, so its answer lines are a fixed shape
rather than prose: ``- <key> = yes`` / ``= no``, and ``= ?`` until scored.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from .cases import EvalCategory

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

_HEADING = re.compile(r"^###\s+`(?P<case>[^`]+)`\s+—\s+run\s+(?P<run>\d+)\s*$")
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
    """Every human answer, keyed by the run it was given about."""

    answers: Mapping[tuple[str, int], Mapping[str, bool]]

    def for_run(self, case_id: str, run_index: int) -> Mapping[str, bool] | None:
        return self.answers.get((case_id, run_index))

    def failed_questions(self, case_id: str, run_index: int) -> tuple[str, ...]:
        """Which questions this run did not pass, in the sheet's own order."""
        given = self.for_run(case_id, run_index)
        if given is None:
            return ()
        return tuple(
            question.key
            for question in QUESTIONS
            if question.key in given and not question.passed(given[question.key])
        )

    def passed(self, case_id: str, run_index: int) -> bool:
        """A run passes the rubric when every question it was asked passed."""
        return not self.failed_questions(case_id, run_index)


def judged_results(result) -> tuple:
    """The case results a person scores, in the order the battery ran them."""
    return tuple(
        item for item in result.results if item.case.category in JUDGED_CATEGORIES
    )


def render_sheet(result) -> str:
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
        f"{sum(len(item.runs) for item in judged)} runs × {len(QUESTIONS)} "
        "questions. Every case is re-scored on every gate run, including the "
        "ones that did not change."
    )
    lines.append("")

    for item in judged:
        for run in item.runs:
            lines.append(f"### `{item.case.id}` — run {run.run_index + 1}")
            lines.append("")
            asked = item.prompt or item.case.prompt
            if asked:
                lines.append("> " + asked.replace("\n", "\n> "))
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
    answers: dict[tuple[str, int], dict[str, bool]] = {}
    missing: list[str] = []
    current: tuple[str, int] | None = None

    for line in text.splitlines():
        heading = _HEADING.match(line.strip())
        if heading:
            current = (heading.group("case"), int(heading.group("run")) - 1)
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
            missing.append(f"{current[0]} run {current[1] + 1} / {key}")
            continue
        answers[current][key] = value == "yes"

    for key, given in answers.items():
        for question in QUESTIONS:
            if question.key not in given:
                missing.append(f"{key[0]} run {key[1] + 1} / {question.key}")

    if missing:
        raise RubricIncomplete(sorted(set(missing)))
    return RubricScores(answers={key: dict(value) for key, value in answers.items()})


def assert_covers(result, scores: RubricScores) -> None:
    """Refuse a sheet that does not cover every judged run of this battery.

    The second defence, made mechanical: a reviewer who scored the four cases
    that changed and left the rest would otherwise produce a combined verdict
    over twelve unscored runs.
    """
    wanted = {
        (item.case.id, run.run_index)
        for item in judged_results(result)
        for run in item.runs
    }
    scored = set(scores.answers)
    unscored = sorted(f"{case} run {index + 1}" for case, index in wanted - scored)
    if unscored:
        raise RubricMismatch(
            "this sheet does not score every judged run of the battery: "
            + ", ".join(unscored)
        )
    stray = sorted(f"{case} run {index + 1}" for case, index in scored - wanted)
    if stray:
        raise RubricMismatch(
            "this sheet scores runs that are not in the battery: "
            + ", ".join(stray)
        )


def sheet_filename(report_name: str) -> str:
    """The sheet that belongs beside one report."""
    stem = report_name[:-3] if report_name.endswith(".md") else report_name
    return f"{stem}.rubric.md"


def question_lines(keys: Iterable[str]) -> tuple[str, ...]:
    """The prose of named questions, for a report explaining what failed."""
    return tuple(QUESTIONS_BY_KEY[key].text for key in keys)


__all__ = [
    "JUDGED_CATEGORIES",
    "QUESTIONS",
    "QUESTIONS_BY_KEY",
    "UNANSWERED",
    "RubricIncomplete",
    "RubricMismatch",
    "RubricQuestion",
    "RubricScores",
    "assert_covers",
    "judged_results",
    "question_lines",
    "read_sheet",
    "render_sheet",
    "sheet_filename",
]
