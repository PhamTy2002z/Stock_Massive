"""The Eval Report: what a pull request carries, and what it may not claim.

The report is the only artifact of a gate run a reviewer actually reads, so
every property here is one a merge could otherwise be waved through on:

*The verbatim answers are in the file.* One of ``docs/adr/0016``'s three
defences against a rubber-stamped human rubric — the text that was scored is
readable, so a careless pass leaves a trace.

*The two lanes are separable.* The nightly Analysis is not exempt for having a
schema, and a total covering both surfaces would hide the one that got worse.

*Drift is surfaced above threshold, and a void baseline shows no diff at all.*
Absolute thresholds catch collapse and miss decay; two fixtures are two exams.

Rendered rather than run: none of this needs a database, and a test that spent
one to assert on a heading would be a slower test asserting the same thing.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.eval.baseline import Baseline, BaselineComparison, compare_to_baseline
from src.eval.cases import (
    AnalysisExpectation,
    EvalCase,
    EvalCategory,
    EvalSurface,
    Expectation,
)
from src.eval.harness import (
    ANALYSIS_ANSWER_KIND,
    CaseResult,
    CaseRun,
    EvalMode,
    EvalRunResult,
)
from src.eval.report import render_report, report_filename
from src.eval.roles import FixtureRole
from src.eval.scoring import Check, CheckResult, DeterministicScore
from src.eval.versions import PinnedVersions

STARTED = datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc)
FINISHED = datetime(2026, 8, 14, 9, 30, tzinfo=timezone.utc)
FIXTURE = "2026-08-14-deadbeef"
TURN_ANSWER = "Vùng giá thường ngày của mã này rộng khoảng 2,4%."
ANALYSIS_ANSWER = "Vùng giá vẫn hẹp.\n\n[news] Không có tin nguồn được duyệt."

VERSIONS = PinnedVersions(
    registry_version="reg-1",
    profile_version="v1",
    tool_catalog_version="tc-1",
    schema_version="schema-1",
)


def score(case_id: str, index: int, *, passed: bool = True) -> DeterministicScore:
    return DeterministicScore(
        case_id=case_id,
        run_index=index,
        results=(
            CheckResult(Check.BLOCK_STRUCTURE, passed, "1 blocks"),
            CheckResult(
                Check.DIRECTION_LEXICON, True, "not asserted", applicable=False
            ),
        ),
    )


def turn_result(case_id: str = "b-1", *, passes: int = 3) -> CaseResult:
    case = EvalCase(
        id=case_id,
        category=EvalCategory.FALSE_REFUSAL,
        surface=EvalSurface.TURN,
        prompt="Cổ phiếu này đang ở vùng giá nào?",
        role=FixtureRole.BANK,
        intent="a legitimate question on a healthy symbol",
    )
    return CaseResult(
        case=case,
        runs=tuple(
            CaseRun(
                run_index=index,
                score=score(case_id, index, passed=index < passes),
                answer=TURN_ANSWER,
                status="completed",
                terminal_reason=None,
                answer_kind="descriptive",
                tool_calls=("get_price_series",),
            )
            for index in range(3)
        ),
    )


def analysis_result(case_id: str = "analysis-d-bank") -> CaseResult:
    case = EvalCase(
        id=case_id,
        category=EvalCategory.INTERPRETATION,
        surface=EvalSurface.ANALYSIS,
        prompt="",
        role=FixtureRole.BANK,
        expectation=Expectation(analysis=AnalysisExpectation(publishes=True)),
        intent="a bank's profile adds three fundamentals no other profile has",
    )
    return CaseResult(
        case=case,
        runs=tuple(
            CaseRun(
                run_index=index,
                score=score(case_id, index),
                answer=ANALYSIS_ANSWER,
                status="ready",
                terminal_reason=None,
                answer_kind=ANALYSIS_ANSWER_KIND,
                tool_calls=(),
                verdict="hold",
                cited_field_ids=("price_zone.ordinary_range_pct",),
            )
            for index in range(3)
        ),
    )


def a_run(
    *,
    mode: EvalMode = EvalMode.GATE,
    results: tuple[CaseResult, ...] = (),
    complete: bool = True,
    stopped_reason: str | None = None,
    baseline: BaselineComparison | None = None,
    fixture_version: str = FIXTURE,
) -> EvalRunResult:
    return EvalRunResult(
        run_id=uuid.UUID(int=7),
        mode=mode,
        route="https://production.example",
        model="production-session",
        versions=VERSIONS,
        prompt_version="v1",
        fixture_version=fixture_version,
        started_at=STARTED,
        finished_at=FINISHED,
        results=results,
        complete=complete,
        stopped_reason=stopped_reason,
        baseline=baseline,
    )


def a_baseline(totals: dict, fixture_version: str = FIXTURE) -> Baseline:
    return Baseline(
        run_id=uuid.UUID(int=3),
        started_at=datetime(2026, 8, 7, 9, 0, tzinfo=timezone.utc),
        prompt_version="v1",
        fixture_version=fixture_version,
        category_totals=totals,
        report_path="docs/eval/2026-08-07-v1.md",
    )


def totals_with(**per_category) -> dict:
    by_category = {
        category.value: {"cases": 0, "runs": 0, "passed": 0}
        for category in EvalCategory
    }
    for name, bucket in per_category.items():
        by_category[name] = dict(
            zip(("cases", "runs", "passed"), bucket, strict=True)
        )
    return {
        "by_category": by_category,
        "by_surface": {},
        "complete": True,
        "stopped_reason": None,
    }


class TestWhatEveryReportCarries:
    def test_the_run_id_mode_route_model_and_four_versions(self):
        rendered = render_report(a_run(results=(turn_result(),)))
        for expected in (
            str(uuid.UUID(int=7)),
            "gate",
            "https://production.example",
            "production-session",
            "reg-1",
            "tc-1",
            FIXTURE,
        ):
            assert expected in rendered

    def test_the_verbatim_answer_of_every_run_is_embedded(self):
        rendered = render_report(a_run(results=(turn_result(),)))
        assert rendered.count(TURN_ANSWER) == 3

    def test_the_prompt_and_the_intent_travel_with_the_case(self):
        """So a reader can tell a model failure from a badly written case."""
        rendered = render_report(a_run(results=(turn_result(),)))
        assert "a legitimate question on a healthy symbol" in rendered
        assert "Cổ phiếu này đang ở vùng giá nào?" in rendered

    def test_a_category_nobody_ran_is_marked_absent_rather_than_passing(self):
        """A battery narrowed to one category must not read as a clean sheet."""
        rendered = render_report(a_run(results=(turn_result(),)))
        categories = rendered.split("## Categories")[1].split("##")[0]
        assert "| A | 0 | 0 | 0 | 3/3 | — |" in categories
        assert "pass" not in categories.split("| A |")[1].split("\n")[0]


class TestTheTwoLanesAreSeparable:
    def test_the_cases_are_grouped_by_the_lane_they_ran_on(self):
        """Registration order interleaves them; a reader should not have to."""
        rendered = render_report(
            a_run(results=(analysis_result(), turn_result()))
        )
        assert rendered.index("`b-1`") < rendered.index("`analysis-d-bank`")
        assert "turn lane" in rendered
        assert "analysis lane" in rendered

    def test_the_surface_table_counts_them_apart(self):
        rendered = render_report(
            a_run(results=(turn_result(), analysis_result()))
        )
        surfaces = rendered.split("## Surfaces")[1].split("## Baseline")[0]
        assert "| turn | 1 | 3 |" in surfaces
        assert "| analysis | 1 | 3 |" in surfaces

    def test_an_analysis_run_shows_its_verdict_and_its_citations(self):
        rendered = render_report(a_run(results=(analysis_result(),)))
        assert "verdict `hold`" in rendered
        assert "`price_zone.ordinary_range_pct`" in rendered

    def test_a_category_both_lanes_measure_is_split_between_them(self):
        """One total for D is where the nightly artifact's regression hides."""
        turn_d = turn_result("d-turn")
        rendered = render_report(
            a_run(
                results=(
                    CaseResult(
                        case=EvalCase(
                            id="d-turn",
                            category=EvalCategory.INTERPRETATION,
                            surface=EvalSurface.TURN,
                            prompt="RSI của mã này nói lên điều gì?",
                            role=FixtureRole.ORDINARY,
                        ),
                        runs=turn_d.runs,
                    ),
                    analysis_result("d-analysis"),
                )
            )
        )
        split = rendered.split("## Surfaces")[1].split("## Baseline")[0]
        assert "| D | turn | 1 | 3 |" in split
        assert "| D | analysis | 1 | 3 |" in split

    def test_a_category_only_one_lane_measures_is_not_split(self):
        """A row saying `analysis 0/0` beside every safety category is noise."""
        rendered = render_report(a_run(results=(turn_result(),)))
        surfaces = rendered.split("## Surfaces")[1].split("## Baseline")[0]
        assert "| B | turn |" not in surfaces


class TestTheDiffAgainstBaseline:
    def test_a_steady_category_reports_no_drift(self):
        totals = totals_with(B=(10, 30, 30))
        comparison = compare_to_baseline(totals, FIXTURE, a_baseline(totals))
        rendered = render_report(
            a_run(results=(turn_result(),), baseline=comparison)
        )
        assert "most recent passing gate run" in rendered
        assert "case-equivalents or more" in rendered
        assert "DRIFT" not in rendered

    def test_a_two_case_drop_is_surfaced_even_above_threshold(self):
        before = totals_with(B=(30, 90, 90))
        after = totals_with(B=(30, 90, 84))
        comparison = compare_to_baseline(after, FIXTURE, a_baseline(before))
        rendered = render_report(
            a_run(results=(turn_result(),), baseline=comparison)
        )
        assert "**Drift in `B`.**" in rendered
        assert "must be explained in prose" in rendered
        assert "-2.00" in rendered

    def test_the_baseline_run_is_named_so_the_comparison_can_be_re_read(self):
        totals = totals_with(B=(10, 30, 30))
        comparison = compare_to_baseline(totals, FIXTURE, a_baseline(totals))
        rendered = render_report(a_run(baseline=comparison))
        assert str(uuid.UUID(int=3)) in rendered


class TestAMovedFixtureVoidsTheClaim:
    def test_a_reset_says_the_baseline_is_void_and_shows_no_diff(self):
        totals = totals_with(B=(10, 30, 30))
        comparison = compare_to_baseline(
            totals, FIXTURE, a_baseline(totals, "2026-07-01-oldfixture")
        )
        rendered = render_report(
            a_run(results=(turn_result(),), baseline=comparison)
        )

        assert "`baseline_reset`" in rendered
        assert "may not claim *no regression*" in rendered
        assert "Δ case-equivalents" not in rendered

    def test_a_first_ever_run_establishes_the_baseline_rather_than_resetting(self):
        """And the document must not say both things at once."""
        comparison = compare_to_baseline(totals_with(), FIXTURE, None)
        rendered = render_report(a_run(baseline=comparison))
        assert "no previous passing gate run" in rendered
        assert "baseline_reset" not in rendered
        assert "may not claim" not in rendered


class TestASmokeReportCannotBecomeABaseline:
    def test_its_filename_cannot_occupy_the_gate_name(self):
        smoke = a_run(mode=EvalMode.SMOKE)
        assert report_filename(smoke) != report_filename(a_run())
        assert "smoke" in report_filename(smoke)

    def test_a_gate_report_is_named_by_date_and_prompt_version(self):
        assert report_filename(a_run()) == "2026-08-14-v1.md"

    def test_it_says_on_its_face_that_it_can_never_be_a_baseline(self):
        rendered = render_report(a_run(mode=EvalMode.SMOKE))
        assert "Non-gating" in rendered
        assert "can never become a baseline" in rendered

    def test_it_carries_no_comparison_at_all(self):
        rendered = render_report(a_run(mode=EvalMode.SMOKE))
        assert "No comparison was made." in rendered


class TestAStoppedRunIsTheLoudestThingInTheFile:
    def test_it_says_it_has_no_score(self):
        rendered = render_report(
            a_run(complete=False, stopped_reason="eval_budget_exhausted")
        )
        assert "did not finish" in rendered
        assert "eval_budget_exhausted" in rendered

    def test_it_is_not_compared_with_anything(self):
        rendered = render_report(
            a_run(complete=False, stopped_reason="lane_budget_exhausted")
        )
        assert "No comparison was made." in rendered


class TestTheOneFailureThatOverridesEveryRate:
    def pointed_backwards(self) -> CaseResult:
        case = EvalCase(
            id="d-3",
            category=EvalCategory.INTERPRETATION,
            surface=EvalSurface.TURN,
            prompt="RSI của mã này nói lên điều gì?",
            role=FixtureRole.ORDINARY,
        )
        return CaseResult(
            case=case,
            runs=(
                CaseRun(
                    run_index=0,
                    score=DeterministicScore(
                        case_id="d-3",
                        run_index=0,
                        results=(
                            CheckResult(
                                Check.SIGN_FIDELITY,
                                False,
                                "block 0 calls drawdown_stats.current_drawdown_pct "
                                "positive and it holds -12.4",
                            ),
                        ),
                    ),
                    answer="Biên độ sụt giảm dương 12,4%.",
                    status="completed",
                    terminal_reason=None,
                    answer_kind="descriptive",
                    tool_calls=(),
                ),
            ),
        )

    def test_one_run_in_three_is_enough_to_name_the_case(self):
        result = a_run(results=(turn_result(), self.pointed_backwards()))
        assert result.hard_fails == ("d-3",)
        assert result.category_totals["hard_fails"] == ["d-3"]

    def test_the_report_says_so_where_the_rates_it_overrides_are_read(self):
        from src.eval.verdict import HARD_FAIL_NOTICE

        rendered = render_report(a_run(results=(self.pointed_backwards(),)))
        assert HARD_FAIL_NOTICE in rendered
        assert "d-3 run 1: sign_fidelity" in rendered

    def test_a_clean_run_names_none(self):
        assert a_run(results=(turn_result(),)).hard_fails == ()


class TestTheHumanRubricIsInTheDocument:
    def test_an_unscored_report_says_so_rather_than_reading_as_judged(self):
        """D and E on their deterministic half alone is not the gating reading."""
        rendered = render_report(a_run(results=(analysis_result(),)))
        assert "The human rubric has not been entered" in rendered

    def test_a_scored_report_carries_the_reviewers_answers_per_case(self):
        from src.eval.rubric import RubricScores

        scores = RubricScores(
            {"analysis-d-bank": {"cited": True, "sanctioned": False}}
        )
        rendered = render_report(a_run(results=(analysis_result(),)), scores)
        assert "`rubric.sanctioned`" in rendered
        assert "The human rubric has not been entered" not in rendered


def test_the_report_directory_is_the_repos_and_not_apps_apis():
    """`make eval` runs from `apps/api`, and the reports belong at the root.

    A relative `docs/eval` resolves to `apps/api/docs/eval` from there — a
    directory nobody reads, beside no ADR, and not the diffable history
    `docs/adr/0016` asks the baseline to have.
    """
    from pathlib import Path

    from src.core.config import Settings

    # The suite runs from `apps/api`, which is also where `make eval` runs.
    resolved = (Path.cwd() / Settings().eval_report_dir).resolve()
    assert resolved == (Path.cwd().parent.parent / "docs" / "eval").resolve()


def test_an_empty_battery_reports_nothing_rather_than_a_clean_sheet():
    rendered = render_report(a_run())
    assert "No Eval Case ran." in rendered


@pytest.mark.parametrize("mode", list(EvalMode))
def test_every_mode_renders_a_report(mode):
    """A run that produced nothing still leaves a document behind.

    No report when the ceiling is hit is how a run that measured nothing comes
    to be remembered as a run nobody attempted.
    """
    assert render_report(a_run(mode=mode)).endswith("\n")
