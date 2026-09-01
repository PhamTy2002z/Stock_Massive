"""The gate is the only file with a bar in it, so it is the file with the teeth.

Three properties are tested here and each one has cost a run somewhere: a hard
dimension is not negotiable and not read from a file, a run that did not finish
is never a pass however good its numbers look, and a soft dimension with no
threshold is reported rather than silently treated as met.
"""

from __future__ import annotations

import pytest

from golden.gate import evaluate, load_thresholds, render, wilson
from golden.grade import SCHEMA, grade

CORPUS = {
    "dimensions": {
        "settlement": {"class": "hard"},
        "citation_url": {"class": "hard"},
        "evidence_identity": {"class": "hard"},
        "material_claim": {"class": "hard"},
        "temporal_validity": {"class": "hard"},
        "refusal_policy": {"class": "hard"},
        "budget": {"class": "hard"},
        "multi_source_label": {"class": "reported"},
        "distinct_domains": {"class": "reported"},
        "read_depth": {"class": "reported"},
        "parallel_rate": {"class": "reported"},
        "uncited_external_number": {"class": "reported"},
    },
    "markers": {"refusal": ["không đủ bằng chứng"], "advice": ["bạn nên mua"]},
    "evidence_dates": {"https://a.vn/x": "2026-08-01"},
}


def case(case_id="c-1", trial=1, **overrides):
    body = {
        "id": case_id,
        "trial": trial,
        "question": "q",
        "expect": {},
        "answer_text": "trả lời",
        "turn": {"status": "complete", "terminal_reason": None},
        "tool_calls": [
            {"id": "call-1", "name": "web_search", "round": 1, "kind": "external",
             "arguments": {"query": "x"}}
        ],
        "sources": [
            {"url": "https://a.vn/x", "domain": "a.vn", "title": "T", "from_call": "call-1"}
        ],
        "cost": {"micro_usd": 500},
    }
    body.update(overrides)
    return body


def decidable(case_id="c-0", **overrides):
    """A case that makes every hard dimension answerable.

    Needed because a hard dimension nothing declared is BLIND rather than green,
    so "a clean run" has to be a run the gate could actually judge.
    """
    body = case(
        case_id,
        expect={"must_refuse": True, "min_distinct_domains": 1},
        as_of="2026-08-20",
        answer_text="Không đủ bằng chứng để kết luận; con số công bố là 55.891 tỷ đồng.",
        ground_truth={"values": [{"key": "charter", "value": "55891", "tolerance": "0.01"}]},
    )
    body["sources"] = [
        {"url": "https://a.vn/x", "domain": "a.vn", "title": "T", "from_call": "call-1",
         "retrieved_at": "2026-08-10T00:00:00+00:00"}
    ]
    body.update(overrides)
    return body


def artifact(*cases, status="complete", trials=1):
    return {
        "schema": SCHEMA,
        "run": {
            "status": status,
            "trials": trials,
            "planned_case_trials": len(cases),
            "incomplete_reason": None if status == "complete" else "stopped early",
            "runtime_constants": {"MAX_TOOL_ROUNDS": 4, "MAX_EXTERNAL_TOOL_CALLS": 12},
        },
        "cases": list(cases),
    }


# -- the interval ----------------------------------------------------------


def test_wilson_brackets_the_point_estimate():
    low, high = wilson(18, 20)
    assert low < 0.9 < high
    assert 0.0 <= low <= high <= 1.0


def test_wilson_never_returns_a_zero_width_interval_on_a_perfect_run():
    low, high = wilson(20, 20)
    assert high == pytest.approx(1.0)
    # The lower bound is the whole reason for using Wilson here: twenty out of
    # twenty is not evidence of a hundred percent, and the normal approximation
    # would say it was.
    assert 0.8 < low < 1.0


def test_wilson_says_nothing_about_an_empty_sample():
    assert wilson(0, 0) == (0.0, 1.0)


# -- the verdict -----------------------------------------------------------


def test_a_clean_run_passes():
    verdict = evaluate(grade(artifact(decidable()), CORPUS))
    assert verdict.status == "pass"
    assert verdict.exit_code == 0


def test_one_fabricated_citation_fails_the_whole_run():
    dirty = decidable(case_id="c-2", answer_text="theo https://nowhere.vn/page")
    verdict = evaluate(grade(artifact(decidable(), dirty), CORPUS))
    assert verdict.status == "fail"
    assert verdict.exit_code == 1
    row = next(r for r in verdict.rows if r.dimension == "citation_url")
    assert row.verdict == "FAIL"
    assert "c-2" in row.detail


def test_a_hard_dimension_fails_when_any_trial_of_a_case_fails():
    """Three trials, one bad. A hard dimension takes the conjunction."""
    good = case(case_id="c-1", trial=1)
    also_good = case(case_id="c-1", trial=2)
    bad = case(case_id="c-1", trial=3, turn={"status": "unknown"})
    verdict = evaluate(grade(artifact(good, also_good, bad, trials=3), CORPUS))
    row = next(r for r in verdict.rows if r.dimension == "settlement")
    assert (row.passed, row.decided) == (0, 1)
    assert row.trials_passed == 2 and row.trials_decided == 3
    assert verdict.status == "fail"


def test_a_run_that_did_not_finish_is_never_a_pass():
    verdict = evaluate(grade(artifact(case(), status="incomplete"), CORPUS))
    assert verdict.status == "fail"
    assert any("incomplete" in note for note in verdict.notes)


def test_an_artifact_from_another_schema_is_unusable():
    verdict = evaluate(grade({"schema": "golden.artifact@1", "cases": []}, CORPUS))
    assert verdict.status == "unusable"
    assert verdict.exit_code == 2


def test_a_soft_dimension_without_a_threshold_is_reported_not_passed():
    verdict = evaluate(grade(artifact(case()), CORPUS), {"soft": {"multi_source_label": None}})
    row = next(r for r in verdict.rows if r.dimension == "multi_source_label")
    assert row.verdict in {"reported", "no verdict"}


def test_a_locked_soft_threshold_can_fail_a_run():
    thin = case(expect={"min_distinct_domains": 3})
    verdict = evaluate(
        grade(artifact(thin), CORPUS), {"soft": {"multi_source_label": 0.9}}
    )
    row = next(r for r in verdict.rows if r.dimension == "multi_source_label")
    assert row.verdict == "FAIL"
    assert verdict.status == "fail"


def test_the_shipped_thresholds_file_locks_nothing_yet():
    """No threshold before a distribution — asserted, not just written down."""
    thresholds = load_thresholds()
    assert thresholds["locked_from"] is None
    assert set(thresholds["soft"].values()) == {None}


def test_the_rendered_table_names_every_dimension():
    verdict = evaluate(grade(artifact(decidable()), CORPUS))
    text = render(verdict)
    for dimension in CORPUS["dimensions"]:
        assert dimension in text
    assert "status: pass" in text


def test_a_hard_dimension_nothing_decided_is_not_a_pass():
    """A blind hard gate is the way a gate quietly becomes decoration.

    ``material_claim`` decides nothing until a case freezes ground truth. Until
    then the corpus cannot ask the question, and a run over it is not a release
    verdict however green the other rows look.
    """
    verdict = evaluate(grade(artifact(case()), CORPUS))
    row = next(r for r in verdict.rows if r.dimension == "material_claim")
    assert row.verdict == "BLIND"
    assert verdict.status == "fail"
    assert any("nothing to decide" in note for note in verdict.notes)


def test_the_rubric_is_reported_and_never_moves_the_verdict():
    """A model's opinion of an answer does not get a vote on the release gate."""
    scored = decidable()
    scored["judge"] = {
        "status": "scored",
        "scores": {
            axis: {"score": 1, "why": "kém"}
            for axis in (
                "synthesis",
                "structure_for_intent",
                "counterargument",
                "uncertainty",
                "decision_utility",
            )
        },
    }
    verdict = evaluate(grade(artifact(scored), CORPUS))
    assert verdict.status == "pass"
    assert verdict.rubric["scored"] == 1
    assert verdict.rubric["axes"]["synthesis"]["mean"] == 1.0
    assert "rubric §3" in render(verdict)
