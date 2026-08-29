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
) -> EvidenceRef:
    """Build a stable ID from source content and its exact locator."""

    identity = json.dumps(
        {
            "contentSha256": content_sha256,
            "kind": kind.value,
            "location": location.to_payload() if location else None,
            "source": source,
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
    )


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
