"""Mechanical ledger validation and URL-safe memo rendering."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from src.agent.evidence import (
    ClaimKind,
    ClaimLedger,
    EvidenceKind,
    PublicationConfidence,
    PublicationMethod,
    SourceClass,
    TimePrecision,
    VerificationVerdict,
    VerifiedClaim,
    VerifierOutcome,
    build_evidence_ref,
    render_claim_ledger,
    validate_claim_ledger,
)
from src.agent.evidence.source_policy import POLICY_VERSION

AS_OF = datetime.fromisoformat("2026-08-21T15:00:00+07:00")


def evidence(
    key: str,
    excerpt: str,
    *,
    source_class: SourceClass = SourceClass.MEDIA,
    publisher: str | None = None,
    published_at: datetime | None = None,
):
    url = f"https://{key}.example/article"
    return build_evidence_ref(
        kind=EvidenceKind.WEB_PAGE,
        source_class=source_class,
        title=f"Source {key}",
        source=url,
        canonical_url=url,
        publisher=publisher or key,
        excerpt=excerpt,
        content_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
        observed_at=datetime.fromisoformat("2026-08-21T08:00:00+07:00"),
        published_at=published_at or datetime.fromisoformat("2026-08-20T09:00:00+07:00"),
        publication_method=PublicationMethod.HTML_META,
        publication_confidence=PublicationConfidence.HIGH,
        publication_precision=TimePrecision.INSTANT,
    )


def claim(
    *support,
    text: str = "Lợi nhuận đạt 1.245 tỷ đồng.",
    verdict: VerificationVerdict = VerificationVerdict.VERIFIED,
    contradict=(),
    material: bool = True,
):
    return VerifiedClaim(
        claim_id="claim_1",
        text=text,
        kind=ClaimKind.FACT,
        material=material,
        verdict=verdict,
        supporting_evidence_ids=tuple(item.evidence_id for item in support),
        contradicting_evidence_ids=tuple(item.evidence_id for item in contradict),
        invalidation_text="Luận điểm sai nếu lợi nhuận bị điều chỉnh giảm.",
        unit="tỷ đồng",
        currency="VND",
    )


def ledger(*evidence_items, claims):
    return ClaimLedger(
        version="1",
        policy_version=POLICY_VERSION,
        as_of=AS_OF,
        evidence=tuple(evidence_items),
        claims=tuple(claims),
        gaps=(),
        assumptions=("Không phải khuyến nghị cá nhân hóa.",),
        verifier_outcome=VerifierOutcome.VERIFIED,
    )


def test_one_primary_source_can_verify_a_material_number():
    primary = evidence(
        "issuer",
        "Lợi nhuận đạt 1.245 tỷ đồng.",
        source_class=SourceClass.ISSUER,
    )

    report = validate_claim_ledger(ledger(primary, claims=(claim(primary),)))

    assert report.valid is True
    assert report.ledger.claims[0].verdict is VerificationVerdict.VERIFIED


def test_one_media_publisher_is_downgraded_to_single_source():
    media = evidence("media", "Lợi nhuận đạt 1.245 tỷ đồng.")

    report = validate_claim_ledger(ledger(media, claims=(claim(media),)))

    assert report.valid is False
    assert report.claims[0].accepted_verdict is VerificationVerdict.SINGLE_SOURCE
    assert "verdict_not_supported_by_policy" in report.claims[0].errors


def test_two_independent_media_publishers_can_verify():
    first = evidence("first", "Lợi nhuận đạt 1.245 tỷ đồng.", publisher="First News")
    second = evidence("second", "Doanh nghiệp báo lãi 1.245 tỷ đồng.", publisher="Second News")

    report = validate_claim_ledger(ledger(first, second, claims=(claim(first, second),)))

    assert report.valid is True
    assert report.ledger.claims[0].verdict is VerificationVerdict.VERIFIED


def test_two_urls_from_the_same_publisher_are_still_one_source():
    first = evidence("first", "Lợi nhuận đạt 1.245 tỷ đồng.", publisher="Same News")
    second = evidence("second", "Doanh nghiệp báo lãi 1.245 tỷ đồng.", publisher="Same News")

    report = validate_claim_ledger(ledger(first, second, claims=(claim(first, second),)))

    assert report.ledger.claims[0].verdict is VerificationVerdict.SINGLE_SOURCE


def test_material_number_absent_from_every_excerpt_fails_closed():
    source = evidence("issuer", "Lợi nhuận đạt 1.200 tỷ đồng.", source_class=SourceClass.ISSUER)

    report = validate_claim_ledger(ledger(source, claims=(claim(source),)))

    assert report.valid is False
    assert report.claims[0].numeric_failures
    assert report.ledger.claims[0].verdict is VerificationVerdict.UNSUPPORTED


def test_unknown_evidence_id_never_becomes_verified():
    source = evidence("issuer", "Lợi nhuận đạt 1.245 tỷ đồng.", source_class=SourceClass.ISSUER)
    proposed = replace(claim(source), supporting_evidence_ids=("ev_unknown",))

    report = validate_claim_ledger(ledger(source, claims=(proposed,)))

    assert report.claims[0].unknown_evidence_ids == ("ev_unknown",)
    assert report.ledger.claims[0].verdict is VerificationVerdict.UNSUPPORTED


def test_evidence_published_after_as_of_is_temporally_invalid():
    future = evidence(
        "issuer",
        "Lợi nhuận đạt 1.245 tỷ đồng.",
        source_class=SourceClass.ISSUER,
        published_at=datetime.fromisoformat("2026-08-22T09:00:00+07:00"),
    )
    proposed = claim(future, verdict=VerificationVerdict.TEMPORALLY_INVALID)

    report = validate_claim_ledger(ledger(future, claims=(proposed,)))

    assert report.claims[0].temporally_invalid_evidence_ids == (future.evidence_id,)
    assert report.ledger.claims[0].verdict is VerificationVerdict.TEMPORALLY_INVALID


def test_conflict_is_disclosed_without_choosing_a_winner():
    supporting = evidence("issuer", "Lợi nhuận đạt 1.245 tỷ đồng.", source_class=SourceClass.ISSUER)
    opposing = evidence("audit", "Lợi nhuận điều chỉnh còn 1.100 tỷ đồng.")
    proposed = claim(
        supporting,
        contradict=(opposing,),
        verdict=VerificationVerdict.CONFLICTING,
    )

    report = validate_claim_ledger(ledger(supporting, opposing, claims=(proposed,)))
    memo = render_claim_ledger(report.ledger)

    assert report.ledger.claims[0].verdict is VerificationVerdict.CONFLICTING
    assert "Nguồn mâu thuẫn" in memo
    assert supporting.canonical_url in memo and opposing.canonical_url in memo


def test_renderer_drops_unsupported_citations_and_omits_every_unledgered_url():
    source = evidence("issuer", "Lợi nhuận đạt 1.245 tỷ đồng.", source_class=SourceClass.ISSUER)
    unsafe = claim(
        source,
        text="Xem https://evil.example/fake để biết lợi nhuận 9.999 tỷ đồng.",
        verdict=VerificationVerdict.VERIFIED,
    )
    candidate = replace(
        ledger(source, claims=(unsafe,)),
        gaps=("Chi tiết ở https://gap.example",),
    )

    report = validate_claim_ledger(candidate)
    memo = render_claim_ledger(report.ledger)

    assert report.ledger.claims[0].verdict is VerificationVerdict.UNSUPPORTED
    assert "https://evil.example" not in memo
    assert "https://gap.example" not in memo
    assert source.canonical_url not in memo


def test_exact_excerpt_hash_cannot_disagree_with_the_quote():
    source = evidence("issuer", "Lợi nhuận đạt 1.245 tỷ đồng.")

    with pytest.raises(ValueError, match="exact excerpt"):
        replace(source, excerpt_sha256="0" * 64)
