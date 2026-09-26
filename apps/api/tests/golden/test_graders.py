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


def test_budget_holds_a_deep_turn_to_the_deep_ceiling_not_the_light_one():
    """A deep Turn reading widely is the lane working, not the lane breaching.

    Measured on the first Phase 6 deep case: 19 dispatched external calls, which
    is inside the deep lane's cap of 20 and well over the light lane's 7. Graded
    against one flat pair it failed a *hard* dimension for doing exactly what it
    was configured to do.
    """
    from src.agent.lanes import DEEP, LIGHT

    from golden.graders import grade_budget

    limits = {
        "MAX_TOOL_ROUNDS": LIGHT.max_tool_rounds,
        "MAX_EXTERNAL_TOOL_CALLS": LIGHT.max_external_calls,
        "lanes": {
            lane.name: {
                "max_tool_rounds": lane.max_tool_rounds,
                "max_external_calls": lane.max_external_calls,
                "deadline_seconds": lane.deadline_seconds,
            }
            for lane in (LIGHT, DEEP)
        },
    }
    # The two lanes share ceilings in this build, so the light one is narrowed
    # here: the grader's subject is which lane's cap it reads, not the values.
    limits["lanes"]["light"]["max_external_calls"] = DEEP.max_external_calls - 5
    calls = [
        {"kind": "external", "round": index % DEEP.max_tool_rounds, "status": "ok",
         "result_chars": 100}
        for index in range(DEEP.max_external_calls - 3)
    ]
    deep_case = {
        "id": "deep", "trial": 1,
        "question": "Kiểm chứng luận điểm mua HPG giúp tôi",
        "tool_calls": calls, "cost": {"micro_usd": 1000},
    }
    light_case = {**deep_case, "id": "light", "question": "VN-Index bao nhiêu điểm?"}

    assert grade_budget(deep_case, {}, {"runtime_constants": limits}).passed
    # The same call count on a light question is still a breach, and the message
    # names which lane's ceiling it broke.
    light = grade_budget(light_case, {}, {"runtime_constants": limits})
    assert not light.passed
    assert "light" in light.detail


def test_budget_falls_back_to_the_flat_pair_for_an_artifact_without_lanes():
    """An artifact recorded before lanes were written down still grades."""
    from golden.graders import grade_budget

    limits = {"MAX_TOOL_ROUNDS": 4, "MAX_EXTERNAL_TOOL_CALLS": 7}
    case = {
        "id": "old", "trial": 1, "question": "VN-Index bao nhiêu điểm?",
        "tool_calls": [
            {"kind": "external", "round": 0, "status": "ok", "result_chars": 10}
        ],
        "cost": {"micro_usd": 500},
    }

    assert grade_budget(case, {}, {"runtime_constants": limits}).passed


# -- the three the visual mode adds ----------------------------------------

import json as _json  # noqa: E402 - the visual fixtures are JSON the runtime wrote

from golden.graders import (  # noqa: E402
    grade_mode_isolation,
    grade_visual_grounding,
    grade_visual_replay,
)
from src.agent.evidence.pipeline import evidence_from_calls  # noqa: E402
from src.agent.messages import ToolCallStatus, TurnToolCall  # noqa: E402
from src.agent.visual import build_visual  # noqa: E402

MARKET_RESULT = {
    "symbol": "FPT",
    "interval": "1D",
    "provider": "vnstock",
    "provider_version": "3.2.0",
    "source": "kbs",
    "publisher": "KB Securities",
    "source_class": "store",
    "currency": "VND",
    "price_unit": "VND",
    "price_scale_applied": 1000,
    "timezone": "Asia/Ho_Chi_Minh",
    "requested": {"start": "2026-08-24", "end": "2026-08-25"},
    "actual": {"start": "2026-08-24T15:00:00+07:00", "end": "2026-08-25T15:00:00+07:00"},
    "row_count": 2,
    "rows_dropped_after_horizon": 0,
    "truncated": False,
    "quality": "ok",
    "retrieved_at": "2026-09-04T17:00:00+07:00",
    "content_sha256": "d" * 64,
    "rows": [
        {
            "bar_opened_at": "2026-08-24T07:00:00+07:00",
            "bar_closed_at": "2026-08-24T15:00:00+07:00",
            "open": 72_500, "high": 72_700, "low": 71_400, "close": 71_400,
            "volume": 4_611_900,
        },
        {
            "bar_opened_at": "2026-08-25T07:00:00+07:00",
            "bar_closed_at": "2026-08-25T15:00:00+07:00",
            "open": 71_400, "high": 72_000, "low": 71_000, "close": 71_900,
            "volume": 3_100_200,
        },
    ],
    "excerpt": (
        "FPT · nến 1D · nguồn KB Securities qua vnstock\n"
        "2026-08-24T15:00:00+07:00: đóng 71.400 đồng · khối lượng 4.611.900 cổ phiếu"
    ),
}


def _market_call() -> TurnToolCall:
    return TurnToolCall(
        id="call-m1",
        name="get_market_data",
        status=ToolCallStatus.OK,
        result_text=_json.dumps(MARKET_RESULT, ensure_ascii=False),
    )


def _ledger_payload():
    """A validated ledger over that one market read, as the store holds it."""
    from datetime import datetime, timezone

    from src.agent.evidence.contracts import (
        ClaimKind, ClaimLedger, VerificationVerdict, VerifiedClaim, VerifierOutcome,
    )
    from src.agent.evidence.pipeline import LEDGER_VERSION
    from src.agent.evidence.source_policy import POLICY_VERSION

    evidence = evidence_from_calls([_market_call()])
    ledger = ClaimLedger(
        version=LEDGER_VERSION,
        policy_version=POLICY_VERSION,
        as_of=datetime(2026, 9, 4, 17, 0, tzinfo=timezone.utc),
        evidence=evidence,
        claims=(
            VerifiedClaim(
                claim_id="c1",
                text="FPT đóng cửa ở 71.400 đồng.",
                kind=ClaimKind.FACT,
                material=True,
                verdict=VerificationVerdict.SINGLE_SOURCE,
                supporting_evidence_ids=(evidence[0].evidence_id,),
            ),
        ),
        gaps=(),
        assumptions=("Không phải khuyến nghị cá nhân hóa.",),
        verifier_outcome=VerifierOutcome.VERIFIED,
    )
    return ledger, ledger.to_payload()


def desk_case(**overrides):
    """One settled Signal Desk Turn, exactly as the runner records it."""
    ledger, payload = _ledger_payload()
    call = _market_call()
    visual = build_visual(calls=[call], ledger=ledger, as_of=ledger.as_of)
    assert visual is not None
    body = case(
        turn_mode="signal_desk",
        lane="deep",
        claim_ledger=payload,
        visual=visual,
        tool_calls=[
            {
                "id": call.id,
                "name": call.name,
                "round": 1,
                "kind": "store",
                "status": "ok",
                "arguments": {"symbol": "FPT"},
                "result_text": call.result_text,
            }
        ],
    )
    body.update(overrides)
    return body


def test_a_chart_whose_every_value_was_read_is_grounded():
    finding = grade_visual_grounding(desk_case(), CORPUS, RUN)

    assert finding.passed is True


def test_a_single_edited_price_fails_grounding():
    """The assertion the whole dimension exists for, stated as a mutation."""
    body = desk_case()
    body["visual"]["assemblies"][0]["data"]["values"][0]["close"] = 99_999

    finding = grade_visual_grounding(body, CORPUS, RUN)

    assert finding.passed is False
    assert "99999" in finding.detail.replace(",", "")


def test_an_evidence_id_the_ledger_does_not_hold_fails_grounding():
    body = desk_case()
    body["visual"]["evidenceIds"] = ["ev_invented"]

    finding = grade_visual_grounding(body, CORPUS, RUN)

    assert finding.passed is False
    assert "ev_invented" in finding.detail


def test_a_chart_naming_a_call_this_trial_never_made_fails_grounding():
    body = desk_case()
    body["visual"]["sourceCallIds"] = ["call-elsewhere"]

    finding = grade_visual_grounding(body, CORPUS, RUN)

    assert finding.passed is False


def test_a_case_that_owes_a_chart_and_has_none_fails_rather_than_abstains():
    body = desk_case(visual=None, expect={"must_draw_chart": True})

    assert grade_visual_grounding(body, CORPUS, RUN).passed is False


def test_a_case_that_must_not_draw_one_fails_when_it_does():
    body = desk_case(expect={"must_not_draw_chart": True})

    assert grade_visual_grounding(body, CORPUS, RUN).passed is False


def test_a_turn_with_no_chart_is_undecided_rather_than_a_free_pass():
    assert grade_visual_grounding(case(), CORPUS, RUN).passed is None


def test_the_stored_chart_replays_from_the_same_calls():
    finding = grade_visual_replay(desk_case(), CORPUS, RUN)

    assert finding.passed is True


def test_a_chart_edited_after_assembly_fails_replay():
    """The failure grounding cannot see: real figures, wrong chart."""
    body = desk_case()
    # Both rows are genuinely read values, so grounding still passes; what has
    # changed is that these are not the rows the assembler produces.
    body["visual"]["assemblies"][0]["data"]["values"].reverse()

    assert grade_visual_grounding(body, CORPUS, RUN).passed is True
    assert grade_visual_replay(body, CORPUS, RUN).passed is False


def test_replay_is_undecided_when_there_is_no_chart():
    assert grade_visual_replay(case(), CORPUS, RUN).passed is None


def test_a_chat_turn_with_no_market_call_and_no_chart_is_isolated():
    assert grade_mode_isolation(case(turn_mode="chat"), CORPUS, RUN).passed is True


def test_a_market_call_on_a_chat_turn_is_the_boundary_moving():
    body = case(
        turn_mode="chat",
        tool_calls=[{"id": "call-m1", "name": "get_market_data", "round": 1, "kind": "store"}],
    )

    finding = grade_mode_isolation(body, CORPUS, RUN)

    assert finding.passed is False
    assert "market call" in finding.detail


def test_a_chart_on_a_chat_turn_is_the_boundary_moving():
    body = desk_case(turn_mode="chat", tool_calls=[])

    assert grade_mode_isolation(body, CORPUS, RUN).passed is False


def test_a_signal_desk_turn_is_permitted_both():
    assert grade_mode_isolation(desk_case(), CORPUS, RUN).passed is True


def test_a_signal_desk_turn_is_measured_against_the_deep_lane():
    """A ceiling read off the wording would fail a deep Turn for doing its job."""
    limits = {
        "runtime_constants": {
            "lanes": {
                "light": {"max_tool_rounds": 3, "max_external_calls": 7},
                "deep": {"max_tool_rounds": 10, "max_external_calls": 20},
            }
        }
    }
    body = desk_case(
        lane="deep",
        tool_calls=[
            {"id": f"c{i}", "name": "web_search", "round": i, "kind": "external",
             "status": "ok", "result_chars": 10}
            for i in range(1, 9)
        ],
    )

    assert grade_budget(body, CORPUS, limits).passed is True
