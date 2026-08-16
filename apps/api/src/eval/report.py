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

**The fixed ops query's output is in the file, written here.** ``docs/adr/0016``
requires the field reading to appear in the next Eval Report, and the point of
that requirement is reconciliation: the battery scores a frozen fixture and says
nothing about what live traffic did, so the two numbers only ever meet on this
page. Rendered from the snapshot the run carried rather than fetched now, and
never pasted in by hand.
"""

from __future__ import annotations

from pathlib import Path

from src.agent.ops import (
    GROUNDING_FAILED_RATE_THRESHOLD,
    OPS_WINDOW_DAYS,
    OpsSnapshot,
)

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
    lines.extend(_ops_section(result.ops))

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


def _ops_section(ops: OpsSnapshot | None) -> list[str]:
    """What the live service did, beside what the fixture measured.

    ``docs/adr/0016``'s fixed ops query, output required here so that *the
    battery and the field are reconciled instead of drifting apart*. A gate run
    can be green over a frozen exam while production quietly blocks one answer
    in five, and this section is the only place a reader would find out.

    The threshold line comes first and reads as a sentence, because it is the
    one number in this document a person is asked to act on: **``grounding_failed``
    above 5% of Turns over 7 days reopens category B.** No alerting sits behind
    it — one developer and no rotation means an alert would be noise — so being
    legible on the page is the whole of the mechanism.
    """
    lines = ["## The field", ""]
    if ops is None:
        lines.append(
            "The fixed ops query did not run. Its output is required here by "
            "`docs/adr/0016`, so a report without it is a report that was "
            "assembled by hand or by an older build."
        )
        lines.append("")
        return lines

    window = (
        f"`{ops.since.isoformat()}` to `{ops.until.isoformat()}` "
        f"({ops.window_days} days)"
    )
    if not ops.readable:
        lines.append(
            f"**The application store could not be read**, so the field is "
            f"unknown over {window} rather than quiet: `{ops.error}`. The "
            "scores above are unaffected — they are measured on the eval "
            "database — but nothing here has been reconciled against "
            "production."
        )
        lines.append("")
        return lines

    lines.append(f"One fixed read-only query over {window}. No table, no alerting.")
    lines.append("")

    lines.extend(_grounding_headline(ops))
    lines.extend(_ops_tables(ops))
    return lines


def _grounding_headline(ops: OpsSnapshot) -> list[str]:
    """The rate, and the verdict where the rule is entitled to give one.

    Three readings, and only the last of them carries a verdict. **No Turn ran**
    is not "at or below the threshold" — nothing was measured, and a window
    claiming the bar was met is claiming a result it does not have. **A widened
    window** is a useful reading and not the quantity the rule decides on: *5% of
    Turns over 7 days* is one sentence and the span is half of it.
    """
    if not ops.turns:
        return [
            "**No Turn ran in this window**, so there is nothing to read the "
            f"{GROUNDING_FAILED_RATE_THRESHOLD:.0%} `grounding_failed` "
            "threshold against.",
            "",
        ]

    reading = (
        f"**`grounding_failed`: {ops.grounding_failed} of {ops.turns} Turns "
        f"({_rate(ops.grounding_failed, ops.turns)})**"
    )
    if not ops.threshold_applies:
        return [
            f"{reading} — read over {ops.window_days} days rather than "
            f"{OPS_WINDOW_DAYS}, so the "
            f"{GROUNDING_FAILED_RATE_THRESHOLD:.0%} threshold is **not applied "
            "here**. It is stated over seven days, and a different span is a "
            "useful reading rather than the one the rule decides on.",
            "",
        ]

    breached = "**above**" if ops.reopens_category_b else "at or below"
    verdict_line = (
        "> **Category B is reopened.** A sustained share this high means the "
        "Recommendation Gate is blocking answers that were right, not that the "
        "model is fabricating — over-blocking is exactly what category B "
        "measures. Add cases from the flagged messages and re-run; nothing "
        "else changes."
        if ops.reopens_category_b
        else "Category B stands. The threshold exists to catch the Gate "
        "refusing ordinary correct answers, which is how this product would "
        "die quietly."
    )
    return [
        f"{reading} — {breached} the "
        f"{GROUNDING_FAILED_RATE_THRESHOLD:.0%} threshold.",
        "",
        verdict_line,
        "",
    ]


def _ops_tables(ops: OpsSnapshot) -> list[str]:
    """The four distributions, each against the population it was counted over."""
    lines: list[str] = []
    lines.extend(
        _ops_table(
            "Incomplete Turns, by reason",
            "Reason",
            ops.incomplete_reasons,
            ops.turns,
            "No Turn ended incomplete in this window.",
        )
    )
    lines.extend(
        _ops_table(
            "`unknown_tool`, by the tool that was asked for",
            "Tool",
            ops.unknown_tool_calls,
            ops.tool_calls,
            "Nothing reached for a tool that does not exist, in "
            f"{ops.tool_calls} calls.",
            note=(
                "Also `docs/adr/0011`'s demand trigger: these names are the "
                "evidence for whether sandboxed execution is ever worth "
                "revisiting."
            ),
        )
    )
    lines.extend(
        _ops_table(
            "`answer_kind`, over Turns",
            "Kind",
            ops.answer_kinds,
            ops.turns,
            "No Turn ran in this window.",
        )
    )
    lines.extend(
        _ops_table(
            "Flagged messages, by reason",
            "Reason",
            ops.flags,
            ops.flags_total,
            "Nothing was flagged in this window.",
            note=_flag_note(ops),
        )
    )
    return lines


def _flag_note(ops: OpsSnapshot) -> str:
    """Why flags matter, and — when there are any — how many.

    The share column of the table below is *composition*: which reason
    dominates, which is what drives the flag loop.

    **A count and not a rate against Turns**, deliberately. A flag is placed in
    time by ``flagged_at`` and a Turn by ``started_at``, so a flag inside this
    window is often about an answer given outside it. Dividing one by the other
    would print a percentage of two different populations, which is worse than
    printing no percentage at all.
    """
    loop = (
        "A flag confirmed as a genuine failure becomes a new Eval Case, frozen "
        "with its fixture. That is the only sanctioned way this battery grows."
    )
    if not ops.flags_total:
        return loop
    return (
        f"{ops.flags_total} flagged in this window — counted by when they were "
        f"flagged, not by when the answer was given, so this is not a rate "
        f"against the {ops.turns} Turns above. {loop}"
    )


def _ops_table(
    title: str,
    heading: str,
    counts,
    total: int,
    empty: str,
    *,
    note: str | None = None,
) -> list[str]:
    """One signal, with its share of the population it was counted over.

    The share is here rather than left to the reader because every one of these
    counts is meaningless without its denominator — three unknown tool calls is
    a curiosity out of four thousand and an emergency out of twelve.
    """
    lines = [f"### {title}", ""]
    if note:
        lines.append(note)
        lines.append("")
    if not any(counts.values()):
        lines.append(empty)
        lines.append("")
        return lines
    lines.append(f"| {heading} | Count | Share |")
    lines.append("| --- | ---: | ---: |")
    for name, count in counts.items():
        lines.append(f"| `{name}` | {count} | {_rate(count, total)} |")
    lines.append("")
    return lines


def _rate(part: int, whole: int) -> str:
    return "—" if not whole else f"{part / whole * 100:.1f}%"


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
