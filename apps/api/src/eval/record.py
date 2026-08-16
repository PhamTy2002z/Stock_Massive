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
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from src.agent.prompt import AnswerKind

from .cases import EvalCase, battery
from .harness import CaseResult, CaseRun, EvalMode, EvalRunResult
from .scoring import Check, CheckResult, DeterministicScore
from .versions import PinnedVersions

#: Bumped when a reader would have to parse the file differently.
RECORD_FORMAT_VERSION = 1


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
        "results": [item.as_wire() for item in result.results],
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
    return EvalRunResult(
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
        answer_kind=payload.get("answer_kind", AnswerKind.EDUCATION.value),
        tool_calls=tuple(payload.get("tool_calls", ())),
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
