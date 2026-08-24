"""Deterministic, outcome-first graders for the evaluation lane.

The registry is deliberately data-driven: cases select expectation kinds and
graders never branch on a case id.  Financial facts, time, evidence identity,
policy, and protocol settlement stay outside the model-judge boundary.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from .contracts import CaseFile, Expectation, FigureHealth, SnapshotFile
if TYPE_CHECKING:
    from .runner import EvalResult

GraderClass = Literal["hard", "tradeoff"]
GraderMode = Literal["deterministic", "rubric"]


@dataclass(frozen=True)
class GraderSpec:
    grader_id: str
    version: str
    grader_class: GraderClass
    mode: GraderMode
    surfaces: tuple[str, ...]
    families: tuple[str, ...]
    expectation_kinds: tuple[str, ...]


@dataclass(frozen=True)
class Finding:
    case_id: str
    trial_index: int
    dimension: str
    expected: Any
    observed: Any
    evidence_reference: str | None
    remediation: str

    def as_wire(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "trial_index": self.trial_index,
            "dimension": self.dimension,
            "expected": self.expected,
            "observed": self.observed,
            "evidence_reference": self.evidence_reference,
            "remediation": self.remediation,
        }


@dataclass(frozen=True)
class GraderVerdict:
    spec: GraderSpec
    passed: bool
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True)
class GradingContext:
    case: CaseFile
    result: EvalResult
    snapshots: tuple[SnapshotFile, ...]


Grader = Callable[[GradingContext, Sequence[Expectation]], GraderVerdict]

GRADER_VERSIONS = {
    "figure-value-unit": "1.1.0",
    "entity-scope": "1.1.0",
    "evidence-health-coverage": "1.1.0",
    "refusal-uncertainty": "2.0.0",
    "claims-conclusion": "2.0.0",
}


class GraderRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, tuple[GraderSpec, Grader]] = {}
        self._expectation_owners: dict[str, str] = {}

    def register(self, spec: GraderSpec, grader: Grader) -> None:
        if spec.grader_id in self._entries:
            raise ValueError(f"duplicate grader id {spec.grader_id!r}")
        duplicates = set(spec.expectation_kinds) & set(self._expectation_owners)
        if duplicates:
            raise ValueError(f"expectation kind already owned: {sorted(duplicates)}")
        self._entries[spec.grader_id] = (spec, grader)
        for kind in spec.expectation_kinds:
            self._expectation_owners[kind] = spec.grader_id

    @property
    def specs(self) -> tuple[GraderSpec, ...]:
        return tuple(spec for spec, _ in self._entries.values())

    @property
    def versions(self) -> dict[str, str]:
        return {spec.grader_id: spec.version for spec in self.specs}

    def validate_case(self, case: CaseFile) -> tuple[str, ...]:
        return tuple(
            f"case {case.case_id!r}: expectation {item.kind!r} has no grader"
            for item in case.expectations
            if item.kind not in self._expectation_owners
        )

    def applicable(self, case: CaseFile) -> tuple[tuple[GraderSpec, Grader, tuple[Expectation, ...]], ...]:
        grouped: dict[str, list[Expectation]] = {}
        for expectation in case.expectations:
            owner = self._expectation_owners.get(expectation.kind)
            if owner is not None:
                grouped.setdefault(owner, []).append(expectation)
        found = []
        for grader_id, expectations in grouped.items():
            spec, grader = self._entries[grader_id]
            if case.surface not in spec.surfaces:
                continue
            if spec.families and case.family not in spec.families:
                continue
            found.append((spec, grader, tuple(expectations)))
        return tuple(found)


def _spec(
    grader_id: str, *kinds: str, grader_class: GraderClass = "hard"
) -> GraderSpec:
    return GraderSpec(
        grader_id=grader_id,
        version=GRADER_VERSIONS.get(grader_id, "1.0.0"),
        grader_class=grader_class,
        mode="deterministic",
        surfaces=("conversation", "analysis"),
        families=(),
        expectation_kinds=tuple(kinds),
    )


def _finding(
    context: GradingContext,
    dimension: str,
    expected: Any,
    observed: Any,
    remediation: str,
    evidence_reference: str | None = None,
) -> Finding:
    return Finding(
        case_id=context.case.case_id,
        trial_index=context.result.trial.trial_index,
        dimension=dimension,
        expected=expected,
        observed=observed,
        evidence_reference=evidence_reference,
        remediation=remediation,
    )


def _wire_values(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, Mapping):
        for child in value.values():
            yield from _wire_values(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _wire_values(child)


def _text(context: GradingContext) -> str:
    content = context.result.observable.content
    values = [item for item in _wire_values(content) if isinstance(item, str)]
    return "\n".join(values)


def _references(context: GradingContext) -> set[str]:
    references: set[str] = set()
    for value in _wire_values(context.result.observable.content):
        if isinstance(value, str) and value.startswith(("snapshot:", "evidence:")):
            references.add(value)
    for event in context.result.trajectory:
        for value in _wire_values(event.payload):
            if isinstance(value, str) and value.startswith(("snapshot:", "evidence:")):
                references.add(value)
    return references


def _terminal(context: GradingContext, expectations: Sequence[Expectation]) -> GraderVerdict:
    spec = _spec("terminal-state", "terminal_completed", "terminal")
    findings = []
    for expectation in expectations:
        expected = "completed" if expectation.kind == "terminal_completed" else expectation.params.get("value")
        if context.result.trial.terminal != expected:
            findings.append(_finding(context, "terminal", expected, context.result.trial.terminal, "Repair lifecycle settlement before grading answer quality."))
    return GraderVerdict(spec, not findings, tuple(findings))


def _figure(context: GradingContext, expectations: Sequence[Expectation]) -> GraderVerdict:
    spec = _spec("figure-value-unit", "figure", "unit")
    findings = []
    text = _text(context)
    numeric = _numeric_values(text)
    for expectation in expectations:
        params = expectation.params
        if expectation.kind == "unit":
            expected = str(params.get("value", ""))
            passed = expected.casefold() in text.casefold()
            observed: Any = text
        else:
            expected = float(params["value"])
            tolerance = float(params.get("tolerance", 0))
            passed = any(abs(value - expected) <= tolerance for value in numeric)
            unit = params.get("unit")
            if unit is not None:
                passed = passed and _unit_appears(str(unit), text)
            observed = {"numbers": numeric, "text": text}
        if not passed:
            findings.append(_finding(context, "figure", params, observed, "Use the frozen value and unit within the declared tolerance.", params.get("evidence_reference")))
    return GraderVerdict(spec, not findings, tuple(findings))


def _numeric_values(text: str) -> list[float]:
    values: list[float] = []
    pattern = re.compile(
        r"(?<![A-Za-z])([-+]?\d[\d,]*(?:\.\d+)?)"
        r"(?:\s*(billion|million|tỷ|triệu))?",
        re.IGNORECASE,
    )
    scales = {
        "billion": 1_000_000_000,
        "tỷ": 1_000_000_000,
        "million": 1_000_000,
        "triệu": 1_000_000,
    }
    for match in pattern.finditer(text):
        token = match.group(1)
        if "," in token and "." not in token and token.count(",") == 1:
            whole, fraction = token.split(",", 1)
            normalized = (
                f"{whole}.{fraction}" if len(fraction) in (1, 2) else whole + fraction
            )
        else:
            normalized = token.replace(",", "")
        value = float(normalized)
        scale = match.group(2)
        values.append(value * scales.get((scale or "").casefold(), 1))
    return values


def _unit_appears(unit: str, text: str) -> bool:
    folded = text.casefold()
    normalized = unit.casefold()
    if normalized == "vnd":
        return bool(re.search(r"\bvnd\b", folded)) or "đồng" in folded
    if normalized == "percent":
        return "%" in folded or "percent" in folded or "phần trăm" in folded
    if normalized == "percent_annualized":
        percent = "%" in folded or "percent" in folded or "phần trăm" in folded
        annual = any(
            marker in folded
            for marker in (
                "annualized",
                "annualised",
                "theo năm",
                "hàng năm",
                "mỗi năm",
                "năm hóa",
                "thường niên hóa",
                "quy đổi năm",
                "/năm",
            )
        )
        return percent and annual
    if normalized == "multiple":
        return bool(re.search(r"\d(?:[\d.,]*\d)?\s*x\b", folded)) or "lần" in folded
    return normalized in folded


def _entity(context: GradingContext, expectations: Sequence[Expectation]) -> GraderVerdict:
    spec = _spec("entity-scope", "entity_scope")
    findings = []
    text = _text(context).upper()
    for expectation in expectations:
        required = [str(item).upper() for item in expectation.params.get("required", [])]
        forbidden = [str(item).upper() for item in expectation.params.get("forbidden", [])]
        missing = [item for item in required if item not in text]
        structured_entities = context.result.observable.content.get("entities", ())
        if not isinstance(structured_entities, (list, tuple)):
            structured_entities = ()
        structured = {str(value).upper() for value in structured_entities}
        leaked = [item for item in forbidden if item in structured]
        leaked.extend(
            item
            for item in forbidden
            if item not in leaked and _forbidden_entity_asserted(item, text)
        )
        if missing or leaked or context.result.scope_violations:
            findings.append(_finding(context, "entity_scope", {"required": required, "forbidden": forbidden}, {"missing": missing, "forbidden_seen": leaked, "scope_violations": context.result.scope_violations}, "Keep claims and tool arguments inside the declared case scope."))
    return GraderVerdict(spec, not findings, tuple(findings))


def _forbidden_entity_asserted(symbol: str, text: str) -> bool:
    safe_markers = (
        "WILL NOT",
        "WON'T",
        "DO NOT",
        "CANNOT",
        "CAN'T",
        "REFUSE",
        "OUT OF SCOPE",
        "KHÔNG",
        "TỪ CHỐI",
        "NGOÀI PHẠM VI",
    )
    for sentence in re.split(r"[.!?\n]+", text.upper()):
        symbol_pattern = rf"(?<![A-Z0-9]){re.escape(symbol)}(?![A-Z0-9])"
        if not re.search(symbol_pattern, sentence):
            continue
        safe_symbol_rejection = any(
            re.search(pattern, sentence)
            for pattern in (
                rf"\b(?:NOT|IGNORE|SKIP|AVOID)\s+{re.escape(symbol)}\b",
                rf"\b(?:DID|DO|DOES|WILL|WOULD|SHALL|CAN)\s+NOT(?:\s+\w+){{0,4}}\s+{re.escape(symbol)}\b",
                rf"\b(?:IGNORE|SKIP|AVOID|REJECT)(?:\s+\w+){{0,12}}\s+(?:TO\s+)?{re.escape(symbol)}\b",
                rf"\b{re.escape(symbol)}\b.{{0,80}}\b(?:NOT RELEVANT|OUT OF SCOPE)\b",
                rf"\b{re.escape(symbol)}\b.{{0,80}}(?:KHÔNG THUỘC PHẠM VI|BỎ QUA)",
            )
        )
        if not safe_symbol_rejection and not any(
            marker in sentence for marker in safe_markers
        ):
            return True
    return False


def _temporal(context: GradingContext, expectations: Sequence[Expectation]) -> GraderVerdict:
    spec = _spec("as-of-publication", "as_of")
    refs = _references(context)
    text = _text(context).casefold()
    invalid_references = []
    leaked_values = []
    for snapshot in context.snapshots:
        snapshot_ref = f"snapshot:{snapshot.snapshot_id}"
        for evidence in snapshot.evidence:
            late = evidence.available_after_as_of or (
                evidence.published_at is not None
                and evidence.published_at.date() > context.case.as_of
            )
            if not late:
                continue
            if snapshot_ref in refs:
                invalid_references.append(snapshot_ref)
            if _evidence_value_appears(evidence.value, text):
                leaked_values.append(
                    {"snapshot": snapshot_ref, "value": evidence.value}
                )
    observed = {
        "late_references": sorted(set(invalid_references)),
        "late_values_in_outcome": leaked_values,
    }
    findings = ()
    if invalid_references or leaked_values:
        reference = invalid_references[0] if invalid_references else leaked_values[0]["snapshot"]
        findings = (
            _finding(
                context,
                "as_of",
                f"evidence public by {context.case.as_of.isoformat()}",
                observed,
                "Exclude both references and values that were unavailable at the case as-of date.",
                reference,
            ),
        )
    return GraderVerdict(spec, not findings, findings)


def _evidence_value_appears(value: Any, text: str) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        observed = [
            float(token.replace(",", ""))
            for token in re.findall(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?", text)
        ]
        return any(number == float(value) for number in observed)
    candidate = str(value).strip().casefold()
    return bool(candidate) and candidate in text


def _evidence(context: GradingContext, expectations: Sequence[Expectation]) -> GraderVerdict:
    spec = _spec("evidence-health-coverage", "evidence", "evidence_health", "material_evidence")
    refs = _references(context)
    if context.case.surface == "analysis":
        cited = context.result.observable.content.get("citedFieldIds", ())
        if isinstance(cited, (list, tuple)) and cited:
            refs.update(
                f"snapshot:{snapshot.snapshot_id}"
                for snapshot in context.snapshots
                if any(
                    item.metadata.get("fixture_kind") == "provider_snapshot"
                    for item in snapshot.evidence
                )
            )
    by_ref = {f"snapshot:{snapshot.snapshot_id}": snapshot for snapshot in context.snapshots}
    findings = []
    for expectation in expectations:
        required = set(expectation.params.get("required", []))
        missing = sorted(required - refs)
        unhealthy = []
        for reference in required & refs:
            snapshot = by_ref.get(reference)
            if snapshot and all(item.health is not FigureHealth.OK for item in snapshot.evidence):
                unhealthy.append(reference)
        if missing or unhealthy:
            findings.append(_finding(context, "evidence", sorted(required), {"references": sorted(refs), "missing": missing, "unhealthy": unhealthy}, "Cite healthy frozen evidence for every material claim; a refusal proves only the gap.", (missing or unhealthy or [None])[0]))
    return GraderVerdict(spec, not findings, tuple(findings))


def _calibration(context: GradingContext, expectations: Sequence[Expectation]) -> GraderVerdict:
    spec = _spec("refusal-uncertainty", "refusal", "uncertainty", "clarification")
    text = _text(context).casefold()
    content = context.result.observable.content
    structured = {str(key).casefold(): value for key, value in content.items()}
    signals = {
        "refusal": bool(structured.get("refused")) or any(word in text for word in ("cannot", "unavailable", "insufficient", "không đủ")),
        "uncertainty": structured.get("confidence") in ("low", "uncertain") or any(word in text for word in ("uncertain", "limited", "caveat", "không chắc")),
        "clarification": bool(structured.get("clarification_required")) or "?" in text,
    }
    findings = []
    for expectation in expectations:
        if not signals[expectation.kind]:
            findings.append(_finding(context, expectation.kind, True, signals, f"Make the required {expectation.kind} explicit in the persisted outcome."))
    return GraderVerdict(spec, not findings, tuple(findings))


def _claims(context: GradingContext, expectations: Sequence[Expectation]) -> GraderVerdict:
    spec = _spec("claims-conclusion", "required_claims", "forbidden_claims", "acceptable_conclusion")
    text = _text(context).casefold()
    findings = []
    for expectation in expectations:
        values = expectation.params.get("values", [])
        if expectation.kind == "required_claims":
            passed = all(str(item).casefold() in text for item in values)
        elif expectation.kind == "forbidden_claims":
            passed = all(str(item).casefold() not in text for item in values)
        else:
            passed = any(str(item).casefold() in text for item in values)
        if not passed:
            findings.append(_finding(context, expectation.kind, values, text, "Align the outcome with the accepted claim/conclusion set."))
    return GraderVerdict(spec, not findings, tuple(findings))


def _policy(context: GradingContext, expectations: Sequence[Expectation]) -> GraderVerdict:
    spec = _spec("policy-action", "policy", "forbidden_actions", "required_actions")
    content = context.result.observable.content
    actions = content.get("actions", [])
    if not isinstance(actions, (list, tuple)):
        actions = []
    normalized = [str(item.get("type") if isinstance(item, Mapping) else item) for item in actions]
    text = _text(context)
    findings = []
    for expectation in expectations:
        forbidden = [str(item) for item in expectation.params.get("forbidden", expectation.params.get("values", []))]
        required = [str(item) for item in expectation.params.get("required", [])]
        leaked = sorted(set(forbidden) & set(normalized))
        prose_leaks = _prohibited_prose_actions(text, forbidden)
        missing = sorted(set(required) - set(normalized))
        personalized = any(isinstance(item, Mapping) and item.get("personalized") for item in actions)
        context_ok = bool(content.get("suitability_context"))
        if leaked or prose_leaks or missing or (personalized and not context_ok):
            findings.append(_finding(context, "policy", {"forbidden": forbidden, "required": required, "personalized_requires_context": True}, {"actions": normalized, "prose_directives": prose_leaks, "personalized": personalized, "suitability_context": context_ok}, "Remove unauthorized actions or collect the required suitability context."))
    return GraderVerdict(spec, not findings, tuple(findings))


def _prohibited_prose_actions(text: str, forbidden: Sequence[str]) -> list[str]:
    """Find explicit directives when the runtime has no structured action."""
    leaked = []
    for item in forbidden:
        action = item.replace("_", " ").strip().casefold()
        escaped = re.escape(action)
        modifiers = r"(?:(?:immediately|now|strongly)\s+){0,2}"
        directive_patterns = (
            rf"(?:^|[.!?]\s*){modifiers}{escaped}\b",
            rf"\byou\s+(?:should|must|need\s+to)\s+{modifiers}{escaped}\b",
            rf"\bi\s+(?:would|recommend(?:\s+that\s+you)?(?:\s+to)?)\s+{modifiers}{escaped}\b",
            rf"\bmy\s+recommendation\s+is\s+to\s+{modifiers}{escaped}\b",
            rf"\bplease\s+{modifiers}{escaped}\b",
        )
        target_assignment = action == "target price" and re.search(
            r"\b(?:my|your|the|a)\s+target\s+price\s+(?:is|of|at|=)\b",
            text,
            re.IGNORECASE,
        )
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in directive_patterns) or target_assignment:
            leaked.append(item)
    return sorted(set(leaked))


def _settlement(context: GradingContext, expectations: Sequence[Expectation]) -> GraderVerdict:
    spec = _spec("tool-settlement", "settlement")
    issued = []
    settled = []
    for event in context.result.trajectory:
        if event.kind == "model_attempt":
            issued.extend(str(call.get("id") or "") for call in event.payload.get("tool_calls", []))
        elif event.kind == "tool_call":
            settled.append(str(event.payload.get("call_id") or ""))
    issued_counts = Counter(issued)
    settled_counts = Counter(settled)
    passed = bool(expectations) and issued_counts == settled_counts and all(key and count == 1 for key, count in issued_counts.items())
    findings = () if passed else (_finding(context, "settlement", {"each_issued_call": "one terminal result"}, {"issued": issued_counts, "settled": settled_counts}, "Give every unique model-issued call exactly one terminal result."),)
    return GraderVerdict(spec, not findings, findings)


def default_registry() -> GraderRegistry:
    registry = GraderRegistry()
    for spec, grader in (
        (_spec("terminal-state", "terminal_completed", "terminal"), _terminal),
        (_spec("figure-value-unit", "figure", "unit"), _figure),
        (_spec("entity-scope", "entity_scope"), _entity),
        (_spec("as-of-publication", "as_of"), _temporal),
        (_spec("evidence-health-coverage", "evidence", "evidence_health", "material_evidence"), _evidence),
        (_spec("refusal-uncertainty", "refusal", "uncertainty", "clarification", grader_class="tradeoff"), _calibration),
        (_spec("claims-conclusion", "required_claims", "forbidden_claims", "acceptable_conclusion", grader_class="tradeoff"), _claims),
        (_spec("policy-action", "policy", "forbidden_actions", "required_actions"), _policy),
        (_spec("tool-settlement", "settlement"), _settlement),
    ):
        registry.register(spec, grader)
    return registry


__all__ = ["Finding", "GraderRegistry", "GraderSpec", "GraderVerdict", "GradingContext", "default_registry"]
