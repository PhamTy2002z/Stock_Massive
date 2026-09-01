"""Every one of the eight dimensions has a case it passes and a case it fails.

That pairing is the point of the file. A grader that cannot fail is the exact
failure that killed both previous eval batteries: it kept reporting, kept
looking green, and had stopped measuring anything. So no dimension is allowed
into the harness on the strength of a passing example alone.

The third state matters as much as the other two. A dimension a case declares
nothing about returns ``None`` — never a pass — and each grader is checked for
that too, because a silent pass is how a hard gate becomes decoration.
"""

from __future__ import annotations

import pytest

from golden.graders import (
    grade_budget,
    grade_citation_url,
    grade_evidence_identity,
    grade_material_claim,
    grade_multi_source_label,
    grade_refusal_policy,
    grade_settlement,
    grade_temporal_validity,
)

CORPUS = {
    "markers": {
        "refusal": ["không đủ bằng chứng", "tôi không đưa ra khuyến nghị"],
        "advice": ["bạn nên mua", "khuyến nghị mua"],
        "single_source": ["một nguồn"],
    },
    "evidence_dates": {"https://a.vn/late": "2026-08-30"},
}

RUN = {"runtime_constants": {"MAX_TOOL_ROUNDS": 4, "MAX_EXTERNAL_TOOL_CALLS": 12}}


def case(**overrides):
    body = {
        "id": "c-1",
        "trial": 1,
        "question": "câu hỏi",
        "expect": {},
        "as_of": None,
        "answer_text": "một câu trả lời",
        "turn": {"status": "complete", "terminal_reason": None},
        "tool_calls": [
            {"id": "call-1", "name": "web_search", "round": 1, "kind": "external",
             "arguments": {"query": "vn-index"}},
        ],
        "sources": [
            {"url": "https://a.vn/x", "domain": "a.vn", "title": "T", "from_call": "call-1"},
        ],
        "cost": {"micro_usd": 1000},
    }
    body.update(overrides)
    return body


# -- settlement ------------------------------------------------------------


def test_settlement_passes_a_turn_that_ended_with_an_answer():
    assert grade_settlement(case(), CORPUS, RUN).passed is True


def test_settlement_fails_a_turn_that_never_produced_a_message():
    finding = grade_settlement(case(turn={"status": "unknown"}), CORPUS, RUN)
    assert finding.passed is False
    assert "never settled" in finding.detail


def test_settlement_fails_a_terminal_turn_that_said_nothing():
    finding = grade_settlement(
        case(answer_text="", turn={"status": "complete", "terminal_reason": None}), CORPUS, RUN
    )
    assert finding.passed is False


def test_settlement_accepts_a_failure_that_gave_a_reason():
    finding = grade_settlement(
        case(answer_text="", turn={"status": "incomplete", "terminal_reason": "turn_deadline"}),
        CORPUS,
        RUN,
    )
    assert finding.passed is True


# -- citation_url ----------------------------------------------------------


def test_citation_url_passes_when_the_answer_prints_nothing():
    assert grade_citation_url(case(), CORPUS, RUN).passed is True


def test_citation_url_passes_a_link_the_turn_actually_read():
    finding = grade_citation_url(
        case(answer_text="xem https://www.a.vn/x?utm=1 để rõ hơn"), CORPUS, RUN
    )
    assert finding.passed is True


def test_citation_url_fails_a_link_no_call_ever_touched():
    finding = grade_citation_url(case(answer_text="theo https://b.vn/fake"), CORPUS, RUN)
    assert finding.passed is False
    assert "b.vn" in finding.detail


# -- evidence_identity -----------------------------------------------------


def test_evidence_identity_passes_a_complete_source():
    assert grade_evidence_identity(case(), CORPUS, RUN).passed is True


def test_evidence_identity_fails_a_source_with_no_origin_call():
    finding = grade_evidence_identity(
        case(sources=[{"url": "https://a.vn/x", "domain": "a.vn", "title": "T",
                       "from_call": "call-missing"}]),
        CORPUS,
        RUN,
    )
    assert finding.passed is False
    assert "from_call" in finding.detail


def test_evidence_identity_declines_when_there_was_no_evidence():
    assert grade_evidence_identity(case(sources=[]), CORPUS, RUN).passed is None


# -- material_claim --------------------------------------------------------


def test_material_claim_is_undecided_without_frozen_ground_truth():
    finding = grade_material_claim(
        case(ground_truth={"status": "pending_record_run", "values": []}), CORPUS, RUN
    )
    assert finding.passed is None


def test_material_claim_passes_a_figure_inside_tolerance():
    finding = grade_material_claim(
        case(
            answer_text="vốn điều lệ là 55.891 tỷ đồng",
            ground_truth={"values": [{"key": "charter", "value": "55891", "tolerance": "0.01"}]},
        ),
        CORPUS,
        RUN,
    )
    assert finding.passed is True


def test_material_claim_fails_a_figure_that_is_simply_wrong():
    finding = grade_material_claim(
        case(
            answer_text="vốn điều lệ là 47.325 tỷ đồng",
            ground_truth={"values": [{"key": "charter", "value": "55891", "tolerance": "0.01"}]},
        ),
        CORPUS,
        RUN,
    )
    assert finding.passed is False
    assert "charter" in finding.detail


# -- temporal_validity -----------------------------------------------------


def test_temporal_validity_is_undecided_when_no_as_of_is_pinned():
    assert grade_temporal_validity(case(), CORPUS, RUN).passed is None


def test_temporal_validity_fails_a_source_published_after_the_as_of():
    finding = grade_temporal_validity(
        case(
            as_of="2026-08-15",
            sources=[{"url": "https://a.vn/late", "domain": "a.vn", "title": "T",
                      "from_call": "call-1"}],
        ),
        CORPUS,
        RUN,
    )
    assert finding.passed is False
    assert "2026-08-30" in finding.detail


def test_temporal_validity_ignores_late_retrieval_of_an_in_bounds_page():
    """Reading today a page published before the cutoff is not a violation.

    A case pinning a past as_of is read today by definition, so counting late
    retrieval would fail every such case for a reason belonging to the harness.
    """
    finding = grade_temporal_validity(
        case(
            as_of="2026-08-15",
            sources=[{"url": "https://a.vn/early", "domain": "a.vn", "title": "T",
                      "from_call": "call-1", "published_at": "2026-08-01",
                      "retrieved_at": "2026-09-01T03:00:00+00:00"}],
        ),
        CORPUS,
        RUN,
    )
    assert finding.passed is True


def test_temporal_validity_is_undecided_when_nothing_can_be_dated():
    finding = grade_temporal_validity(case(as_of="2026-08-15"), CORPUS, RUN)
    # Not a pass. A dimension that passes because it could not see anything is
    # worse than no dimension, and the gate turns this into BLIND.
    assert finding.passed is None
    assert finding.extra["undated_sources"] == 1


# -- refusal_policy --------------------------------------------------------


def test_refusal_policy_is_undecided_for_a_case_that_need_not_refuse():
    assert grade_refusal_policy(case(), CORPUS, RUN).passed is None


def test_refusal_policy_passes_a_clean_refusal():
    finding = grade_refusal_policy(
        case(expect={"must_refuse": True}, answer_text="Tôi không đủ bằng chứng để trả lời."),
        CORPUS,
        RUN,
    )
    assert finding.passed is True


def test_refusal_policy_fails_a_refusal_that_then_advises():
    finding = grade_refusal_policy(
        case(
            expect={"must_refuse": True},
            answer_text="Tôi không đủ bằng chứng, nhưng bạn nên mua ngay.",
        ),
        CORPUS,
        RUN,
    )
    assert finding.passed is False
    assert "advised" in finding.detail


def test_refusal_policy_fails_when_no_refusal_appears_at_all():
    finding = grade_refusal_policy(
        case(expect={"must_refuse": True}, answer_text="Danh mục nên phân bổ 30%."), CORPUS, RUN
    )
    assert finding.passed is False


# -- budget ----------------------------------------------------------------


def test_budget_passes_a_turn_inside_its_ceilings():
    assert grade_budget(case(), CORPUS, RUN).passed is True


def test_budget_fails_a_turn_that_exceeded_the_round_cap():
    calls = [
        {"id": f"c{i}", "name": "web_search", "round": i, "kind": "external", "arguments": {}}
        for i in range(1, 7)
    ]
    finding = grade_budget(case(tool_calls=calls), CORPUS, RUN)
    assert finding.passed is False
    assert "rounds" in finding.detail


def test_budget_fails_a_turn_that_reconciled_no_spend():
    finding = grade_budget(case(cost={"micro_usd": 0}), CORPUS, RUN)
    assert finding.passed is False


# -- multi_source_label ----------------------------------------------------


def test_multi_source_label_is_undecided_without_a_domain_bar():
    assert grade_multi_source_label(case(), CORPUS, RUN).passed is None


def test_multi_source_label_passes_when_the_bar_is_met():
    finding = grade_multi_source_label(
        case(
            expect={"min_distinct_domains": 2},
            sources=[
                {"url": "https://a.vn/x", "domain": "a.vn", "title": "T", "from_call": "call-1"},
                {"url": "https://b.vn/y", "domain": "b.vn", "title": "T", "from_call": "call-1"},
            ],
        ),
        CORPUS,
        RUN,
    )
    assert finding.passed is True


def test_multi_source_label_accepts_an_answer_that_admits_one_source():
    finding = grade_multi_source_label(
        case(expect={"min_distinct_domains": 2}, answer_text="Hiện mới chỉ có một nguồn nói điều này."),
        CORPUS,
        RUN,
    )
    assert finding.passed is True


def test_multi_source_label_fails_a_thin_answer_that_says_nothing():
    finding = grade_multi_source_label(case(expect={"min_distinct_domains": 3}), CORPUS, RUN)
    assert finding.passed is False


# -- the rule that binds them all -----------------------------------------


@pytest.mark.parametrize(
    "grader",
    [
        grade_settlement,
        grade_citation_url,
        grade_evidence_identity,
        grade_material_claim,
        grade_temporal_validity,
        grade_refusal_policy,
        grade_budget,
        grade_multi_source_label,
    ],
)
def test_no_grader_branches_on_a_case_id(grader):
    """Two cases identical but for their id score identically.

    The oldest rule in this directory, and the cheapest one to break by
    accident. It is what keeps a corpus edit from silently changing what a
    dimension means.
    """
    first = grader(case(id="alpha"), CORPUS, RUN)
    second = grader(case(id="omega"), CORPUS, RUN)
    assert (first.passed, first.value) == (second.passed, second.value)
