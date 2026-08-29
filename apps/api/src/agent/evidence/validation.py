"""Deterministic validation for answer claims and evidence relationships."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .contracts import ClaimRef, EvidenceRef, EvidenceRelation


class ClaimStatus(str, Enum):
    SUPPORTED = "supported"
    CONFLICTING = "conflicting"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class TextSpan:
    text: str
    start: int
    end: int

    def to_payload(self) -> dict[str, Any]:
        return {"text": self.text, "start": self.start, "end": self.end}


@dataclass(frozen=True)
class ClaimAssessment:
    claim_id: str
    status: ClaimStatus
    span_matches: bool
    support_count: int
    contradiction_count: int
    unknown_evidence_ids: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "claimId": self.claim_id,
            "status": self.status.value,
            "spanMatches": self.span_matches,
            "supportCount": self.support_count,
            "contradictionCount": self.contradiction_count,
            "unknownEvidenceIds": list(self.unknown_evidence_ids),
        }


@dataclass(frozen=True)
class EvidenceValidationReport:
    claims: tuple[ClaimAssessment, ...]
    uncovered_numeric_spans: tuple[TextSpan, ...]
    duplicate_evidence_ids: tuple[str, ...]
    duplicate_claim_ids: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return (
            not self.uncovered_numeric_spans
            and not self.duplicate_evidence_ids
            and not self.duplicate_claim_ids
            and all(claim.status is ClaimStatus.SUPPORTED for claim in self.claims)
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "claims": [claim.to_payload() for claim in self.claims],
            "uncoveredNumericSpans": [
                span.to_payload() for span in self.uncovered_numeric_spans
            ],
            "duplicateEvidenceIds": list(self.duplicate_evidence_ids),
            "duplicateClaimIds": list(self.duplicate_claim_ids),
        }


_NUMBER_RE = re.compile(
    r"(?<![\w])(?:\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)"
    r"(?:\s?(?:%|đ|VND|USD|tỷ|triệu|nghìn|điểm|cổ phiếu))?(?![\w])",
    flags=re.IGNORECASE,
)


def _duplicates(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in values:
        if value in seen:
            repeated.add(value)
        seen.add(value)
    return tuple(sorted(repeated))


def _is_list_marker(answer: str, match: re.Match[str]) -> bool:
    line_start = answer.rfind("\n", 0, match.start()) + 1
    before = answer[line_start : match.start()]
    after = answer[match.end() :]
    return not before.strip() and bool(re.match(r"[.)]\s", after))


def _numeric_spans(answer: str) -> tuple[TextSpan, ...]:
    return tuple(
        TextSpan(match.group(0), match.start(), match.end())
        for match in _NUMBER_RE.finditer(answer)
        if not _is_list_marker(answer, match)
    )


def validate_claims(
    *,
    answer: str,
    evidence: tuple[EvidenceRef, ...],
    claims: tuple[ClaimRef, ...],
    require_numeric_coverage: bool = True,
) -> EvidenceValidationReport:
    """Assess support, conflicts, references, and numeric claim coverage.

    The validator never decides which source is true. A claim with both known
    supporting and contradicting evidence is surfaced as ``conflicting`` so the
    answer layer can disclose the disagreement instead of silently ranking it.
    """

    evidence_ids = [item.evidence_id for item in evidence]
    evidence_by_id = {item.evidence_id: item for item in evidence}
    duplicate_evidence_ids = _duplicates(evidence_ids)
    duplicate_claim_ids = _duplicates([claim.claim_id for claim in claims])
    assessments: list[ClaimAssessment] = []

    for claim in claims:
        span_matches = (
            claim.end <= len(answer) and answer[claim.start : claim.end] == claim.text
        )
        unknown = tuple(
            sorted(
                {
                    link.evidence_id
                    for link in claim.links
                    if link.evidence_id not in evidence_by_id
                }
            )
        )
        known_links = [
            link for link in claim.links if link.evidence_id in evidence_by_id
        ]
        support_count = sum(
            link.relation is EvidenceRelation.SUPPORTS for link in known_links
        )
        contradiction_count = sum(
            link.relation is EvidenceRelation.CONTRADICTS for link in known_links
        )

        if not span_matches or unknown or support_count == 0:
            status = ClaimStatus.UNSUPPORTED
        elif contradiction_count:
            status = ClaimStatus.CONFLICTING
        else:
            status = ClaimStatus.SUPPORTED
        assessments.append(
            ClaimAssessment(
                claim_id=claim.claim_id,
                status=status,
                span_matches=span_matches,
                support_count=support_count,
                contradiction_count=contradiction_count,
                unknown_evidence_ids=unknown,
            )
        )

    covered_ranges = tuple((claim.start, claim.end) for claim in claims)
    uncovered = (
        tuple(
            span
            for span in _numeric_spans(answer)
            if not any(
                start <= span.start and span.end <= end
                for start, end in covered_ranges
            )
        )
        if require_numeric_coverage
        else ()
    )
    return EvidenceValidationReport(
        claims=tuple(assessments),
        uncovered_numeric_spans=uncovered,
        duplicate_evidence_ids=duplicate_evidence_ids,
        duplicate_claim_ids=duplicate_claim_ids,
    )
