from __future__ import annotations

import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.eval.contracts import TrajectoryEvent, TrialOutcome
from src.eval.dataset import load_dataset
from src.eval.grading import GradePipeline
from src.eval.runner import EvalResult, ObservableOutcome

NOW = datetime(2026, 8, 21, 10, tzinfo=timezone.utc)
ROOT = Path(__file__).parents[1] / "eval" / "datasets" / "investment-intelligence-v1"


def scripted_result(case, *, run_id="run-battery", trial_index=0):
    words = ["FPT", "uncertain", "limited", "cannot", "unavailable", "substitute", "valuation", "counterargument", "hold", "watch", "neutral", "falsifier", "alternative", "conflict"]
    references = []
    actions = []
    clarification = False
    refused = False
    settled = any(item.kind == "settlement" for item in case.expectations)
    for expectation in case.expectations:
        params = expectation.params
        if expectation.kind == "figure":
            words.extend([str(params["value"]), str(params.get("unit", ""))])
        elif expectation.kind == "unit":
            words.append(str(params["value"]))
        elif expectation.kind in ("required_claims", "acceptable_conclusion"):
            words.extend(str(item) for item in params.get("values", []))
        elif expectation.kind == "entity_scope":
            words.extend(str(item) for item in params.get("required", []))
        elif expectation.kind in ("material_evidence", "evidence", "evidence_health"):
            references.extend(str(item) for item in params.get("required", []))
        elif expectation.kind == "clarification":
            clarification = True
        elif expectation.kind == "refusal":
            refused = True
    words.extend(references)
    events = []
    if settled:
        events = [
            TrajectoryEvent(schema="eval.trajectory-event@1", seq=0, kind="model_attempt", at=NOW, payload={"tool_calls": [{"id": "battery-call"}]}),
            TrajectoryEvent(schema="eval.trajectory-event@1", seq=1, kind="tool_call", at=NOW, payload={"call_id": "battery-call", "status": "ok", "evidence_references": references}),
        ]
    events.append(TrajectoryEvent(schema="eval.trajectory-event@1", seq=len(events), kind="terminal", at=NOW, payload={"status": "completed"}))
    trial = TrialOutcome(schema="eval.trial@1", run_id=run_id, case_id=case.case_id, trial_index=trial_index, started_at=NOW, finished_at=NOW, terminal="completed")
    observable = ObservableOutcome(surface=case.surface, lifecycle_status="ready" if case.surface == "analysis" else "completed", terminal_reason=None, persisted_id="synthetic", content={"text": " ".join(words), "confidence": "low", "refused": refused, "clarification_required": clarification, "actions": actions, "evidence_references": references})
    return EvalResult(trial=trial, observable=observable, trajectory=tuple(events))


def test_battery_contract_and_registry_coverage():
    dataset = load_dataset(ROOT)
    cases = tuple(dataset.cases.values())
    assert len(cases) == 16
    assert Counter(case.family for case in cases) == {"fact-unit-as-of": 4, "multi-axis-synthesis": 4, "sparse-refused-conflict": 4, "adversarial-policy": 4}
    assert Counter(case.surface for case in cases) == {"conversation": 10, "analysis": 6}
    assert sum(case.family == "adversarial-policy" for case in cases) == 4
    assert all(any("naive fluent" in trap for trap in case.traps) for case in cases)
    GradePipeline().validate_cases(cases)


@pytest.mark.asyncio
async def test_complete_scripted_battery_counts_every_case_and_family():
    dataset = load_dataset(ROOT)
    pipeline = GradePipeline()
    grades = []
    for case in dataset.cases.values():
        snapshots = tuple(dataset.snapshots[pin.snapshot_id] for pin in case.snapshots)
        grades.append(await pipeline.grade(case=case, snapshots=snapshots, result=scripted_result(case)))
    assert len(grades) == 16
    assert all(item.hard_passed for item in grades)


def test_grader_import_does_not_pull_runtime_or_attempt_provider_setup():
    completed = subprocess.run(
        [sys.executable, "-c", "import sys; import src.eval.graders; assert 'src.eval.runner' not in sys.modules"],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Vnstock" not in completed.stdout
    assert "Vnai" not in completed.stdout


def test_cli_import_opens_no_network_connection():
    script = """
import socket
attempts = []
original = socket.socket.connect
def record(self, address):
    attempts.append(address)
    raise RuntimeError('network blocked')
socket.socket.connect = record
import src.eval.cli
assert not attempts, attempts
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Vnstock" not in completed.stdout
