"""What the server draws when the model drew nothing, and what it refuses to draw.

Two claims, and the second is the one that matters. The server can arrange
frames — that is mechanical. It must not write a sentence, because choosing
which two numbers belong in one sentence *is* the analysis, and this layer has
no idea what was asked.
"""

from __future__ import annotations

from src.studies import auto_compose, grammar


def frame(kind, columns, rows, unit=None):
    return {
        "kind": kind,
        "columns": list(columns),
        "rows": [list(row) for row in rows],
        "unit": unit,
        "labels": {name: name for name in columns},
    }


PROVENANCE = {"source": "store", "asOf": "2026-08-30T00:00:00+00:00"}
WEB = {"source": "web", "asOf": "2026-08-30T00:00:00+00:00"}

SERIES = frame(
    "series",
    ("session", "close"),
    [(f"2026-08-{day:02d}", 20.0 + day) for day in range(1, 11)],
    "VND",
)
TILES = frame("table", ("roe", "roa", "margin"), [(18.5, 1.4, 22.0)], "%")


def gathered(*entries):
    return [(f"f-{index}", payload, prov) for index, (payload, prov) in enumerate(entries)]


def test_nothing_gathered_composes_nothing():
    assert auto_compose.compose([]) is None


def test_every_frame_the_turn_made_is_drawn_the_way_its_shape_says():
    composed = auto_compose.compose(gathered((SERIES, PROVENANCE), (TILES, PROVENANCE)))
    assert composed is not None
    spec, frames = composed

    blocks = spec.sections[0].blocks
    assert [block.widget for block in blocks] == ["line_series"]
    # The one-row frame became the strip rather than a picture: a frame of one
    # row is already somebody's summary.
    assert [kpi.label for kpi in spec.kpis] == ["roe", "roa", "margin"]
    assert spec.kpis[0].value.text == "18,5%"
    # Every frame a block or a figure names is in the row that is written.
    assert set(frames) >= {block.frame for block in blocks}
    assert set(frames) >= {kpi.value.frame for kpi in spec.kpis}


def test_the_server_never_writes_a_sentence():
    composed = auto_compose.compose(gathered((SERIES, PROVENANCE), (TILES, PROVENANCE)))
    assert composed is not None
    spec, _frames = composed
    assert all(
        block.to_payload()["kind"] == "visual"
        for section in spec.sections
        for block in section.blocks
    )


def test_a_composed_board_says_the_server_composed_it():
    composed = auto_compose.compose(gathered((SERIES, PROVENANCE)))
    assert composed is not None
    spec, _frames = composed
    assert spec.auto_composed is True
    assert spec.to_payload()["autoComposed"] is True
    assert spec.to_payload()["specVersion"] == 2


def test_a_turn_whose_only_frame_is_one_row_still_gets_a_picture():
    """A strip and nothing under it is not a board."""
    composed = auto_compose.compose(gathered((TILES, PROVENANCE)))
    assert composed is not None
    spec, _frames = composed
    assert spec.sections[0].blocks
    assert spec.kpis


import pytest


@pytest.mark.parametrize("count", range(1, grammar.MAX_VISUALS + 4))
def test_a_composed_board_passes_its_own_grammar(count):
    """Except the KPI floor, which is waived for exactly this case.

    The server has frames, not an answer, so composing a strip of three would be
    this layer deciding which numbers are the point. Every other rule holds, at
    every size up past the ceiling — a composed board the compiler would have
    refused from the model is a board this system contradicts itself about.
    """
    composed = auto_compose.compose(gathered(*[(SERIES, PROVENANCE)] * count))
    assert composed is not None
    spec, _frames = composed
    payload = spec.to_payload()
    assert len(payload["sections"]) <= grammar.MAX_SECTIONS
    assert len(payload["kpis"]) <= grammar.MAX_KPIS
    for section in payload["sections"]:
        assert len(section["blocks"]) <= grammar.MAX_BLOCKS_PER_SECTION
        assert sum(block["span"] for block in section["blocks"]) % 12 == 0


def test_a_frame_copied_off_a_page_keeps_saying_so():
    composed = auto_compose.compose(gathered((SERIES, WEB)))
    assert composed is not None
    spec, _frames = composed
    assert spec.sections[0].blocks[0].to_payload()["source"] == "web"


def test_more_frames_than_a_board_draws_are_cut_at_the_ceiling():
    many = gathered(*[(SERIES, PROVENANCE)] * (grammar.MAX_VISUALS + 4))
    composed = auto_compose.compose(many)
    assert composed is not None
    spec, _frames = composed
    drawn = sum(len(section.blocks) for section in spec.sections)
    assert drawn == grammar.MAX_VISUALS


def test_the_strip_never_grows_past_what_a_strip_holds():
    wide = frame(
        "table",
        tuple(f"c{index}" for index in range(10)),
        [tuple(float(index) for index in range(10))],
    )
    composed = auto_compose.compose(gathered((wide, PROVENANCE)))
    assert composed is not None
    spec, _frames = composed
    assert len(spec.kpis) == grammar.MAX_KPIS


def test_a_working_frame_too_tall_to_be_a_picture_is_not_drawn():
    """The fallback draws what a reader can read, not every row a plan touched.

    A template files every step as an artifact, and some steps are the tables a
    Study reads on its way to an answer — the market-wide screen reads tens of
    thousands of closes before it ranks anything. This is the board a Turn gets
    when the model drew nothing, so answering it with that intermediate would be
    showing a reader the workings, and copying megabytes into a second row to do
    it.
    """
    tall = frame(
        "series",
        ("session", "close"),
        [(f"2026-01-{index:05d}", float(index)) for index in range(auto_compose.MAX_DRAWABLE_ROWS + 1)],
    )

    composed = auto_compose.compose(gathered((tall, PROVENANCE), (SERIES, PROVENANCE)))

    assert composed is not None
    spec, frames = composed
    assert len(frames) == 1
    assert next(iter(frames.values()))["rows"] == SERIES["rows"]


def test_a_turn_holding_nothing_but_working_frames_composes_no_board():
    """Nothing drawable is nothing to draw, and the loop is told so.

    ``None`` rather than an empty board: the caller's next line is "say plainly
    what could not be drawn", and a board with no pictures in it would be this
    system answering a question it did not answer.
    """
    tall = frame(
        "series",
        ("session", "close"),
        [(f"2026-01-{index:05d}", float(index)) for index in range(auto_compose.MAX_DRAWABLE_ROWS + 1)],
    )

    assert auto_compose.compose(gathered((tall, PROVENANCE))) is None
