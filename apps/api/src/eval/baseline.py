"""Immutable baseline compatibility and hard-regression release decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class IncompatibleBaseline(ValueError):
    pass


IDENTITY_FIELDS = ("dataset_digest", "case_contract_digest", "graders", "rubric_version", "policy_version", "trials")


@dataclass(frozen=True)
class Comparison:
    compatible: bool
    passed: bool
    hard_regressions: tuple[dict[str, Any], ...]
    tradeoffs: Mapping[str, Any]
    reason: str | None = None

    def as_wire(self) -> dict[str, Any]:
        return {"compatible": self.compatible, "passed": self.passed, "hard_regressions": list(self.hard_regressions), "tradeoffs": dict(self.tradeoffs), "reason": self.reason}


def compare(baseline: Mapping[str, Any], candidate: Mapping[str, Any], *, reviewed_reset: Mapping[str, Any] | None = None) -> Comparison:
    baseline_identity = baseline.get("manifest", baseline.get("identity", {}))
    candidate_identity = candidate.get("manifest", candidate.get("identity", {}))
    mismatches = {field: {"baseline": baseline_identity.get(field), "candidate": candidate_identity.get(field)} for field in IDENTITY_FIELDS if baseline_identity.get(field) != candidate_identity.get(field)}
    if mismatches:
        if not _valid_reset(reviewed_reset, baseline, candidate):
            raise IncompatibleBaseline(f"baseline identity mismatch requires reviewed reset: {mismatches}")
        return Comparison(False, False, (), {}, "reviewed reset records lineage; incompatible exams are not compared")
    if not baseline.get("completeness", {}).get("complete", False):
        return Comparison(not mismatches, False, (), {}, "baseline run is incomplete")
    if not candidate.get("completeness", {}).get("complete", False):
        return Comparison(not mismatches, False, (), {}, "candidate run is incomplete")

    base_dimensions = baseline.get("aggregate", {}).get("dimension", {})
    candidate_dimensions = candidate.get("aggregate", {}).get("dimension", {})
    regressions = []
    for dimension in sorted(set(base_dimensions) | set(candidate_dimensions)):
        current = candidate_dimensions.get(dimension)
        previous = base_dimensions.get(dimension, {})
        if current is None:
            regressions.append({"dimension": dimension, "baseline": previous, "candidate": None, "reason": "hard measurement missing"})
        elif current.get("any_trial_hard_failure") and not previous.get("any_trial_hard_failure", False):
            regressions.append({"dimension": dimension, "baseline": previous, "candidate": current})
    tradeoffs = {
        "candidate_quality": candidate.get("aggregate", {}).get("rubric"),
        "baseline_quality": baseline.get("aggregate", {}).get("rubric"),
        "candidate_usage": candidate.get("usage"),
        "baseline_usage": baseline.get("usage"),
    }
    return Comparison(not mismatches, not regressions, tuple(regressions), tradeoffs)


def _valid_reset(reset: Mapping[str, Any] | None, baseline: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    return bool(reset and reset.get("reviewed") is True and reset.get("from_digest") == baseline.get("artifact_digest") and reset.get("to_digest") == candidate.get("artifact_digest") and reset.get("reason"))


__all__ = ["Comparison", "IDENTITY_FIELDS", "IncompatibleBaseline", "compare"]
