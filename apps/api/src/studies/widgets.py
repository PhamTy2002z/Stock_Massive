"""The closed set of pictures the browser knows how to draw.

Two readers, one file. A Study declares the widgets its ``view`` may emit and
this refuses one the browser has no component for — at import, where the Study
is written. The browser reads the same set out of
``contracts/signal-desk-widget-catalog.json``, which ``tests/studies/
test_widget_catalog.py`` holds equal to this module, so the JSON cannot drift
into promising a widget that no longer exists.

Why a version per widget rather than per catalog: a Signal Desk persisted last month
has to keep rendering. When ``session_heatmap`` needs a different options shape
it ships as version 2 and the old artifacts keep asking for version 1. A viewer
that meets a version it does not know falls back to ``data_table`` — the numbers
without the picture, which is a degradation a reader can see through, unlike a
blank panel.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .contracts import FrameKind


@dataclass(frozen=True)
class Widget:
    """One drawable, the frame kinds it accepts, and what it is for."""

    name: str
    version: int
    frame_kinds: tuple[FrameKind, ...]
    purpose: str


#: The widget every viewer is required to implement, and the one a viewer falls
#: back to when it does not recognise a name or a version. It accepts every
#: frame kind precisely so that the fallback can never itself fail to apply.
FALLBACK_WIDGET = ("data_table", 1)

CATALOG: Mapping[tuple[str, int], Widget] = MappingProxyType(
    {
        ("stat_tiles", 1): Widget(
            name="stat_tiles",
            version=1,
            frame_kinds=("table",),
            purpose="Vài con số dẫn dắt, mỗi ô một dòng của frame",
        ),
        ("bar_series", 1): Widget(
            name="bar_series",
            version=1,
            frame_kinds=("series",),
            purpose="Cột theo trục thời gian hoặc theo nhóm rời rạc",
        ),
        ("session_heatmap", 1): Widget(
            name="session_heatmap",
            version=1,
            frame_kinds=("matrix",),
            purpose="Ma trận phiên × khung giờ, ô trống là thiếu dữ liệu",
        ),
        ("ranked_bars", 1): Widget(
            name="ranked_bars",
            version=1,
            frame_kinds=("table",),
            purpose="Xếp hạng có nhãn, dài nhất trên cùng",
        ),
        ("line_series", 1): Widget(
            name="line_series",
            version=1,
            frame_kinds=("series",),
            purpose="Đường theo trục thời gian, tối đa hai trục giá trị",
        ),
        ("range_strip", 1): Widget(
            name="range_strip",
            version=1,
            frame_kinds=("table",),
            purpose="Dải giá thấp–cao, marker vị trí hiện tại, dải con tuỳ chọn",
        ),
        ("condition_checklist", 1): Widget(
            name="condition_checklist",
            version=1,
            frame_kinds=("table",),
            purpose="Danh sách điều kiện: đạt, chưa đạt, hay chưa rõ",
        ),
        ("scatter_quadrant", 1): Widget(
            name="scatter_quadrant",
            version=1,
            frame_kinds=("table",),
            purpose="Điểm trên hai trục, chia bốn vùng bằng đường tham chiếu",
        ),
        ("data_table", 1): Widget(
            name="data_table",
            version=1,
            frame_kinds=("series", "matrix", "table"),
            purpose="Bảng số thuần — cũng là fallback khi viewer không biết widget",
        ),
    }
)


def known(widget: str, version: int) -> bool:
    return (widget, version) in CATALOG


def accepts(widget: str, version: int, kind: FrameKind) -> bool:
    entry = CATALOG.get((widget, version))
    return entry is not None and kind in entry.frame_kinds


def catalog_payload() -> dict[str, object]:
    """The shape published to ``contracts/signal-desk-widget-catalog.json``."""
    return {
        "fallback": {"widget": FALLBACK_WIDGET[0], "version": FALLBACK_WIDGET[1]},
        "widgets": [
            {
                "name": entry.name,
                "version": entry.version,
                "frameKinds": list(entry.frame_kinds),
                "purpose": entry.purpose,
            }
            for entry in sorted(CATALOG.values(), key=lambda w: (w.name, w.version))
        ],
    }


if FALLBACK_WIDGET not in CATALOG:  # pragma: no cover - guards a typo above
    raise ImportError(
        f"the fallback widget {FALLBACK_WIDGET} is not in the catalog it falls "
        "back to"
    )


__all__ = ["CATALOG", "FALLBACK_WIDGET", "Widget", "accepts", "catalog_payload", "known"]
