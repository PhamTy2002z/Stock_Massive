"""Ordered deterministic grading followed by an optional blinded rubric."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .contracts import CaseFile, SnapshotFile
from .graders import Finding, GraderRegistry, GraderVerdict, GradingContext, default_registry
from .rubric import RubricJudge, RubricResult, run_rubric
if TYPE_CHECKING:
    from .runner import EvalResult


class UnsupportedExpectation(ValueError):
    pass


@dataclass(frozen=True)
class CaseGrade:
    case_id: str
    trial_index: int
    hard_passed: bool
    verdicts: tuple[GraderVerdict, ...]
    findings: tuple[Finding, ...]
    rubric: RubricResult | None

    def as_wire(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "trial_index": self.trial_index,
            "hard_passed": self.hard_passed,
            "verdicts": [
                {"grader": item.spec.grader_id, "version": item.spec.version, "class": item.spec.grader_class, "mode": item.spec.mode, "passed": item.passed, "findings": [finding.as_wire() for finding in item.findings]}
                for item in self.verdicts
            ],
            "findings": [item.as_wire() for item in self.findings],
            "rubric": None if self.rubric is None else self.rubric.as_wire(),
        }


class GradePipeline:
    def __init__(self, registry: GraderRegistry | None = None, judge: RubricJudge | None = None) -> None:
        self.registry = registry or default_registry()
        self.judge = judge

    def validate_cases(self, cases: tuple[CaseFile, ...]) -> None:
        errors = [error for case in cases for error in self.registry.validate_case(case)]
        if errors:
            raise UnsupportedExpectation("\n".join(errors))

    async def grade(self, *, case: CaseFile, snapshots: tuple[SnapshotFile, ...], result: EvalResult) -> CaseGrade:
        self.validate_cases((case,))
        context = GradingContext(case=case, result=result, snapshots=snapshots)
        verdicts = tuple(grader(context, expectations) for _spec, grader, expectations in self.registry.applicable(case))
        findings = tuple(finding for verdict in verdicts for finding in verdict.findings)
        rubric = None if self.judge is None else await run_rubric(self.judge, case=case, snapshots=snapshots, result=result)
        return CaseGrade(case.case_id, result.trial.trial_index, all(item.passed for item in verdicts if item.spec.grader_class == "hard"), verdicts, findings, rubric)


__all__ = ["CaseGrade", "GradePipeline", "UnsupportedExpectation"]
