from __future__ import annotations

from pathlib import Path

import pytest

from src.eval.baseline import IncompatibleBaseline, compare
from src.eval.dataset import load_dataset
from src.eval.harness import EvalHarness
from src.eval.report import build_artifact, load_artifact, persist_artifact, render_markdown

from .test_eval_battery import scripted_result
from .test_eval_harness import ROOT, policy


def identity(dataset):
    prices = {"input": 0.0, "cached_input": 0.0, "cache_write": 0.0, "output": 0.0}
    return {
        "dataset_id": dataset.manifest.dataset_id,
        "dataset_digest": dataset.dataset_digest,
        "case_contract_digest": "c" * 16,
        "graders": {"terminal-state": "1.0.0"},
        "rubric_version": "investment-intelligence-rubric@1",
        "policy_version": "1.0.0",
        "trials": 1,
        "code": {"git_sha": "a" * 40, "dirty": True},
        "prompts": {"version": "v1", "contract_sha": "sha", "loop_version": "loop-v1", "generation_version": "generation-v1"},
        "tools": {"digest": "d" * 16, "names": [], "unavailable": []},
        "model": {"session_model": "session", "batch_model": "batch", "route_base_url": "offline", "streaming": False, "reasoning_history": False, "prompt_cache_control": False, "pricing_version": "zero", "pricing_effective_from": None, "session_prices": prices, "batch_prices": prices, "request_timeout_seconds": 1.0, "route_breaker_enabled": False},
        "provider_capabilities": {},
    }


@pytest.mark.asyncio
async def test_canonical_artifact_roundtrip_and_markdown_are_deterministic(tmp_path):
    dataset = load_dataset(ROOT)
    selected_policy = policy()
    run = await EvalHarness(dataset=dataset, policy=selected_policy, executor=lambda **kwargs: scripted_result(kwargs["case"], run_id=kwargs["run_id"], trial_index=kwargs["trial_index"])).run(mode="smoke", run_id="run-deterministic")
    artifact = build_artifact(run, identity=identity(dataset), policy=selected_policy, reproduction_command="make eval-smoke")
    first = persist_artifact(tmp_path / "first.json", artifact)
    second = persist_artifact(tmp_path / "second.json", artifact)
    assert first.read_bytes() == second.read_bytes()
    assert load_artifact(first) == artifact
    assert artifact["manifest"]["schema"] == "eval.run-manifest@1"
    assert artifact["manifest"]["run_id"] == "run-deterministic"
    assert artifact["manifest"]["mode"] == "smoke"
    assert artifact["manifest"]["dataset_digest"] == dataset.dataset_digest
    assert "identity" not in artifact
    assert render_markdown(artifact) == render_markdown(artifact)
    assert "Data-provider calls: `0`" in render_markdown(artifact)


def test_baseline_mismatch_requires_reviewed_reset():
    baseline = {"artifact_digest": "base", "identity": {"dataset_digest": "old", "case_contract_digest": "cases", "graders": {}, "rubric_version": None, "policy_version": "1", "trials": 3}, "completeness": {"complete": True}, "aggregate": {"dimension": {}}, "usage": {}}
    candidate = {"artifact_digest": "next", "identity": {**baseline["identity"], "dataset_digest": "new"}, "completeness": {"complete": True}, "aggregate": {"dimension": {}}, "usage": {}}
    with pytest.raises(IncompatibleBaseline, match="reviewed reset"):
        compare(baseline, candidate)
    reviewed = compare(baseline, candidate, reviewed_reset={"reviewed": True, "from_digest": "base", "to_digest": "next", "reason": "Reviewed exam reset"})
    assert not reviewed.compatible
    assert not reviewed.passed
    assert "not compared" in reviewed.reason


def test_resolved_tool_contract_mismatch_requires_reviewed_reset():
    identity_wire = {
        "dataset_digest": "same",
        "case_contract_digest": "cases",
        "tools": {"digest": "a" * 16, "names": ["get_field"], "unavailable": []},
        "graders": {},
        "rubric_version": None,
        "policy_version": "1",
        "trials": 3,
    }
    baseline = {
        "identity": identity_wire,
        "completeness": {"complete": True},
        "aggregate": {"dimension": {}},
        "usage": {},
    }
    candidate = {
        **baseline,
        "identity": {
            **identity_wire,
            "tools": {**identity_wire["tools"], "digest": "b" * 16},
        },
    }

    with pytest.raises(IncompatibleBaseline, match="tools"):
        compare(baseline, candidate)


def test_incomplete_or_new_hard_regression_cannot_pass():
    identity_wire = {"dataset_digest": "same", "case_contract_digest": "cases", "graders": {}, "rubric_version": None, "policy_version": "1", "trials": 3}
    baseline = {"identity": identity_wire, "completeness": {"complete": True}, "aggregate": {"dimension": {"policy-action": {"any_trial_hard_failure": False}}}, "usage": {}}
    incomplete = {"identity": identity_wire, "completeness": {"complete": False}, "aggregate": {"dimension": {}}, "usage": {}}
    assert not compare(baseline, incomplete).passed
    incomplete_baseline = {**baseline, "completeness": {"complete": False}}
    assert compare(incomplete_baseline, baseline).reason == "baseline run is incomplete"
    regressed = {"identity": identity_wire, "completeness": {"complete": True}, "aggregate": {"dimension": {"policy-action": {"any_trial_hard_failure": True}}}, "usage": {}}
    result = compare(baseline, regressed)
    assert not result.passed
    assert result.hard_regressions[0]["dimension"] == "policy-action"

    missing = {"identity": identity_wire, "completeness": {"complete": True}, "aggregate": {"dimension": {}}, "usage": {}}
    result = compare(baseline, missing)
    assert not result.passed
    assert result.hard_regressions[0]["reason"] == "hard measurement missing"


def test_comparison_reports_rubric_quality_separately_from_usage():
    identity_wire = {"dataset_digest": "same", "case_contract_digest": "cases", "graders": {}, "rubric_version": "rubric-v1", "policy_version": "1", "trials": 3}
    baseline = {"identity": identity_wire, "completeness": {"complete": True}, "aggregate": {"dimension": {}, "rubric": {"available": 3, "dimensions": {"utility": {"mean": 3.0}}}}, "usage": {"candidate_cost_usd": 1.0}}
    candidate = {"identity": identity_wire, "completeness": {"complete": True}, "aggregate": {"dimension": {}, "rubric": {"available": 3, "dimensions": {"utility": {"mean": 4.0}}}}, "usage": {"candidate_cost_usd": 1.2}}
    tradeoffs = compare(baseline, candidate).tradeoffs
    assert tradeoffs["baseline_quality"]["dimensions"]["utility"]["mean"] == 3.0
    assert tradeoffs["candidate_quality"]["dimensions"]["utility"]["mean"] == 4.0
    assert tradeoffs["candidate_usage"]["candidate_cost_usd"] == 1.2


def test_markdown_includes_hard_failed_samples():
    artifact = {
        "run_id": "run-failed-sample",
        "artifact_digest": "deadbeefdeadbeef",
        "identity": {},
        "provider": {"data_provider_calls": 0},
        "completeness": {"complete": True, "observed_trials": 1, "expected_trials": 1, "failures": []},
        "aggregate": {"hard_failures": 1},
        "usage": {},
        "reproduction_command": "make eval-smoke",
        "trials": [{"case_id": "fact-close-price", "grade": {"findings": [{"case_id": "fact-close-price", "trial_index": 0, "dimension": "figure", "remediation": "Use the frozen value."}]}}],
    }
    markdown = render_markdown(artifact)
    assert "`fact-close-price` trial `0`: figure: Use the frozen value." in markdown
