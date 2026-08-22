"""The run, written down so a person can finish scoring it tomorrow.

The human rubric takes 20–30 minutes (``docs/adr/0016``), which is longer than
the process that produced the answers. So a gate run leaves three files beside
each other and each has exactly one reader:

- ``<name>.md`` — the **report**, for a person, deterministic results included;
- ``<name>.rubric.md`` — the **blind sheet**, for the reviewer, with the
  deterministic results deliberately absent;
- ``<name>.json`` — this **record**, for the machine, so ``rubric score`` can
  combine the two without re-running anything.

That is not the per-case detail ADR-0016 keeps out of ``eval_run``: the
prohibition is on the *table*, whose value is baseline comparison in SQL and
which a hundred nested case results would make useless. A file beside the report
is where per-case detail was already meant to live.

The record stores what happened, never what the case *was*. Cases are code, so
they are looked up in the registry by id on read — and a record naming a case
this build no longer registers is refused rather than silently scored short.

Two things on the record are not case results, and both are here because the
**report a pull request attaches is written by ``rubric``**, from this file,
long after the run and against a different database:

- the **baseline** the run was read against, so the diff the merge rule asks for
  survives into that document. What is stored is the baseline *row*, not the
  computed diff: the diff is derived from two sets of totals that are both in
  hand on read, and a stored derivation is one that can go stale.
- the **ops-query snapshot**, so the field reading is the one taken during the
  run rather than a fresh window measured whenever somebody got around to
  scoring the rubric.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from src.agent.ops import OpsSnapshot

from .baseline import Baseline, compare_to_baseline
from .cases import EvalCase, battery
from .harness import CaseResult, CaseRun, EvalMode, EvalRunResult
from .scoring import Check, CheckResult, DeterministicScore
from .versions import PinnedVersions

#: Bumped when a reader would have to parse the file differently. Version 2 adds
#: the baseline and the ops-query snapshot, both of which the report is rendered
#: from — a version-1 record would produce a document silently missing the diff
#: the merge rule asks for, so it is refused rather than read short.
RECORD_FORMAT_VERSION = 2


class RecordUnreadable(RuntimeError):
    """A record this build cannot turn back into a battery run."""


def as_wire(result: EvalRunResult) -> dict[str, Any]:
    return {
        "format": RECORD_FORMAT_VERSION,
        "run_id": str(result.run_id),
        "mode": result.mode.value,
        "route": result.route,
        "model": result.model,
        "versions": result.versions.as_wire(),
        "prompt_version": result.prompt_version,
        "fixture_version": result.fixture_version,
        "started_at": result.started_at.isoformat(),
        "finished_at": result.finished_at.isoformat(),
        "complete": result.complete,
        "stopped_reason": result.stopped_reason,
        "report_path": result.report_path,
        # The baseline row rather than the comparison. Whether a comparison was
        # made at all is a property of this run — gate, and complete — so it is
        # re-decided on read instead of being stored as a second flag that could
        # disagree with the mode beside it.
        "baseline": _baseline_wire(result),
        "ops": None if result.ops is None else result.ops.as_wire(),
        "results": [item.as_wire() for item in result.results],
    }


def _baseline_wire(result: EvalRunResult) -> dict[str, Any] | None:
    comparison = result.baseline
    if comparison is None or comparison.baseline is None:
        return None
    baseline = comparison.baseline
    return {
        "run_id": str(baseline.run_id),
        "started_at": baseline.started_at.isoformat(),
        "prompt_version": baseline.prompt_version,
        "fixture_version": baseline.fixture_version,
        "category_totals": dict(baseline.category_totals),
        "report_path": baseline.report_path,
    }


def write_record(result: EvalRunResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(as_wire(result), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return path


def from_wire(payload: dict[str, Any]) -> EvalRunResult:
    declared = int(payload.get("format", 0))
    if declared != RECORD_FORMAT_VERSION:
        raise RecordUnreadable(
            f"this record is written in format {declared}; this build reads "
            f"format {RECORD_FORMAT_VERSION}"
        )
    registered = {case.id: case for case in battery()}
    result = EvalRunResult(
        run_id=uuid.UUID(payload["run_id"]),
        mode=EvalMode(payload["mode"]),
        route=payload["route"],
        model=payload["model"],
        versions=PinnedVersions.from_wire(payload["versions"]),
        prompt_version=payload["prompt_version"],
        fixture_version=payload["fixture_version"],
        started_at=datetime.fromisoformat(payload["started_at"]),
        finished_at=datetime.fromisoformat(payload["finished_at"]),
        results=tuple(
            _case_result(item, registered) for item in payload.get("results", ())
        ),
        complete=bool(payload.get("complete", True)),
        stopped_reason=payload.get("stopped_reason"),
        report_path=payload.get("report_path"),
        ops=(
            None
            if payload.get("ops") is None
            else OpsSnapshot.from_wire(payload["ops"])
        ),
    )
    if not result.gating:
        # The same rule ``EvalHarness._baseline_for`` applies, asked again
        # rather than stored: a smoke run has no gating value to compare with,
        # and a run that stopped has no score for a diff to be between.
        return result
    return replace(
        result,
        baseline=compare_to_baseline(
            dict(result.category_totals),
            result.fixture_version,
            _baseline(payload.get("baseline")),
        ),
    )


def _baseline(payload: dict[str, Any] | None) -> Baseline | None:
    if not payload:
        return None
    return Baseline(
        run_id=uuid.UUID(payload["run_id"]),
        started_at=datetime.fromisoformat(payload["started_at"]),
        prompt_version=payload["prompt_version"],
        fixture_version=payload["fixture_version"],
        category_totals=dict(payload.get("category_totals") or {}),
        report_path=payload.get("report_path"),
    )


def read_record(path: Path) -> EvalRunResult:
    if not path.exists():
        raise RecordUnreadable(
            f"no run record at {path}: it is written beside the report by "
            "`make eval`"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RecordUnreadable(f"{path} is not readable JSON: {exc}") from exc
    return from_wire(payload)


def record_filename(report_name: str) -> str:
    """The record that belongs beside one report."""
    stem = report_name[:-3] if report_name.endswith(".md") else report_name
    return f"{stem}.json"


def _case_result(payload: dict[str, Any], registered: dict[str, EvalCase]) -> CaseResult:
    case_id = payload["case_id"]
    case = registered.get(case_id)
    if case is None:
        raise RecordUnreadable(
            f"{case_id!r} is in this record and not in the battery this build "
            "seats; the record describes a different exam"
        )
    return CaseResult(
        case=case,
        runs=tuple(_run(item, case_id) for item in payload.get("runs", ())),
        prompt=payload.get("prompt", ""),
    )


def _run(payload: dict[str, Any], case_id: str) -> CaseRun:
    score = payload.get("score") or {}
    return CaseRun(
        run_index=int(payload["run_index"]),
        score=DeterministicScore(
            case_id=case_id,
            run_index=int(payload["run_index"]),
            results=tuple(_check(item) for item in score.get("checks", ())),
        ),
        answer=payload.get("answer", ""),
        status=payload.get("status", ""),
        terminal_reason=payload.get("terminal_reason"),
        verdict=payload.get("verdict"),
        cited_field_ids=tuple(payload.get("cited_field_ids", ())),
    )


def _check(payload: dict[str, Any]) -> CheckResult:
    return CheckResult(
        check=Check(payload["check"]),
        passed=bool(payload["passed"]),
        detail=payload.get("detail", ""),
        applicable=bool(payload.get("applicable", True)),
    )


__all__ = [
    "RECORD_FORMAT_VERSION",
    "RecordUnreadable",
    "as_wire",
    "from_wire",
    "read_record",
    "record_filename",
    "write_record",
]
