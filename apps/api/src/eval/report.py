"""The artifact a run leaves behind, so ``report_path`` points at something.

Deliberately the minimum ``docs/adr/0016`` requires of *this* ticket: the run
id, the mode, the route and exact model, the four versions, per-category totals,
and the **verbatim answers being judged**. The baseline diff, the
``baseline_reset`` rule and the merge rule are the report ticket's, and writing
half of them here would leave two writers for one document.

The verbatim answers are not padding. They are one of three defences against a
rubber-stamped human rubric: the text a reviewer scored is in the file, so a
careless pass leaves a readable trace.

A stopped run gets a report too, and it is the loudest thing in the file. The
alternative — no report when the ceiling is hit — is how a run that measured
nothing comes to be remembered as a run that was never attempted.
"""

from __future__ import annotations

from pathlib import Path

from .harness import EvalRunResult
from .rubric import QUESTIONS, RubricScores
from .verdict import HARD_FAIL_NOTICE, verdict


def report_filename(result: EvalRunResult) -> str:
    """``<date>-<prompt_version>.md`` for a gate run, and never for a smoke one.

    A smoke run has no gating value, so its report must not be able to occupy
    the name a baseline is read from. It carries the mode and a short run id
    instead.
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
            "> **Non-gating.** This is a `smoke` run on the dev route; it does "
            "not exercise the production model and may not be attached to a "
            "pull request."
        )
        lines.append("")

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

    lines.append("## Surfaces")
    lines.append("")
    lines.append("| Surface | Cases | Runs | Deterministic passes |")
    lines.append("| --- | ---: | ---: | ---: |")
    for surface, bucket in totals["by_surface"].items():
        lines.append(
            f"| {surface} | {bucket['cases']} | {bucket['runs']} | "
            f"{bucket['passed']} |"
        )
    lines.append("")

    lines.append("## Cases")
    lines.append("")
    if not result.results:
        lines.append(
            "No Eval Case is registered. The ~56 cases are seeded by the "
            "category tickets; a battery that reported a score over an empty "
            "registry would be reporting nothing."
        )
        lines.append("")
    for case_result in result.results:
        case = case_result.case
        lines.append(
            f"### `{case.id}` — category {case.category.value}, "
            f"{case.surface.value} lane"
        )
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
            lines.append(
                f"**Run {run.run_index + 1} — {mark}** "
                f"(`{run.status}`/`{run.terminal_reason or 'none'}`, "
                f"`{run.answer_kind}`)"
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


def write_report(
    result: EvalRunResult, directory: Path, scores: RubricScores | None = None
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / report_filename(result)
    path.write_text(render_report(result, scores), encoding="utf-8")
    return path


__all__ = ["render_report", "report_filename", "write_report"]
