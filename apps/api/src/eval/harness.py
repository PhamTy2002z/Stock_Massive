"""Sequential multi-trial scheduling, completeness, spend, and aggregation."""

from __future__ import annotations

import inspect
import math
import uuid
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import CaseFile, SnapshotFile
from .dataset import LoadedDataset
from .grading import CaseGrade, GradePipeline
if TYPE_CHECKING:
    from .runner import EvalResult

GATE_POLICY_SCHEMA = "eval.gate-policy@1"


class GatePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_tag: Literal["eval.gate-policy@1"] = Field(alias="schema")
    policy_id: str
    version: str
    dataset_id: str
    paid_trials: int = Field(ge=3)
    run_ceiling_usd: float = Field(gt=0)
    reservation_usd_per_trial: float = Field(gt=0)
    hard_dimensions: tuple[str, ...] = Field(min_length=1)
    thresholds: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def reservation_fits(self) -> "GatePolicy":
        if self.reservation_usd_per_trial > self.run_ceiling_usd:
            raise ValueError("one trial reservation cannot exceed the run ceiling")
        return self


class PolicyOverride(ValueError):
    pass


@dataclass(frozen=True)
class TrialRecord:
    case: CaseFile
    result: EvalResult
    grade: CaseGrade

    def as_wire(self) -> dict[str, Any]:
        return {
            "case_id": self.case.case_id,
            "family": self.case.family,
            "surface": self.case.surface,
            "trial": self.result.trial.model_dump(mode="json", by_alias=True),
            "observable": {
                "surface": self.result.observable.surface,
                "lifecycle_status": self.result.observable.lifecycle_status,
                "terminal_reason": self.result.observable.terminal_reason,
                "persisted_id": self.result.observable.persisted_id,
                "content": dict(self.result.observable.content),
            },
            "trajectory": [item.model_dump(mode="json", by_alias=True) for item in self.result.trajectory],
            "provider_access_attempts": list(self.result.provider_access_attempts),
            "scope_violations": list(self.result.scope_violations),
            "grade": self.grade.as_wire(),
        }


@dataclass(frozen=True)
class HarnessRun:
    run_id: str
    mode: Literal["smoke", "multi-trial"]
    records: tuple[TrialRecord, ...]
    completeness: Mapping[str, Any]
    aggregate: Mapping[str, Any]
    usage: Mapping[str, Any]
    provider: Mapping[str, Any]


Executor = Callable[..., Any]


class EvalHarness:
    def __init__(self, *, dataset: LoadedDataset, policy: GatePolicy, executor: Executor, pipeline: GradePipeline | None = None) -> None:
        if policy.dataset_id != dataset.manifest.dataset_id:
            raise ValueError("gate policy dataset does not match the loaded dataset")
        self.dataset = dataset
        self.policy = policy
        self.executor = executor
        self.pipeline = pipeline or GradePipeline()
        self.pipeline.validate_cases(tuple(dataset.cases.values()))
        registered_hard = {
            spec.grader_id
            for spec in self.pipeline.registry.specs
            if spec.grader_class == "hard"
        }
        configured_hard = set(policy.hard_dimensions)
        if configured_hard != registered_hard:
            raise ValueError(
                "gate policy hard dimensions must exactly match the registry; "
                f"missing={sorted(registered_hard - configured_hard)} "
                f"unknown={sorted(configured_hard - registered_hard)}"
            )

    async def run(
        self,
        *,
        mode: Literal["smoke", "multi-trial"],
        requested_trials: int | None = None,
        requested_ceiling_usd: float | None = None,
        run_id: str | None = None,
    ) -> HarnessRun:
        trials = 1 if mode == "smoke" else self.policy.paid_trials
        if requested_trials is not None and requested_trials != trials:
            raise PolicyOverride(f"trial count is repository-owned ({trials}); candidate requested {requested_trials}")
        ceiling = 0.0 if mode == "smoke" else self.policy.run_ceiling_usd
        if requested_ceiling_usd is not None and requested_ceiling_usd != ceiling:
            raise PolicyOverride(f"run ceiling is repository-owned ({ceiling}); candidate requested {requested_ceiling_usd}")

        identity = run_id or f"eval-{uuid.uuid4().hex[:16]}"
        records: list[TrialRecord] = []
        failures: list[dict[str, Any]] = []
        spent = 0.0
        reserved = 0.0
        stopped_reason: str | None = None
        rubric_ceiling_setter = getattr(self.pipeline.judge, "set_remaining_ceiling", None)
        if mode == "multi-trial" and self.pipeline.judge is not None and not callable(rubric_ceiling_setter):
            raise ValueError(
                "a paid rubric judge must enforce the remaining run ceiling before dispatch"
            )

        for trial_index in range(trials):
            for case_id in sorted(self.dataset.cases):
                if mode == "multi-trial" and reserved + self.policy.reservation_usd_per_trial > ceiling + 1e-12:
                    stopped_reason = "run_ceiling_exhausted_before_reservation"
                    break
                if mode == "multi-trial":
                    reserved += self.policy.reservation_usd_per_trial
                case = self.dataset.cases[case_id]
                snapshots = tuple(self.dataset.snapshots[pin.snapshot_id] for pin in case.snapshots)
                try:
                    value = self.executor(case=case, snapshots=snapshots, run_id=identity, trial_index=trial_index, mode=mode, remaining_ceiling_usd=max(0.0, ceiling - spent))
                    result = await value if inspect.isawaitable(value) else value
                    if result.trial.cost_usd is not None:
                        spent += result.trial.cost_usd
                    if mode == "multi-trial" and rubric_ceiling_setter is not None:
                        rubric_ceiling_setter(
                            max(0.0, ceiling - spent)
                            if result.trial.cost_usd is not None
                            else None
                        )
                    grade = await self.pipeline.grade(case=case, snapshots=snapshots, result=result)
                    record = TrialRecord(case, result, grade)
                    records.append(record)
                    if grade.rubric is not None and grade.rubric.cost_usd is not None:
                        spent += grade.rubric.cost_usd
                    if result.trial.terminal in ("incomplete", "cancelled", "failed"):
                        failures.append({"case_id": case_id, "trial_index": trial_index, "reason": result.observable.terminal_reason or result.trial.terminal})
                    if result.provider_access_attempts:
                        failures.append({"case_id": case_id, "trial_index": trial_index, "reason": "data_provider_access_forbidden"})
                    if grade.rubric is not None and not grade.rubric.available:
                        failures.append({"case_id": case_id, "trial_index": trial_index, "reason": "rubric_unavailable"})
                except Exception as exc:  # noqa: BLE001 - incomplete is artifact data
                    failures.append({"case_id": case_id, "trial_index": trial_index, "reason": f"{type(exc).__name__}: {exc}"})
                    stopped_reason = "trial_execution_failed"
                    break
            if stopped_reason is not None:
                break

        expected = len(self.dataset.cases) * trials
        complete = len(records) == expected and not failures and stopped_reason is None
        completeness = {"complete": complete, "expected_trials": expected, "observed_trials": len(records), "stopped_reason": stopped_reason, "failures": failures}
        return HarnessRun(identity, mode, tuple(records), completeness, aggregate_records(records), usage_summary(records), provider_summary(records, self.dataset.snapshots))


def _interval(passed: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    z = 1.96
    p = passed / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return [round(max(0.0, center - spread), 6), round(min(1.0, center + spread), 6)]


def aggregate_records(records: list[TrialRecord] | tuple[TrialRecord, ...]) -> dict[str, Any]:
    groups: dict[str, dict[str, list[bool]]] = {name: defaultdict(list) for name in ("case", "family", "surface", "dimension")}
    for record in records:
        groups["case"][record.case.case_id].append(record.grade.hard_passed)
        groups["family"][record.case.family].append(record.grade.hard_passed)
        groups["surface"][record.case.surface].append(record.grade.hard_passed)
        for verdict in record.grade.verdicts:
            groups["dimension"][verdict.spec.grader_id].append(verdict.passed)
    wire: dict[str, Any] = {}
    for group, values in groups.items():
        wire[group] = {
            key: {"passed": sum(outcomes), "total": len(outcomes), "pass_rate": round(sum(outcomes) / len(outcomes), 6), "confidence_95": _interval(sum(outcomes), len(outcomes)), "any_trial_hard_failure": not all(outcomes)}
            for key, outcomes in sorted(values.items())
        }
    wire["hard_failures"] = sum(not record.grade.hard_passed for record in records)
    rubric_results = [record.grade.rubric for record in records if record.grade.rubric is not None]
    available = [item for item in rubric_results if item.available and item.scores is not None]
    wire["rubric"] = {
        "available": len(available),
        "total": len(rubric_results),
        "dimensions": {
            dimension: {
                "mean": round(sum(getattr(item.scores, dimension) for item in available) / len(available), 6),
                "min": min(getattr(item.scores, dimension) for item in available),
                "max": max(getattr(item.scores, dimension) for item in available),
            }
            for dimension in ("synthesis", "counterargument", "uncertainty", "utility")
        } if available else {},
    }
    return wire


def usage_summary(records: list[TrialRecord] | tuple[TrialRecord, ...]) -> dict[str, Any]:
    costs = [record.result.trial.cost_usd for record in records]
    known_costs = [value for value in costs if value is not None]
    candidate_usage_known = all(record.result.trial.usage_known for record in records)
    rubric_results = [record.grade.rubric for record in records if record.grade.rubric is not None]
    rubric_usage_known = all(item.usage_tokens is not None for item in rubric_results)
    return {
        "candidate_tokens": sum(record.result.trial.usage_tokens for record in records) if candidate_usage_known else None,
        "candidate_usage_known": candidate_usage_known,
        "candidate_cost_usd": round(sum(known_costs), 8) if candidate_usage_known and len(known_costs) == len(costs) else None,
        "candidate_cost_known_trials": len(known_costs),
        "rubric_tokens": sum(item.usage_tokens for item in rubric_results if item.usage_tokens is not None) if rubric_usage_known else None,
        "rubric_usage_known": rubric_usage_known,
        "rubric_cost_usd": (round(sum(record.grade.rubric.cost_usd or 0 for record in records if record.grade.rubric is not None), 8) if all(record.grade.rubric is None or record.grade.rubric.cost_usd is not None for record in records) else None),
        "latency_ms": {"total": sum(record.result.trial.latency_ms for record in records), "mean": round(sum(record.result.trial.latency_ms for record in records) / len(records), 3) if records else None},
    }


def provider_summary(records: list[TrialRecord] | tuple[TrialRecord, ...], snapshots: Mapping[str, SnapshotFile] | None = None) -> dict[str, Any]:
    evidence = {}
    calls = 0
    for record in records:
        calls += len(record.result.provider_access_attempts)
        for pin in record.case.snapshots:
            evidence[pin.snapshot_id] = True
    frozen = []
    for snapshot_id in sorted(evidence):
        snapshot = None if snapshots is None else snapshots.get(snapshot_id)
        frozen.append(
            {
                "snapshot_id": snapshot_id,
                "providers": [] if snapshot is None else sorted({item.source.value for item in snapshot.evidence}),
                "capabilities": [] if snapshot is None else sorted({item.capability for item in snapshot.evidence}),
                "price_basis": [] if snapshot is None else sorted({item.price_basis for item in snapshot.evidence if item.price_basis is not None}),
                "freshness": None if snapshot is None else {"effective_from": min(item.effective_at for item in snapshot.evidence).isoformat(), "effective_to": max(item.effective_at for item in snapshot.evidence).isoformat()},
            }
        )
    return {"data_provider_calls": calls, "frozen_snapshots": frozen}


__all__ = ["EvalHarness", "GatePolicy", "HarnessRun", "PolicyOverride", "TrialRecord", "aggregate_records", "provider_summary", "usage_summary"]
