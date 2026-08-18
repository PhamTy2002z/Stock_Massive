"""The Evidence Manifest, the Risk Notice, and answer_kind (#83)."""

from __future__ import annotations

import pytest

from src.agent.grounding import Citation, EvidenceSource
from src.agent.manifest import (
    ALL_RISK_MEANINGS,
    CANONICAL_RISK_NOTICE,
    MANIFEST_SCHEMA_VERSION,
    RISK_NOTICE_VERSION,
    GateOutcome,
    RiskMeaning,
    RiskNotice,
    assemble_message,
    assert_discloses_nothing,
    build_manifest,
    risk_notice,
    sources_and_methods,
)
from src.agent.prompt import PROMPT_HASH, PROMPT_VERSION, AnswerKind, prefix

FIELD = Citation(
    call_id="c1",
    tool_name="indicator_pack",
    field_path="registered_fields.indicator_pack.rsi_14.value",
    value=61.2,
    unit="index_0_100",
    interpretation="Chỉ số sức mạnh tương đối.",
    claim="descriptive",
    provenance="indicator_pack:indicator_pack.rsi_14",
    as_of="2026-08-14",
    stale=False,
    source=EvidenceSource.REGISTERED_FIELD,
    window_health={"refusal": None, "last_session": "2026-08-14"},
)
NEWS = Citation(
    call_id="c3",
    tool_name="search_news",
    field_path="items.0.untrusted_evidence.title",
    value="FPT báo lãi",
    unit=None,
    interpretation=None,
    claim=None,
    provenance="CafeF",
    as_of="2026-08-13T09:00:00+00:00",
    stale=False,
    source=EvidenceSource.SOURCE_CLAIM,
    contradictory=True,
)


def manifest(**overrides):
    arguments = {
        "git_sha": "9f2c1ab",
        "model": "gpt-5.6-terra",
        "route": "https://route.example",
        "provider_request_id": "req_123",
        "tool_catalog_version": "abc123",
        "answer_kind": AnswerKind.ANALYSIS,
        "status": "complete",
        "terminal_reason": None,
        "citations": (FIELD, NEWS),
    }
    arguments.update(overrides)
    return build_manifest(**arguments)


# --- the Manifest ----------------------------------------------------------


def test_the_manifest_carries_every_field_a_dispute_needs():
    wire = manifest().as_wire()

    assert wire["schema_version"] == MANIFEST_SCHEMA_VERSION
    assert wire["prompt_version"] == PROMPT_VERSION
    assert wire["prompt_hash"] == PROMPT_HASH
    assert wire["git_sha"] == "9f2c1ab"
    assert wire["model"] == "gpt-5.6-terra"
    assert wire["route"] == "https://route.example"
    assert wire["provider_request_id"] == "req_123"
    assert wire["tool_catalog_version"] == "abc123"
    assert wire["mcp_servers_version"] == "disabled"
    assert wire["registry_version"]
    assert wire["risk_notice_version"] == RISK_NOTICE_VERSION
    assert wire["answer_kind"] == "analysis"
    assert wire["status"] == "complete"
    assert wire["terminal_reason"] is None
    assert wire["outcomes"]["grounding"] == "passed"


def test_the_cited_fields_survive_the_deletion_of_the_traces_behind_them():
    """The Manifest copies the resolved figure, so day 91 changes nothing."""
    cited = manifest().as_wire()["cited_fields"]

    assert cited[0]["value"] == 61.2
    assert cited[0]["unit"] == "index_0_100"
    assert cited[0]["as_of"] == "2026-08-14"
    assert cited[0]["provenance"] == "indicator_pack:indicator_pack.rsi_14"


def test_the_manifest_is_immutable_after_it_is_built():
    built = manifest()

    with pytest.raises(Exception):
        built.git_sha = "tampered"  # type: ignore[misc]


def test_the_manifest_carries_no_prompt_text_and_no_credential():
    built = manifest()

    assert_discloses_nothing(built, prefix(), "super-secret-api-key")

    with pytest.raises(AssertionError):
        assert_discloses_nothing(built, "gpt-5.6-terra")


def test_a_blocked_recommendation_is_recorded_as_an_outcome():
    built = manifest(
        status="incomplete",
        terminal_reason="grounding_failed",
        outcomes=GateOutcome(
            grounding="blocked",
            recommendation="blocked",
            failure_code="window_health_refusal",
        ),
    )

    assert built.as_wire()["outcomes"] == {
        "scope": "in_scope",
        "grounding": "blocked",
        "recommendation": "blocked",
        "failure_code": "window_health_refusal",
    }


# --- the Risk Notice -------------------------------------------------------


def test_the_canonical_notice_is_versioned_and_retains_all_four_meanings():
    notice = risk_notice()

    assert notice.version == RISK_NOTICE_VERSION
    assert notice.text == CANONICAL_RISK_NOTICE
    assert notice.meanings == ALL_RISK_MEANINGS
    assert "không phải tư vấn đầu tư cá nhân" in notice.text
    assert "cam kết lợi nhuận" in notice.text
    assert "tự chịu trách nhiệm" in notice.text


def test_a_translation_that_drops_a_meaning_is_refused():
    with pytest.raises(ValueError) as raised:
        RiskNotice(
            version=RISK_NOTICE_VERSION,
            locale="en",
            text="For analysis only. Not personal advice. No promised outcome.",
            meanings=ALL_RISK_MEANINGS - {RiskMeaning.LIMITED_DATA_USER_RESPONSIBLE},
        )

    assert "limited_data_user_responsible" in str(raised.value)


def test_a_translation_retaining_all_four_is_accepted():
    notice = RiskNotice(
        version=RISK_NOTICE_VERSION,
        locale="en",
        text=(
            "This is analysis and reference material, not personal investment "
            "advice or a promise of returns. Data may be delayed, missing or "
            "revised; decisions remain yours."
        ),
    )

    assert notice.meanings == ALL_RISK_MEANINGS


# --- what rides on the message --------------------------------------------


def test_every_assembled_message_carries_the_notice_and_the_manifest():
    message = assemble_message(
        blocks=[{"text": "Kết luận."}],
        text="Kết luận.",
        answer_kind=AnswerKind.ANALYSIS,
        manifest=manifest(),
        citations=(FIELD, NEWS),
    )

    assert message["risk_notice"]["version"] == RISK_NOTICE_VERSION
    assert message["evidence_manifest"]["prompt_hash"] == PROMPT_HASH
    assert message["answer_kind"] == "analysis"
    assert message["sources_and_methods"]


def test_a_usefully_incomplete_message_carries_them_too():
    message = assemble_message(
        blocks=[{"text": "Một phần."}],
        text="Một phần.",
        answer_kind=AnswerKind.ANALYSIS,
        manifest=manifest(status="incomplete", terminal_reason="turn_deadline"),
    )

    assert message["risk_notice"]["text"] == CANONICAL_RISK_NOTICE
    assert message["evidence_manifest"]["terminal_reason"] == "turn_deadline"


def test_sources_and_methods_is_built_from_resolved_citations_only():
    surface = sources_and_methods((FIELD, NEWS))

    assert surface[0]["provider_source"] == "indicator_pack:indicator_pack.rsi_14"
    assert surface[0]["tool_call_id"] == "c1"
    assert surface[0]["registered_field"].endswith("rsi_14.value")
    assert surface[0]["freshness"] == {"as_of": "2026-08-14", "stale": False}
    assert surface[0]["window_health"] == {
        "refusal": None,
        "last_session": "2026-08-14",
    }
    # News is carried as a claim class, never as a registered field.
    assert surface[1]["registered_field"] is None
    assert surface[1]["claim_class"] == "source_claim"
    assert surface[1]["contradictory"] is True
