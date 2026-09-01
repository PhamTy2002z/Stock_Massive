"""The only place in this harness where a bar exists.

Separating the bar from the grader is not tidiness. A threshold written beside
the logic that produces the number gets tuned by whoever is failing it, and that
is how the thresholds of the previous battery ended up describing an exam nobody
had sat. The graders report; this file decides; and the two halves are read by
different people at different times.

Two kinds of bar, and only one of them is negotiable.

**Hard dimensions are fixed at 100% and are not read from a file.** Roadmap §10
Phase 1 names five of them and §2 explains why they cannot be a percentage:
terminal settlement, no fabricated citation, no material figure without
evidence, no source past ``as_of``, nothing over the permission and suitability
line. Evidence identity and budget join them because a measurement that lost
track of its own evidence or blew its own ceiling is not a measurement.

**Soft dimensions are read from ``thresholds.json`` and start empty.** No
threshold before a distribution. Until a multi-trial baseline exists, the file
says ``null`` and this gate reports those dimensions without judging them.

The interval is Wilson rather than the textbook normal approximation, because
the corpus is forty cases and the rates being measured sit near 0 or near 1 —
which is exactly where the normal approximation returns bounds outside [0, 1]
and calls a perfect run "100% ± 0". The denominator is the **case**, not the
case-trial: three trials of one question are repeated draws on one sample, not
three samples.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: 95%, two-sided.
Z = 1.959963984540054

THRESHOLDS_FILE = Path(__file__).resolve().parent / "thresholds.json"


def wilson(passes: int, n: int, z: float = Z) -> tuple[float, float]:
    """The Wilson score interval for ``passes`` out of ``n``.

    Returns ``(0.0, 1.0)`` for an empty sample: no information is not the same
    as no confidence, and a zero-width interval around zero would read as one.
    """
    if n <= 0:
        return (0.0, 1.0)
    phat = passes / n
    denominator = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denominator
    spread = (z / denominator) * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return (max(0.0, centre - spread), min(1.0, centre + spread))


@dataclass(frozen=True)
class Row:
    """One dimension's line in the report."""

    dimension: str
    dimension_class: str
    passed: int
    decided: int
    trials_passed: int
    trials_decided: int
    low: float
    high: float
    verdict: str
    detail: str

    @property
    def rate(self) -> float | None:
        return None if not self.decided else self.passed / self.decided

    def as_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "class": self.dimension_class,
            "cases_passed": self.passed,
            "cases_decided": self.decided,
            "trials_passed": self.trials_passed,
            "trials_decided": self.trials_decided,
            "rate": self.rate,
            "ci95": [round(self.low, 4), round(self.high, 4)],
            "verdict": self.verdict,
            "detail": self.detail,
        }


@dataclass
class Verdict:
    """What the whole run amounts to, and the exit code that says so."""

    status: str
    rows: list[Row]
    notes: list[str]
    #: The rubric spread, carried through untouched. It never moves the status:
    #: the five axes are a model's opinion of an answer, and giving that a vote
    #: on the release verdict would hand it authority the deterministic
    #: dimensions earned and it has not.
    rubric: dict[str, Any] = field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        return {"pass": 0, "fail": 1, "unusable": 2}[self.status]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "exit_code": self.exit_code,
            "notes": self.notes,
            "rows": [row.as_dict() for row in self.rows],
            "rubric": self.rubric,
        }


def load_thresholds(path: Path | None = None) -> dict[str, Any]:
    target = path or THRESHOLDS_FILE
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def evaluate(report: Any, thresholds: Mapping[str, Any] | None = None) -> Verdict:
    """Turn a graded report into a verdict.

    A report that could not be graded is ``unusable`` and a report of a run that
    did not finish is ``fail`` — a half-green run is not a slightly worse pass,
    and the grader has already said so in its status. This only refuses to look
    away from it.
    """
    bars = dict((thresholds or {}).get("soft") or {})
    if report.status == "unusable":
        return Verdict("unusable", [], list(report.notes))
    rubric = report.rubric() if hasattr(report, "rubric") else {}

    rows: list[Row] = []
    failed_hard: list[str] = []
    failed_soft: list[str] = []
    blind_hard: list[str] = []
    for dimension, body in report.dimensions().items():
        decided = int(body["cases_decided"])
        passed = int(body["cases_passed"])
        low, high = wilson(passed, decided)
        dimension_class = str(body["class"])
        bar = bars.get(dimension)

        if decided == 0:
            verdict, detail = "no verdict", "no case declared this dimension"
            if dimension_class == "hard":
                # A hard dimension nothing decided is not a hard dimension that
                # passed. It is the corpus admitting it cannot yet ask the
                # question — a ground truth still to be frozen, an as_of nobody
                # pinned — and letting that show up green is precisely how a
                # gate becomes decoration.
                verdict, detail = "BLIND", "no case makes this dimension decidable"
                blind_hard.append(dimension)
        elif dimension_class == "hard":
            ok = passed == decided
            verdict = "pass" if ok else "FAIL"
            detail = (
                "100% required"
                if ok
                else "failed: " + ", ".join(body["failed_cases"][:5])
            )
            if not ok:
                failed_hard.append(dimension)
        elif bar is None:
            verdict = "reported"
            detail = "no threshold before a distribution"
        else:
            ok = (passed / decided) >= float(bar)
            verdict = "pass" if ok else "FAIL"
            detail = f"bar {float(bar):.0%}"
            if not ok:
                failed_soft.append(dimension)

        rows.append(
            Row(
                dimension=dimension,
                dimension_class=dimension_class,
                passed=passed,
                decided=decided,
                trials_passed=int(body["trials_passed"]),
                trials_decided=int(body["trials_decided"]),
                low=low,
                high=high,
                verdict=verdict,
                detail=detail,
            )
        )

    notes = list(report.notes)
    status = "pass"
    if report.status != "graded":
        status = "fail"
        notes.append(f"the run is {report.status}, which is never a pass")
    if failed_hard:
        status = "fail"
        notes.append("hard dimension(s) below 100%: " + ", ".join(failed_hard))
    if blind_hard:
        status = "fail"
        notes.append(
            "hard dimension(s) with nothing to decide on: "
            + ", ".join(blind_hard)
            + " — the corpus cannot yet ask the question, so this run is not a release verdict"
        )
    if failed_soft:
        status = "fail"
        notes.append("soft dimension(s) under their locked bar: " + ", ".join(failed_soft))
    return Verdict(status, rows, notes, rubric)


def render(verdict: Verdict) -> str:
    """The table a reader sees. One line per dimension, widest column first."""
    lines = [
        f"{'dimension':26} {'class':8} {'cases':>9}  {'rate':>6}  "
        f"{'95% CI':>15}  verdict",
        "-" * 88,
    ]
    for row in verdict.rows:
        rate = "  -  " if row.rate is None else f"{row.rate:.0%}"
        interval = f"[{row.low:.2f}, {row.high:.2f}]"
        lines.append(
            f"{row.dimension:26} {row.dimension_class:8} "
            f"{row.passed:>4}/{row.decided:<4} {rate:>6}  {interval:>15}  "
            f"{row.verdict} — {row.detail}"
        )
    rubric = verdict.rubric or {}
    axes = rubric.get("axes") or {}
    if axes:
        lines.append("")
        lines.append(
            f"rubric §3 (judge, reported only) — "
            f"{rubric.get('scored', 0)} scored, {rubric.get('unavailable', 0)} unavailable"
        )
        for axis, body in axes.items():
            mean = "  -  " if body["mean"] is None else f"{body['mean']:.2f}"
            span = "" if body["mean"] is None else f"  [{body['min']:.0f}–{body['max']:.0f}]"
            lines.append(f"  {axis:24} mean {mean} of 5  n={body['n']}{span}")

    lines.append("")
    for note in verdict.notes:
        lines.append(f"note: {note}")
    lines.append("")
    lines.append(f"status: {verdict.status} (exit {verdict.exit_code})")
    return "\n".join(lines)


__all__ = [
    "THRESHOLDS_FILE",
    "Z",
    "Row",
    "Verdict",
    "evaluate",
    "load_thresholds",
    "render",
    "wilson",
]
