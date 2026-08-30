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

**A retired version stays in the catalog.** Five widgets ship a version 2 that
reads the meaning a frame declares about its own series and points, and their
version 1 is listed beside it rather than replaced. Dropping it would make every
artifact written before the change fall back to a table — the version scheme
exists to prevent exactly that. The browser maps both versions onto the same
component, which is sound because the older version's frames declare no meaning
and are drawn the way they always were.
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
        ("stat_tiles", 2): Widget(
            name="stat_tiles",
            version=2,
            frame_kinds=("table",),
            purpose="Như v1, thêm màu ô theo vai trò từng dòng khai trong frame",
        ),
        ("bar_series", 1): Widget(
            name="bar_series",
            version=1,
            frame_kinds=("series",),
            purpose="Cột theo trục thời gian hoặc theo nhóm rời rạc",
        ),
        ("bar_series", 2): Widget(
            name="bar_series",
            version=2,
            frame_kinds=("series",),
            purpose="Như v1, thêm màu cột theo vai trò từng dòng khai trong frame",
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
        ("ranked_bars", 2): Widget(
            name="ranked_bars",
            version=2,
            frame_kinds=("table",),
            purpose="Như v1, thêm màu thanh theo vai trò từng dòng khai trong frame",
        ),
        ("line_series", 1): Widget(
            name="line_series",
            version=1,
            frame_kinds=("series",),
            purpose="Đường theo trục thời gian, tối đa hai trục giá trị",
        ),
        ("line_series", 2): Widget(
            name="line_series",
            version=2,
            frame_kinds=("series",),
            purpose="Như v1, thêm màu đường theo vai trò từng cột khai trong frame",
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
        ("scatter_quadrant", 2): Widget(
            name="scatter_quadrant",
            version=2,
            frame_kinds=("table",),
            purpose="Như v1, thêm màu điểm theo vai trò từng dòng khai trong frame",
        ),
        ("grouped_bar", 1): Widget(
            name="grouped_bar",
            version=1,
            frame_kinds=("series", "table"),
            purpose="Cột theo nhóm: mỗi thực thể một chùm, mỗi chỉ tiêu một cột",
        ),
        ("comparison_table", 1): Widget(
            name="comparison_table",
            version=1,
            frame_kinds=("table",),
            purpose="Bảng đối chiếu: hàng là mã, cột là chỉ tiêu, ô thắng thua tô màu",
        ),
        ("donut", 1): Widget(
            name="donut",
            version=1,
            frame_kinds=("table",),
            purpose="Phần của một tổng, tối đa năm phần",
        ),
        ("waterfall", 1): Widget(
            name="waterfall",
            version=1,
            frame_kinds=("table", "series"),
            purpose="Cộng dồn từng bước từ đầu kỳ tới cuối kỳ",
        ),
        ("bullet", 1): Widget(
            name="bullet",
            version=1,
            frame_kinds=("table",),
            purpose="Giá trị so với một mốc tham chiếu, mỗi dòng một thanh",
        ),
        ("text_card", 1): Widget(
            name="text_card",
            version=1,
            frame_kinds=("table",),
            purpose="Vài dòng chữ lấy thẳng từ frame, không có số nào tự viết",
        ),
        ("kpi_strip", 1): Widget(
            name="kpi_strip",
            version=1,
            frame_kinds=("table",),
            purpose="Dải ô dẫn dắt trên đầu bảng, mỗi ô một con số đã tra sẵn",
        ),
        ("caption", 1): Widget(
            name="caption",
            version=1,
            frame_kinds=("series", "matrix", "table"),
            purpose="Một câu có chỗ trống, mỗi chỗ là một ô đã tra sẵn",
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
