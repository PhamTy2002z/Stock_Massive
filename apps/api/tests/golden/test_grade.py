"""The grader is the one part of the golden harness that runs for free.

So it is the part that gets tested. Every grader here has a case it passes and a
case it fails on purpose: a grader that cannot fail is the failure mode that
killed both previous eval batteries, and a test that only ever saw a green
artifact would not have noticed.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from golden.grade import (
    GRADERS,
    SCHEMA,
    canonical_numbers,
    covered,
    grade,
    grade_file,
    is_claim,
    parse_number,
)


def artifact(*cases, status: str = "complete", **run):
    return {
        "schema": SCHEMA,
        "run": {"status": status, "corpus_cases": len(cases), **run},
        "cases": list(cases),
    }


def case(case_id: str = "wf-001", **overrides):
    base = {
        "id": case_id,
        "question": "",
        "family": "fact_as_of",
        "expect": {},
        "answer_text": "",
        "tool_calls": [],
        "sources": [],
        "external_evidence_text": "",
        "store_evidence_text": "",
    }
    base.update(overrides)
    return base


def finding(report, grader, case_id="wf-001"):
    return next(f for f in report.findings if f.grader == grader and f.case_id == case_id)


# -- numbers ---------------------------------------------------------------


@pytest.mark.parametrize(
    "token,expected",
    [
        ("1234", Decimal("1234")),
        ("1.234", Decimal("1234")),
        ("1,234", Decimal("1234")),
        ("1.234,5", Decimal("1234.5")),
        ("1,234.5", Decimal("1234.5")),
        ("12,3", Decimal("12.3")),
        ("12.3", Decimal("12.3")),
        ("87.500", Decimal("87500")),
    ],
)
def test_both_number_conventions_reach_the_same_value(token, expected):
    assert parse_number(token) == expected


def test_a_page_written_the_other_way_round_still_supports_the_figure():
    """Why the values are canonicalised: 1.234,5 and 1,234.5 are one number."""
    answer = canonical_numbers("gia tri giao dich 1.234,5 ty")
    page = canonical_numbers("turnover of 1,234.5 billion")
    assert answer <= page


def test_years_and_small_counts_are_not_claims_needing_a_source():
    assert not is_claim(Decimal("2026"))
    assert not is_claim(Decimal("3"))
    assert is_claim(Decimal("87500"))
    assert is_claim(Decimal("12.3"))


def test_rounding_counts_as_covered_but_a_different_number_does_not():
    assert covered(Decimal("12.3"), {Decimal("12.34")})
    assert not covered(Decimal("12.3"), {Decimal("15.9")})


# -- distinct_domains ------------------------------------------------------


def test_distinct_domains_passes_when_the_source_list_is_wide_enough():
    report = grade(
        artifact(
            case(
                expect={"min_distinct_domains": 3},
                sources=[
                    {"domain": "vietstock.vn"},
                    {"domain": "cafef.vn"},
                    {"domain": "vneconomy.vn"},
                ],
            )
        )
    )
    result = finding(report, "distinct_domains")
    assert result.value == 3
    assert result.passed is True


def test_distinct_domains_fails_when_three_sources_are_one_domain():
    report = grade(
        artifact(
            case(
                expect={"min_distinct_domains": 3},
                sources=[{"domain": "cafef.vn"}] * 3,
            )
        )
    )
    result = finding(report, "distinct_domains")
    assert result.value == 1
    assert result.passed is False


# -- read_depth ------------------------------------------------------------


def test_read_depth_counts_pages_opened_not_searches_issued():
    report = grade(
        artifact(
            case(
                expect={"min_pages_read": 2},
                tool_calls=[
                    {"name": "web_search", "round": 1},
                    {"name": "fetch_url", "round": 2},
                    {"name": "fetch_url", "round": 2},
                ],
            )
        )
    )
    result = finding(report, "read_depth")
    assert result.value == 2
    assert result.passed is True


def test_read_depth_fails_a_turn_that_only_searched():
    report = grade(
        artifact(
            case(
                expect={"min_pages_read": 2},
                tool_calls=[
                    {"name": "web_search", "round": 1},
                    {"name": "web_search", "round": 1},
                ],
            )
        )
    )
    result = finding(report, "read_depth")
    assert result.value == 0
    assert result.passed is False


# -- parallel_rate ---------------------------------------------------------


def test_parallel_rate_is_measured_per_round_not_per_turn():
    """Two searches across two rounds is sequential, and the rate must say so."""
    sequential = grade(
        artifact(
            case(
                tool_calls=[
                    {"name": "web_search", "round": 1},
                    {"name": "web_search", "round": 2},
                ]
            )
        )
    )
    assert finding(sequential, "parallel_rate").value == 0.0

    parallel = grade(
        artifact(
            case(
                tool_calls=[
                    {"name": "web_search", "round": 1},
                    {"name": "web_search", "round": 1},
                ]
            )
        )
    )
    assert finding(parallel, "parallel_rate").value == 1.0


def test_parallel_rate_has_no_value_when_the_turn_never_searched():
    report = grade(artifact(case(tool_calls=[{"name": "get_field", "round": 1}])))
    result = finding(report, "parallel_rate")
    assert result.value is None
    assert result.passed is None


# -- uncited_external_number ----------------------------------------------


def test_a_figure_the_page_carries_is_cited():
    report = grade(
        artifact(
            case(
                expect={"must_cite_external_numbers": True},
                answer_text="Khoi ngoai ban rong 1.245,7 ty dong trong phien.",
                external_evidence_text="Foreign investors net sold 1,245.7 billion dong.",
            )
        )
    )
    result = finding(report, "uncited_external_number")
    assert result.value == 0
    assert result.passed is True


def test_a_figure_no_page_carries_is_uncited():
    report = grade(
        artifact(
            case(
                expect={"must_cite_external_numbers": True},
                answer_text="Khoi ngoai ban rong 9.999,9 ty dong trong phien.",
                external_evidence_text="Foreign investors net sold 1,245.7 billion dong.",
            )
        )
    )
    result = finding(report, "uncited_external_number")
    assert result.value == 1
    assert result.passed is False


def test_a_figure_the_store_carries_is_cited_too():
    """The definition covers both halves of the evidence, not only the web."""
    report = grade(
        artifact(
            case(
                expect={"must_cite_external_numbers": True},
                answer_text="ADTV 60 phien la 87.500 trieu dong.",
                store_evidence_text='{"field": "adtv_60d", "value": 87500}',
            )
        )
    )
    assert finding(report, "uncited_external_number").passed is True


def test_a_number_the_user_supplied_is_not_charged_to_the_answer():
    report = grade(
        artifact(
            case(
                question="Gia 87.500 co hop ly khong?",
                expect={"must_cite_external_numbers": True},
                answer_text="Muc 87.500 nam trong bien do.",
            )
        )
    )
    assert finding(report, "uncited_external_number").passed is True


# -- run-level honesty -----------------------------------------------------


def test_a_run_that_stopped_at_its_ceiling_is_never_a_pass():
    report = grade(
        artifact(case(), status="incomplete", incomplete_reason="spend ceiling reached")
    )
    assert report.status == "incomplete"
    assert "ceiling" in " ".join(report.notes)


def test_a_short_run_is_incomplete_even_when_every_case_it_ran_is_green():
    report = grade(
        {
            "schema": SCHEMA,
            "run": {"status": "complete", "corpus_cases": 20},
            "cases": [case()],
        }
    )
    assert report.status == "incomplete"


def test_an_artifact_from_another_schema_is_unusable_not_empty():
    report = grade({"schema": "eval.artifact@1", "cases": []})
    assert report.status == "unusable"


def test_every_declared_grader_produces_a_finding_for_every_case():
    report = grade(artifact(case("wf-001"), case("wf-002")))
    produced = {(f.case_id, f.grader) for f in report.findings}
    assert produced == {(cid, g) for cid in ("wf-001", "wf-002") for g in GRADERS}


def test_grading_the_same_artifact_twice_gives_the_same_report(tmp_path):
    path = tmp_path / "artifact.json"
    path.write_text(
        json.dumps(
            artifact(
                case(
                    expect={"min_distinct_domains": 2, "must_cite_external_numbers": True},
                    answer_text="Gia 87.500 dong.",
                    external_evidence_text="87,500 dong",
                    sources=[{"domain": "cafef.vn"}, {"domain": "vietstock.vn"}],
                    tool_calls=[{"name": "web_search", "round": 1}],
                )
            )
        ),
        encoding="utf-8",
    )
    assert grade_file(path).as_dict() == grade_file(path).as_dict()
