"""The rubric pass, tested against a model that never runs.

Two properties carry the whole design. The judge must see the answer and nothing
else — a judge shown the evidence re-checks arithmetic the backend already
checks mechanically, and a judge shown the other scores agrees with them. And a
judge that cannot answer must say so: a parse failure produces ``unavailable``,
never a middling score, because a missing verdict is missing information whereas
a three out of five is a claim.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from golden.grade import SCHEMA, grade
from golden.judge import AXES, Judge, build_user_message, judge_artifact, parse_scores

CORPUS = {
    "families": {"event_memo": "Something moved and the question is why."},
    "dimensions": {},
}

GOOD_JSON = json.dumps(
    {axis: {"score": 4, "why": "khá"} for axis in AXES}, ensure_ascii=False
)


class FakeCompletion:
    def __init__(self, text, model="fake-model"):
        self.text = text
        self.model = model


class FakeClient:
    """Answers with whatever it was handed, and remembers what it was asked."""

    def __init__(self, *replies, raises=None):
        self.replies = list(replies)
        self.raises = raises
        self.requests = []

    async def complete(self, request, spend):
        self.requests.append(request)
        if self.raises is not None:
            raise self.raises
        return FakeCompletion(self.replies.pop(0) if self.replies else GOOD_JSON)

    async def aclose(self):
        return None


class SilentJudge(Judge):
    """A judge whose ledger read is stubbed out; nothing here touches a database."""

    async def _reconcile(self, owner_id: str) -> int:
        return 1000


def case(**overrides):
    body = {
        "id": "c-1",
        "trial": 1,
        "family": "event_memo",
        "question": "VN-Index giảm ba phiên, vì sao?",
        "answer_text": "Thị trường giảm vì áp lực bán ròng.",
        "external_evidence_text": "một trang nói 1.832,12 điểm",
        "sources": [{"url": "https://a.vn/x", "domain": "a.vn", "title": "T"}],
        "cost": {"micro_usd": 500},
    }
    body.update(overrides)
    return body


# -- the parser ------------------------------------------------------------


def test_a_fenced_reply_still_parses():
    scores = parse_scores(f"```json\n{GOOD_JSON}\n```")
    assert sorted(scores) == sorted(AXES)


@pytest.mark.parametrize(
    "reply",
    [
        "no json at all",
        json.dumps({"synthesis": {"score": 4}}),
        json.dumps({axis: {"score": 9} for axis in AXES}),
        "[]",
    ],
)
def test_an_unreadable_reply_raises_rather_than_guessing(reply):
    with pytest.raises((ValueError, json.JSONDecodeError)):
        parse_scores(reply)


# -- what the judge is shown ----------------------------------------------


def test_the_judge_sees_the_answer_and_not_the_evidence():
    shown = build_user_message(case(), CORPUS)
    assert "Thị trường giảm vì áp lực bán ròng." in shown
    assert "VN-Index giảm ba phiên" in shown
    # The two things it must never see. A judge given either of these stops
    # scoring the shape of the answer and starts re-doing work the
    # deterministic dimensions already do exactly.
    assert "1.832,12" not in shown
    assert "a.vn" not in shown


# -- the pass --------------------------------------------------------------


def run(coro):
    return asyncio.run(coro)


def test_a_scored_case_carries_five_axes():
    client = FakeClient(GOOD_JSON)
    judge = SilentJudge(client, "fake-model")
    verdict = run(judge.score(case(), CORPUS))
    assert verdict["status"] == "scored"
    assert sorted(verdict["scores"]) == sorted(AXES)


def test_one_bad_reply_is_retried_and_the_second_one_counts():
    client = FakeClient("garbage", GOOD_JSON)
    judge = SilentJudge(client, "fake-model")
    assert run(judge.score(case(), CORPUS))["status"] == "scored"
    assert len(client.requests) == 2


def test_two_bad_replies_are_a_verdict_of_unavailable():
    client = FakeClient("garbage", "still garbage")
    judge = SilentJudge(client, "fake-model")
    verdict = run(judge.score(case(), CORPUS))
    assert verdict["status"] == "unavailable"
    assert "scores" not in verdict


def test_a_provider_failure_is_data_rather_than_a_crash():
    judge = SilentJudge(FakeClient(raises=RuntimeError("route down")), "fake-model")
    verdict = run(judge.score(case(), CORPUS))
    assert verdict["status"] == "unavailable"
    assert "route down" in verdict["reason"]


def test_the_ceiling_stops_the_pass_and_says_so(monkeypatch):
    artifact = {"schema": SCHEMA, "run": {}, "cases": [case(), case(id="c-2")]}

    async def fake_judge(self, one, corpus):
        self.spent_micro_usd += 1_000_000
        return {"status": "scored", "model": "fake", "prompt_version": "t",
                "scores": {axis: {"score": 3, "why": ""} for axis in AXES}}

    monkeypatch.setattr(Judge, "score", fake_judge)
    run(
        judge_artifact(
            artifact, CORPUS, ceiling_micro_usd=500_000, client=FakeClient(), model="fake"
        )
    )
    assert artifact["cases"][0]["judge"]["status"] == "scored"
    second = artifact["cases"][1]["judge"]
    assert second["status"] == "unavailable"
    assert "ceiling" in second["reason"]


# -- what the grader does with it -----------------------------------------


def test_the_grader_reports_scored_axes_and_ignores_unavailable_ones():
    scored = case()
    scored["judge"] = {
        "status": "scored",
        "scores": {axis: {"score": 4, "why": "khá"} for axis in AXES},
    }
    blank = case(id="c-2")
    blank["judge"] = {"status": "unavailable", "reason": "route down"}
    artifact = {
        "schema": SCHEMA,
        "run": {"status": "complete", "planned_case_trials": 2, "runtime_constants": {}},
        "cases": [scored, blank],
    }
    report = grade(artifact, CORPUS)
    judged = [f for f in report.findings if f.grader.startswith("judge_")]
    # Five axes for the case that was scored, none at all for the one that was
    # not: an unavailable verdict contributes no number rather than a neutral
    # one.
    assert len(judged) == len(AXES)
    assert {f.case_id for f in judged} == {"c-1"}


def test_the_judge_never_spends_the_probe_allowance():
    """The rubric pass must not eat the allowance production needs at boot.

    ``CAPABILITY_PROBE`` carries a hard daily ceiling shared with the route
    probe that runs on every restart. A judge pass over forty cases borrowing it
    would exhaust it in a handful of calls and leave the next boot unable to
    measure its own route, so the judge owns its calls under its own type.
    """
    from src.core.llm import BudgetLane, OwnerType

    client = FakeClient(GOOD_JSON)
    judge = SilentJudge(client, "fake-model", user_id=7)
    captured = {}

    async def capture(request, spend):
        captured["spend"] = spend
        return FakeCompletion(GOOD_JSON)

    client.complete = capture
    run(judge.score(case(), CORPUS))

    spend = captured["spend"]
    assert spend.owner.type is OwnerType.GOLDEN_JUDGE
    assert spend.owner.type is not OwnerType.CAPABILITY_PROBE
    assert spend.lane is BudgetLane.ANALYSIS
    # And its rows never land where a case's own cost is read from.
    assert spend.owner.id.startswith("golden-judge:")
