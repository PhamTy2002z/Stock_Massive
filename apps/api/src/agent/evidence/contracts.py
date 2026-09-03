"""Stable contracts connecting answer claims to their supporting evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class EvidenceKind(str, Enum):
    """The smallest source unit that can be cited without losing provenance."""

    WEB_PAGE = "web_page"
    DOCUMENT_PAGE = "document_page"
    DOCUMENT_CELL_RANGE = "document_cell_range"
    DOCUMENT_SECTION = "document_section"
    STORE_FIGURE = "store_figure"
    CALCULATION = "calculation"


class SourceClass(str, Enum):
    """Source identity, kept separate from whether a claim is supported."""

    STORE = "store"
    REGULATOR = "regulator"
    EXCHANGE = "exchange"
    ISSUER = "issuer"
    PRIMARY_DOCUMENT = "primary_document"
    MEDIA = "media"
    AGGREGATOR = "aggregator"
    USER_DOCUMENT = "user_document"
    UNKNOWN = "unknown"


class TosRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class PublicationMethod(str, Enum):
    PROVIDER = "provider"
    HTML_META = "html_meta"
    JSON_LD = "json_ld"
    VISIBLE_TEXT = "visible_text"
    URL_PATTERN = "url_pattern"
    UNKNOWN = "unknown"


class PublicationConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class TimePrecision(str, Enum):
    INSTANT = "instant"
    DATE = "date"
    UNKNOWN = "unknown"


class EvidenceRelation(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"


@dataclass(frozen=True)
class EvidenceLocation:
    """A precise location inside one source.

    PDF pages are one-indexed. Spreadsheet ranges use A1 notation and always
    name their sheet. DOCX has no stable page model, so it uses a section and a
    one-indexed block number instead of pretending pagination is intrinsic.
    """

    page: int | None = None
    sheet: str | None = None
    cell_range: str | None = None
    section: str | None = None
    block: int | None = None

    def __post_init__(self) -> None:
        if self.page is not None and self.page < 1:
            raise ValueError("page must be one-indexed")
        if self.block is not None and self.block < 1:
            raise ValueError("block must be one-indexed")
        if self.cell_range is not None and not self.sheet:
            raise ValueError("a cell range must name its sheet")
        if self.cell_range is not None and not self.cell_range.strip():
            raise ValueError("cell_range cannot be blank")
        if self.page is not None and self.sheet is not None:
            raise ValueError("a location cannot be both a page and a sheet")
        if self.page is not None and self.block is not None:
            raise ValueError("a page location cannot also be a document block")
        for name, value in (("sheet", self.sheet), ("section", self.section)):
            if value is not None and not value.strip():
                raise ValueError(f"{name} cannot be blank")

    def to_payload(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "page": self.page,
                "sheet": self.sheet,
                "cellRange": self.cell_range,
                "section": self.section,
                "block": self.block,
            }.items()
            if value is not None
        }


def _require_aware(name: str, value: datetime | None) -> None:
    if value is not None and value.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")


@dataclass(frozen=True)
class EvidenceRef:
    """One immutable, displayable source excerpt."""

    evidence_id: str
    kind: EvidenceKind
    source_class: SourceClass
    title: str
    source: str
    excerpt: str
    content_sha256: str
    location: EvidenceLocation | None = None
    observed_at: datetime | None = None
    as_of: datetime | None = None
    canonical_url: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    effective_at: datetime | None = None
    publication_method: PublicationMethod = PublicationMethod.UNKNOWN
    publication_confidence: PublicationConfidence = PublicationConfidence.UNKNOWN
    publication_precision: TimePrecision = TimePrecision.UNKNOWN
    tos_risk: TosRisk = TosRisk.UNKNOWN
    excerpt_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_id or len(self.evidence_id) > 128:
            raise ValueError("evidence_id must contain 1..128 characters")
        if not self.title.strip():
            raise ValueError("evidence title cannot be blank")
        if not self.source.strip():
            raise ValueError("evidence source cannot be blank")
        if not self.excerpt.strip():
            raise ValueError("evidence excerpt cannot be blank")
        if len(self.content_sha256) != 64:
            raise ValueError("content_sha256 must be a SHA-256 hex digest")
        try:
            int(self.content_sha256, 16)
        except ValueError as exc:
            raise ValueError("content_sha256 must be a SHA-256 hex digest") from exc
        _require_aware("observed_at", self.observed_at)
        _require_aware("as_of", self.as_of)
        _require_aware("published_at", self.published_at)
        _require_aware("effective_at", self.effective_at)
        if self.canonical_url is not None and not self.canonical_url.strip():
            raise ValueError("canonical_url cannot be blank")
        if self.publisher is not None and not self.publisher.strip():
            raise ValueError("publisher cannot be blank")
        if self.excerpt_sha256 is not None:
            expected = hashlib.sha256(self.excerpt.encode("utf-8")).hexdigest()
            if self.excerpt_sha256 != expected:
                raise ValueError("excerpt_sha256 must identify the exact excerpt")

    def to_payload(self) -> dict[str, Any]:
        return {
            "evidenceId": self.evidence_id,
            "kind": self.kind.value,
            "sourceClass": self.source_class.value,
            "title": self.title,
            "source": self.source,
            "excerpt": self.excerpt,
            "contentSha256": self.content_sha256,
            "location": self.location.to_payload() if self.location else None,
            "observedAt": self.observed_at.isoformat() if self.observed_at else None,
            "asOf": self.as_of.isoformat() if self.as_of else None,
            "canonicalUrl": self.canonical_url,
            "publisher": self.publisher,
            "publishedAt": self.published_at.isoformat() if self.published_at else None,
            "effectiveAt": self.effective_at.isoformat() if self.effective_at else None,
            "publicationMethod": self.publication_method.value,
            "publicationConfidence": self.publication_confidence.value,
            "publicationPrecision": self.publication_precision.value,
            "tosRisk": self.tos_risk.value,
            "excerptSha256": self.excerpt_sha256,
        }


def build_evidence_ref(
    *,
    kind: EvidenceKind,
    source_class: SourceClass,
    title: str,
    source: str,
    excerpt: str,
    content_sha256: str,
    location: EvidenceLocation | None = None,
    observed_at: datetime | None = None,
    as_of: datetime | None = None,
    canonical_url: str | None = None,
    publisher: str | None = None,
    published_at: datetime | None = None,
    effective_at: datetime | None = None,
    publication_method: PublicationMethod = PublicationMethod.UNKNOWN,
    publication_confidence: PublicationConfidence = PublicationConfidence.UNKNOWN,
    publication_precision: TimePrecision = TimePrecision.UNKNOWN,
    tos_risk: TosRisk = TosRisk.UNKNOWN,
) -> EvidenceRef:
    """Build a stable ID from source content and its exact locator."""

    identity = json.dumps(
        {
            "contentSha256": content_sha256,
            "kind": kind.value,
            "location": location.to_payload() if location else None,
            "source": canonical_url or source,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    evidence_id = "ev_" + hashlib.sha256(identity).hexdigest()[:24]
    return EvidenceRef(
        evidence_id=evidence_id,
        kind=kind,
        source_class=source_class,
        title=title,
        source=source,
        excerpt=excerpt,
        content_sha256=content_sha256,
        location=location,
        observed_at=observed_at,
        as_of=as_of,
        canonical_url=canonical_url,
        publisher=publisher,
        published_at=published_at,
        effective_at=effective_at,
        publication_method=publication_method,
        publication_confidence=publication_confidence,
        publication_precision=publication_precision,
        tos_risk=tos_risk,
        excerpt_sha256=hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
    )


class ClaimKind(str, Enum):
    FACT = "fact"
    INFERENCE = "inference"
    SCENARIO = "scenario"


class VerificationVerdict(str, Enum):
    VERIFIED = "verified"
    SINGLE_SOURCE = "single_source"
    CONFLICTING = "conflicting"
    UNSUPPORTED = "unsupported"
    TEMPORALLY_INVALID = "temporally_invalid"


class VerifierOutcome(str, Enum):
    VERIFIED = "verified"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    VERIFIER_FAILED = "verifier_failed"
    BUDGET_EXHAUSTED = "budget_exhausted"


@dataclass(frozen=True)
class DraftClaim:
    claim_id: str
    text: str
    kind: ClaimKind
    material: bool
    candidate_evidence_ids: tuple[str, ...]
    unit: str | None = None
    currency: str | None = None

    def __post_init__(self) -> None:
        if not self.claim_id or len(self.claim_id) > 128:
            raise ValueError("claim_id must contain 1..128 characters")
        if not self.text.strip():
            raise ValueError("claim text cannot be blank")
        if len(set(self.candidate_evidence_ids)) != len(self.candidate_evidence_ids):
            raise ValueError("candidate evidence IDs cannot contain duplicates")

    def to_payload(self) -> dict[str, Any]:
        return {
            "claimId": self.claim_id,
            "text": self.text,
            "kind": self.kind.value,
            "material": self.material,
            "candidateEvidenceIds": list(self.candidate_evidence_ids),
            "unit": self.unit,
            "currency": self.currency,
        }


@dataclass(frozen=True)
class VerifiedClaim:
    claim_id: str
    text: str
    kind: ClaimKind
    material: bool
    verdict: VerificationVerdict
    supporting_evidence_ids: tuple[str, ...]
    contradicting_evidence_ids: tuple[str, ...] = ()
    invalidation_text: str | None = None
    unit: str | None = None
    currency: str | None = None

    def __post_init__(self) -> None:
        if not self.claim_id or len(self.claim_id) > 128:
            raise ValueError("claim_id must contain 1..128 characters")
        if not self.text.strip():
            raise ValueError("claim text cannot be blank")
        combined = self.supporting_evidence_ids + self.contradicting_evidence_ids
        if len(set(combined)) != len(combined):
            raise ValueError("claim evidence IDs cannot contain duplicates")
        if self.invalidation_text is not None and not self.invalidation_text.strip():
            raise ValueError("invalidation_text cannot be blank")

    def to_payload(self) -> dict[str, Any]:
        return {
            "claimId": self.claim_id,
            "text": self.text,
            "kind": self.kind.value,
            "material": self.material,
            "verdict": self.verdict.value,
            "supportingEvidenceIds": list(self.supporting_evidence_ids),
            "contradictingEvidenceIds": list(self.contradicting_evidence_ids),
            "invalidationText": self.invalidation_text,
            "unit": self.unit,
            "currency": self.currency,
        }


@dataclass(frozen=True)
class ClaimLedger:
    version: str
    policy_version: str
    as_of: datetime
    evidence: tuple[EvidenceRef, ...]
    claims: tuple[VerifiedClaim, ...]
    gaps: tuple[str, ...]
    assumptions: tuple[str, ...]
    verifier_outcome: VerifierOutcome

    def __post_init__(self) -> None:
        if not self.version.strip() or not self.policy_version.strip():
            raise ValueError("ledger versions cannot be blank")
        _require_aware("as_of", self.as_of)
        if any(not item.strip() for item in self.gaps + self.assumptions):
            raise ValueError("ledger gaps and assumptions cannot be blank")

    def to_payload(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "policyVersion": self.policy_version,
            "asOf": self.as_of.isoformat(),
            "evidence": [item.to_payload() for item in self.evidence],
            "claims": [item.to_payload() for item in self.claims],
            "gaps": list(self.gaps),
            "assumptions": list(self.assumptions),
            "verifierOutcome": self.verifier_outcome.value,
        }


@dataclass(frozen=True)
class ClaimLink:
    evidence_id: str
    relation: EvidenceRelation

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise ValueError("a claim link must name evidence")

    def to_payload(self) -> dict[str, str]:
        return {
            "evidenceId": self.evidence_id,
            "relation": self.relation.value,
        }


@dataclass(frozen=True)
class ClaimRef:
    """A verbatim answer span and the evidence relationships asserted for it."""

    claim_id: str
    text: str
    start: int
    end: int
    links: tuple[ClaimLink, ...]

    def __post_init__(self) -> None:
        if not self.claim_id or len(self.claim_id) > 128:
            raise ValueError("claim_id must contain 1..128 characters")
        if not self.text:
            raise ValueError("claim text cannot be blank")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("claim range must be a non-empty half-open range")
        if self.end - self.start != len(self.text):
            raise ValueError("claim range length must equal claim text length")
        pairs = {(link.evidence_id, link.relation) for link in self.links}
        if len(pairs) != len(self.links):
            raise ValueError("claim links cannot contain duplicates")

    def to_payload(self) -> dict[str, Any]:
        return {
            "claimId": self.claim_id,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "links": [link.to_payload() for link in self.links],
        }
