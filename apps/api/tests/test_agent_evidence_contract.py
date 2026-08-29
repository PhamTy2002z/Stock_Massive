"""The answer/evidence contract stays deterministic and UI-addressable."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from src.agent.evidence import (
    ClaimLink,
    ClaimRef,
    ClaimStatus,
    EvidenceKind,
    EvidenceLocation,
    EvidenceRelation,
    SourceClass,
    build_evidence_ref,
    validate_claims,
)


def _evidence(source: str, excerpt: str):
    digest = hashlib.sha256(excerpt.encode()).hexdigest()
    return build_evidence_ref(
        kind=EvidenceKind.WEB_PAGE,
        source_class=SourceClass.EXCHANGE,
        title=f"Nguồn {source}",
        source=source,
        excerpt=excerpt,
        content_sha256=digest,
        location=EvidenceLocation(section="Market data"),
        observed_at=datetime(2026, 8, 29, tzinfo=UTC),
    )


def _claim(answer: str, text: str, *links: ClaimLink, claim_id: str = "cl_1"):
    start = answer.index(text)
    return ClaimRef(
        claim_id=claim_id,
        text=text,
        start=start,
        end=start + len(text),
        links=tuple(links),
    )


def test_supported_numeric_claim_has_stable_serializable_provenance():
    answer = "FPT tăng 12,5% trong năm 2026."
    evidence = _evidence("https://example.test/fpt", "FPT 2026 +12.5%")
    claim = _claim(
        answer,
        answer,
        ClaimLink(evidence.evidence_id, EvidenceRelation.SUPPORTS),
    )

    report = validate_claims(
        answer=answer, evidence=(evidence,), claims=(claim,)
    )

    assert report.valid is True
    assert report.claims[0].status is ClaimStatus.SUPPORTED
    assert report.uncovered_numeric_spans == ()
    payload = evidence.to_payload()
    assert payload["sourceClass"] == "exchange"
    assert payload["location"] == {"section": "Market data"}
    assert payload["observedAt"] == "2026-08-29T00:00:00+00:00"
    assert evidence.evidence_id == _evidence(
        "https://example.test/fpt", "FPT 2026 +12.5%"
    ).evidence_id


def test_validator_surfaces_conflict_without_choosing_a_winner():
    answer = "Doanh thu là 100 tỷ đồng."
    issuer = _evidence("issuer", "Doanh thu: 100 tỷ đồng")
    media = _evidence("media", "Doanh thu điều chỉnh: 95 tỷ đồng")
    claim = _claim(
        answer,
        answer,
        ClaimLink(issuer.evidence_id, EvidenceRelation.SUPPORTS),
        ClaimLink(media.evidence_id, EvidenceRelation.CONTRADICTS),
    )

    report = validate_claims(
        answer=answer, evidence=(issuer, media), claims=(claim,)
    )

    assert report.valid is False
    assert report.claims[0].status is ClaimStatus.CONFLICTING
    assert report.claims[0].support_count == 1
    assert report.claims[0].contradiction_count == 1


def test_unknown_reference_and_wrong_answer_span_are_unsupported():
    answer = "P/E hiện tại là 8,2 lần."
    evidence = _evidence("store", "P/E: 8.2")
    claim = ClaimRef(
        claim_id="cl_wrong",
        text="P/E hiện tại là 8,2 lần.",
        start=1,
        end=1 + len("P/E hiện tại là 8,2 lần."),
        links=(ClaimLink("ev_missing", EvidenceRelation.SUPPORTS),),
    )

    report = validate_claims(
        answer=answer, evidence=(evidence,), claims=(claim,)
    )

    assert report.claims[0].status is ClaimStatus.UNSUPPORTED
    assert report.claims[0].span_matches is False
    assert report.claims[0].unknown_evidence_ids == ("ev_missing",)


def test_unclaimed_numbers_are_reported_but_numbered_list_markers_are_not():
    answer = "1. Biên lợi nhuận đạt 18%.\n2. ROE chưa được công bố."

    report = validate_claims(answer=answer, evidence=(), claims=())

    assert [(span.text, span.start) for span in report.uncovered_numeric_spans] == [
        ("18%", answer.index("18%"))
    ]


def test_duplicate_ids_are_contract_failures_even_when_claim_is_supported():
    answer = "Giá đóng cửa là 120.000đ."
    evidence = _evidence("store", "close=120000")
    claim = _claim(
        answer,
        answer,
        ClaimLink(evidence.evidence_id, EvidenceRelation.SUPPORTS),
    )

    report = validate_claims(
        answer=answer,
        evidence=(evidence, evidence),
        claims=(claim, claim),
    )

    assert report.valid is False
    assert report.duplicate_evidence_ids == (evidence.evidence_id,)
    assert report.duplicate_claim_ids == (claim.claim_id,)


def test_contract_rejects_ambiguous_locations_and_naive_times():
    with pytest.raises(ValueError, match="both a page and a sheet"):
        EvidenceLocation(page=1, sheet="Sheet1")

    with pytest.raises(ValueError, match="timezone"):
        build_evidence_ref(
            kind=EvidenceKind.WEB_PAGE,
            source_class=SourceClass.UNKNOWN,
            title="Example",
            source="example",
            excerpt="text",
            content_sha256=hashlib.sha256(b"text").hexdigest(),
            observed_at=datetime(2026, 8, 29),
        )
