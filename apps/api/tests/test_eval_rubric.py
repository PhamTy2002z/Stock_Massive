from __future__ import annotations

import json
from dataclasses import replace

import pytest

from src.core.llm import PricingTable, TokenPrices
from src.eval.rubric import LLMRubricJudge, blinded_payload, run_rubric
from src.eval.smoke import smoke_config

from .eval_world import analysis_case, analysis_snapshot
from .test_eval_graders import result


def test_rubric_payload_is_blinded_and_contains_only_authorized_inputs():
    payload = blinded_payload(analysis_case(), (analysis_snapshot(),), result())
    decoded = json.loads(payload)
    assert "candidate" not in payload.casefold()
    assert "hard_pass" not in payload.casefold()
    assert set(decoded) == {"authorized_context", "frozen_evidence", "outcome", "rubric", "rubric_version", "task"}
    assert decoded["rubric"]["dimensions"] == ["synthesis", "counterargument", "uncertainty", "utility"]


@pytest.mark.asyncio
async def test_rubric_accepts_only_strict_json():
    class Judge:
        def judge(self, _payload):
            return json.dumps({"synthesis": 4, "counterargument": 3, "uncertainty": 5, "utility": 4, "justification": "Balances the frozen axes and states the caveat."})

    graded = await run_rubric(Judge(), case=analysis_case(), snapshots=(analysis_snapshot(),), result=result())
    assert graded.available
    assert graded.scores is not None
    assert graded.scores.uncertainty == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", ["good answer", '{"synthesis": 5}', '{"synthesis": 9, "counterargument": 3, "uncertainty": 3, "utility": 3, "justification": "x"}', '{"synthesis": 4, "counterargument": 4, "uncertainty": 4, "utility": 4, "justification": "x", "hard_pass": true}'])
async def test_judge_failure_is_unavailable_not_a_hard_override(answer):
    class Judge:
        def judge(self, _payload):
            return answer

    graded = await run_rubric(Judge(), case=analysis_case(), snapshots=(analysis_snapshot(),), result=result(terminal="failed"))
    assert not graded.available
    assert graded.scores is None
    assert graded.error


@pytest.mark.asyncio
async def test_judge_transport_failure_is_unavailable():
    class Judge:
        def judge(self, _payload):
            raise RuntimeError("judge transport failed")

    graded = await run_rubric(
        Judge(),
        case=analysis_case(),
        snapshots=(analysis_snapshot(),),
        result=result(),
    )
    assert not graded.available
    assert graded.error == "RuntimeError: judge transport failed"


@pytest.mark.asyncio
async def test_live_rubric_refuses_before_dispatch_when_run_ceiling_is_too_small():
    class Client:
        calls = 0

        async def complete(self, _request, _spend):
            self.calls += 1
            raise AssertionError("dispatch must not occur")

    prices = TokenPrices(input=100.0, cached_input=100.0, cache_write=100.0, output=100.0)
    base = smoke_config()
    config = replace(
        base,
        pricing=PricingTable(
            version="rubric-ceiling-test",
            effective_from=None,
            session=prices,
            batch=prices,
        ),
    )
    client = Client()
    judge = LLMRubricJudge(client, config=config, owner_prefix="run-rubric")
    judge.set_remaining_ceiling(0.0)

    with pytest.raises(ValueError, match="remaining run ceiling"):
        await judge.judge("{}")
    assert client.calls == 0
