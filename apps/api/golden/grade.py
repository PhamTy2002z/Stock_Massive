"""Score one golden artifact. A pure function: no network, no database, no model.

Grading is separated from running for one reason: a run costs money and a score
must be repeatable for free. Every number here comes out of the artifact file,
so re-grading a months-old run gives the same findings it gave the day it ran.

The four graders read only fields the runtime **already emits**. That is the
single rule the two previous eval batteries broke: they scored a contract the
runtime had stopped producing, and every verdict silently became ``unavailable``
until nobody trusted the suite. A grader for a field that does not exist in a
real artifact does not belong in this file, however easy it would be to write.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

SCHEMA = "golden.artifact@1"

#: Grader names, in report order. Written out rather than derived so that a
#: grader removed from the file cannot silently disappear from a report too.
GRADERS = (
    "distinct_domains",
    "read_depth",
    "parallel_rate",
    "uncited_external_number",
)

#: A bare integer at or below this is a count, a rank or a month far more often
#: than it is a claim about the world, and treating it as a claim buries the
#: real findings in noise.
SMALL_INTEGER_CEILING = 12

#: A bare four-digit integer in this range is read as a year, not as a figure.
YEAR_RANGE = range(1900, 2100)

_NUMBER = re.compile(r"\d[\d.,]*")
_TRAILING_SEPARATORS = re.compile(r"[.,]+$")


@dataclass(frozen=True)
class Finding:
    """One grader's verdict on one case."""

    case_id: str
    grader: str
    value: float | int | None
    passed: bool | None
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "grader": self.grader,
            "value": self.value,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass
class Report:
    """Every finding, plus the run-level facts a reader needs to trust them."""

    status: str
    findings: list[Finding] = field(default_factory=list)
    run: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "run": self.run,
            "notes": self.notes,
            "findings": [item.as_dict() for item in self.findings],
            "distribution": self.distribution(),
        }

    def distribution(self) -> dict[str, Any]:
        """Per-grader spread. Deliberately not a threshold.

        Phase 08 sets thresholds after looking at this. Setting one here would
        be the same mistake the last battery made: a subtle bar on an exam
        nobody had sat yet.
        """
        out: dict[str, Any] = {}
        graders = GRADERS
        if self.run.get("mode") == "signal_desk":
            from .graders_signal_desk import GRADERS as SIGNAL_DESK_GRADERS

            graders = SIGNAL_DESK_GRADERS
        for grader in graders:
            values = [
                f.value for f in self.findings if f.grader == grader and f.value is not None
            ]
            passes = [f.passed for f in self.findings if f.grader == grader]
            decided = [p for p in passes if p is not None]
            out[grader] = {
                "n": len(passes),
                "n_scored": len(values),
                "min": min(values) if values else None,
                "median": _median(values) if values else None,
                "max": max(values) if values else None,
                "passed": sum(1 for p in decided if p),
                "decided": len(decided),
            }
        return out


def _median(values: Sequence[float | int]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (float(ordered[middle - 1]) + float(ordered[middle])) / 2


# -- numbers ---------------------------------------------------------------


def canonical_numbers(text: str) -> set[Decimal]:
    """Every number in ``text``, as one canonical value each.

    Vietnamese and English number formats share the same two separators with
    opposite meanings — ``1.234,5`` and ``1,234.5`` are the same quantity — so a
    string comparison would call an answer uncited purely because the page that
    supports it writes numbers the other way round. Canonicalising both sides
    into :class:`Decimal` is what makes the comparison mean what it says.
    """
    found: set[Decimal] = set()
    for match in _NUMBER.finditer(text or ""):
        value = parse_number(match.group(0))
        if value is not None:
            found.add(value)
    return found


def parse_number(token: str) -> Decimal | None:
    """One numeric token as a value, or ``None`` when it is not one."""
    cleaned = _TRAILING_SEPARATORS.sub("", token.strip())
    if not cleaned or not cleaned[0].isdigit():
        return None
    dots = cleaned.count(".")
    commas = cleaned.count(",")
    if dots and commas:
        # Whichever separator comes last is the decimal point.
        decimal_sep = "." if cleaned.rfind(".") > cleaned.rfind(",") else ","
    elif dots or commas:
        sep = "." if dots else ","
        groups = cleaned.split(sep)
        # ``1.234`` groups as thousands, ``1.23`` cannot: a thousands group is
        # always exactly three digits and never the first one.
        thousands = len(groups) > 1 and all(len(g) == 3 for g in groups[1:])
        decimal_sep = None if thousands else sep
    else:
        decimal_sep = None

    if decimal_sep is None:
        digits = cleaned.replace(".", "").replace(",", "")
    else:
        other = "," if decimal_sep == "." else "."
        digits = cleaned.replace(other, "").replace(decimal_sep, ".")
    try:
        return Decimal(digits).normalize()
    except (InvalidOperation, ValueError):
        return None


def is_claim(value: Decimal) -> bool:
    """Whether a number is worth asking for a source for.

    Counts, months and years are numbers an answer produces on its own; asking
    a page to support them would make every case fail for reasons that have
    nothing to do with evidence.
    """
    if value != value.to_integral_value():
        return True
    integral = int(value)
    if abs(integral) <= SMALL_INTEGER_CEILING:
        return False
    if integral in YEAR_RANGE and len(str(abs(integral))) == 4:
        return False
    return True


def covered(value: Decimal, evidence: Iterable[Decimal]) -> bool:
    """Whether one answer number is supported by one of the evidence numbers.

    Exact first, then rounding: an answer that says ``12,3`` where the page says
    ``12,34`` has rounded rather than invented, and a grader that cannot tell
    those apart would spend its findings on honest sentences.
    """
    places = -value.as_tuple().exponent
    for candidate in evidence:
        if candidate == value:
            return True
        if places >= 0:
            try:
                if round(candidate, places) == value:
                    return True
            except (InvalidOperation, ValueError):
                continue
    return False


# -- graders ---------------------------------------------------------------


def _sources(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw = case.get("sources") or ()
    return tuple(item for item in raw if isinstance(item, Mapping))


def grade_distinct_domains(case: Mapping[str, Any]) -> Finding:
    """How many different domains the source list beside the answer covers."""
    domains = {
        str(item.get("domain") or "").lower()
        for item in _sources(case)
        if item.get("domain")
    }
    expected = (case.get("expect") or {}).get("min_distinct_domains")
    passed = None if expected is None else len(domains) >= int(expected)
    return Finding(
        case_id=str(case.get("id")),
        grader="distinct_domains",
        value=len(domains),
        passed=passed,
        detail=", ".join(sorted(domains)) or "no source carried a domain",
    )


def grade_read_depth(case: Mapping[str, Any]) -> Finding:
    """How many pages the Turn actually opened, as opposed to searched for."""
    calls = case.get("tool_calls") or ()
    fetches = sum(1 for call in calls if call.get("name") == "fetch_url")
    expected = (case.get("expect") or {}).get("min_pages_read")
    passed = None if expected is None else fetches >= int(expected)
    return Finding(
        case_id=str(case.get("id")),
        grader="read_depth",
        value=fetches,
        passed=passed,
        detail=f"{fetches} fetch_url call(s)",
    )


def grade_parallel_rate(case: Mapping[str, Any]) -> Finding:
    """The share of this Turn's rounds that issued more than one search.

    The unit is the round, not the Turn. Grouping by Turn instead answers a
    different and much easier question — a Turn spreading two searches over two
    rounds is sequential, and the Turn-level count cannot see that.
    """
    calls = [call for call in (case.get("tool_calls") or ()) if call.get("name") == "web_search"]
    if not calls:
        return Finding(
            case_id=str(case.get("id")),
            grader="parallel_rate",
            value=None,
            passed=None,
            detail="the Turn issued no search, so it has no rate",
        )
    rounds: dict[Any, int] = {}
    for call in calls:
        rounds[call.get("round")] = rounds.get(call.get("round"), 0) + 1
    multi = sum(1 for count in rounds.values() if count > 1)
    rate = multi / len(rounds)
    return Finding(
        case_id=str(case.get("id")),
        grader="parallel_rate",
        value=round(rate, 4),
        passed=None,
        detail=f"{multi}/{len(rounds)} round(s) issued more than one search",
    )


def grade_uncited_external_number(case: Mapping[str, Any]) -> Finding:
    """Numbers in the answer that no page read and no store result supports.

    The definition this implements is written out in ``README.md`` and it is not
    the obvious one: the prompt **forbids** citing sources inside the answer, so
    "cited" here cannot mean a footnote. It means the source list drawn beside
    the answer covers the figure the answer used.
    """
    answer = str(case.get("answer_text") or "")
    if not answer.strip():
        return Finding(
            case_id=str(case.get("id")),
            grader="uncited_external_number",
            value=None,
            passed=None,
            detail="the Turn produced no answer text to check",
        )
    evidence = canonical_numbers(str(case.get("external_evidence_text") or ""))
    evidence |= canonical_numbers(str(case.get("store_evidence_text") or ""))
    question = canonical_numbers(str(case.get("question") or ""))

    uncited = sorted(
        value
        for value in canonical_numbers(answer)
        if is_claim(value) and value not in question and not covered(value, evidence)
    )
    required = bool((case.get("expect") or {}).get("must_cite_external_numbers"))
    passed = (len(uncited) == 0) if required else None
    detail = (
        "every figure is supported"
        if not uncited
        else "unsupported: " + ", ".join(str(v) for v in uncited[:10])
    )
    return Finding(
        case_id=str(case.get("id")),
        grader="uncited_external_number",
        value=len(uncited),
        passed=passed,
        detail=detail,
    )


_GRADERS = {
    "distinct_domains": grade_distinct_domains,
    "read_depth": grade_read_depth,
    "parallel_rate": grade_parallel_rate,
    "uncited_external_number": grade_uncited_external_number,
}


def grade(artifact: Mapping[str, Any]) -> Report:
    """Score a whole artifact. Never turns an unusable run into a pass."""
    schema = artifact.get("schema")
    if schema != SCHEMA:
        return Report(
            status="unusable",
            run={"schema": schema},
            notes=[f"artifact schema is {schema!r}, this grader reads {SCHEMA!r}"],
        )
    run = dict(artifact.get("run") or {})
    cases = [case for case in (artifact.get("cases") or ()) if isinstance(case, Mapping)]
    report = Report(status="graded", run=run)

    if not cases:
        report.status = "unusable"
        report.notes.append("the artifact holds no case")
        return report

    # A half-green run is not a pass. A run that stopped at its ceiling, lost a
    # case or ran a different corpus than it claims still gets scored — a reader
    # wants the numbers — but its status says out loud that it is not a verdict.
    if run.get("status") != "complete":
        report.status = "incomplete"
        report.notes.append(
            f"the run ended {run.get('status')!r}: {run.get('incomplete_reason') or 'no reason recorded'}"
        )
    expected_cases = run.get("corpus_cases")
    if expected_cases is not None and int(expected_cases) != len(cases):
        report.status = "incomplete"
        report.notes.append(
            f"the corpus declares {expected_cases} case(s) and the artifact holds {len(cases)}"
        )

    if run.get("mode") == "signal_desk":
        from .graders_signal_desk import (
            COST_P50_CEILING_MICRO_USD,
            EXPECTATION_GRADERS,
            FIXED_GRADERS,
            grade_case,
        )

        for case in cases:
            report.findings.extend(grade_case(case))
        fixed_pass = all(
            finding.passed is True
            for finding in report.findings
            if finding.grader in FIXED_GRADERS
        )
        per_case: list[bool] = []
        for case in cases:
            case_id = str(case.get("id"))
            decided = [
                finding.passed
                for finding in report.findings
                if finding.case_id == case_id
                and finding.grader in FIXED_GRADERS + EXPECTATION_GRADERS
                and finding.passed is not None
            ]
            per_case.append(bool(decided) and all(decided))
        case_rate = sum(per_case) / len(per_case)
        costs = [int((case.get("cost") or {}).get("micro_usd") or 0) for case in cases]
        cost_p50 = _median(costs)
        report.run["signal_desk_gate"] = {
            "fixed_invariants_pass": fixed_pass,
            "case_pass_rate": round(case_rate, 4),
            "case_pass_threshold": 0.9,
            "cost_p50_micro_usd": cost_p50,
            "cost_ceiling_micro_usd": COST_P50_CEILING_MICRO_USD,
            "passed": fixed_pass
            and case_rate >= 0.9
            and cost_p50 <= COST_P50_CEILING_MICRO_USD,
        }
    else:
        for case in cases:
            for name in GRADERS:
                report.findings.append(_GRADERS[name](case))
    return report


def grade_file(path: str | Path) -> Report:
    return grade(json.loads(Path(path).read_text(encoding="utf-8")))


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Score a golden artifact.")
    parser.add_argument("artifact", help="path to a golden artifact JSON file")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)

    report = grade_file(args.artifact)
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2, default=str))
    else:
        print(f"status: {report.status}")
        for note in report.notes:
            print(f"  note: {note}")
        print()
        for grader, spread in report.distribution().items():
            print(
                f"{grader:26} n={spread['n']:<3} "
                f"min={spread['min']} median={spread['median']} max={spread['max']} "
                f"passed={spread['passed']}/{spread['decided']}"
            )
        print()
        for finding in report.findings:
            mark = {True: "pass", False: "FAIL", None: "  - "}[finding.passed]
            print(f"[{mark}] {finding.case_id:10} {finding.grader:26} {finding.detail}")
    # A grader run is a measurement, not a gate. Phase 08 owns the thresholds,
    # so this exits non-zero only when the artifact cannot be scored at all.
    return 0 if report.status != "unusable" else 2


if __name__ == "__main__":
    raise SystemExit(main())
