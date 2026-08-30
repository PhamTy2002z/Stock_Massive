"""Pure graders and proof builders for ``signal_desk`` golden artifacts.

The runner records one persisted composition payload.  Raw frame rows live only
inside that payload; the proof blocks below contain hashes and counts, so an
offline grader can re-check the evidence without making a database or model
call and without copying the numeric arrays into a second artifact field.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from .grade import Finding

FIXED_GRADERS = (
    "board_present",
    "refs_resolve",
    "frames_absent",
    "compute_literal_free",
    "evidence_on_page",
    "replay_identical",
)
EXPECTATION_GRADERS = (
    "expect_board",
    "expect_min_kpi",
    "expect_archetype",
    "expect_refusal",
)
METRIC_GRADERS = (
    "visual_ratio",
    "narrative_chars",
    "kpi_count",
    "widget_variety",
    "auto_composed_rate",
    "cost_micro_usd",
    "latency",
    "external_calls",
)
GRADERS = FIXED_GRADERS + EXPECTATION_GRADERS + METRIC_GRADERS

COST_P50_CEILING_MICRO_USD = 84_362


def _compact(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_compact(value).encode("utf-8")).hexdigest()


def _composition(case: Mapping[str, Any]) -> Mapping[str, Any]:
    value = case.get("composition")
    return value if isinstance(value, Mapping) else {}


def _spec(case: Mapping[str, Any]) -> Mapping[str, Any]:
    value = _composition(case).get("spec")
    return value if isinstance(value, Mapping) else {}


def _frames(case: Mapping[str, Any]) -> Mapping[str, Any]:
    value = _composition(case).get("frames")
    return value if isinstance(value, Mapping) else {}


def _finding(
    case: Mapping[str, Any],
    grader: str,
    value: float | int | None,
    passed: bool | None,
    detail: str,
) -> Finding:
    return Finding(str(case.get("id")), grader, value, passed, detail)


def _resolved_values(value: Any, path: str = "spec") -> list[tuple[str, Mapping[str, Any]]]:
    found: list[tuple[str, Mapping[str, Any]]] = []
    if isinstance(value, Mapping):
        if {"raw", "frame", "row", "column"}.issubset(value):
            found.append((path, value))
        for key, child in value.items():
            found.extend(_resolved_values(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_resolved_values(child, f"{path}[{index}]"))
    return found


def build_ref_proof(composition: Mapping[str, Any]) -> dict[str, Any]:
    """Hash resolved refs beside the cells obtained by re-resolving them."""
    spec = composition.get("spec") if isinstance(composition.get("spec"), Mapping) else {}
    frames = composition.get("frames") if isinstance(composition.get("frames"), Mapping) else {}
    declared: list[dict[str, Any]] = []
    resolved: list[dict[str, Any]] = []
    failures: list[str] = []
    for path, ref in _resolved_values(spec):
        item = {
            "path": path,
            "frame": ref.get("frame"),
            "row": ref.get("row"),
            "column": ref.get("column"),
            "raw": ref.get("raw"),
        }
        declared.append(item)
        frame = frames.get(ref.get("frame"))
        try:
            columns = list(frame.get("columns") or ())
            row_index = int(ref.get("row"))
            column = str(ref.get("column"))
            rows = list(frame.get("rows") or ())
            actual = list(rows[row_index])[columns.index(column)]
        except (AttributeError, TypeError, ValueError, IndexError):
            failures.append(path)
            resolved.append({**item, "raw": "<unresolved>"})
            continue
        resolved.append({**item, "raw": actual})
        if actual != ref.get("raw"):
            failures.append(path)
    return {
        "checked": len(declared),
        "all_resolved": not failures,
        "declared_sha256": _digest(declared),
        "resolved_sha256": _digest(resolved),
        "failures": failures,
    }


def _source_map(composition: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for item in composition.get("frame_metadata") or ():
        if isinstance(item, Mapping) and item.get("key"):
            out[str(item["key"])] = {"source": item.get("source") or "store"}
    return out


def _replay_spec(composition: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Replay a stored board through the same production composer, without IO."""
    from src.studies import archetypes, auto_compose, composer, contracts, grammar, lint

    stored = composition.get("spec")
    frames = composition.get("frames")
    if not isinstance(stored, Mapping) or not isinstance(frames, Mapping) or not frames:
        return None
    if bool(stored.get("autoComposed")):
        sources = _source_map(composition)
        gathered = [
            (key, frame, sources.get(key, {"source": "store"}))
            for key, frame in frames.items()
            if isinstance(frame, Mapping)
        ]
        replayed = auto_compose.compose(gathered, title=str(stored.get("title") or ""))
        return None if replayed is None else replayed[0].to_payload()

    arguments = composition.get("replay_arguments")
    if not isinstance(arguments, Mapping):
        return None
    try:
        board = grammar.parse(arguments)
        payloads = {str(key): value for key, value in frames.items() if isinstance(value, Mapping)}
        compiled = composer.compile_board(board, payloads, _source_map(composition))
        report = lint.score(compiled.sections, len(compiled.kpis))
        return contracts.BoardSpec(
            title=board.title,
            archetype=board.archetype or archetypes.DEFAULT,
            kpis=compiled.kpis,
            sections=compiled.sections,
            appendix=compiled.appendix,
            lint=report.to_payload(),
            auto_composed=False,
        ).to_payload()
    except (TypeError, ValueError):
        return None


def build_replay_proof(composition: Mapping[str, Any]) -> dict[str, Any]:
    stored = composition.get("spec")
    replayed = _replay_spec(composition)
    return {
        "available": replayed is not None,
        "stored_sha256": _digest(stored),
        "replayed_sha256": None if replayed is None else _digest(replayed),
        "identical": replayed is not None and _compact(stored) == _compact(replayed),
    }


def replay_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Rewrite source frame ids to the deterministic ``fN`` compiler keys."""
    rewritten = copy.deepcopy(dict(arguments))
    order: list[str] = []

    def remember(reference: Any) -> None:
        text = str(reference or "")
        if text and text not in order:
            order.append(text)

    for section in rewritten.get("sections") or ():
        for block in section.get("blocks") or ():
            if block.get("kind") == "visual":
                remember(block.get("frame_id"))
            else:
                for ref in (block.get("refs") or {}).values():
                    remember(ref.get("frame_id"))
    for kpi in rewritten.get("kpis") or ():
        remember((kpi.get("value") or {}).get("frame_id"))
        remember((kpi.get("delta") or {}).get("frame_id"))
    remember(rewritten.get("appendix_frame_id"))
    mapping = {reference: f"f{index}" for index, reference in enumerate(order)}

    def replace(value: Any) -> None:
        if isinstance(value, dict):
            if "frame_id" in value and str(value["frame_id"]) in mapping:
                value["frame_id"] = mapping[str(value["frame_id"])]
            for child in value.values():
                replace(child)
        elif isinstance(value, list):
            for child in value:
                replace(child)

    replace(rewritten)
    if str(rewritten.get("appendix_frame_id") or "") in mapping:
        rewritten["appendix_frame_id"] = mapping[str(rewritten["appendix_frame_id"])]
    return rewritten


def grade_board_present(case: Mapping[str, Any]) -> Finding:
    present = _spec(case).get("specVersion") == 2
    return _finding(
        case,
        "board_present",
        int(present),
        present,
        "composition spec v2" if present else "no composition spec v2",
    )


def grade_refs_resolve(case: Mapping[str, Any]) -> Finding:
    composition = _composition(case)
    recorded = composition.get("ref_proof")
    current = build_ref_proof(composition)
    passed = (
        bool(current["all_resolved"])
        and isinstance(recorded, Mapping)
        and dict(recorded) == current
    )
    detail = (
        "all refs re-resolve"
        if passed
        else f"ref proof mismatch; failures={current['failures']}"
    )
    return _finding(case, "refs_resolve", int(current["checked"]), passed, detail)


def _meaningful_frame_literals(case: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    literals: list[tuple[str, str, str]] = []
    metadata = {
        str(item.get("key")): str(item.get("source") or "store")
        for item in (_composition(case).get("frame_metadata") or ())
        if isinstance(item, Mapping)
    }
    for key, frame in _frames(case).items():
        if not isinstance(frame, Mapping):
            continue
        for row in frame.get("rows") or ():
            for value in row if isinstance(row, (list, tuple)) else ():
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                literal = str(value)
                if len([char for char in literal if char.isdigit()]) >= 3:
                    literals.append((str(key), metadata.get(str(key), "store"), literal))
    return literals


def grade_frames_absent(case: Mapping[str, Any]) -> Finding:
    body = str(case.get("model_visible_text") or "")
    leaked = [
        (key, source, literal)
        for key, source, literal in _meaningful_frame_literals(case)
        if literal in body
    ]
    detail = "no meaningful frame literal entered model-visible text"
    if leaked:
        detail = "leaked: " + ", ".join(
            f"{key}:{literal} ({source})" for key, source, literal in leaked[:8]
        )
    return _finding(case, "frames_absent", len(leaked), not leaked, detail)


def grade_compute_literal_free(case: Mapping[str, Any]) -> Finding:
    from src.studies.compute import validator

    calls = [
        call
        for call in case.get("tool_calls") or ()
        if isinstance(call, Mapping) and call.get("name") == "compute"
    ]
    violations = []
    for call in calls:
        violations.extend(validator.validate(str((call.get("arguments") or {}).get("code") or "")))
    detail = (
        "all compute calls validate"
        if not violations
        else f"{len(violations)} literal/validator violation(s)"
    )
    return _finding(case, "compute_literal_free", len(violations), not violations, detail)


def _result_payload(call: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        value = json.loads(str(call.get("result_text") or ""))
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, Mapping) else {}


def grade_evidence_on_page(case: Mapping[str, Any]) -> Finding:
    calls = [
        call
        for call in case.get("tool_calls") or ()
        if isinstance(call, Mapping) and call.get("name") == "frame_from_evidence"
    ]
    failed: list[str] = []
    checked = 0
    for call in calls:
        rows = list((call.get("arguments") or {}).get("rows") or ())
        result = _result_payload(call)
        checked += len(rows)
        if int(result.get("matched") or 0) != len(rows) or int(result.get("refusedCount") or 0):
            failed.append(str(call.get("id") or "?"))
    detail = (
        "all evidence rows matched"
        if not failed
        else "unmatched evidence call(s): " + ", ".join(failed)
    )
    return _finding(case, "evidence_on_page", checked, not failed, detail)


def grade_replay_identical(case: Mapping[str, Any]) -> Finding:
    composition = _composition(case)
    current = build_replay_proof(composition)
    recorded = composition.get("replay_proof")
    passed = (
        bool(current["identical"])
        and isinstance(recorded, Mapping)
        and dict(recorded) == current
    )
    detail = (
        "composer replay is byte-identical"
        if passed
        else "composer replay unavailable or different"
    )
    return _finding(
        case, "replay_identical", int(bool(current["identical"])), passed, detail
    )


def grade_expect_board(case: Mapping[str, Any]) -> Finding:
    expected = (case.get("expect") or {}).get("board")
    actual = _spec(case).get("specVersion") == 2
    passed = None if expected is None else actual is bool(expected)
    return _finding(
        case,
        "expect_board",
        int(actual),
        passed,
        f"expected={expected!r}, actual={actual!r}",
    )


def grade_expect_min_kpi(case: Mapping[str, Any]) -> Finding:
    expected = (case.get("expect") or {}).get("min_kpi")
    actual = len(_spec(case).get("kpis") or ())
    passed = None if expected is None else actual >= int(expected)
    return _finding(
        case,
        "expect_min_kpi",
        actual,
        passed,
        f"expected at least {expected!r}, actual={actual}",
    )


def grade_expect_archetype(case: Mapping[str, Any]) -> Finding:
    expected = (case.get("expect") or {}).get("archetype")
    actual = _spec(case).get("archetype")
    passed = None if expected is None else actual == expected
    return _finding(
        case,
        "expect_archetype",
        None,
        passed,
        f"expected={expected!r}, actual={actual!r}",
    )


def grade_expect_refusal(case: Mapping[str, Any]) -> Finding:
    expected = (case.get("expect") or {}).get("refusal")
    codes: set[str] = set()
    for call in case.get("tool_calls") or ():
        if not isinstance(call, Mapping):
            continue
        result = _result_payload(call)
        for value in (
            call.get("outcome"),
            result.get("error"),
            result.get("issue"),
            result.get("rejected"),
        ):
            if value:
                codes.add(str(value))
    passed = None if expected is None else str(expected) in codes
    return _finding(
        case,
        "expect_refusal",
        len(codes),
        passed,
        f"expected={expected!r}, observed={sorted(codes)}",
    )


def _visuals(spec: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        block
        for section in spec.get("sections") or ()
        for block in section.get("blocks") or ()
        if isinstance(block, Mapping) and block.get("kind") == "visual"
    ]


def _captions(spec: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        block
        for section in spec.get("sections") or ()
        for block in section.get("blocks") or ()
        if isinstance(block, Mapping) and block.get("kind") == "caption"
    ]


def grade_visual_ratio(case: Mapping[str, Any]) -> Finding:
    visuals, captions = _visuals(_spec(case)), _captions(_spec(case))
    total = len(visuals) + len(captions)
    value = 1.0 if not total else len(visuals) / total
    return _finding(
        case,
        "visual_ratio",
        round(value, 4),
        None,
        f"{len(visuals)}/{total} blocks are visual",
    )


def grade_narrative_chars(case: Mapping[str, Any]) -> Finding:
    value = sum(len(str(item.get("template") or "")) for item in _captions(_spec(case)))
    return _finding(case, "narrative_chars", value, None, f"{value} caption character(s)")


def grade_kpi_count(case: Mapping[str, Any]) -> Finding:
    value = len(_spec(case).get("kpis") or ())
    return _finding(case, "kpi_count", value, None, f"{value} KPI(s)")


def grade_widget_variety(case: Mapping[str, Any]) -> Finding:
    value = len({str(item.get("widget")) for item in _visuals(_spec(case))})
    return _finding(case, "widget_variety", value, None, f"{value} widget kind(s)")


def grade_auto_composed_rate(case: Mapping[str, Any]) -> Finding:
    value = int(bool(_spec(case).get("autoComposed")))
    return _finding(
        case,
        "auto_composed_rate",
        value,
        None,
        "auto-composed" if value else "model-composed",
    )


def grade_cost_micro_usd(case: Mapping[str, Any]) -> Finding:
    value = int((case.get("cost") or {}).get("micro_usd") or 0)
    return _finding(case, "cost_micro_usd", value, None, f"{value} micro-USD")


def grade_latency(case: Mapping[str, Any]) -> Finding:
    value = int((case.get("turn") or {}).get("wall_ms") or 0)
    return _finding(case, "latency", value, None, f"{value} ms")


def grade_external_calls(case: Mapping[str, Any]) -> Finding:
    recorded = case.get("external_calls")
    value = (
        int(recorded)
        if recorded is not None
        else sum(
            1
            for call in case.get("tool_calls") or ()
            if isinstance(call, Mapping) and call.get("kind") == "external"
        )
    )
    return _finding(case, "external_calls", value, None, f"{value} external call(s)")


_GRADERS = {name: globals()[f"grade_{name}"] for name in GRADERS}


def grade_case(case: Mapping[str, Any]) -> list[Finding]:
    return [_GRADERS[name](case) for name in GRADERS]


__all__ = [
    "COST_P50_CEILING_MICRO_USD",
    "EXPECTATION_GRADERS",
    "FIXED_GRADERS",
    "GRADERS",
    "METRIC_GRADERS",
    "build_ref_proof",
    "build_replay_proof",
    "grade_case",
    "replay_arguments",
] + [f"grade_{name}" for name in GRADERS]
