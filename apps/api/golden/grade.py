"""Score one golden artifact. A pure function: no network, no database, no model.

Grading is separated from running for one reason: a run costs money and a score
must be repeatable for free. Every number here comes out of the artifact file,
so re-grading a months-old run gives the same findings it gave the day it ran.
The judge is a *separate pass* that writes its verdicts into the artifact before
this one reads it, which is what lets a model-scored rubric exist without this
file ever calling a model.

Twelve dimensions now, and the rule that governed the first four governs all of
them: a grader reads only fields the runtime **already emits**. That is the
single rule the two previous eval batteries broke — they scored a contract the
runtime had stopped producing, and every verdict silently became ``unavailable``
until nobody trusted the suite.

Reducing across trials is done here rather than in a grader, and the two
reducers are different on purpose. A **hard** dimension passes a case only when
every trial of it passed: a fabricated citation in one run out of three is a
fabricated citation. A **reported** dimension takes the majority, because it is
describing a tendency rather than enforcing a floor.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .graders import DIMENSIONS as HARD_FIRST_DIMENSIONS
from .graders import GRADERS as NEW_GRADERS
from .graders import Finding
from .text import (
    SMALL_INTEGER_CEILING,
    YEAR_RANGE,
    canonical_numbers,
    covered,
    is_claim,
    parse_number,
)

SCHEMA = "golden.artifact@2"

#: The five axes of roadmap §3, scored by the judge pass and reported here.
JUDGE_AXES = (
    "synthesis",
    "structure_for_intent",
    "counterargument",
    "uncertainty",
    "decision_utility",
)

#: What each dimension is when the corpus is not at hand. The corpus wins where
#: it is available — this exists so that grading a lone artifact still labels
#: its dimensions the way roadmap §10 Phase 1 labels them, rather than calling
#: everything reported and quietly turning a hard gate into a statistic.
DEFAULT_CLASSES: dict[str, str] = {
    "settlement": "hard",
    "citation_url": "hard",
    "evidence_identity": "hard",
    "material_claim": "hard",
    "temporal_validity": "hard",
    "refusal_policy": "hard",
    "budget": "hard",
}


# -- the four original signals ---------------------------------------------
#
# Kept exactly as they scored, including the one that is never allowed to gate.
# They read the same fields they always read; what changed around them is that
# there are now eight dimensions beside them and a corpus to read declarations
# from.


def _sources(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw = case.get("sources") or ()
    return tuple(item for item in raw if isinstance(item, Mapping))


def _finding(case: Mapping[str, Any], grader: str, **kwargs: Any) -> Finding:
    return Finding(
        case_id=str(case.get("id")),
        trial=int(case.get("trial") or 1),
        grader=grader,
        **kwargs,
    )


def grade_distinct_domains(
    case: Mapping[str, Any], corpus: Mapping[str, Any], run: Mapping[str, Any]
) -> Finding:
    """How many different domains the source list beside the answer covers."""
    domains = {
        str(item.get("domain") or "").lower() for item in _sources(case) if item.get("domain")
    }
    expected = (case.get("expect") or {}).get("min_distinct_domains")
    passed = None if expected is None else len(domains) >= int(expected)
    return _finding(
        case,
        "distinct_domains",
        value=len(domains),
        passed=passed,
        detail=", ".join(sorted(domains)) or "no source carried a domain",
    )


def grade_read_depth(
    case: Mapping[str, Any], corpus: Mapping[str, Any], run: Mapping[str, Any]
) -> Finding:
    """How many pages the Turn actually opened, as opposed to searched for."""
    calls = case.get("tool_calls") or ()
    fetches = sum(1 for call in calls if call.get("name") == "fetch_url")
    expected = (case.get("expect") or {}).get("min_pages_read")
    passed = None if expected is None else fetches >= int(expected)
    return _finding(
        case,
        "read_depth",
        value=fetches,
        passed=passed,
        detail=f"{fetches} fetch_url call(s)",
    )


def grade_parallel_rate(
    case: Mapping[str, Any], corpus: Mapping[str, Any], run: Mapping[str, Any]
) -> Finding:
    """The share of this Turn's rounds that issued more than one search.

    The unit is the round, not the Turn. Grouping by Turn instead answers a
    different and much easier question — a Turn spreading two searches over two
    rounds is sequential, and the Turn-level count cannot see that.
    """
    calls = [call for call in (case.get("tool_calls") or ()) if call.get("name") == "web_search"]
    if not calls:
        return _finding(
            case,
            "parallel_rate",
            value=None,
            passed=None,
            detail="the Turn issued no search, so it has no rate",
        )
    rounds: dict[Any, int] = {}
    for call in calls:
        rounds[call.get("round")] = rounds.get(call.get("round"), 0) + 1
    multi = sum(1 for count in rounds.values() if count > 1)
    rate = multi / len(rounds)
    return _finding(
        case,
        "parallel_rate",
        value=round(rate, 4),
        passed=None,
        detail=f"{multi}/{len(rounds)} round(s) issued more than one search",
    )


def grade_uncited_external_number(
    case: Mapping[str, Any], corpus: Mapping[str, Any], run: Mapping[str, Any]
) -> Finding:
    """Numbers in the answer that no page read and no store result supports.

    The definition this implements is written out in ``README.md`` and it is not
    the obvious one: the prompt **forbids** citing sources inside the answer, so
    "cited" here cannot mean a footnote. It means the source list drawn beside
    the answer covers the figure the answer used. It is reported and never
    gating, and the measurement behind that decision is in the README.
    """
    answer = str(case.get("answer_text") or "")
    if not answer.strip():
        return _finding(
            case,
            "uncited_external_number",
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
    return _finding(
        case, "uncited_external_number", value=len(uncited), passed=passed, detail=detail
    )


LEGACY_GRADERS: dict[str, Any] = {
    "distinct_domains": grade_distinct_domains,
    "read_depth": grade_read_depth,
    "parallel_rate": grade_parallel_rate,
    "uncited_external_number": grade_uncited_external_number,
}

_GRADERS: dict[str, Any] = {**NEW_GRADERS, **LEGACY_GRADERS}

#: Dimension names in report order. Written out rather than derived so that a
#: grader removed from the file cannot silently disappear from a report too.
GRADERS: tuple[str, ...] = (*HARD_FIRST_DIMENSIONS, *LEGACY_GRADERS)


# -- reduction -------------------------------------------------------------


def _median(values: Sequence[float | int]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (float(ordered[middle - 1]) + float(ordered[middle])) / 2


def _reduce_case(passes: Sequence[bool], dimension_class: str) -> bool | None:
    """One case's verdict out of its trials.

    Hard dimensions take the conjunction: three trials and one fabricated
    citation is a fabricated citation. Reported dimensions take the majority,
    because they describe a tendency and a single unlucky trial should not
    define it.
    """
    decided = [p for p in passes if p is not None]
    if not decided:
        return None
    if dimension_class == "hard":
        return all(decided)
    return sum(1 for p in decided if p) * 2 > len(decided)


@dataclass
class Report:
    """Every finding, plus the run-level facts a reader needs to trust them."""

    status: str
    findings: list[Finding] = field(default_factory=list)
    run: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    classes: dict[str, str] = field(default_factory=dict)
    judge_scored: int = 0
    judge_unavailable: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "run": self.run,
            "notes": self.notes,
            "findings": [item.as_dict() for item in self.findings],
            "distribution": self.distribution(),
            "dimensions": self.dimensions(),
            "rubric": self.rubric(),
        }

    def rubric(self) -> dict[str, Any]:
        """The five axes of §3, summarised as a spread rather than a verdict.

        A mean and a range, never a pass rate. The rubric is the one part of the
        measurement a model produced, and turning a model's opinion into a
        binary would give it an authority the deterministic dimensions have
        earned and it has not. ``unavailable`` is carried beside the numbers
        because a mean over the cases the judge could read says nothing about
        the ones it could not.
        """
        out: dict[str, Any] = {
            "scored": self.judge_scored,
            "unavailable": self.judge_unavailable,
            "axes": {},
        }
        for axis in JUDGE_AXES:
            values = [
                float(f.value)
                for f in self.findings
                if f.grader == f"judge_{axis}" and f.value is not None
            ]
            out["axes"][axis] = {
                "n": len(values),
                "mean": round(sum(values) / len(values), 2) if values else None,
                "min": min(values) if values else None,
                "max": max(values) if values else None,
            }
        return out

    def class_of(self, dimension: str) -> str:
        return self.classes.get(dimension, DEFAULT_CLASSES.get(dimension, "reported"))

    def distribution(self) -> dict[str, Any]:
        """Per-dimension spread over every case-trial. Deliberately not a threshold."""
        out: dict[str, Any] = {}
        for grader in GRADERS:
            found = [f for f in self.findings if f.grader == grader]
            values = [f.value for f in found if f.value is not None]
            decided = [f.passed for f in found if f.passed is not None]
            out[grader] = {
                "n": len(found),
                "n_scored": len(values),
                "min": min(values) if values else None,
                "median": _median(values) if values else None,
                "max": max(values) if values else None,
                "passed": sum(1 for p in decided if p),
                "decided": len(decided),
            }
        return out

    def dimensions(self) -> dict[str, Any]:
        """Per-dimension verdict reduced to the case, which is the unit that counts.

        Trials of one case are not independent samples of the system — they are
        repeated draws on the same question — so the denominator a confidence
        interval is taken over is the number of **cases**, not the number of
        case-trials. Both are reported; only the first is a sample.
        """
        out: dict[str, Any] = {}
        for grader in GRADERS:
            found = [f for f in self.findings if f.grader == grader]
            by_case: dict[str, list[bool | None]] = {}
            for finding in found:
                by_case.setdefault(finding.case_id, []).append(finding.passed)
            dimension_class = self.class_of(grader)
            verdicts = {
                case_id: _reduce_case(passes, dimension_class)
                for case_id, passes in by_case.items()
            }
            decided = {c: v for c, v in verdicts.items() if v is not None}
            trial_decided = [f.passed for f in found if f.passed is not None]
            out[grader] = {
                "class": dimension_class,
                "cases": len(verdicts),
                "cases_decided": len(decided),
                "cases_passed": sum(1 for v in decided.values() if v),
                "trials_decided": len(trial_decided),
                "trials_passed": sum(1 for p in trial_decided if p),
                "failed_cases": sorted(c for c, v in decided.items() if not v),
            }
        return out


# -- entry points ----------------------------------------------------------


def grade(
    artifact: Mapping[str, Any], corpus: Mapping[str, Any] | None = None
) -> Report:
    """Score a whole artifact. Never turns an unusable run into a pass."""
    schema = artifact.get("schema")
    if schema != SCHEMA:
        return Report(
            status="unusable",
            run={"schema": schema},
            notes=[f"artifact schema is {schema!r}, this grader reads {SCHEMA!r}"],
        )
    corpus = dict(corpus or {})
    run = dict(artifact.get("run") or {})
    cases = [case for case in (artifact.get("cases") or ()) if isinstance(case, Mapping)]
    classes = {
        name: str((body or {}).get("class") or "reported")
        for name, body in (corpus.get("dimensions") or {}).items()
    }
    report = Report(status="graded", run=run, classes=classes)

    if not corpus:
        report.notes.append(
            "no corpus was supplied: marker-reading and date-reading dimensions "
            "see an empty vocabulary, and dimension classes fall back to the "
            "defaults written in grade.py"
        )

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
            f"the run ended {run.get('status')!r}: "
            f"{run.get('incomplete_reason') or 'no reason recorded'}"
        )
    expected = run.get("planned_case_trials")
    if expected is None:
        declared = run.get("corpus_cases")
        expected = None if declared is None else int(declared) * int(run.get("trials") or 1)
    if expected is not None and int(expected) != len(cases):
        report.status = "incomplete"
        report.notes.append(
            f"the run planned {expected} case-trial(s) and the artifact holds {len(cases)}"
        )

    for case in cases:
        for name in GRADERS:
            finding = _GRADERS[name](case, corpus, run)
            report.findings.append(
                Finding(
                    case_id=finding.case_id,
                    grader=finding.grader,
                    value=finding.value,
                    passed=finding.passed,
                    detail=finding.detail,
                    trial=finding.trial,
                    dimension_class=report.class_of(name),
                    extra=finding.extra,
                )
            )
        judge = case.get("judge")
        if isinstance(judge, Mapping):
            if judge.get("status") == "scored":
                report.judge_scored += 1
            else:
                report.judge_unavailable += 1
        report.findings.extend(_judge_findings(case))
    return report


def _judge_findings(case: Mapping[str, Any]) -> list[Finding]:
    """The rubric pass's five axes, read off whatever the judge wrote.

    A judge that did not run, or that could not be parsed, produces no finding
    at all rather than a neutral score. A missing rubric score is missing
    information; a middling one is a claim.
    """
    judge = case.get("judge")
    if not isinstance(judge, Mapping) or judge.get("status") != "scored":
        return []
    scores = judge.get("scores") or {}
    out: list[Finding] = []
    for axis in JUDGE_AXES:
        entry = scores.get(axis)
        if isinstance(entry, Mapping):
            score, why = entry.get("score"), str(entry.get("why") or "")
        else:
            score, why = entry, ""
        if score is None:
            continue
        out.append(
            Finding(
                case_id=str(case.get("id")),
                trial=int(case.get("trial") or 1),
                grader=f"judge_{axis}",
                value=float(score),
                passed=None,
                detail=why or f"{axis} scored {score}",
                dimension_class="reported",
            )
        )
    return out


def load_corpus(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def corpus_beside(artifact: Mapping[str, Any], root: Path) -> dict[str, Any]:
    """The corpus this artifact names, if it is sitting next to the harness.

    Resolved by ``corpus_id`` rather than by a path recorded in the artifact,
    because a path recorded on one machine is a path that does not exist on the
    next one. A corpus that cannot be found is not an error — grading proceeds
    and the report says which dimensions are reading an empty vocabulary.
    """
    corpus_id = str((artifact.get("run") or {}).get("corpus_id") or "")
    candidate = root / f"{corpus_id}.json"
    if corpus_id and candidate.exists():
        return load_corpus(candidate)
    return {}


def grade_file(path: str | Path, corpus_path: str | Path | None = None) -> Report:
    artifact = json.loads(Path(path).read_text(encoding="utf-8"))
    if corpus_path is not None:
        corpus = load_corpus(corpus_path)
    else:
        corpus = corpus_beside(artifact, Path(__file__).resolve().parent)
    return grade(artifact, corpus)


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Score a golden artifact.")
    parser.add_argument("artifact", help="path to a golden artifact JSON file")
    parser.add_argument(
        "--corpus",
        default=None,
        help="the corpus the artifact was run from; found by corpus_id when omitted",
    )
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)

    report = grade_file(args.artifact, args.corpus)
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2, default=str))
    else:
        print(f"status: {report.status}")
        for note in report.notes:
            print(f"  note: {note}")
        print()
        for grader, body in report.dimensions().items():
            print(
                f"{grader:26} {body['class']:8} "
                f"cases {body['cases_passed']}/{body['cases_decided']:<4} "
                f"trials {body['trials_passed']}/{body['trials_decided']}"
            )
        print()
        for finding in report.findings:
            mark = {True: "pass", False: "FAIL", None: "  - "}[finding.passed]
            print(
                f"[{mark}] {finding.case_id:10} t{finding.trial} "
                f"{finding.grader:26} {finding.detail}"
            )
    # A grader run is a measurement, not a gate. ``gate.py`` owns the verdict,
    # so this exits non-zero only when the artifact cannot be scored at all.
    return 0 if report.status != "unusable" else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_CLASSES",
    "GRADERS",
    "JUDGE_AXES",
    "SCHEMA",
    "SMALL_INTEGER_CEILING",
    "YEAR_RANGE",
    "Finding",
    "Report",
    "canonical_numbers",
    "corpus_beside",
    "covered",
    "grade",
    "grade_file",
    "is_claim",
    "load_corpus",
    "parse_number",
]
