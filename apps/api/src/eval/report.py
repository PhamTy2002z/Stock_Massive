"""The Eval Report: what a gate run leaves for a pull request to carry.

Committed as ``docs/eval/<date>-<prompt_version>.md`` so the baseline has a
**diffable history**, and ``eval_run.report_path`` points at the file. What it
carries is fixed by ``docs/adr/0016``: the run id, the mode, the route and exact
model, the four versions, per-category scores **with the two lanes separable**,
the diff against baseline, and the **verbatim answers being judged**.

The verbatim answers are not padding. They are one of three defences against a
rubber-stamped human rubric: the text a reviewer scored is in the file, so a
careless pass leaves a readable trace.

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
    SurfaceScore,
    category_scores_by_surface,
    surface_scores,
)
from .cases import EvalSurface
from .harness import EvalRunResult
from .rubric import QUESTIONS, RubricScores
from .verdict import HARD_FAIL_NOTICE, verdict


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
    return f"{day}-{result.prompt_version}-{result.mode.value}-{str(result.run_id)[:8]}.md"


def render_report(
    result: EvalRunResult, scores: RubricScores | None = None
) -> str:
    lines: list[str] = []
    lines.append(f"# Eval Report — {result.started_at.date().isoformat()}")
    lines.append("")
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

    lines.extend(_baseline_banners(result))

    lines.append("## Run")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
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

    totals = result.category_totals
    scored = verdict(result, scores)
    if not scored.judged:
        lines.append(
            "> **The human rubric has not been entered.** D and E are shown on "
            "their deterministic half alone, which is not the reading "
            "`docs/adr/0016` gates on: run `make eval-rubric` and score the "
            "sheet beside this file."
        )
        lines.append("")

    lines.append("## Categories")
    lines.append("")
    lines.append("| Category | Cases | Runs | Passes | Rule | Verdict |")
    lines.append("| --- | ---: | ---: | ---: | --- | --- |")
    for item in scored.categories:
        rule = "3/3" if item.every_run else f"≥ {item.threshold:.0%}"
        mark = "pass" if item.met else ("—" if not item.runs else "**FAIL**")
        lines.append(
            f"| {item.category.value} | {item.cases} | {item.runs} | "
            f"{item.passed} | {rule} | {mark} |"
        )
    lines.append("")

    # Loud, and above the per-category detail, because it overrides all of it.
    if scored.hard_failures:
        lines.append(f"> **{HARD_FAIL_NOTICE}**")
        lines.append("")

    # A category total is not actionable. What a reader does next is open the
    # case that broke, so the case, the run and the property are here rather
    # than only in the per-case section below.
    if scored.failures:
        lines.append("### What broke")
        lines.append("")
        for failure in scored.failures:
            lines.append(f"- {failure}")
        lines.append("")
    elif scored.passed:
        lines.append("Every category met its rule.")
        lines.append("")

    lines.extend(_surface_section(totals))
    lines.extend(_baseline_section(result))

    lines.append("## Cases")
    lines.append("")
    if not result.results:
        lines.append(
            "No Eval Case ran. A battery that reported a score over an empty "
            "registry would be reporting nothing."
        )
        lines.append("")
    for case_result in _by_lane(result):
        case = case_result.case
        lines.append(
            f"### `{case.id}` — category {case.category.value}, "
            f"{case.surface.value} lane"
        )
        lines.append("")
        if case.role is not None:
            lines.append(f"Seat: `{case.role.value}`")
            lines.append("")
        if case.intent:
            lines.append(f"*{case.intent}*")
            lines.append("")
        asked = case_result.prompt or case.prompt
        if asked:
            lines.append("> " + asked.replace("\n", "\n> "))
            lines.append("")
        # The reviewer judged the case on its three answers together, so the
        # answers sit at the case rather than beside one of the runs.
        given = scores.for_case(case.id) if scores is not None else None
        if given:
            for question in QUESTIONS:
                if question.key not in given:
                    continue
                answer = given[question.key]
                tick = "✓" if question.passed(answer) else "✗"
                lines.append(
                    f"- {tick} `rubric.{question.key}` — "
                    f"{'yes' if answer else 'no'}: {question.text}"
                )
            lines.append("")
        for run in case_result.runs:
            mark = "pass" if run.passed else "FAIL"
            header = (
                f"**Run {run.run_index + 1} — {mark}** "
                f"(`{run.status}`/`{run.terminal_reason or 'none'}`, "
                f"`{run.answer_kind}`"
            )
            if run.verdict:
                header += f", verdict `{run.verdict}`"
            lines.append(header + ")")
            lines.append("")
            if run.cited_field_ids:
                lines.append(
                    "Cited: "
                    + ", ".join(f"`{item}`" for item in run.cited_field_ids)
                )
                lines.append("")
            for check in run.score.results:
                if not check.applicable:
                    continue
                tick = "✓" if check.passed else "✗"
                lines.append(f"- {tick} `{check.check.value}` — {check.detail}")
            lines.append("")
            lines.append("<details><summary>Answer as shown</summary>")
            lines.append("")
            lines.append("```")
            lines.append(run.answer or "(nothing was released)")
            lines.append("```")
            lines.append("")
            lines.append("</details>")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _by_lane(result: EvalRunResult) -> list:
    """Every case, grouped by the surface it ran on.

    Grouped so the two lanes are separable in the document as well as in the
    totals: a reader looking for what the nightly artifact said should not have
    to filter forty Turns out of the way to find it. Registration order is kept
    within each lane, because that is the order the battery ran them in.
    """
    return [
        case_result
        for surface in EvalSurface
        for case_result in result.results
        if case_result.case.surface is surface
    ]


def _baseline_banners(result: EvalRunResult) -> list[str]:
    """The two things this pull request may owe prose about, before the numbers."""
    comparison = result.baseline
    if comparison is None:
        return []
    lines: list[str] = []
    if comparison.baseline_reset:
        frozen = (
            comparison.baseline.fixture_version
            if comparison.baseline is not None
            else "an unrecorded fixture"
        )
        lines.append(
            "> **`baseline_reset`.** This run is on fixture "
            f"`{result.fixture_version}` and the previous baseline was frozen "
            f"against `{frozen}`, so that baseline is **void**. This pull "
            "request may not claim *no regression*: comparing scores across two "
            "fixtures compares two different exams."
        )
        lines.append("")
    if comparison.drifted:
        names = ", ".join(f"`{diff.category}`" for diff in comparison.drifted)
        lines.append(
            f"> **Drift in {names}.** A drop of {CASE_EQUIVALENT_DRIFT} "
            "case-equivalents or more does not block the merge and **must be "
            "explained in prose in this pull request**, threshold or no "
            "threshold."
        )
        lines.append("")
    return lines


def _surface_section(totals) -> list[str]:
    """The two lanes apart, which is the point of measuring both.

    The nightly Analysis is not exempt from the battery for having a schema, and
    one total covering both surfaces would hide the one that got worse behind
    the one that did not — first for the run as a whole, then for each category
    both lanes actually measure.
    """
    lines = [
        "## Surfaces",
        "",
        "| Surface | Cases | Runs | Deterministic passes | Rate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for score in surface_scores(totals):
        lines.append(
            f"| {score.surface} | {score.cases} | {score.runs} | "
            f"{score.passed} | {_pct(score)} |"
        )
    lines.append("")

    shared = category_scores_by_surface(totals)
    if shared:
        lines.append(
            "Where both lanes measure the same category, they are separated "
            "here. One total is where a regression in the nightly artifact "
            "hides behind a healthy Turn lane."
        )
        lines.append("")
        lines.append("| Category | Surface | Cases | Runs | Passes | Rate |")
        lines.append("| --- | --- | ---: | ---: | ---: | ---: |")
        for category, lanes in shared:
            for score in lanes:
                lines.append(
                    f"| {category} | {score.surface} | {score.cases} | "
                    f"{score.runs} | {score.passed} | {_pct(score)} |"
                )
        lines.append("")
    return lines


def _baseline_section(result: EvalRunResult) -> list[str]:
    """What this run is worth beside the last passing one, or why it is not."""
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


def _pct(score) -> str:
    return "—" if not score.runs else f"{score.rate * 100:.0f}%"


def write_report(
    result: EvalRunResult, directory: Path, scores: RubricScores | None = None
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / report_filename(result)
    path.write_text(render_report(result, scores), encoding="utf-8")
    return path


__all__ = ["render_report", "report_filename", "write_report"]
