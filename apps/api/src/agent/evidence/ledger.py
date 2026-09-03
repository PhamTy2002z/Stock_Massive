"""Fail-closed claim-ledger validation and ledger-only memo rendering."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urlsplit

from . import numbers
from .contracts import (
    ClaimKind,
    ClaimLedger,
    EvidenceKind,
    EvidenceRef,
    PublicationConfidence,
    PublicationMethod,
    SourceClass,
    TimePrecision,
    VerificationVerdict,
    VerifiedClaim,
    VerifierOutcome,
)
from .source_policy import (
    PublicationStamp,
    canonical_url,
    is_temporally_admissible,
)

_PRIMARY_CLASSES = frozenset(
    {
        SourceClass.REGULATOR,
        SourceClass.EXCHANGE,
        SourceClass.ISSUER,
        SourceClass.PRIMARY_DOCUMENT,
        SourceClass.USER_DOCUMENT,
    }
)
_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+")


@dataclass(frozen=True)
class LedgerClaimAssessment:
    claim_id: str
    proposed_verdict: VerificationVerdict
    accepted_verdict: VerificationVerdict
    unknown_evidence_ids: tuple[str, ...]
    temporally_invalid_evidence_ids: tuple[str, ...]
    numeric_failures: tuple[str, ...]
    errors: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "claimId": self.claim_id,
            "proposedVerdict": self.proposed_verdict.value,
            "acceptedVerdict": self.accepted_verdict.value,
            "unknownEvidenceIds": list(self.unknown_evidence_ids),
            "temporallyInvalidEvidenceIds": list(
                self.temporally_invalid_evidence_ids
            ),
            "numericFailures": list(self.numeric_failures),
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class ClaimLedgerValidationReport:
    ledger: ClaimLedger
    claims: tuple[LedgerClaimAssessment, ...]
    duplicate_evidence_ids: tuple[str, ...]
    duplicate_claim_ids: tuple[str, ...]
    invalid_evidence_ids: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not (
            self.duplicate_evidence_ids
            or self.duplicate_claim_ids
            or self.invalid_evidence_ids
            or any(item.errors for item in self.claims)
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "ledger": self.ledger.to_payload(),
            "claims": [item.to_payload() for item in self.claims],
            "duplicateEvidenceIds": list(self.duplicate_evidence_ids),
            "duplicateClaimIds": list(self.duplicate_claim_ids),
            "invalidEvidenceIds": list(self.invalid_evidence_ids),
        }


def _duplicates(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in values:
        if value in seen:
            repeated.add(value)
        seen.add(value)
    return tuple(sorted(repeated))


def _evidence_identity_error(evidence: EvidenceRef) -> str | None:
    if evidence.excerpt_sha256 is None:
        return "missing_exact_excerpt_hash"
    if evidence.kind is not EvidenceKind.WEB_PAGE:
        return None
    target = evidence.canonical_url
    if not target:
        return "missing_canonical_url"
    try:
        if canonical_url(target) != target:
            return "noncanonical_url"
    except ValueError:
        return "invalid_canonical_url"
    return None


def _temporal_valid(evidence: EvidenceRef, ledger: ClaimLedger, *, material: bool) -> bool:
    if evidence.observed_at is not None and evidence.observed_at > ledger.as_of:
        return False
    if evidence.effective_at is not None and evidence.effective_at > ledger.as_of:
        return False
    if evidence.published_at is None:
        # Unknown may help explain a non-material scenario, but cannot carry a
        # material fact whose historical knowability is part of the contract.
        return not material
    return is_temporally_admissible(
        PublicationStamp(
            published_at=evidence.published_at,
            method=evidence.publication_method,
            confidence=evidence.publication_confidence,
            precision=evidence.publication_precision,
        ),
        ledger.as_of,
    )


def _publisher_identity(evidence: EvidenceRef) -> str:
    if evidence.publisher:
        return evidence.publisher.casefold().strip()
    target = evidence.canonical_url or evidence.source
    return (urlsplit(target).hostname or target).casefold().strip()


def _numbers_supported(claim: VerifiedClaim, evidence: tuple[EvidenceRef, ...]) -> tuple[str, ...]:
    failures: list[str] = []
    for occurrence in numbers.occurrences(claim.text):
        target = occurrence.scaled if occurrence.scaled is not None else occurrence.written
        if any(
            numbers.contains(item.excerpt, target, claim.unit) is numbers.Verdict.MATCHED
            for item in evidence
        ):
            continue
        failures.append(str(target))
    return tuple(failures)


def _accepted_verdict(
    claim: VerifiedClaim,
    support: tuple[EvidenceRef, ...],
    contradict: tuple[EvidenceRef, ...],
    *,
    temporal_failure: bool,
    numeric_failure: bool,
    structural_failure: bool,
) -> VerificationVerdict:
    if structural_failure or numeric_failure:
        return VerificationVerdict.UNSUPPORTED
    if not support:
        return (
            VerificationVerdict.TEMPORALLY_INVALID
            if temporal_failure
            else VerificationVerdict.UNSUPPORTED
        )
    if contradict:
        return VerificationVerdict.CONFLICTING
    if not claim.material:
        return VerificationVerdict.VERIFIED
    if any(item.source_class in _PRIMARY_CLASSES for item in support):
        return VerificationVerdict.VERIFIED
    publishers = {_publisher_identity(item) for item in support}
    return (
        VerificationVerdict.VERIFIED
        if len(publishers) >= 2
        else VerificationVerdict.SINGLE_SOURCE
    )


def validate_claim_ledger(ledger: ClaimLedger) -> ClaimLedgerValidationReport:
    """Recompute every verdict from evidence; model labels carry no authority."""

    duplicate_evidence = _duplicates(tuple(item.evidence_id for item in ledger.evidence))
    duplicate_claims = _duplicates(tuple(item.claim_id for item in ledger.claims))
    evidence_by_id = {item.evidence_id: item for item in ledger.evidence}
    invalid_evidence = tuple(
        sorted(
            item.evidence_id
            for item in ledger.evidence
            if _evidence_identity_error(item) is not None
        )
    )
    safe_claims: list[VerifiedClaim] = []
    assessments: list[LedgerClaimAssessment] = []

    for claim in ledger.claims:
        named_ids = claim.supporting_evidence_ids + claim.contradicting_evidence_ids
        unknown = tuple(sorted({item for item in named_ids if item not in evidence_by_id}))
        support_candidates = tuple(
            evidence_by_id[item]
            for item in claim.supporting_evidence_ids
            if item in evidence_by_id and item not in invalid_evidence
        )
        contradict_candidates = tuple(
            evidence_by_id[item]
            for item in claim.contradicting_evidence_ids
            if item in evidence_by_id and item not in invalid_evidence
        )
        temporal_ids = tuple(
            item.evidence_id
            for item in support_candidates + contradict_candidates
            if not _temporal_valid(item, ledger, material=claim.material)
        )
        support = tuple(
            item for item in support_candidates if item.evidence_id not in temporal_ids
        )
        contradict = tuple(
            item for item in contradict_candidates if item.evidence_id not in temporal_ids
        )
        numeric_failures = (
            _numbers_supported(claim, support)
            if claim.material and claim.kind is ClaimKind.FACT and support
            else ()
        )
        errors: list[str] = []
        if unknown:
            errors.append("unknown_evidence_id")
        if any(item in invalid_evidence for item in named_ids):
            errors.append("invalid_evidence_identity")
        if _URL_RE.search(claim.text):
            errors.append("claim_contains_unledgered_url")
        if numeric_failures:
            errors.append("material_number_absent_from_excerpt")
        accepted = _accepted_verdict(
            claim,
            support,
            contradict,
            temporal_failure=bool(temporal_ids),
            numeric_failure=bool(numeric_failures),
            structural_failure=bool(errors and errors != ["material_number_absent_from_excerpt"]),
        )
        if accepted is not claim.verdict:
            errors.append("verdict_not_supported_by_policy")
        safe_claims.append(
            replace(
                claim,
                verdict=accepted,
                supporting_evidence_ids=tuple(item.evidence_id for item in support),
                contradicting_evidence_ids=tuple(item.evidence_id for item in contradict),
            )
        )
        assessments.append(
            LedgerClaimAssessment(
                claim_id=claim.claim_id,
                proposed_verdict=claim.verdict,
                accepted_verdict=accepted,
                unknown_evidence_ids=unknown,
                temporally_invalid_evidence_ids=temporal_ids,
                numeric_failures=numeric_failures,
                errors=tuple(dict.fromkeys(errors)),
            )
        )

    safe_outcome = (
        VerifierOutcome.VERIFIED
        if safe_claims
        and all(
            item.verdict
            in {
                VerificationVerdict.VERIFIED,
                VerificationVerdict.SINGLE_SOURCE,
                VerificationVerdict.CONFLICTING,
            }
            for item in safe_claims
        )
        else VerifierOutcome.INSUFFICIENT_EVIDENCE
    )
    safe_ledger = replace(
        ledger,
        claims=tuple(safe_claims),
        verifier_outcome=safe_outcome,
    )
    return ClaimLedgerValidationReport(
        ledger=safe_ledger,
        claims=tuple(assessments),
        duplicate_evidence_ids=duplicate_evidence,
        duplicate_claim_ids=duplicate_claims,
        invalid_evidence_ids=invalid_evidence,
    )


def _clean_text(value: str) -> str:
    without_urls = _URL_RE.sub("[URL omitted]", value)
    return re.sub(r"\s+", " ", without_urls).strip().replace("[", "\\[").replace("]", "\\]")


def render_claim_ledger(ledger: ClaimLedger) -> str:
    """Render only checked ledger values; no model-authored URL is accepted."""

    evidence_by_id = {item.evidence_id: item for item in ledger.evidence}
    cited_ids: list[str] = []

    def cite(ids: tuple[str, ...]) -> str:
        numbers_out: list[str] = []
        for evidence_id in ids:
            if evidence_id not in evidence_by_id:
                continue
            if evidence_id not in cited_ids:
                cited_ids.append(evidence_id)
            numbers_out.append(f"[{cited_ids.index(evidence_id) + 1}]")
        return "".join(numbers_out)

    lines = [
        f"**Trạng thái kiểm chứng:** `{ledger.verifier_outcome.value}`",
        f"**As of:** {ledger.as_of.isoformat()}",
        "",
        "### Kết luận theo bằng chứng",
    ]
    rendered = 0
    for claim in ledger.claims:
        if claim.verdict is VerificationVerdict.UNSUPPORTED:
            continue
        status = {
            VerificationVerdict.VERIFIED: "Đã kiểm chứng",
            VerificationVerdict.SINGLE_SOURCE: "Một nguồn",
            VerificationVerdict.CONFLICTING: "Nguồn mâu thuẫn",
            VerificationVerdict.TEMPORALLY_INVALID: "Sai mốc thời gian",
            VerificationVerdict.UNSUPPORTED: "Chưa kiểm chứng",
        }[claim.verdict]
        references = claim.supporting_evidence_ids + claim.contradicting_evidence_ids
        lines.append(f"- **{status}:** {_clean_text(claim.text)} {cite(references)}".rstrip())
        rendered += 1
    if not rendered:
        lines.append("- Chưa có tuyên bố nào đủ điều kiện để hiển thị là đã kiểm chứng.")

    unsupported = [item for item in ledger.claims if item.verdict is VerificationVerdict.UNSUPPORTED]
    if unsupported:
        lines.extend(("", "### Chưa kiểm chứng"))
        lines.extend(f"- {_clean_text(item.text)}" for item in unsupported)

    lines.extend(("", "### Điều gì có thể làm luận điểm sai"))
    invalidations = [
        item.invalidation_text
        for item in ledger.claims
        if item.invalidation_text and item.invalidation_text.strip()
    ]
    if invalidations:
        lines.extend(f"- {_clean_text(item)}" for item in invalidations)
    else:
        lines.append("- Chưa xác định được điều kiện vô hiệu hóa từ bằng chứng hiện có.")

    if ledger.assumptions:
        lines.extend(("", "### Giả định"))
        lines.extend(f"- {_clean_text(item)}" for item in ledger.assumptions)
    if ledger.gaps:
        lines.extend(("", "### Khoảng trống bằng chứng"))
        lines.extend(f"- {_clean_text(item)}" for item in ledger.gaps)

    if cited_ids:
        lines.extend(("", "### Nguồn"))
        for index, evidence_id in enumerate(cited_ids, start=1):
            item = evidence_by_id[evidence_id]
            target = canonical_url(item.canonical_url or item.source)
            publisher = _clean_text(item.publisher or urlsplit(target).hostname or "Nguồn")
            title = _clean_text(item.title)
            published = item.published_at.isoformat() if item.published_at else "không rõ ngày công bố"
            lines.append(f"[{index}] {publisher} — {title} — {published} — <{target}>")
    return "\n".join(lines).strip()


__all__ = [
    "ClaimLedgerValidationReport",
    "LedgerClaimAssessment",
    "render_claim_ledger",
    "validate_claim_ledger",
]
