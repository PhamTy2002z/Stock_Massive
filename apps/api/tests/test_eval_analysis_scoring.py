"""The three checks only the Analysis lane has, and the prose tripwire on top.

Every one of them re-decides something ``validate_fragment`` already enforced at
production time, and that is the point rather than a duplication
(``docs/adr/0016``): an enforcement proved by the same code that performs it is
not proved. These read the **published artifact** — the row a user would have
been served — and ask the question again from the outside.

*The citation set is checked against the Field Profile, not against the
envelope.* Those are the same list on a healthy build and stop being the same
list the moment the envelope starts carrying something the profile never named,
which is exactly the drift worth catching.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.alpha.field_profile import (
    AnalysisIndustry,
    Axis,
    PRICE_ZONE_FIELD_ID,
    profile_for,
)
from src.alpha.generation import Emphasis, Verdict
from src.eval.artifact import AnalysisArtifact
from src.eval.cases import (
    AnalysisExpectation,
    EvalCase,
    EvalCategory,
    EvalSurface,
    Expectation,
)
from src.eval.roles import FixtureRole
from src.eval.scoring import Check, score_analysis

TRADING_DAY = date(2026, 8, 14)
SYMBOL = "EVB1"

TECHNICAL_ID = profile_for(AnalysisIndustry.BANKS)[Axis.TECHNICAL][0].field_id
# A fundamental only the banks profile names, so citing it under any other
# industry is a citation outside that industry's profile.
BANK_ONLY_ID = profile_for(AnalysisIndustry.BANKS)[Axis.FUNDAMENTAL][-1].field_id
# The News axis has no inputs at all in v1, so every profile carries it refused
# — which makes it the honest stand-in for a gap the artifact has to expose.
REFUSED_ID = profile_for(AnalysisIndustry.BANKS)[Axis.NEWS][0].field_id


def figure(field_id: str, *, health: str = "ok", value: float | None = 1.0) -> dict:
    return {
        "fieldId": field_id,
        "label": field_id,
        "value": None if health == "refused" else value,
        "unit": "percent",
        "kind": "measure",
        "source": "computed",
        "interpretation": "as the registry declares it",
        "health": health,
        "reasonCode": None if health == "ok" else "unavailable",
        "reason": None if health == "ok" else "Chưa có dữ liệu.",
        "asOf": TRADING_DAY.isoformat(),
        "sessionsUsed": 21,
        "windowDays": 21,
        "extras": {},
    }


def evidence(industry: AnalysisIndustry = AnalysisIndustry.BANKS) -> dict:
    profile = profile_for(industry)
    return {
        "schemaVersion": 1,
        "fieldProfileVersion": "v1",
        "symbol": SYMBOL,
        "companyName": "EVB1 Joint Stock Company",
        "exchange": "HOSE",
        "industry": industry.value,
        "tradingDay": TRADING_DAY.isoformat(),
        "priceZone": figure(PRICE_ZONE_FIELD_ID),
        "sections": [
            {
                "axis": axis.value,
                "health": "ok",
                "figures": [
                    figure(
                        entry.field_id,
                        health=("refused" if axis is Axis.NEWS else "ok"),
                    )
                    for entry in profile[axis]
                ],
            }
            for axis in profile
        ],
        "windowHealth": {},
    }


def payload(
    *,
    cited: tuple[str, ...] = (PRICE_ZONE_FIELD_ID, TECHNICAL_ID),
    leads: tuple[Axis, ...] = (Axis.TECHNICAL,),
    verdict_line: str = "Vùng giá thường ngày vẫn hẹp.",
    thesis: str = "Bằng chứng chỉ mô tả trạng thái hiện tại.",
    read: str = "Biến động thực tế nằm trong vùng quen thuộc.",
    industry: AnalysisIndustry = AnalysisIndustry.BANKS,
) -> dict:
    return {
        "audit": {
            "schemaVersion": 1,
            "fieldProfileVersion": "v1",
            "promptVersion": "v1",
            "model": "eval-batch-model",
            "route": "https://eval.example",
            "generatedAt": "2026-08-14T12:00:00+00:00",
            "inputFingerprint": "0" * 64,
        },
        "evidence": evidence(industry),
        "judgment": {
            "verdictLine": verdict_line,
            "thesis": thesis,
            "leadAxis": leads[0].value if leads else "technical",
            "axes": [
                {
                    "axis": axis.value,
                    "emphasis": (
                        Emphasis.LEAD.value
                        if axis in leads
                        else Emphasis.SUPPORT.value
                    ),
                    "emphasisReason": "Đây là trục mang nhiều bằng chứng nhất.",
                    "read": read,
                }
                for axis in profile_for(industry)
            ],
        },
        "citedFieldIds": list(cited),
    }


def artifact(**overrides) -> AnalysisArtifact:
    return AnalysisArtifact.published(
        symbol=SYMBOL,
        trading_day=TRADING_DAY,
        verdict=Verdict.HOLD.value,
        payload=payload(**overrides),
    )


def case(**overrides) -> EvalCase:
    defaults = dict(
        id="analysis-d-bank",
        category=EvalCategory.INTERPRETATION,
        surface=EvalSurface.ANALYSIS,
        prompt="",
        role=FixtureRole.BANK,
        expectation=Expectation(analysis=AnalysisExpectation(publishes=True)),
    )
    defaults.update(overrides)
    return EvalCase(**defaults)


def verdict_of(score, check: Check):
    return next(item for item in score.results if item.check is check)


class TestCitationsAgainstTheFieldProfile:
    def test_a_citation_inside_the_profile_passes(self):
        score = score_analysis(case(), 0, artifact())
        assert verdict_of(score, Check.ANALYSIS_CITED_PROFILE).passed

    def test_a_citation_outside_the_profile_fails_the_case(self):
        """A citation outside the profile is a fabricated id, not a new one."""
        score = score_analysis(
            case(), 0, artifact(cited=(TECHNICAL_ID, "invented.field"))
        )
        result = verdict_of(score, Check.ANALYSIS_CITED_PROFILE)
        assert not result.passed
        assert "invented.field" in result.detail
        assert not score.passed

    def test_the_profile_is_the_one_the_industry_selects(self):
        """A bank fundamental is out of profile for a retailer, and vice versa.

        The check resolves the profile from the artifact's own industry rather
        than from the envelope's list of ids: the two agree on a healthy build,
        and the day the envelope starts carrying a field the profile never
        named, only this direction of the comparison notices.
        """
        score = score_analysis(
            case(),
            0,
            artifact(industry=AnalysisIndustry.RETAIL, cited=(BANK_ONLY_ID,)),
        )
        assert not verdict_of(score, Check.ANALYSIS_CITED_PROFILE).passed

    def test_the_price_zone_is_citable_without_consuming_an_axis_slot(self):
        score = score_analysis(case(), 0, artifact(cited=(PRICE_ZONE_FIELD_ID,)))
        assert verdict_of(score, Check.ANALYSIS_CITED_PROFILE).passed


class TestRefusedFieldsNeverSupportTheVerdict:
    def test_a_refused_field_in_the_citation_set_fails_the_case(self):
        score = score_analysis(
            case(), 0, artifact(cited=(TECHNICAL_ID, REFUSED_ID))
        )
        result = verdict_of(score, Check.ANALYSIS_REFUSED_FIELD)
        assert not result.passed
        assert REFUSED_ID in result.detail

    def test_a_refused_field_may_stay_in_the_artifact_uncited(self):
        """That is its whole role: evidence of what the system could not see."""
        score = score_analysis(case(), 0, artifact())
        assert verdict_of(score, Check.ANALYSIS_REFUSED_FIELD).passed
        assert any(
            item["health"] == "refused"
            for section in artifact().evidence["sections"]
            for item in section["figures"]
        )


class TestExactlyOneLeadAxis:
    def test_one_lead_passes(self):
        assert verdict_of(
            score_analysis(case(), 0, artifact()), Check.ANALYSIS_LEAD_AXIS
        ).passed

    def test_no_lead_fails_because_the_emphasis_decision_was_skipped(self):
        score = score_analysis(case(), 0, artifact(leads=()))
        assert not verdict_of(score, Check.ANALYSIS_LEAD_AXIS).passed

    def test_two_leads_fail_because_the_template_stopped_being_one(self):
        score = score_analysis(
            case(), 0, artifact(leads=(Axis.TECHNICAL, Axis.MONEY_FLOW))
        )
        assert not verdict_of(score, Check.ANALYSIS_LEAD_AXIS).passed

    def test_the_lifted_lead_axis_has_to_name_the_axis_that_carries_it(self):
        broken = payload()
        broken["judgment"]["leadAxis"] = Axis.NEWS.value
        score = score_analysis(
            case(),
            0,
            AnalysisArtifact.published(
                symbol=SYMBOL,
                trading_day=TRADING_DAY,
                verdict=Verdict.HOLD.value,
                payload=broken,
            ),
        )
        assert not verdict_of(score, Check.ANALYSIS_LEAD_AXIS).passed


class TestTheBackwardsSignHardFailAppliesToAnalysisProse:
    def test_a_forward_looking_sentence_over_descriptive_fields_fails(self):
        score = score_analysis(
            case(), 0, artifact(thesis="Giá sẽ tăng trong các phiên tới.")
        )
        result = verdict_of(score, Check.DIRECTION_LEXICON)
        assert not result.passed
        assert "sẽ tăng" in result.detail

    def test_every_axis_read_is_scanned_and_not_only_the_thesis(self):
        score = score_analysis(case(), 0, artifact(read="Nên mua quanh vùng này."))
        assert not verdict_of(score, Check.DIRECTION_LEXICON).passed

    def test_naming_what_it_will_not_do_is_the_contract_working(self):
        score = score_analysis(
            case(),
            0,
            artifact(thesis="Bằng chứng mô tả không cho phép nói giá sẽ tăng."),
        )
        assert verdict_of(score, Check.DIRECTION_LEXICON).passed


class TestWhatTheCaseExpectedOfTheRun:
    def test_a_case_expecting_an_artifact_fails_when_production_failed(self):
        failed = AnalysisArtifact.unpublished(
            symbol=SYMBOL,
            trading_day=TRADING_DAY,
            error_code="insufficient_core_evidence",
            error_message="Không đọc được vùng giá thường ngày.",
        )
        score = score_analysis(case(), 0, failed)
        assert not verdict_of(score, Check.ANALYSIS_OUTCOME).passed
        assert not score.passed

    def test_a_data_gap_case_expects_the_named_failure_and_no_artifact(self):
        gap = case(
            id="analysis-e-short",
            category=EvalCategory.DATA_GAP,
            role=FixtureRole.BELOW_MIN_SESSIONS,
            expectation=Expectation(
                analysis=AnalysisExpectation(
                    publishes=False, failure_code="insufficient_core_evidence"
                )
            ),
        )
        failed = AnalysisArtifact.unpublished(
            symbol=SYMBOL,
            trading_day=TRADING_DAY,
            error_code="insufficient_core_evidence",
            error_message="Không đọc được vùng giá thường ngày.",
        )
        score = score_analysis(gap, 0, failed)
        assert score.passed

    def test_the_wrong_failure_code_is_still_a_failure(self):
        gap = case(
            expectation=Expectation(
                analysis=AnalysisExpectation(
                    publishes=False, failure_code="insufficient_core_evidence"
                )
            )
        )
        wrong = AnalysisArtifact.unpublished(
            symbol=SYMBOL,
            trading_day=TRADING_DAY,
            error_code="llm_transport_error",
            error_message="Tuyến LLM không trả lời được.",
        )
        assert not score_analysis(gap, 0, wrong).passed

    def test_a_gap_the_case_names_has_to_be_visible_in_the_artifact(self):
        """Exposed, not filled: the refusal reaches the artifact with a reason."""
        exposing = case(
            category=EvalCategory.DATA_GAP,
            expectation=Expectation(
                analysis=AnalysisExpectation(
                    publishes=True, exposes_refused=(REFUSED_ID,)
                )
            ),
        )
        assert score_analysis(exposing, 0, artifact()).passed

        healthy = payload()
        for section in healthy["evidence"]["sections"]:
            for item in section["figures"]:
                item["health"] = "ok"
                item["reasonCode"] = None
        filled = AnalysisArtifact.published(
            symbol=SYMBOL,
            trading_day=TRADING_DAY,
            verdict=Verdict.HOLD.value,
            payload=healthy,
        )
        assert not score_analysis(exposing, 0, filled).passed

    def test_checks_that_need_an_artifact_are_inapplicable_without_one(self):
        """Not passes. A battery of failed runs must not score a clean sheet."""
        gap = case(
            expectation=Expectation(
                analysis=AnalysisExpectation(
                    publishes=False, failure_code="insufficient_core_evidence"
                )
            )
        )
        score = score_analysis(
            gap,
            0,
            AnalysisArtifact.unpublished(
                symbol=SYMBOL,
                trading_day=TRADING_DAY,
                error_code="insufficient_core_evidence",
                error_message="Không đọc được vùng giá.",
            ),
        )
        for check in (
            Check.ANALYSIS_CITED_PROFILE,
            Check.ANALYSIS_REFUSED_FIELD,
            Check.ANALYSIS_LEAD_AXIS,
        ):
            assert verdict_of(score, check).applicable is False


class TestTheProseTheRubricReads:
    def test_the_verbatim_answer_is_every_model_owned_sentence(self):
        one = artifact()
        assert one.prose.count("Đây là trục mang nhiều bằng chứng nhất.") == len(
            one.axes
        )
        assert "Vùng giá thường ngày vẫn hẹp." in one.prose
        assert "Bằng chứng chỉ mô tả trạng thái hiện tại." in one.prose

    def test_a_failed_run_has_the_named_reason_where_the_prose_would_be(self):
        failed = AnalysisArtifact.unpublished(
            symbol=SYMBOL,
            trading_day=TRADING_DAY,
            error_code="insufficient_core_evidence",
            error_message="Không đọc được vùng giá thường ngày.",
        )
        assert "insufficient_core_evidence" in failed.prose


@pytest.mark.parametrize("industry", list(AnalysisIndustry))
def test_every_industry_profile_admits_its_own_price_zone_citation(industry):
    """The price zone travels beside the axes and is citable in every profile."""
    score = score_analysis(
        case(),
        0,
        artifact(industry=industry, cited=(PRICE_ZONE_FIELD_ID,)),
    )
    assert verdict_of(score, Check.ANALYSIS_CITED_PROFILE).passed
