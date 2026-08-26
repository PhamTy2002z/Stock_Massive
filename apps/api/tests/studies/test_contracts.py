"""What a Study declaration refuses to be built out of."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.stocks.signals.issues import SignalIssue
from src.studies.contracts import (
    CanvasBlock,
    CanvasSpec,
    Frame,
    Provenance,
    StudyRefused,
    StudyResult,
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


def test_provenance_names_its_freeze_in_the_payload():
    moment = datetime(2026, 8, 26, 7, 30, tzinfo=timezone.utc)
    payload = Provenance(
        source="vnstock",
        as_of=moment,
        sessions_used=30,
        health="normal",
        reason=None,
    ).to_payload()

    assert payload["asOf"] == moment.isoformat()
    assert payload["sessionsUsed"] == 30
    assert payload["health"] == "normal"


def test_a_canvas_needs_a_title_and_a_block():
    block = CanvasBlock(
        widget="bar_series", widget_version=1, frame="profile", options={}
    )

    with pytest.raises(ValueError, match="title"):
        CanvasSpec(title="   ", blocks=(block,))
    with pytest.raises(ValueError, match="no blocks"):
        CanvasSpec(title="Thanh khoản", blocks=())


def test_a_result_with_no_frames_has_nothing_to_draw():
    provenance = Provenance(
        source="vnstock",
        as_of=datetime.now(timezone.utc),
        sessions_used=1,
        health="normal",
        reason=None,
    )

    with pytest.raises(ValueError, match="nothing to draw"):
        StudyResult(headline={"symbol": "STB"}, frames={}, provenance=provenance)
    with pytest.raises(ValueError, match="no headline"):
        StudyResult(headline={}, frames={"profile": a_frame()}, provenance=provenance)


def test_a_refusal_carries_the_code_the_tool_layer_records():
    refusal = StudyRefused(SignalIssue.INSUFFICIENT_HISTORY, "9 of 10 sessions")

    assert refusal.issue is SignalIssue.INSUFFICIENT_HISTORY
    assert "insufficient_history" in str(refusal)
