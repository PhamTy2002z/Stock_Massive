"""Evidence contracts, validation, and bounded document extraction."""

from .contracts import (
    ClaimLink,
    ClaimRef,
    EvidenceKind,
    EvidenceLocation,
    EvidenceRef,
    EvidenceRelation,
    SourceClass,
    build_evidence_ref,
)
from .validation import (
    ClaimAssessment,
    ClaimStatus,
    EvidenceValidationReport,
    TextSpan,
    validate_claims,
)

__all__ = (
    "ClaimAssessment",
    "ClaimLink",
    "ClaimRef",
    "ClaimStatus",
    "EvidenceKind",
    "EvidenceLocation",
    "EvidenceRef",
    "EvidenceRelation",
    "EvidenceValidationReport",
    "SourceClass",
    "TextSpan",
    "build_evidence_ref",
    "validate_claims",
)
