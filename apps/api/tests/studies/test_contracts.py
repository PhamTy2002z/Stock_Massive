"""What a Study declaration refuses to be built out of."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.stocks.signals.issues import SignalIssue
from src.studies.contracts import (
    CATEGORY_SLOTS,
    METHOD_NOTE_LIMIT,
    REASON_LIMIT,
    SignalDeskBlock,
    SignalDeskSpec,
    Frame,
    Provenance,
    StudyRefused,
)


def a_frame(**overrides) -> Frame:
    fields = {
        "kind": "series",
        "columns": ("bucket", "avg_volume"),
        "rows": (("09:15", 1_000),),
        "unit": "shares",
        "labels": {"bucket": "Khung giờ", "avg_volume": "KL trung bình"},
    }
    fields.update(overrides)
    return Frame(**fields)


def test_a_row_narrower_than_the_columns_is_refused():
    with pytest.raises(ValueError, match="row 0 has 1 cells against 2 columns"):
        a_frame(rows=(("09:15",),))


def test_a_column_with_no_vietnamese_label_is_refused():
    with pytest.raises(ValueError, match="avg_volume"):
        a_frame(labels={"bucket": "Khung giờ"})


def test_a_frame_with_no_columns_describes_nothing():
    with pytest.raises(ValueError, match="no columns"):
        a_frame(columns=(), rows=(), labels={})


# -- what a frame may say about its own numbers ----------------------------


def test_a_frame_says_nothing_about_meaning_unless_it_is_asked_to():
    """The default is silence, and silence has to survive the wire.

    Every artifact written before frames could carry meaning is a frame that
    says nothing, and it has to keep drawing the way it drew.
    """
    payload = a_frame().to_payload()

    assert payload["columnRoles"] == {}
    assert payload["pointRoles"] == []


def test_every_role_the_palette_draws_is_a_role_a_frame_may_declare():
    frame = a_frame(
        rows=(("09:15", 1_000), ("09:30", 2_000)),
        column_roles={"avg_volume": "up"},
        point_roles=("focus", f"category:{CATEGORY_SLOTS}"),
    )

    assert frame.to_payload()["columnRoles"] == {"avg_volume": "up"}
    assert frame.to_payload()["pointRoles"] == ["focus", f"category:{CATEGORY_SLOTS}"]


def test_a_word_the_palette_has_no_colour_for_is_refused():
    with pytest.raises(ValueError, match="not a role"):
        a_frame(column_roles={"avg_volume": "bullish"})
    with pytest.raises(ValueError, match="not a role"):
        a_frame(point_roles=("emphasis",))


def test_a_category_past_the_last_slot_is_refused():
    """Six groups is the palette. A seventh would be drawn in nothing."""
    a_frame(point_roles=(f"category:{CATEGORY_SLOTS}",))

    with pytest.raises(ValueError, match="not a role"):
        a_frame(point_roles=(f"category:{CATEGORY_SLOTS + 1}",))
    with pytest.raises(ValueError, match="not a role"):
        a_frame(point_roles=("category:0",))


def test_a_role_on_a_column_the_frame_does_not_have_is_refused():
    with pytest.raises(ValueError, match="which this Frame does not have"):
        a_frame(column_roles={"avg_value": "up"})


def test_point_roles_that_do_not_line_up_with_the_rows_are_refused():
    with pytest.raises(ValueError, match="2 point roles against 1 rows"):
        a_frame(point_roles=("up", "down"))


# -- what the strip may say to a reader ------------------------------------


def a_provenance(**overrides) -> Provenance:
    fields = {
        "source": "store",
        "as_of": datetime(2026, 8, 26, 7, 30, tzinfo=timezone.utc),
        "sessions_used": 30,
        "health": "normal",
        "reason": None,
    }
    fields.update(overrides)
    return Provenance(**fields)


def test_a_reason_longer_than_a_sentence_is_refused():
    """The real case: five clauses of methodology joined onto a health line."""
    a_provenance(reason="Đ" * REASON_LIMIT)

    with pytest.raises(ValueError, match="against a limit"):
        a_provenance(reason="Đ" * (REASON_LIMIT + 1))


def test_a_reason_written_in_this_systems_own_words_is_refused():
    with pytest.raises(ValueError, match="code name"):
        a_provenance(reason="dislocation_rank thiếu cho 4 mã")
    with pytest.raises(ValueError, match="describing itself"):
        a_provenance(reason="Store chưa có báo cáo quý này")


def test_an_empty_reason_is_refused_rather_than_printed_as_a_blank_line():
    with pytest.raises(ValueError, match="leave it out"):
        a_provenance(reason="   ")


def test_a_method_note_is_allowed_a_clause_and_not_a_paragraph():
    a_provenance(method_notes=("Đ" * METHOD_NOTE_LIMIT,))

    with pytest.raises(ValueError, match=r"method_notes\[0\]"):
        a_provenance(method_notes=("Đ" * (METHOD_NOTE_LIMIT + 1),))


def test_the_method_travels_beside_the_reason_rather_than_inside_it():
    payload = a_provenance(
        health="degraded",
        reason="Mới có báo cáo quý II/2026 cho 1.124/1.523 mã",
        method_notes=("Thanh khoản ước bằng trung vị của giá đóng cửa.",),
    ).to_payload()

    assert payload["reason"] == "Mới có báo cáo quý II/2026 cho 1.124/1.523 mã"
    assert payload["methodNotes"] == ["Thanh khoản ước bằng trung vị của giá đóng cửa."]


def test_provenance_names_its_freeze_in_the_payload():
    moment = datetime(2026, 8, 26, 7, 30, tzinfo=timezone.utc)
    payload = Provenance(
        source="store",
        as_of=moment,
        sessions_used=30,
        health="normal",
        reason=None,
    ).to_payload()

    assert payload["asOf"] == moment.isoformat()
    assert payload["sessionsUsed"] == 30
    assert payload["health"] == "normal"


def test_a_signal_desk_needs_a_title_and_a_block():
    block = SignalDeskBlock(
        widget="bar_series", widget_version=1, frame="profile", options={}
    )

    with pytest.raises(ValueError, match="title"):
        SignalDeskSpec(title="   ", blocks=(block,))
    with pytest.raises(ValueError, match="no blocks"):
        SignalDeskSpec(title="Thanh khoản", blocks=())


def test_a_refusal_carries_the_code_the_tool_layer_records():
    refusal = StudyRefused(SignalIssue.INSUFFICIENT_HISTORY, "9 of 10 sessions")

    assert refusal.issue is SignalIssue.INSUFFICIENT_HISTORY
    assert "insufficient_history" in str(refusal)
