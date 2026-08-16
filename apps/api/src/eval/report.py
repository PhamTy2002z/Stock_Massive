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


def render_report(result: EvalRunResult) -> str:
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
    lines.append("## Categories")
    lines.append("")
    lines.append("| Category | Cases | Runs | Deterministic passes |")
    lines.append("| --- | ---: | ---: | ---: |")
    for category, bucket in totals["by_category"].items():
        lines.append(
            f"| {category} | {bucket['cases']} | {bucket['runs']} | "
            f"{bucket['passed']} |"
        )
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
        if case.prompt:
            lines.append("> " + case.prompt.replace("\n", "\n> "))
            lines.append("")
        for run in case_result.runs:
            verdict = "pass" if run.passed else "FAIL"
            lines.append(
                f"**Run {run.run_index + 1} — {verdict}** "
                f"(`{run.status}`/`{run.terminal_reason or 'none'}`, "
                f"`{run.answer_kind}`)"
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

    return "\n".join(lines).rstrip() + "\n"


def write_report(result: EvalRunResult, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / report_filename(result)
    path.write_text(render_report(result), encoding="utf-8")
    return path


__all__ = ["render_report", "report_filename", "write_report"]
