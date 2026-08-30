"""How much of a board is picture, and the thresholds that are provisional.

Every number asserted here is a guess with a date on it — the plan resets each
from the distribution of the first fifty real boards. The tests assert the
*mechanism*, and read the constants rather than repeating them, so resetting a
threshold is one edit rather than one edit and a hunt.

Measured on the **compiled** board rather than on the model's plan, because the
two differ by the pictures the server adds — a comparison earns the bars beside
it — and a board marked down for a chart that is on it would be a board marked
down for the compiler doing its job.
"""

from __future__ import annotations

from src.studies import lint
from src.studies.contracts import (
    BoardSection,
    CaptionBlock,
    ResolvedValue,
    VisualBlock,
)


def visual(widget="line_series", frame="f"):
    return VisualBlock(
        widget=widget,
        widget_version=1,
        frame=frame,
        options={},
        span=12,
        source="store",
    )


def caption(text="Một câu."):
    return CaptionBlock(
        template=text,
        text=text,
        refs={
            "a": ResolvedValue(
                text="1", raw=1.0, unit=None, frame="f", row=0, column="c"
            )
        },
        span=12,
    )


def sections(*blocks):
    return [BoardSection(heading=None, blocks=tuple(blocks))]


def test_a_board_of_pictures_scores_full_marks():
    report = lint.score(sections(visual("line_series"), visual("donut")), 3)
    assert report.passed
    assert report.score == 1.0
    assert report.visual_ratio == 1.0


def test_a_board_that_is_mostly_prose_is_named():
    report = lint.score(sections(visual(), caption(), caption()), 3)
    assert "visual_ratio_low" in {v.code for v in report.violations}
    assert report.visual_ratio < lint.MIN_VISUAL_RATIO


def test_two_pictures_and_a_caption_is_under_the_floor():
    """A consequence of the threshold, written down because it surprises.

    Seven tenths means a board needs three pictures before it can carry one
    sentence. The plan set the number before any distribution of real boards
    existed and says so; phase 09 resets it from fifty.
    """
    report = lint.score(sections(visual("a"), visual("b"), caption()), 3)
    assert report.visual_ratio < lint.MIN_VISUAL_RATIO


def test_a_board_of_captions_past_the_narrative_ceiling_is_named():
    long_one = "x" * (lint.MAX_NARRATIVE_CHARS + 1)
    report = lint.score(sections(visual("a"), visual("b"), visual("c"), caption(long_one)), 3)
    assert "narrative_too_long" in {v.code for v in report.violations}
    assert report.narrative_chars > lint.MAX_NARRATIVE_CHARS


def test_a_board_drawing_one_thing_repeatedly_is_a_table():
    report = lint.score(sections(visual(), visual(), visual()), 3)
    assert "widget_kinds_thin" in {v.code for v in report.violations}
    assert report.widget_kinds == 1


def test_one_picture_alone_is_not_a_board_drawing_one_thing_repeatedly():
    """The kinds rule needs more than one visual before it means anything."""
    report = lint.score(sections(visual()), 3)
    assert "widget_kinds_thin" not in {v.code for v in report.violations}


def test_the_score_is_the_fraction_of_rules_met_rather_than_a_verdict():
    """A board that fails one of three reads as two thirds, not as a failure.

    It is stored either way — the grammar decides admission, this decides how
    good the admitted board is — so a score that collapsed to pass/fail would
    throw away the only measurement phase 09 has to set its thresholds from.
    """
    report = lint.score(sections(visual("a"), visual("b"), caption(), caption()), 3)
    assert 0.0 < report.score < 1.0


def test_the_payload_carries_every_measurement_and_not_only_the_verdict():
    payload = lint.score(sections(visual("a"), visual("b")), 3).to_payload()
    assert set(payload) == {
        "score",
        "visualRatio",
        "narrativeChars",
        "kpiCount",
        "widgetKinds",
        "violations",
    }
    assert payload["kpiCount"] == 3


def test_a_board_with_no_blocks_at_all_is_not_divided_by_zero():
    assert lint.score([], 0).visual_ratio == 1.0


def test_the_thresholds_are_constants_in_one_place():
    """Named here so resetting them at phase 09 is a grep with one hit each."""
    assert lint.MIN_VISUAL_RATIO == 0.7
    assert lint.MAX_NARRATIVE_CHARS == 1_200
    assert lint.MIN_WIDGET_KINDS == 2
