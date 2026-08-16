"""Categories B, D and E, the blind rubric, and the fail that overrides a rate.

Five properties, and each of them is a way the battery could report a clean
sheet while measuring nothing.

*B is the category that catches the quiet death.* A Recommendation Gate too
strict to answer anything looks exactly like a careful one from the runtime's
side, so B's assertion has to be structural: a recommendation block, released.

*B and D have to run across four industries.* Emphasis and field membership
differ by industry, and a category that drifted to one representative symbol
would report a rate over a third of what it claims to cover.

*The rubric is blind, complete, and binary.* Three questions, no scale, no
deterministic result on the sheet, and no combined verdict until every question
is answered.

*A backwards sign is a hard fail at 1/3.* Even where its category is above
threshold. That is the exact defect that disqualified the assessed external
library, and the test for it is a category that passes its rate and fails
anyway.

*Human scores weigh what machine scores weigh.* A D run the deterministic layer
liked and a reviewer did not is a failure at full weight.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from src.agent.grounding import BlockKind, Citation, EvidenceSource, ReleasedBlock
from src.agent.loop import TurnOutcome, TurnStatus
from src.agent.prompt import AnswerKind
from src.core.llm import Usage
from src.eval import categories as _seeded  # noqa: F401 - seats the battery
from src.eval.cases import EvalCase, EvalCategory, battery
from src.eval.categories.quality import INDUSTRY_SEATS
from src.eval.rubric import (
    JUDGED_CATEGORIES,
    QUESTIONS,
    QUESTIONS_BY_KEY,
    UNANSWERED,
    RubricIncomplete,
    RubricMismatch,
    assert_covers,
    read_sheet,
    render_sheet,
    sheet_filename,
)
from src.eval.scoring import Check, CheckResult, DeterministicScore, check_sign_fidelity
from src.eval.verdict import HARD_FAIL_CHECKS, THRESHOLDS, verdict

TRADING_DAY = date(2026, 8, 14)
DRAWDOWN = "drawdown_stats.current_drawdown_pct"
RSI = "indicator_pack.rsi_14"


def cases_of(category: EvalCategory) -> tuple[EvalCase, ...]:
    return battery(categories=[category])


class TestTheQualityBatteryCoversWhatItClaims:
    def test_ten_false_refusal_cases_expect_a_recommendation(self):
        cases = cases_of(EvalCategory.FALSE_REFUSAL)
        assert len(cases) == 10
        assert all(case.expectation.requires_recommendation for case in cases)
        assert all(
            case.expectation.answer_kind is AnswerKind.ANALYSIS for case in cases
        )

    def test_false_refusal_runs_only_on_healthy_seats(self):
        """A hedge over a refused window is the Gate working, not over-blocking."""
        from src.eval.roles import FixtureRole

        unhealthy = {
            FixtureRole.BELOW_MIN_SESSIONS,
            FixtureRole.PRICE_BASIS_SEAM,
            FixtureRole.LIMIT_LOCK_DENSE,
            FixtureRole.OUTSIDE_UNIVERSE,
        }
        assert not {case.role for case in cases_of(EvalCategory.FALSE_REFUSAL)} & unhealthy

    def test_eight_interpretation_cases_run_against_planted_values(self):
        cases = cases_of(EvalCategory.INTERPRETATION)
        assert len(cases) == 8
        assert all(
            case.expectation.answer_kind is AnswerKind.ANALYSIS for case in cases
        )

    def test_eight_data_gap_cases_cover_all_five_gaps(self):
        ids = {case.id for case in cases_of(EvalCategory.DATA_GAP)}
        assert len(ids) == 8
        for gap in (
            "insufficient-history",
            "degraded",
            "mixed-price-basis",
            "news-unavailable",
            "excluded",
        ):
            assert any(gap in identifier for identifier in ids), gap

    @pytest.mark.parametrize(
        "category", [EvalCategory.FALSE_REFUSAL, EvalCategory.INTERPRETATION]
    )
    def test_b_and_d_each_run_across_four_industries(self, category):
        """One representative symbol proves nothing about a field profile."""
        seats = {case.role for case in cases_of(category)}
        assert set(INDUSTRY_SEATS) <= seats

    def test_the_data_gap_cases_that_can_forbid_a_field_do(self):
        """"Not filled" is decidable; "exposed" is the rubric's."""
        forbidding = [
            case
            for case in cases_of(EvalCategory.DATA_GAP)
            if case.expectation.forbids_field
        ]
        assert len(forbidding) >= 4

    def test_the_thresholds_are_the_adrs(self):
        assert THRESHOLDS[EvalCategory.FALSE_REFUSAL] == 0.90
        assert THRESHOLDS[EvalCategory.INTERPRETATION] == 0.85
        assert THRESHOLDS[EvalCategory.DATA_GAP] == 0.85


def citation(**overrides) -> Citation:
    defaults = dict(
        call_id="c1",
        tool_name="risk_metrics",
        field_path=f"registered_fields.{DRAWDOWN}.value",
        value=-12.4,
        unit="percent",
        interpretation="Đọc như một mức sụt giảm.",
        claim="descriptive",
        provenance="FIINQUANT",
        as_of=TRADING_DAY.isoformat(),
        stale=False,
        source=EvidenceSource.REGISTERED_FIELD,
        field_name=DRAWDOWN,
    )
    defaults.update(overrides)
    return Citation(**defaults)


def outcome_with(*blocks) -> TurnOutcome:
    return TurnOutcome(
        status=TurnStatus.COMPLETE,
        terminal_reason=None,
        text="\n\n".join(block.text for block in blocks),
        answer_kind=AnswerKind.ANALYSIS,
        rounds_used=1,
        rounds_exhausted=False,
        tool_calls=(),
        usage=Usage(),
        blocks=tuple(blocks),
    )


def block(text: str, *citations, kind=BlockKind.PROSE) -> ReleasedBlock:
    return ReleasedBlock(text=text, kind=kind, citations=tuple(citations))


class TestSignFidelity:
    def test_calling_a_negative_drawdown_positive_fails(self):
        result = check_sign_fidelity(
            outcome_with(block("Mức sụt giảm hiện tại là dương 12,4%.", citation()))
        )
        assert not result.passed
        assert DRAWDOWN in result.detail

    def test_calling_a_non_negative_field_negative_fails(self):
        """A volatility never is, so the claim is wrong whatever the value."""
        result = check_sign_fidelity(
            outcome_with(
                block(
                    "RSI đang ở vùng âm.",
                    citation(field_name=RSI, field_path=f"registered_fields.{RSI}.value", value=61.2),
                )
            )
        )
        assert not result.passed

    def test_describing_a_level_as_falling_is_not_a_sign_claim(self):
        """"RSI giảm" says a level moved and nothing about its sign."""
        result = check_sign_fidelity(
            outcome_with(
                block(
                    "RSI giảm so với tuần trước, còn 61,2.",
                    citation(field_name=RSI, field_path=f"registered_fields.{RSI}.value", value=61.2),
                )
            )
        )
        assert result.passed

    def test_a_correct_sign_claim_passes(self):
        result = check_sign_fidelity(
            outcome_with(block("Mức sụt giảm hiện tại là âm 12,4%.", citation()))
        )
        assert result.passed

    def test_a_block_claiming_both_polarities_is_not_attributed(self):
        """Two claims and two fields is an attribution this layer cannot make."""
        result = check_sign_fidelity(
            outcome_with(
                block(
                    "Một chỉ số dương và một chỉ số âm.",
                    citation(),
                    citation(field_name=RSI, value=61.2),
                )
            )
        )
        assert result.passed

    def test_a_block_citing_nothing_registered_is_not_scored(self):
        result = check_sign_fidelity(
            outcome_with(block("Một đoạn nói về số dương.", ))
        )
        assert result.passed


def run(passed: bool, index: int, *, hard: bool = False):
    check = (
        CheckResult(Check.SIGN_FIDELITY, False, "block 0 calls it positive")
        if hard
        else CheckResult(Check.ANSWER_KIND, passed, "expected analysis")
    )
    return SimpleNamespace(
        run_index=index,
        passed=passed,
        answer=f"Câu trả lời {index}",
        score=DeterministicScore(case_id="case", run_index=index, results=(check,)),
    )


def battery_result(cases, complete: bool = True):
    """A battery run shaped the way ``verdict`` and ``render_sheet`` read one."""
    results = []
    for case_id, category, runs in cases:
        case = SimpleNamespace(
            id=case_id, category=category, prompt="Câu hỏi?", intent="", surface=None
        )
        results.append(
            SimpleNamespace(
                case=case,
                runs=tuple(runs),
                prompt="Câu hỏi?",
                passed_runs=sum(1 for item in runs if item.passed),
            )
        )
    return SimpleNamespace(
        results=tuple(results),
        complete=complete,
        run_id="00000000-0000-0000-0000-000000000000",
        mode=SimpleNamespace(value="gate", gating=True),
        fixture_version="2026-08-14-abc",
        prompt_version="1.2.0",
    )


class TestTheHardFailOverridesEveryRate:
    def test_a_category_above_threshold_still_fails_on_a_backwards_sign(self):
        """The proof the ADR asks for: a rate that is fine and a run that is not.

        Ten D runs, nine of them clean — 90%, comfortably over the 85% the
        category needs. The tenth narrated a registered field backwards, and the
        battery does not pass.
        """
        runs = [run(True, index) for index in range(9)]
        runs.append(run(False, 9, hard=True))
        result = battery_result(
            [("case", EvalCategory.INTERPRETATION, runs)]
        )
        scored = verdict(result)
        category = scored.by_category(EvalCategory.INTERPRETATION)

        assert category.rate == pytest.approx(0.9)
        assert category.rate >= category.threshold
        assert category.met, "the rate alone would have passed this category"
        assert scored.hard_failures
        assert not scored.passed

    def test_the_hard_fail_is_the_sign_check_and_says_so(self):
        assert HARD_FAIL_CHECKS == {Check.SIGN_FIDELITY.value}
        runs = [run(False, 0, hard=True)]
        scored = verdict(battery_result([("case", EvalCategory.INTERPRETATION, runs)]))
        (failure,) = scored.hard_failures
        assert failure.hard
        assert "HARD FAIL" in str(failure)


def sheet_for(result) -> str:
    return render_sheet(result)


def answered(sheet: str, **overrides) -> str:
    """Fill every question with its *passing* answer, then override named ones.

    Passing rather than ``yes``: question three asks whether something was
    omitted, so a sheet of yeses is a sheet of one failure per run — which is
    the confusion this helper exists to keep out of the tests below.

    An override lands on the first run in the sheet, which is run 1.
    """
    filled = sheet
    for question in QUESTIONS:
        passing = "yes" if question.passes_on else "no"
        filled = filled.replace(
            f"- {question.key} = {UNANSWERED}", f"- {question.key} = {passing}"
        )
    for key, value in overrides.items():
        passing = "yes" if QUESTIONS_BY_KEY[key].passes_on else "no"
        filled = filled.replace(f"- {key} = {passing}", f"- {key} = {value}", 1)
    return filled


class TestTheBlindSheet:
    @pytest.fixture
    def result(self):
        return battery_result(
            [
                ("d-case", EvalCategory.INTERPRETATION, [run(True, 0), run(True, 1)]),
                ("e-case", EvalCategory.DATA_GAP, [run(True, 0)]),
                ("b-case", EvalCategory.FALSE_REFUSAL, [run(True, 0)]),
            ]
        )

    def test_it_asks_exactly_three_binary_questions_and_offers_no_scale(self, result):
        sheet = sheet_for(result)
        assert len(QUESTIONS) == 3
        for question in QUESTIONS:
            assert f"- {question.key} = {UNANSWERED}" in sheet
        # Nothing on the sheet invites a number, a fraction or a middle.
        for scale in ("1-5", "0-10", "/5", "partially", "somewhat", "score:"):
            assert scale not in sheet

    def test_it_hides_every_deterministic_result(self, result):
        """The first defence, and a property of the function rather than advice."""
        sheet = sheet_for(result)
        for leak in (
            Check.ANSWER_KIND.value,
            Check.SIGN_FIDELITY.value,
            "expected analysis",
            "FAIL",
            "✓",
            "✗",
        ):
            assert leak not in sheet, leak

    def test_it_carries_the_verbatim_answers_being_judged(self, result):
        sheet = sheet_for(result)
        assert "Câu trả lời 0" in sheet
        assert "Câu trả lời 1" in sheet

    def test_it_covers_every_run_of_every_judged_case(self, result):
        sheet = sheet_for(result)
        assert "`d-case` — run 1" in sheet
        assert "`d-case` — run 2" in sheet
        assert "`e-case` — run 1" in sheet

    def test_it_does_not_ask_about_the_categories_a_machine_settled(self, result):
        assert JUDGED_CATEGORIES == {
            EvalCategory.INTERPRETATION,
            EvalCategory.DATA_GAP,
        }
        assert "`b-case`" not in sheet_for(result)

    def test_the_sheet_sits_beside_its_report(self):
        assert sheet_filename("2026-08-16-1.2.0.md") == "2026-08-16-1.2.0.rubric.md"


class TestReadingAFilledSheet:
    @pytest.fixture
    def result(self):
        return battery_result(
            [("d-case", EvalCategory.INTERPRETATION, [run(True, 0), run(True, 1)])]
        )

    def test_an_unfinished_sheet_is_refused_rather_than_defaulted(self, result):
        with pytest.raises(RubricIncomplete) as raised:
            read_sheet(sheet_for(result))
        assert len(raised.value.missing) == 2 * len(QUESTIONS)

    def test_one_missing_answer_is_still_unfinished(self, result):
        sheet = answered(sheet_for(result))
        sheet = sheet.replace("- cited = yes", f"- cited = {UNANSWERED}", 1)
        with pytest.raises(RubricIncomplete):
            read_sheet(sheet)

    def test_a_finished_sheet_reads_back_run_by_run(self, result):
        scores = read_sheet(answered(sheet_for(result)))
        assert scores.for_run("d-case", 0) == {
            "cited": True,
            "sanctioned": True,
            "contradiction": False,
        }
        assert scores.passed("d-case", 0)

    def test_the_omission_question_passes_on_no(self, result):
        """Question three asks whether something was left out, so yes is a fail."""
        scores = read_sheet(answered(sheet_for(result), contradiction="yes"))
        assert scores.failed_questions("d-case", 0) == ("contradiction",)
        assert scores.failed_questions("d-case", 1) == ()

    def test_a_sheet_that_skipped_a_case_is_refused(self, result):
        filled = answered(sheet_for(result))
        trimmed = filled.split("### `d-case` — run 2")[0]
        scores = read_sheet(trimmed)
        with pytest.raises(RubricMismatch):
            assert_covers(result, scores)

    def test_a_sheet_scoring_a_case_that_did_not_run_is_refused(self, result):
        filled = answered(sheet_for(result))
        filled += (
            "\n### `ghost-case` — run 1\n\n"
            "- cited = yes\n- sanctioned = yes\n- contradiction = no\n"
        )
        with pytest.raises(RubricMismatch):
            assert_covers(result, read_sheet(filled))


class TestHumanScoresWeighWhatMachineScoresWeigh:
    @pytest.fixture
    def result(self):
        return battery_result(
            [
                (
                    "d-case",
                    EvalCategory.INTERPRETATION,
                    [run(True, index) for index in range(3)],
                )
            ]
        )

    def test_a_run_the_machine_liked_and_a_person_did_not_is_a_failure(self, result):
        scores = read_sheet(answered(sheet_for(result), sanctioned="no"))
        scored = verdict(result, scores)
        category = scored.by_category(EvalCategory.INTERPRETATION)

        assert category.passed == 2
        assert category.rate == pytest.approx(2 / 3)
        assert not category.met

    def test_the_failure_names_the_question_and_says_a_person_decided_it(
        self, result
    ):
        scores = read_sheet(answered(sheet_for(result), cited="no"))
        (failure,) = verdict(result, scores).failures

        assert failure.check == "rubric.cited"
        assert failure.human
        assert "rubric" in str(failure)
        assert "citedFieldIds" in failure.detail

    def test_a_verdict_without_the_rubric_says_it_is_not_judged(self, result):
        assert not verdict(result).judged
        assert verdict(result, read_sheet(answered(sheet_for(result)))).judged

    def test_a_category_a_person_does_not_score_is_untouched_by_the_rubric(self):
        result = battery_result(
            [("b-case", EvalCategory.FALSE_REFUSAL, [run(True, 0), run(True, 1)])]
        )
        scores = read_sheet("")
        assert verdict(result, scores).by_category(EvalCategory.FALSE_REFUSAL).met


class TestTheReportRevealsOnlyAfterScoring:
    def test_an_unjudged_report_says_d_and_e_are_half_read(self):
        from src.eval.report import render_report

        result = _real_run_result()
        rendered = render_report(result)
        assert "human rubric has not been entered" in rendered

    def test_a_judged_report_carries_the_answers_it_was_scored_with(self):
        from src.eval.report import render_report

        result = _real_run_result()
        scores = read_sheet(answered(render_sheet(result), sanctioned="no"))
        rendered = render_report(result, scores)

        assert "human rubric has not been entered" not in rendered
        assert "rubric.sanctioned" in rendered
        assert QUESTIONS[1].text in rendered


class TestTheRubricCommand:
    """`make eval-rubric`: no database, and no verdict until the sheet is done."""

    @pytest.fixture
    def artifacts(self, tmp_path):
        from src.eval.record import record_filename, write_record

        result = _real_run_result()
        write_record(result, tmp_path / record_filename("report.md"))
        sheet = tmp_path / sheet_filename("report.md")
        sheet.write_text(render_sheet(result), encoding="utf-8")
        return result, sheet, tmp_path / "report.md"

    def test_an_unfinished_sheet_exits_non_zero_and_writes_no_report(
        self, artifacts, capsys
    ):
        from src.eval.cli import main

        _result, sheet, report = artifacts
        assert main(["rubric", "--sheet", str(sheet)]) == 1
        assert not report.exists()
        assert "unanswered" in capsys.readouterr().err

    def test_a_finished_sheet_rewrites_the_report_with_the_answers_in_it(
        self, artifacts
    ):
        from src.eval.cli import main

        _result, sheet, report = artifacts
        sheet.write_text(answered(sheet.read_text(encoding="utf-8")), encoding="utf-8")

        # This record holds one D case and nothing else, so the exit code is 1
        # for the categories nobody ran — which is the rule under test elsewhere.
        # What matters here is that the report was rewritten with the answers.
        main(["rubric", "--sheet", str(sheet)])
        rendered = report.read_text(encoding="utf-8")
        assert "rubric.sanctioned" in rendered
        assert "human rubric has not been entered" not in rendered
        assert "D | 1 | 3 | 3" in rendered

    def test_a_rubric_that_fails_a_question_names_it_on_stderr(
        self, artifacts, capsys
    ):
        from src.eval.cli import main

        _result, sheet, _report = artifacts
        sheet.write_text(
            answered(sheet.read_text(encoding="utf-8"), sanctioned="no"),
            encoding="utf-8",
        )
        # One of three D runs failed on a person's answer, which is 67% against
        # a category that needs 85%.
        assert main(["rubric", "--sheet", str(sheet)]) == 1
        errors = capsys.readouterr().err
        assert "rubric.sanctioned" in errors
        assert "run 1" in errors


class TestTheRunRecord:
    """The rubric takes longer than the run, so the run has to be written down."""

    def test_a_record_round_trips_into_the_same_verdict(self, tmp_path):
        from src.eval.record import read_record, record_filename, write_record

        result = _real_run_result()
        path = write_record(result, tmp_path / record_filename("report.md"))
        restored = read_record(path)

        assert restored.run_id == result.run_id
        assert restored.fixture_version == result.fixture_version
        assert [item.case.id for item in restored.results] == [
            item.case.id for item in result.results
        ]
        assert verdict(restored).by_category(
            EvalCategory.INTERPRETATION
        ).passed == verdict(result).by_category(EvalCategory.INTERPRETATION).passed

    def test_the_verbatim_answers_survive_the_round_trip(self, tmp_path):
        from src.eval.record import read_record, record_filename, write_record

        result = _real_run_result()
        restored = read_record(
            write_record(result, tmp_path / record_filename("report.md"))
        )
        assert [run.answer for run in restored.results[0].runs] == [
            run.answer for run in result.results[0].runs
        ]

    def test_a_record_naming_a_case_this_build_does_not_seat_is_refused(
        self, tmp_path
    ):
        """A record of a different exam is not a record of this one."""
        import json

        from src.eval.record import RecordUnreadable, as_wire, read_record

        payload = as_wire(_real_run_result())
        payload["results"][0]["case_id"] = "d-a-case-nobody-wrote"
        path = tmp_path / "record.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(RecordUnreadable):
            read_record(path)

    def test_the_sheet_written_from_a_record_is_the_sheet_written_from_the_run(
        self, tmp_path
    ):
        from src.eval.record import read_record, record_filename, write_record

        result = _real_run_result()
        restored = read_record(
            write_record(result, tmp_path / record_filename("report.md"))
        )
        assert render_sheet(restored) == render_sheet(result)


def _real_run_result():
    """A genuine ``EvalRunResult``, because the report reads more of it."""
    import uuid
    from datetime import datetime, timezone

    from src.eval.harness import CaseResult, CaseRun, EvalMode, EvalRunResult
    from src.eval.versions import PinnedVersions

    case = next(iter(cases_of(EvalCategory.INTERPRETATION)))
    runs = tuple(
        CaseRun(
            run_index=index,
            score=DeterministicScore(
                case_id=case.id,
                run_index=index,
                results=(CheckResult(Check.ANSWER_KIND, True, "analysis"),),
            ),
            answer=f"Câu trả lời {index}",
            status="complete",
            terminal_reason=None,
            answer_kind="analysis",
            tool_calls=(),
        )
        for index in range(3)
    )
    stamp = datetime(2026, 8, 16, tzinfo=timezone.utc)
    return EvalRunResult(
        run_id=uuid.UUID(int=1),
        mode=EvalMode.GATE,
        route="https://eval.example",
        model="eval-model",
        versions=PinnedVersions("r", "p", "t", "s"),
        prompt_version="1.2.0",
        fixture_version="2026-08-14-abc",
        started_at=stamp,
        finished_at=stamp,
        results=(CaseResult(case=case, runs=runs, prompt="Câu hỏi?"),),
    )
