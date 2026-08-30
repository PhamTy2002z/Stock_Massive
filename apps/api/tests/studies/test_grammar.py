"""What a board is allowed to be, one rule per case.

Thirty-odd assertions on one function, because the grammar is the contract the
model writes against and every one of these rules is a board a reader could not
use. They are grouped by what they protect rather than by which field they read:
a rule about captions and a rule about visuals both exist because of the same
promise, which is that no market number on the board was typed by a model.
"""

from __future__ import annotations

import pytest

from src.studies import grammar


def frame(
    columns=("symbol", "roe"),
    rows=(("VIC", 12.0), ("VCB", 18.0)),
    kind="table",
    unit="%",
):
    return {
        "kind": kind,
        "columns": list(columns),
        "rows": [list(row) for row in rows],
        "unit": unit,
        "labels": {name: name for name in columns},
    }


FRAMES = {"f-a": frame(), "f-b": frame(rows=(("VIC", 9.0),))}


def a_board(**overrides):
    base = {
        "title": "Đối chiếu VIC và VCB",
        "archetype": "compare",
        "kpis": [
            {"label": "ROE VIC", "value": {"frame_id": "f-a", "column": "roe", "row": 0}},
            {"label": "ROE VCB", "value": {"frame_id": "f-a", "column": "roe", "row": 1}},
            {"label": "ROE gần", "value": {"frame_id": "f-b", "column": "roe"}},
        ],
        "sections": [{"heading": "Đối chiếu", "blocks": [{"kind": "visual", "frame_id": "f-a"}]}],
    }
    base.update(overrides)
    return base


def codes(arguments, frames=FRAMES, **kwargs):
    return {
        violation.code
        for violation in grammar.validate(grammar.parse(arguments), frames, **kwargs)
    }


# -- the shape of the arguments -------------------------------------------


def test_a_board_with_no_title_is_not_a_board():
    with pytest.raises(grammar.BoardMalformed, match="title"):
        grammar.parse(a_board(title="  "))


def test_a_board_with_no_sections_is_not_a_board():
    with pytest.raises(grammar.BoardMalformed, match="sections"):
        grammar.parse(a_board(sections=[]))


def test_a_section_with_no_blocks_is_not_a_section():
    with pytest.raises(grammar.BoardMalformed, match="blocks"):
        grammar.parse(a_board(sections=[{"heading": "x", "blocks": []}]))


def test_an_archetype_nothing_knows_is_refused_where_it_is_written():
    with pytest.raises(grammar.BoardMalformed, match="archetype"):
        grammar.parse(a_board(archetype="dashboard"))


def test_a_block_of_neither_kind_is_refused():
    with pytest.raises(grammar.BoardMalformed, match="visual or a caption"):
        grammar.parse(
            a_board(sections=[{"blocks": [{"kind": "chart", "frame_id": "f-a"}]}])
        )


def test_a_visual_with_no_frame_is_refused():
    with pytest.raises(grammar.BoardMalformed, match="no frame_id"):
        grammar.parse(a_board(sections=[{"blocks": [{"kind": "visual"}]}]))


def test_a_caption_with_no_template_is_refused():
    with pytest.raises(grammar.BoardMalformed, match="no template"):
        grammar.parse(a_board(sections=[{"blocks": [{"kind": "caption"}]}]))


def test_a_reference_without_a_column_is_refused():
    with pytest.raises(grammar.BoardMalformed, match="frame_id and a column"):
        grammar.parse(
            a_board(
                kpis=[{"label": "x", "value": {"frame_id": "f-a"}}] * 3,
            )
        )


def test_strict_mode_nulls_are_read_as_absence_rather_than_as_values():
    """Every optional field arrives present and null. None of them is a value."""
    board = grammar.parse(
        {
            "title": "Có null",
            "archetype": None,
            "kpis": None,
            "sections": [
                {
                    "heading": None,
                    "blocks": [
                        {
                            "kind": "visual",
                            "frame_id": "f-a",
                            "widget": None,
                            "columns": None,
                            "template": None,
                            "refs": None,
                        }
                    ],
                }
            ],
            "appendix_frame_id": None,
        }
    )
    assert board.archetype is None
    assert board.kpis == ()
    assert board.sections[0].heading is None
    assert board.sections[0].blocks[0].widget is None


# -- the KPI strip ---------------------------------------------------------


def test_a_board_that_leads_with_nothing_is_a_board_with_no_answer():
    assert "board_missing_kpi_strip" in codes(a_board(kpis=[]))


def test_two_figures_are_a_sentence_written_as_boxes():
    assert "board_missing_kpi_strip" in codes(a_board(kpis=a_board()["kpis"][:2]))


def test_seven_figures_are_a_table_pretending_to_be_a_summary():
    assert "board_too_many_kpi" in codes(a_board(kpis=a_board()["kpis"] * 3))


def test_the_kpi_floor_is_waived_for_a_board_the_server_composed():
    """The server has frames, not an answer, so it never picks three to lead with."""
    assert "board_missing_kpi_strip" not in codes(a_board(kpis=[]), authored=False)
    # And every other rule still applies to it.
    assert "board_too_many_kpi" in codes(
        a_board(kpis=a_board()["kpis"] * 3), authored=False
    )


def test_a_label_longer_than_its_box_is_named():
    board = a_board()
    board["kpis"][0]["label"] = "x" * (grammar.KPI_LABEL_LIMIT + 1)
    assert "kpi_label_too_long" in codes(board)


def test_a_role_nothing_draws_is_named():
    board = a_board()
    board["kpis"][0]["role"] = "bullish"
    assert "kpi_role_unknown" in codes(board)


def test_a_figure_naming_a_column_that_is_not_there_is_named():
    board = a_board()
    board["kpis"][0]["value"]["column"] = "roic"
    assert "kpi_ref_unresolved" in codes(board)


def test_a_figure_naming_a_row_past_the_end_is_named():
    board = a_board()
    board["kpis"][0]["value"]["row"] = 9
    assert "kpi_ref_unresolved" in codes(board)


def test_a_figure_in_a_frame_of_many_rows_needs_an_address():
    board = a_board()
    board["kpis"][0]["value"].pop("row")
    assert "kpi_ref_unresolved" in codes(board)


def test_a_row_is_found_by_a_key_as_well_as_by_a_position():
    board = a_board()
    board["kpis"][0]["value"] = {
        "frame_id": "f-a",
        "column": "roe",
        "row_where": "symbol=VIC",
    }
    assert "kpi_ref_unresolved" not in codes(board)


def test_a_key_matching_no_row_is_named():
    board = a_board()
    board["kpis"][0]["value"] = {
        "frame_id": "f-a",
        "column": "roe",
        "row_where": "symbol=HPG",
    }
    assert "kpi_ref_unresolved" in codes(board)


def test_a_frame_of_one_row_needs_no_address_at_all():
    assert "kpi_ref_unresolved" not in codes(a_board())


# -- captions --------------------------------------------------------------


def caption_board(template, refs=None, **kwargs):
    return a_board(
        sections=[
            {
                "blocks": [
                    {"kind": "visual", "frame_id": "f-a"},
                    {"kind": "visual", "frame_id": "f-b"},
                    {
                        "kind": "caption",
                        "template": template,
                        "refs": refs or {},
                    },
                ]
            }
        ],
        **kwargs,
    )


def test_a_caption_longer_than_its_strip_is_named():
    assert "caption_too_long" in codes(
        caption_board("x" * (grammar.CAPTION_LIMIT + 1))
    )


def test_a_digit_typed_into_a_caption_is_refused():
    assert "caption_has_digit" in codes(caption_board("ROE đạt 18,5%."))


def test_a_year_is_a_digit_like_any_other():
    """The one exception people expect, and the one that must not exist.

    A period a reader needs is a cell in a frame — the quarter column of the
    table above the caption — and quoting it from memory is the same act as
    quoting a price from memory.
    """
    assert "caption_has_digit" in codes(caption_board("Trong năm 2026, biên co lại."))


def test_a_caption_of_pure_placeholders_carries_no_digit():
    assert "caption_has_digit" not in codes(
        caption_board(
            "ROE của VIC là {a} so với {b}.",
            {
                "a": {"frame_id": "f-a", "column": "roe", "row": 0},
                "b": {"frame_id": "f-a", "column": "roe", "row": 1},
            },
        )
    )


def test_a_placeholder_with_no_cell_behind_it_is_named():
    assert "caption_ref_unresolved" in codes(caption_board("ROE là {a}."))


def test_a_cell_named_for_a_placeholder_nobody_uses_is_named():
    assert "caption_ref_unused" in codes(
        caption_board(
            "Không dùng gì.",
            {"a": {"frame_id": "f-a", "column": "roe", "row": 0}},
        )
    )


def test_a_placeholder_pointing_at_a_missing_cell_is_named():
    assert "caption_ref_unresolved" in codes(
        caption_board("ROE là {a}.", {"a": {"frame_id": "f-a", "column": "roic"}})
    )


def test_two_captions_in_one_section_are_one_too_many():
    board = caption_board("Một câu {a}.", {"a": {"frame_id": "f-b", "column": "roe"}})
    board["sections"][0]["blocks"].append(
        {"kind": "caption", "template": "Câu thứ hai.", "refs": {}}
    )
    assert "caption_over_limit" in codes(board)


# -- visuals ---------------------------------------------------------------


def test_a_table_asked_for_outside_the_appendix_is_named():
    assert "table_not_in_appendix" in codes(
        a_board(
            sections=[
                {"blocks": [{"kind": "visual", "frame_id": "f-a", "widget": "data_table"}]}
            ]
        )
    )


def test_one_frame_drawn_twice_is_named():
    assert "visual_frame_reused" in codes(
        a_board(
            sections=[
                {
                    "blocks": [
                        {"kind": "visual", "frame_id": "f-a"},
                        {"kind": "visual", "frame_id": "f-a"},
                    ]
                }
            ]
        )
    )


def test_a_frame_this_turn_does_not_own_is_named():
    assert "frame_not_available" in codes(
        a_board(sections=[{"blocks": [{"kind": "visual", "frame_id": "f-z"}]}])
    )


def test_a_column_the_frame_does_not_have_is_named():
    assert "visual_column_unknown" in codes(
        a_board(
            sections=[
                {"blocks": [{"kind": "visual", "frame_id": "f-a", "columns": ["roic"]}]}
            ]
        )
    )


def test_more_sections_than_a_reader_will_read_is_named():
    section = {"blocks": [{"kind": "visual", "frame_id": "f-a"}]}
    assert "sections_over_limit" in codes(
        a_board(sections=[section] * (grammar.MAX_SECTIONS + 1))
    )


def test_more_blocks_in_one_section_than_it_can_hold_is_named():
    assert "blocks_over_limit" in codes(
        a_board(
            sections=[
                {
                    "blocks": [{"kind": "visual", "frame_id": "f-a"}]
                    * (grammar.MAX_BLOCKS_PER_SECTION + 1)
                }
            ]
        )
    )


def test_an_appendix_naming_a_frame_this_turn_does_not_own_is_named():
    assert "frame_not_available" in codes(a_board(appendix_frame_id="f-z"))


def test_a_board_that_breaks_nothing_reports_nothing():
    assert codes(a_board()) == set()


# -- what the compiler asks of the grammar ---------------------------------


def test_every_frame_the_board_names_is_listed_once_in_reading_order():
    board = grammar.parse(
        a_board(
            sections=[
                {
                    "blocks": [
                        {"kind": "visual", "frame_id": "f-b"},
                        {"kind": "visual", "frame_id": "f-a"},
                    ]
                }
            ],
            appendix_frame_id="f-b",
        )
    )
    # The KPIs name f-a then f-b, so those come first; the appendix repeats f-b
    # and is not listed twice.
    assert grammar.frame_references(board) == ["f-a", "f-b"]
