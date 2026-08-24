from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from src.eval.dataset import load_dataset
from src.eval.harness import EvalHarness, GatePolicy, PolicyOverride
from src.eval.grading import GradePipeline
from src.eval.smoke import execute_scripted_case

from .test_eval_battery import scripted_result

ROOT = Path(__file__).parents[1] / "eval" / "datasets" / "investment-intelligence-v1"


def policy(**updates):
    values = {"schema": "eval.gate-policy@1", "policy_id": "investment-intelligence-v1", "version": "1.0.0", "dataset_id": "investment-intelligence-v1", "paid_trials": 3, "run_ceiling_usd": 10, "reservation_usd_per_trial": 0.01, "hard_dimensions": ["terminal-state", "figure-value-unit", "entity-scope", "as-of-publication", "evidence-health-coverage", "policy-action", "tool-settlement"], "thresholds": {}}
    values.update(updates)
    return GatePolicy.model_validate(values)


@pytest.mark.asyncio
async def test_paid_trials_are_fixed_and_candidate_cannot_weaken_policy():
    dataset = load_dataset(ROOT)
    harness = EvalHarness(dataset=dataset, policy=policy(), executor=lambda **kwargs: scripted_result(kwargs["case"], run_id=kwargs["run_id"], trial_index=kwargs["trial_index"]))
    with pytest.raises(PolicyOverride, match="repository-owned"):
        await harness.run(mode="multi-trial", requested_trials=1)
    with pytest.raises(PolicyOverride, match="repository-owned"):
        await harness.run(mode="multi-trial", requested_ceiling_usd=100)


def test_gate_policy_must_measure_every_registered_hard_dimension():
    dataset = load_dataset(ROOT)
    with pytest.raises(ValueError, match="must exactly match"):
        EvalHarness(
            dataset=dataset,
            policy=policy(hard_dimensions=["terminal-state", "imaginary-hard-check"]),
            executor=lambda **kwargs: scripted_result(kwargs["case"]),
        )


@pytest.mark.asyncio
async def test_multi_trial_retains_all_attempts_and_any_trial_failure():
    dataset = load_dataset(ROOT)

    def executor(**kwargs):
        value = scripted_result(kwargs["case"], run_id=kwargs["run_id"], trial_index=kwargs["trial_index"])
        if kwargs["case"].case_id == "fact-close-price" and kwargs["trial_index"] == 1:
            observable = value.observable.__class__(surface=value.observable.surface, lifecycle_status=value.observable.lifecycle_status, terminal_reason=value.observable.terminal_reason, persisted_id=value.observable.persisted_id, content={"text": "FPT 99,000 USD", "actions": []})
            return value.__class__(value.trial, observable, value.trajectory)
        return value

    run = await EvalHarness(dataset=dataset, policy=policy(), executor=executor).run(mode="multi-trial", run_id="run-three-trials")
    assert run.completeness["complete"]
    assert len(run.records) == 48
    assert run.aggregate["case"]["fact-close-price"]["any_trial_hard_failure"]
    assert run.aggregate["case"]["fact-close-price"]["passed"] == 2


@pytest.mark.asyncio
async def test_ceiling_stops_before_next_reservation_and_marks_incomplete():
    dataset = load_dataset(ROOT)
    constrained = policy(run_ceiling_usd=0.15, reservation_usd_per_trial=0.01)
    run = await EvalHarness(dataset=dataset, policy=constrained, executor=lambda **kwargs: scripted_result(kwargs["case"], run_id=kwargs["run_id"], trial_index=kwargs["trial_index"])).run(mode="multi-trial", run_id="run-budget-stop")
    assert not run.completeness["complete"]
    assert run.completeness["observed_trials"] == 15
    assert run.completeness["stopped_reason"] == "run_ceiling_exhausted_before_reservation"
    assert run.usage["candidate_cost_usd"] is None


@pytest.mark.asyncio
async def test_real_scripted_replay_has_stable_canonical_record():
    dataset = load_dataset(ROOT)
    case = dataset.cases["fact-close-price"]
    snapshots = tuple(dataset.snapshots[pin.snapshot_id] for pin in case.snapshots)
    arguments = {
        "case": case,
        "snapshots": snapshots,
        "run_id": "run-stable-replay",
        "trial_index": 0,
        "mode": "smoke",
        "remaining_ceiling_usd": 0,
    }
    first = await execute_scripted_case(**arguments)
    second = await execute_scripted_case(**arguments)
    assert first.trial == second.trial
    assert first.observable == second.observable
    assert first.trajectory == second.trajectory


@pytest.mark.asyncio
async def test_provider_access_attempt_makes_run_incomplete():
    dataset = load_dataset(ROOT)

    def executor(**kwargs):
        value = scripted_result(
            kwargs["case"],
            run_id=kwargs["run_id"],
            trial_index=kwargs["trial_index"],
        )
        return replace(value, provider_access_attempts=("blocked provider call",))

    run = await EvalHarness(
        dataset=dataset,
        policy=policy(),
        executor=executor,
    ).run(mode="smoke", run_id="run-provider-attempt")
    assert not run.completeness["complete"]
    assert run.provider["data_provider_calls"] == 16
    assert all(
        item["reason"] == "data_provider_access_forbidden"
        for item in run.completeness["failures"]
    )


@pytest.mark.asyncio
async def test_paid_run_rejects_rubric_judge_without_pre_dispatch_ceiling_guard():
    class UnguardedJudge:
        def judge(self, _payload):
            raise AssertionError("judge must not run")

    dataset = load_dataset(ROOT)
    harness = EvalHarness(
        dataset=dataset,
        policy=policy(),
        executor=lambda **kwargs: scripted_result(kwargs["case"]),
        pipeline=GradePipeline(judge=UnguardedJudge()),
    )
    with pytest.raises(ValueError, match="must enforce the remaining run ceiling"):
        await harness.run(mode="multi-trial")
