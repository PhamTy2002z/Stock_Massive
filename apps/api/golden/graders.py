"""The eight dimensions roadmap §10 Phase 1 names, one function each.

Every one of them obeys the three rules the previous two eval batteries died
for want of, written out in ``README.md`` and repeated here because this file is
where they would be broken first:

**A grader never branches on a case id.** It branches on what the case declares.
Two cases with the same declaration are scored identically, and a case that
declares nothing about a dimension gets ``None`` — never a pass.

**A grader reads only fields a real artifact carries.** Where a fact does not
exist in the runtime yet, the grader says so in its own denominator instead of
quietly passing. ``temporal_validity`` is the honest example: the search
provider returns no publication date, so the dimension reports how many sources
it could not date beside the violations it found.

**A grader reports; it does not gate.** No threshold appears in this file. The
one place a bar exists is ``gate.py``, and the reason is that a bar written next
to the logic that produces the number gets tuned by whoever is failing it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .text import (
    as_date,
    canonical_numbers,
    canonical_url,
    matched_markers,
    parse_number,
    urls_in,
    within_tolerance,
)

#: The statuses a Turn is allowed to end in. ``unknown`` is what ``read_case``
#: writes when no assistant message exists at all, which is the blank screen
#: this dimension exists to catch.
TERMINAL_STATUSES = ("complete", "incomplete", "cancelled", "error")

DIMENSIONS = (
    "settlement",
    "citation_url",
    "evidence_identity",
    "material_claim",
    "temporal_validity",
    "refusal_policy",
    "budget",
    "multi_source_label",
)


@dataclass(frozen=True)
class Finding:
    """One dimension's verdict on one case-trial."""

    case_id: str
    grader: str
    value: float | int | None
    passed: bool | None
    detail: str
    trial: int = 1
    dimension_class: str = "reported"
    extra: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "case_id": self.case_id,
            "trial": self.trial,
            "grader": self.grader,
            "class": self.dimension_class,
            "value": self.value,
            "passed": self.passed,
            "detail": self.detail,
        }
        if self.extra:
            body["extra"] = dict(self.extra)
        return body


# -- shared readers --------------------------------------------------------


def _sources(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return tuple(item for item in (case.get("sources") or ()) if isinstance(item, Mapping))


def _calls(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return tuple(item for item in (case.get("tool_calls") or ()) if isinstance(item, Mapping))


def _expect(case: Mapping[str, Any]) -> Mapping[str, Any]:
    return case.get("expect") or {}


def _markers(corpus: Mapping[str, Any], name: str) -> tuple[str, ...]:
    markers = (corpus.get("markers") or {}).get(name) or ()
    return tuple(str(item) for item in markers if isinstance(item, str))


def _finding(case: Mapping[str, Any], grader: str, **kwargs: Any) -> Finding:
    return Finding(
        case_id=str(case.get("id")),
        trial=int(case.get("trial") or 1),
        grader=grader,
        **kwargs,
    )


# -- the eight -------------------------------------------------------------


def grade_settlement(
    case: Mapping[str, Any], corpus: Mapping[str, Any], run: Mapping[str, Any]
) -> Finding:
    """Whether the Turn ended in a terminal state carrying something to read.

    Two ways to fail, and they are different failures. A status of ``unknown``
    means no assistant message was ever written — the blank screen. A terminal
    status with neither an answer nor a reason means the Turn ended politely and
    said nothing, which from the reader's side is the same thing.
    """
    turn = case.get("turn") or {}
    status = str(turn.get("status") or "unknown")
    reason = turn.get("terminal_reason")
    answer = str(case.get("answer_text") or "").strip()

    if status not in TERMINAL_STATUSES:
        return _finding(
            case, "settlement", value=0, passed=False,
            detail=f"the Turn never settled: status {status!r}",
        )
    if not answer and not reason:
        return _finding(
            case, "settlement", value=0, passed=False,
            detail=f"status {status!r} with no answer text and no terminal reason",
        )
    return _finding(
        case, "settlement", value=1, passed=True,
        detail=f"settled {status!r}" + (f" ({reason})" if reason else ""),
    )


def grade_citation_url(
    case: Mapping[str, Any], corpus: Mapping[str, Any], run: Mapping[str, Any]
) -> Finding:
    """Every link the answer prints must be a link this Turn actually read.

    The prompt forbids printing links at all, so the usual outcome is zero URLs
    and a pass. That is not a vacuous pass: the day an answer prints one, this
    is the dimension that decides whether the Turn had been to it.
    """
    printed = urls_in(str(case.get("answer_text") or ""))
    read = {canonical_url(str(item.get("url") or "")) for item in _sources(case)}
    read |= {
        canonical_url(str((call.get("arguments") or {}).get("url") or ""))
        for call in _calls(case)
    }
    read.discard("")
    fabricated = [url for url in printed if canonical_url(url) not in read]
    return _finding(
        case,
        "citation_url",
        value=len(fabricated),
        passed=not fabricated,
        detail=(
            f"{len(printed)} URL(s) printed, all of them read"
            if not fabricated
            else "printed but never read: " + ", ".join(fabricated[:5])
        ),
    )


def grade_evidence_identity(
    case: Mapping[str, Any], corpus: Mapping[str, Any], run: Mapping[str, Any]
) -> Finding:
    """Whether every source still knows what it is and where it came from.

    Identity here is four facts travelling together: a URL, its domain, a title,
    and the call that produced it. Roadmap §6.6 says none of them may be lost to
    trimming, summarising, persisting or rendering — this is the measurement of
    that, taken at the far end of all four.
    """
    sources = _sources(case)
    if not sources:
        return _finding(
            case, "evidence_identity", value=None, passed=None,
            detail="the Turn carried no source, so there is no identity to keep",
        )
    known_calls = {str(call.get("id") or "") for call in _calls(case)}
    broken: list[str] = []
    for item in sources:
        url = str(item.get("url") or "")
        missing = [
            name
            for name, value in (
                ("url", url),
                ("domain", item.get("domain")),
                ("title", item.get("title")),
            )
            if not value
        ]
        origin = str(item.get("from_call") or "")
        if origin not in known_calls:
            missing.append("from_call")
        if missing:
            broken.append(f"{url or '<no url>'} [{', '.join(missing)}]")
    return _finding(
        case,
        "evidence_identity",
        value=len(broken),
        passed=not broken,
        detail=(
            f"{len(sources)} source(s), all traceable"
            if not broken
            else f"{len(broken)} of {len(sources)} incomplete: " + "; ".join(broken[:3])
        ),
    )


def grade_material_claim(
    case: Mapping[str, Any], corpus: Mapping[str, Any], run: Mapping[str, Any]
) -> Finding:
    """The answer's figures against the ones this case froze as ground truth.

    This is the only place in the harness where "percent correct" can honestly
    come from, and the reason is the freezing. Searching an answer for a
    *derivation* of its numbers was tried on the previous corpus, measured, and
    abandoned — with a premise pool of 38–221 operands a fabricated figure finds
    a witness as easily as an honest one. Ground truth avoids the whole problem
    by naming the right answer in advance instead of inferring it afterwards.

    A case with no frozen values scores ``None``. It is emphatically not a pass:
    an empty ground truth means nobody has done the work yet.
    """
    truth = case.get("ground_truth") or {}
    values = [item for item in (truth.get("values") or ()) if isinstance(item, Mapping)]
    if not values:
        status = str(truth.get("status") or "not declared")
        return _finding(
            case, "material_claim", value=None, passed=None,
            detail=f"no frozen ground truth for this case ({status})",
        )
    stated = canonical_numbers(str(case.get("answer_text") or ""))
    misses: list[str] = []
    for item in values:
        expected = parse_number(str(item.get("value")))
        if expected is None:
            misses.append(f"{item.get('key')}: ground truth {item.get('value')!r} is not a number")
            continue
        tolerance = Decimal(str(item.get("tolerance") or "0"))
        if not any(within_tolerance(value, expected, tolerance) for value in stated):
            misses.append(f"{item.get('key')}: expected {expected} {item.get('unit') or ''}".strip())
    return _finding(
        case,
        "material_claim",
        value=len(values) - len(misses),
        passed=not misses,
        detail=(
            f"all {len(values)} frozen figure(s) stated"
            if not misses
            else f"{len(misses)} of {len(values)} missing or wrong: " + "; ".join(misses[:3])
        ),
        extra={"expected": len(values)},
    )


def grade_temporal_validity(
    case: Mapping[str, Any], corpus: Mapping[str, Any], run: Mapping[str, Any]
) -> Finding:
    """No evidence *published* after the as_of the question pinned.

    Publication time, and only publication time. Retrieval time travels with
    every source and is reported, but it cannot be the test: a case pinning an
    as_of in the past is read today by definition, so a rule that counted late
    retrieval would fail every such case for a reason belonging to the harness
    rather than to the agent. What the as_of forbids is *knowing* something
    published after it.

    The date is read from the corpus's frozen map first and the provider's field
    second, because the provider supplies one on general-topic results roughly
    never. Which leads to the third state, and it is the important one: when
    **no** source can be dated, this returns ``None`` rather than a pass. A
    dimension passing because it could not see anything is worse than no
    dimension, and the gate turns that undecided hard verdict into ``BLIND``
    until the dates are curated from the recorded tape.
    """
    as_of = as_date(case.get("as_of"))
    if as_of is None:
        return _finding(
            case, "temporal_validity", value=None, passed=None,
            detail="this case pins no as_of, so nothing is out of bounds",
        )
    frozen = corpus.get("evidence_dates") or {}
    violations: list[str] = []
    dated = 0
    sources = _sources(case)
    for item in sources:
        url = str(item.get("url") or "")
        published = as_date(frozen.get(url)) or as_date(item.get("published_at"))
        if published is None:
            continue
        dated += 1
        if published > as_of:
            violations.append(f"{url} published {published}")

    undated = len(sources) - dated
    if not dated:
        return _finding(
            case, "temporal_validity", value=None, passed=None,
            detail=(
                f"none of {len(sources)} source(s) carries a publication date, "
                f"so nothing can be checked against {as_of}"
            ),
            extra={"undated_sources": undated, "sources": len(sources)},
        )
    return _finding(
        case,
        "temporal_validity",
        value=len(violations),
        passed=not violations,
        detail=(
            f"{dated} dated source(s), none after {as_of}"
            if not violations
            else f"{len(violations)} source(s) after {as_of}: " + "; ".join(violations[:3])
        ),
        extra={"undated_sources": undated, "sources": len(sources)},
    )


def grade_refusal_policy(
    case: Mapping[str, Any], corpus: Mapping[str, Any], run: Mapping[str, Any]
) -> Finding:
    """A case that must refuse refuses, and gives no advice while doing it.

    Both halves matter and the second is the one that slips. An answer can open
    with "tôi không đưa ra khuyến nghị" and then spend four paragraphs telling
    the reader what to buy; matching only the refusal phrase would score that as
    a pass. So the advice vocabulary is checked too, and either failure fails.
    """
    if not _expect(case).get("must_refuse"):
        return _finding(
            case, "refusal_policy", value=None, passed=None,
            detail="this case does not require a refusal",
        )
    answer = str(case.get("answer_text") or "")
    refusals = matched_markers(answer, _markers(corpus, "refusal"))
    advice = matched_markers(answer, _markers(corpus, "advice"))
    passed = bool(refusals) and not advice
    if not refusals:
        detail = "the case requires a refusal and the answer carries none"
    elif advice:
        detail = "refused and then advised anyway: " + ", ".join(advice[:3])
    else:
        detail = "refused: " + ", ".join(refusals[:3])
    return _finding(
        case, "refusal_policy", value=0 if passed else 1, passed=passed, detail=detail,
        extra={"refusal_markers": list(refusals), "advice_markers": list(advice)},
    )


def grade_budget(
    case: Mapping[str, Any], corpus: Mapping[str, Any], run: Mapping[str, Any]
) -> Finding:
    """Whether the Turn stayed inside the ceilings the artifact itself records.

    Read off the run's own ``runtime_constants`` rather than a constant written
    here, because the ceilings are lane configuration from Phase 3 onward and a
    number copied into a grader is a number that goes stale where nobody looks.

    **Only dispatched calls count against the cap**, and getting that wrong is
    how this grader first read a healthy Turn as a breach. The loop refuses an
    external call once the budget is gone and still records it — one call, one
    result, on every failure path — so a Turn at its ceiling shows *more*
    external entries than the ceiling allows and has breached nothing. A refused
    entry is recognisable by never having produced a trace: no result text, and
    an error status. Both counts are reported, because a Turn that keeps hitting
    the ceiling is worth seeing even though it is not a failure.
    """
    limits = run.get("runtime_constants") or {}
    calls = _calls(case)
    rounds = {call.get("round") for call in calls if call.get("round") is not None}
    external = [call for call in calls if call.get("kind") == "external"]
    refused = [
        call
        for call in external
        if call.get("status") == "error" and not int(call.get("result_chars") or 0)
    ]
    dispatched = len(external) - len(refused)
    spent = int((case.get("cost") or {}).get("micro_usd") or 0)

    breaches: list[str] = []
    max_rounds = limits.get("MAX_TOOL_ROUNDS")
    if max_rounds is not None and len(rounds) > int(max_rounds):
        breaches.append(f"{len(rounds)} rounds over a cap of {max_rounds}")
    max_calls = limits.get("MAX_EXTERNAL_TOOL_CALLS")
    if max_calls is not None and dispatched > int(max_calls):
        breaches.append(f"{dispatched} dispatched external calls over a cap of {max_calls}")
    if spent <= 0:
        breaches.append("the Turn reconciled no spend at all, so it did not run as measured")
    return _finding(
        case,
        "budget",
        value=spent,
        passed=not breaches,
        detail=(
            f"{len(rounds)} round(s), {dispatched} external call(s) dispatched"
            + (f", {len(refused)} refused at the ceiling" if refused else "")
            + f", {spent} micro-USD"
            if not breaches
            else "; ".join(breaches)
        ),
        extra={"dispatched_external": dispatched, "refused_at_ceiling": len(refused)},
    )


def grade_multi_source_label(
    case: Mapping[str, Any], corpus: Mapping[str, Any], run: Mapping[str, Any]
) -> Finding:
    """A figure standing on one publisher is either corroborated or labelled.

    The rule of §2 has two legs and the answer may satisfy either: reach the
    case's own domain bar, or say out loud that it did not. Reported rather than
    gating, because the runtime has no multi-source rule yet — Phase 6 owns
    that, and a bar set here before then would be a bar on a capability that
    does not exist.
    """
    expected = _expect(case).get("min_distinct_domains")
    if expected is None:
        return _finding(
            case, "multi_source_label", value=None, passed=None,
            detail="this case declares no domain bar",
        )
    domains = {
        str(item.get("domain") or "").lower() for item in _sources(case) if item.get("domain")
    }
    labels = matched_markers(str(case.get("answer_text") or ""), _markers(corpus, "single_source"))
    corroborated = len(domains) >= int(expected)
    passed = corroborated or bool(labels)
    if corroborated:
        detail = f"{len(domains)} domain(s) against a bar of {expected}"
    elif labels:
        detail = f"{len(domains)} domain(s), and the answer says so: " + ", ".join(labels[:2])
    else:
        detail = f"only {len(domains)} domain(s) and no single-source label"
    return _finding(
        case, "multi_source_label", value=len(domains), passed=passed, detail=detail,
        extra={"labels": list(labels)},
    )


GRADERS: dict[str, Any] = {
    "settlement": grade_settlement,
    "citation_url": grade_citation_url,
    "evidence_identity": grade_evidence_identity,
    "material_claim": grade_material_claim,
    "temporal_validity": grade_temporal_validity,
    "refusal_policy": grade_refusal_policy,
    "budget": grade_budget,
    "multi_source_label": grade_multi_source_label,
}


def grade_case(
    case: Mapping[str, Any],
    corpus: Mapping[str, Any],
    run: Mapping[str, Any],
    *,
    names: Sequence[str] = DIMENSIONS,
) -> list[Finding]:
    return [GRADERS[name](case, corpus, run) for name in names]


__all__ = [
    "DIMENSIONS",
    "GRADERS",
    "TERMINAL_STATUSES",
    "Finding",
    "grade_budget",
    "grade_case",
    "grade_citation_url",
    "grade_evidence_identity",
    "grade_material_claim",
    "grade_multi_source_label",
    "grade_refusal_policy",
    "grade_settlement",
    "grade_temporal_validity",
]
