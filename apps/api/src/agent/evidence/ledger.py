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

#: Calendar dates, in the forms a Vietnamese sentence writes them.
#:
#: Removed from a claim before its figures are checked, because a date is not a
#: measured quantity and the numeric rule only makes sense about quantities. The
#: rule asks whether every number a claim states is printed in the evidence it
#: cites, in that claim's unit — and "đóng cửa 71.500 đồng ngày 04/08" states one
#: figure, not three. Read literally, the 4 and the 8 were numbers no source
#: prints a currency beside, so the whole claim was refused: every dated fact in
#: an answer fell into the unverified list and only the vague sentences survived.
#: When a date is wrong it is wrong about *time*, which is what ``_temporal_valid``
#: and the evidence's own ``published_at`` already decide.
#:
#: The cost is a bare ratio written as a fraction — "tỷ lệ 3/4" — losing its two
#: numbers. Prices, volumes and percentages are not written that way here, and
#: the alternative is the failure above.
_DATE_RE = re.compile(
    r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"  # 04/08 and 04/08/2026
    r"|\b\d{1,2}/\d{4}\b"  # 08/2026
    r"|\b\d{4}-\d{2}-\d{2}\b"  # 2026-08-04
)


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
    for occurrence in numbers.occurrences(_DATE_RE.sub(" ", claim.text)):
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


def _public_locator(source: str) -> str | None:
    """The evidence's address, when it has one a reader can open.

    Not every source is a page. A market read has no URL at all — its locator is
    the provider request that produced the rows, which is a connector slug and
    belongs in the trace rather than in the citation a reader is shown. So a
    locator that is not an http(s) address renders as no locator: the publisher,
    the title and the bar close already say what was read and when it became
    knowable.

    ``None`` rather than a raise, which is the whole fix. Canonicalising
    unconditionally meant that any store-class evidence reaching the source list
    threw inside the verification pass and cost the reader the entire answer,
    chart and prose alike, for the sake of a link that never existed.
    """
    try:
        return canonical_url(source)
    except ValueError:
        return None


#: The sections the findings are grouped into, in the order a reader needs
#: them: what stands, what rests on one feed, what the sources disagree about,
#: what could not be placed in time, and what did not survive the check at all.
#: One set per language the memo may be written in — the model composes the
#: claims this renders in the language of the user's question, so the memo
#: around them follows (owner decision, 2026-09-27).
_VERDICT_SECTIONS = {
    "vi": {
        VerificationVerdict.VERIFIED: "Kết luận theo bằng chứng",
        VerificationVerdict.SINGLE_SOURCE: "Mới có một nguồn",
        VerificationVerdict.CONFLICTING: "Nguồn mâu thuẫn",
        VerificationVerdict.TEMPORALLY_INVALID: "Sai mốc thời gian",
        VerificationVerdict.UNSUPPORTED: "Chưa kiểm chứng",
    },
    "en": {
        VerificationVerdict.VERIFIED: "Conclusions backed by evidence",
        VerificationVerdict.SINGLE_SOURCE: "Only one source",
        VerificationVerdict.CONFLICTING: "Sources conflict",
        VerificationVerdict.TEMPORALLY_INVALID: "Wrong time frame",
        VerificationVerdict.UNSUPPORTED: "Unverified",
    },
}

#: The outcome of the verification pass, in the language the answer is written
#: in. The enum value is the harness's own name for the state and means nothing
#: to the person reading the answer — and a reader who has to decode the first
#: line of a memo reads the rest of it as machinery too.
_OUTCOME_LABELS = {
    "vi": {
        VerifierOutcome.VERIFIED: "đã kiểm chứng",
        VerifierOutcome.INSUFFICIENT_EVIDENCE: "chưa đủ bằng chứng",
        VerifierOutcome.VERIFIER_FAILED: "không kiểm chứng được",
        VerifierOutcome.BUDGET_EXHAUSTED: "dừng vì hết ngân sách",
    },
    "en": {
        VerifierOutcome.VERIFIED: "verified",
        VerifierOutcome.INSUFFICIENT_EVIDENCE: "insufficient evidence",
        VerifierOutcome.VERIFIER_FAILED: "verification failed",
        VerifierOutcome.BUDGET_EXHAUSTED: "stopped: budget exhausted",
    },
}

#: Every other fixed heading and phrase this memo writes, one set per language.
_STRINGS = {
    "vi": {
        "no_claims_heading": "Kết luận theo bằng chứng",
        "no_claims_body": "Chưa có tuyên bố nào đủ điều kiện để hiển thị.",
        "invalidation_heading": "Điều gì có thể làm luận điểm sai",
        "no_invalidation": "Chưa xác định được điều kiện vô hiệu hóa từ bằng chứng hiện có.",
        "assumptions_heading": "Giả định",
        "gaps_heading": "Khoảng trống bằng chứng",
        "result_label": "Kết quả kiểm chứng",
        "as_of_label": "dữ liệu tính đến",
        "sources_heading": "Nguồn",
        "publication_unknown": "không rõ ngày công bố",
        "source_fallback": "Nguồn",
    },
    "en": {
        "no_claims_heading": "Conclusions backed by evidence",
        "no_claims_body": "No claim qualified to be shown.",
        "invalidation_heading": "What would prove this wrong",
        "no_invalidation": "No invalidating condition could be determined from the evidence gathered.",
        "assumptions_heading": "Assumptions",
        "gaps_heading": "Evidence gaps",
        "result_label": "Verification result",
        "as_of_label": "data as of",
        "sources_heading": "Sources",
        "publication_unknown": "publication date unknown",
        "source_fallback": "Source",
    },
}

#: The deep lane's own memo ends in this heading before its dated source list;
#: ``loop.py`` stops the figure check there, in whichever language this memo
#: rendered in — the bibliography's dates and counts are not claims.
SOURCES_SECTION_HEADING = {lang: f"### {strings['sources_heading']}" for lang, strings in _STRINGS.items()}


def render_claim_ledger(ledger: ClaimLedger) -> str:
    """Render only checked ledger values; no model-authored URL is accepted.

    Rendered in the language the claims themselves are written in — read off
    their combined text, since a memo has no answer of its own to read a
    language from before it exists.
    """
    lang = numbers.answer_language(" ".join(claim.text for claim in ledger.claims))
    verdict_sections = _VERDICT_SECTIONS[lang]
    outcome_labels = _OUTCOME_LABELS[lang]
    strings = _STRINGS[lang]

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

    # Grouped by how far each claim got, rather than labelled one line at a
    # time. The label repeated at the head of every bullet was the same word
    # twenty times over, and a reader scanning for what was actually found had
    # to read past it on each line to get to the sentence.
    lines: list[str] = []
    rendered = 0
    for verdict, heading in verdict_sections.items():
        claims = [item for item in ledger.claims if item.verdict is verdict]
        if not claims:
            continue
        lines.extend(("", f"### {heading}"))
        for claim in claims:
            # A claim the check refused carries no citation. A reference number
            # beside it would read as the evidence backing it, which is the one
            # thing this section exists to deny.
            references = (
                ()
                if verdict is VerificationVerdict.UNSUPPORTED
                else claim.supporting_evidence_ids + claim.contradicting_evidence_ids
            )
            lines.append(f"- {_clean_text(claim.text)} {cite(references)}".rstrip())
            rendered += 1
    if not rendered:
        lines.extend(
            ("", f"### {strings['no_claims_heading']}", f"- {strings['no_claims_body']}")
        )

    lines.extend(("", f"### {strings['invalidation_heading']}"))
    invalidations = [
        item.invalidation_text
        for item in ledger.claims
        if item.invalidation_text and item.invalidation_text.strip()
    ]
    if invalidations:
        lines.extend(f"- {_clean_text(item)}" for item in invalidations)
    else:
        lines.append(f"- {strings['no_invalidation']}")

    if ledger.assumptions:
        lines.extend(("", f"### {strings['assumptions_heading']}"))
        lines.extend(f"- {_clean_text(item)}" for item in ledger.assumptions)
    if ledger.gaps:
        lines.extend(("", f"### {strings['gaps_heading']}"))
        lines.extend(f"- {_clean_text(item)}" for item in ledger.gaps)

    # The state of the check itself, last. It is a fact about the answer rather
    # than a finding, and standing at the top it was the first thing a reader
    # met — in the harness's own vocabulary, before a single sentence of what
    # was found.
    lines.extend(
        (
            "",
            f"**{strings['result_label']}:** {outcome_labels[ledger.verifier_outcome]}"
            f" · {strings['as_of_label']} {ledger.as_of.strftime('%H:%M %d/%m/%Y')}",
        )
    )

    if cited_ids:
        lines.extend(("", SOURCES_SECTION_HEADING[lang]))
        for index, evidence_id in enumerate(cited_ids, start=1):
            item = evidence_by_id[evidence_id]
            target = _public_locator(item.canonical_url or item.source)
            publisher = _clean_text(
                item.publisher
                or (urlsplit(target).hostname if target else None)
                or strings["source_fallback"]
            )
            title = _clean_text(item.title)
            published = (
                item.published_at.strftime("%H:%M %d/%m/%Y")
                if item.published_at
                else strings["publication_unknown"]
            )
            row = f"[{index}] {publisher} — {title} — {published}"
            lines.append(f"{row} — <{target}>" if target else row)
    return "\n".join(lines).strip()


__all__ = [
    "ClaimLedgerValidationReport",
    "LedgerClaimAssessment",
    "SOURCES_SECTION_HEADING",
    "render_claim_ledger",
    "validate_claim_ledger",
]
