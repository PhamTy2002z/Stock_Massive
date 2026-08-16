"""The Eval Report: what a gate run leaves for a pull request to carry.

Committed as ``docs/eval/<date>-<prompt_version>.md`` so the baseline has a
**diffable history**, and ``eval_run.report_path`` points at the file. What it
carries is fixed by ``docs/adr/0016``:

- the run id, the mode, the route and exact model, and the four versions;
- per-category scores, **with the two lanes separable**;
- the diff against baseline, including a drop of two case-equivalents or more
  in any category *even while still above threshold*;
- the **verbatim answers being judged**, which is one of the three defences
  against a rubber-stamped human rubric.

Three things this file is deliberate about.

**A stopped run gets a report, and it is the loudest thing in the file.** The
alternative — no report when the ceiling is hit — is how a run that measured
nothing comes to be remembered as a run that was never attempted.

**A smoke run's report cannot occupy the baseline's filename**, and says on its
face that it is non-gating. It does not exercise the production model, so a
reader comparing two reports must not be able to mistake it for one that did.

**A ``baseline_reset`` report shows no diff at all.** Comparing scores across
two fixtures compares two different exams, so the pull request may not claim
*no regression* — and the way to be sure it does not is to give it no numbers
to claim it with.
"""

from __future__ import annotations

from pathlib import Path

from .baseline import (
    CASE_EQUIVALENT_DRIFT,
    CategoryScore,
    category_scores,
    surface_scores,
    thresholds_as_prose,
)
from .cases import EvalSurface
from .harness import CaseResult, CaseRun, EvalRunResult

#: How the human rubric is asked for, in the report it is scored against. Three
#: binary questions per D/E case (``docs/adr/0016``), and binary rather than a
#: scale because a scale is where a careless reviewer's uncertainty hides.
RUBRIC_QUESTIONS: tuple[str, ...] = (
    "Does every directional statement rest on a field present in "
    "`citedFieldIds`?",
    "Is the reading within that field's sanctioned `interpretation`?",
    "Is material contradictory evidence omitted?",
)

#: The categories a person scores. B is a rate a machine can decide from block
#: structure; D and E are not, and they are the two the rubric exists for.
RUBRIC_CATEGORIES = frozenset({"D", "E"})


def report_filename(result: EvalRunResult) -> str:
    """``<date>-<prompt_version>.md`` for a gate run, and never for a smoke one.

    A smoke run has no gating value, so its report must not be able to occupy
    the name a baseline is read from. It carries the mode and a short run id
    instead.

    The gate name is ``docs/adr/0016``'s, verbatim, and it is not unique: two
    gate runs on one day at one ``prompt_version`` write the same file. Left as
    the ADR states it, because the baseline is resolved from ``eval_run`` rather
    than from file names — so a same-day re-run replaces the *document* while
    both rows keep their own totals, and the report a pull request carries is
    the later run's, which is the honest one.
    """
    day = result.started_at.date().isoformat()
    if result.mode.gating:
        return f"{day}-{result.prompt_version}.md"
    return (
        f"{day}-{result.prompt_version}-{result.mode.value}-"
        f"{str(result.run_id)[:8]}.md"
    )


def render_report(result: EvalRunResult) -> str:
    lines: list[str] = [f"# Eval Report — {result.started_at.date().isoformat()}", ""]
    lines.extend(_banners(result))
    lines.extend(_run_table(result))
    lines.extend(_category_table(result))
    lines.extend(_surface_table(result))
    lines.extend(_baseline_section(result))
    lines.extend(_rubric_section(result))
    lines.extend(_case_sections(result))
    return "\n".join(lines).rstrip() + "\n"


def _banners(result: EvalRunResult) -> list[str]:
    """Everything a reader must not be able to miss, above the numbers."""
    lines: list[str] = []
    if not result.complete:
        lines.append(
            f"> **This run did not finish: `{result.stopped_reason}`.** It has no "
            "score. A battery that truncates itself and reports a total is a "
            "battery that lies, so the categories below are counts of what ran "
            "and are not comparable with any baseline."
        )
        lines.append("")
    if not result.mode.gating:
        lines.append(
            "> **Non-gating.** This is a `smoke` run on the dev route. It does "
            "not exercise the production model, may not be attached to a pull "
            "request, and can never become a baseline — the baseline query "
            "reads `gate` runs only."
        )
        lines.append("")

    if result.hard_fails:
        named = ", ".join(f"`{case_id}`" for case_id in result.hard_fails)
        lines.append(
            f"> **Hard fail in {named}.** A registered field was narrated "
            "backwards in sign or direction. This overrides every rate below, "
            "at 1/3, even where the category is above threshold — it is the "
            "exact defect that disqualified the assessed external library, and "
            "it must not dissolve into an average."
        )
        lines.append("")

    comparison = result.baseline
    if comparison is not None and comparison.baseline_reset:
        previous = (
            "there is no previous passing gate run"
            if comparison.baseline is None
            else "the previous baseline was frozen against "
            f"`{comparison.baseline.fixture_version}`"
        )
        lines.append(
            "> **`baseline_reset`.** This run is on fixture "
            f"`{result.fixture_version}` and {previous}, so the previous "
            "baseline is **void**. This pull request may not claim *no "
            "regression*: comparing scores across two fixtures compares two "
            "different exams."
        )
        lines.append("")
    if comparison is not None and comparison.drifted:
        names = ", ".join(f"`{diff.category}`" for diff in comparison.drifted)
        lines.append(
            f"> **Drift in {names}.** A drop of {CASE_EQUIVALENT_DRIFT} "
            "case-equivalents or more does not block the merge and **must be "
            "explained in prose in this pull request**, threshold or no "
            "threshold."
        )
        lines.append("")
    return lines


def _run_table(result: EvalRunResult) -> list[str]:
    lines = ["## Run", "", "| Field | Value |", "| --- | --- |"]
    for name, value in (
        ("run id", str(result.run_id)),
        ("mode", result.mode.value),
        ("route", result.route or "—"),
        ("model", result.model),
        ("started", result.started_at.isoformat()),
        ("finished", result.finished_at.isoformat()),
        ("prompt_version", result.prompt_version),
        ("tool_catalog_version", result.versions.tool_catalog_version),
        ("registry_version", result.versions.registry_version),
        ("fixture_version", result.fixture_version),
        ("profile_version", result.versions.profile_version),
        ("schema_version", result.versions.schema_version),
    ):
        lines.append(f"| {name} | `{value}` |")
    lines.append("")
    return lines


def _category_table(result: EvalRunResult) -> list[str]:
    lines = [
        "## Categories",
        "",
        "Deterministic passes only. Interpretation fidelity and "
        "contradictory-evidence exposure are the blind human rubric's, and "
        "those scores enter the same thresholds **in this pull request** rather "
        "than in the table below.",
        "",
        "| Category | Cases | Runs | Passes | Rate | Threshold | Meets |",
        "| --- | ---: | ---: | ---: | ---: | ---: | :-: |",
    ]
    for score in category_scores(result.category_totals):
        lines.append(
            f"| {score.category} | {score.cases} | {score.runs} | "
            f"{score.passed} | {_pct(score)} | "
            f"{score.threshold * 100:.0f}% | {_mark(score)} |"
        )
    lines.append("")
    lines.append("Thresholds: " + "; ".join(thresholds_as_prose()) + ".")
    lines.append("")
    return lines


def _surface_table(result: EvalRunResult) -> list[str]:
    """The two lanes apart, which is the point of measuring both.

    The nightly Analysis is not exempt from the battery for having a schema, and
    one total covering both would hide the surface that got worse behind the one
    that did not.
    """
    lines = [
        "## Surfaces",
        "",
        "| Surface | Cases | Runs | Passes | Rate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for score in surface_scores(result.category_totals):
        lines.append(
            f"| {score.category} | {score.cases} | {score.runs} | "
            f"{score.passed} | {_pct(score)} |"
        )
    lines.append("")
    return lines


def _baseline_section(result: EvalRunResult) -> list[str]:
    lines = ["## Baseline", ""]
    comparison = result.baseline
    if comparison is None:
        lines.append(
            "No comparison was made. A run that did not finish has no score to "
            "compare, and a smoke run has no gating value to compare with."
        )
        lines.append("")
        return lines
    if comparison.baseline is None:
        lines.append(
            "There is no previous passing gate run in `eval_run`, so this run "
            "establishes the baseline rather than being read against one."
        )
        lines.append("")
        return lines

    baseline = comparison.baseline
    lines.append(
        f"Read against `{baseline.run_id}` "
        f"({baseline.started_at.date().isoformat()}, prompt "
        f"`{baseline.prompt_version}`, fixture `{baseline.fixture_version}`) — "
        "the most recent passing gate run, resolved from `eval_run` by query."
    )
    lines.append("")
    if comparison.baseline_reset:
        lines.append(
            "**Void.** The fixture moved, so no diff is shown: two fixtures are "
            "two exams, and the numbers are not comparable."
        )
        lines.append("")
        return lines

    lines.append("| Category | Baseline | This run | Δ case-equivalents | Drift |")
    lines.append("| --- | ---: | ---: | ---: | :-: |")
    for diff in comparison.diffs:
        lines.append(
            f"| {diff.category} | {_pct(diff.baseline)} | {_pct(diff.current)} | "
            f"{diff.case_equivalents:+.2f} | {'DRIFT' if diff.drifted else '—'} |"
        )
    lines.append("")
    if not comparison.drifted:
        lines.append(
            f"No category lost {CASE_EQUIVALENT_DRIFT} case-equivalents or more."
        )
        lines.append("")
    return lines


def _rubric_section(result: EvalRunResult) -> list[str]:
    """The three binary questions, written where the reviewer will be.

    In the document rather than left to memory, because all three of the ADR's
    defences against rubber-stamping are about making a careless pass leave a
    trace — and a rubric nobody can see in the report is the easiest of them to
    skip.
    """
    quality = [
        item
        for item in result.results
        if item.case.category.value in RUBRIC_CATEGORIES
    ]
    if not quality:
        return []
    lines = [
        "## Human rubric",
        "",
        f"{len(quality)} D/E cases × {len(RUBRIC_QUESTIONS)} binary questions = "
        f"{len(quality) * len(RUBRIC_QUESTIONS)} judgements, scored **blind to "
        "the deterministic results above**, over **every** D/E case and not "
        "only the ones that changed:",
        "",
    ]
    lines.extend(
        f"{index}. {question}"
        for index, question in enumerate(RUBRIC_QUESTIONS, start=1)
    )
    lines.append("")
    lines.append(
        "The answers being judged are embedded verbatim below, so a careless "
        "pass leaves a readable trace."
    )
    lines.append("")
    return lines


def _case_sections(result: EvalRunResult) -> list[str]:
    """Every case, its seat, and the verbatim text the rubric scores.

    Grouped by surface, so the two lanes are separable in the document as well
    as in the totals: a reader looking for what the nightly artifact said should
    not have to filter forty Turns out of the way to find it.
    """
    if not result.results:
        return [
            "## Cases",
            "",
            "No Eval Case ran. A battery that reported a score over an empty "
            "registry would be reporting nothing.",
            "",
        ]

    lines: list[str] = []
    for surface in EvalSurface:
        of_surface = [
            item for item in result.results if item.case.surface is surface
        ]
        if not of_surface:
            continue
        lines.append(f"## Cases — {surface.value} lane")
        lines.append("")
        for case_result in of_surface:
            lines.extend(_one_case(case_result))
    return lines


def _one_case(case_result: CaseResult) -> list[str]:
    case = case_result.case
    lines = [
        f"### `{case.id}` — category {case.category.value}, "
        f"{case_result.passed_runs}/{len(case_result.runs)} deterministic",
        "",
    ]
    if case.intent:
        lines.append(f"*{case.intent}*")
        lines.append("")
    if case.role is not None:
        lines.append(f"Seat: `{case.role.value}`")
        lines.append("")
    if case.prompt:
        lines.append("> " + case.prompt.replace("\n", "\n> "))
        lines.append("")
    for run in case_result.runs:
        lines.extend(_one_run(run))
    return lines


def _one_run(run: CaseRun) -> list[str]:
    verdict = "pass" if run.passed else "FAIL"
    header = (
        f"**Run {run.run_index + 1} — {verdict}** "
        f"(`{run.status}`/`{run.terminal_reason or 'none'}`, `{run.answer_kind}`"
    )
    if run.verdict:
        header += f", verdict `{run.verdict}`"
    lines = [header + ")", ""]
    if run.cited_field_ids:
        lines.append(
            "Cited: " + ", ".join(f"`{item}`" for item in run.cited_field_ids)
        )
        lines.append("")
    for check in run.score.results:
        if not check.applicable:
            continue
        mark = "✓" if check.passed else "✗"
        lines.append(f"- {mark} `{check.check.value}` — {check.detail}")
    lines.append("")
    lines.append("<details><summary>Answer as shown</summary>")
    lines.append("")
    lines.append("```")
    lines.append(run.answer or "(nothing was released)")
    lines.append("```")
    lines.append("")
    lines.append("</details>")
    lines.append("")
    return lines


def _pct(score: CategoryScore) -> str:
    return "—" if not score.runs else f"{score.rate * 100:.0f}%"


def _mark(score: CategoryScore) -> str:
    """Three marks, because a category that did not run is not a third state.

    ``∅`` is a battery that lost its cases. Rendered as a pass it would be the
    quietest possible way for a category to disappear from the exam.
    """
    if not score.cases:
        return "∅"
    return "✓" if score.meets_threshold else "✗"


def write_report(result: EvalRunResult, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / report_filename(result)
    path.write_text(render_report(result), encoding="utf-8")
    return path


__all__ = [
    "RUBRIC_CATEGORIES",
    "RUBRIC_QUESTIONS",
    "render_report",
    "report_filename",
    "write_report",
]
