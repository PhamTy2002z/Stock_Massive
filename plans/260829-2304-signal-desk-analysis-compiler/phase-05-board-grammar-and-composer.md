---
phase: 5
title: "Board grammar & composer"
status: done
priority: P1
effort: "24h"
dependencies: [2, 3]
---

# Phase 5: Board grammar & composer

## Overview
Trục "trình bày". `render_signal_desk` nhận **Board DSL v2**: sections, KPI,
caption có placeholder, widget gợi ý. Server ép ngữ pháp, chọn widget theo
hình dạng frame, tính layout 12 cột, gán màu theo role, chấm lint trực quan,
và **tự soạn board** khi model bỏ cuộc. Trực quan trở thành thứ đo được.

## Requirements
- Functional — **Ngữ pháp** (validator, lỗi có tên):
  ```
  Board    := title · archetype? · sections[1..4] · appendix?
  Section  := heading? · blocks[1..4]
  Block    := Visual | Kpi | Caption
  Visual   := { frame_id, widget?, columns?[≤6], options? }
  Kpi      := { kind:"kpi", label≤40, value:Ref, delta?:Ref, role?:Role }   — 3..6 trên toàn board, gom vào KpiStrip
  Caption  := { kind:"caption", template≤280, refs:{a..f: Ref} }             — ≤1 / section, ≤5 / board
  Appendix := { kind:"table", frame_id }                                     — data_table duy nhất được phép ngoài fallback
  Ref      := { frame_id, row:int | row_where:{col:value}, col:string }
  ```
  Lỗi: `board_missing_kpi_strip` · `board_too_many_kpi` · `caption_too_long` ·
  `caption_has_digit` (chữ số ngoài `{placeholder}` — **kể cả năm**; kỳ tham
  chiếu bằng ref tới ô nhãn) · `caption_ref_unresolved` · `table_not_in_
  appendix` · `visual_frame_reused` · `slot_type_mismatch` (archetype) ·
  `blocks_over_limit` (visual ≤ 8/board).
- **Chọn widget theo hình dạng** (`composer.infer_widget(frame, hint)`):

  | Frame | Mặc định | Ghi chú |
  |---|---|---|
  | `series` trục thời gian, 1–2 cột số | `line_series` | > 2 cột → `grouped_bar` nếu ≤ 12 điểm, else `line_series` 2 cột đầu + note |
  | `series` phân loại ≤ 8 nhóm | `bar_series` | |
  | `table` hàng = symbol × cột metric | `comparison_table` **và** `grouped_bar` (≤ 4 mã × ≤ 6 metric) | archetype Compare đặt cả hai |
  | `table` phần-của-tổng ≤ 5 | `donut` | > 5 → `ranked_bars` |
  | `table` 2 cột số + nhãn | `scatter_quadrant` | |
  | `table` 1 hàng | tách thành KPI | |
  | `matrix` | `session_heatmap` | |
  | có `checklist` roles | `condition_checklist` | |
  | không khớp | `data_table` + `downgraded: reason` | |
  Model gợi ý `widget` → hợp lệ với kind thì giữ; vi phạm luật tri giác (pie
  > 5, table cho series) → server đổi, ghi `upgraded_from`.
- **Layout engine** (`layout.py`): grid 12; KPI strip chia đều (3→4/4/4,
  4→3×4, 5–6→ hai hàng); section 1 visual → 12; 2 → 6/6; 3 → 4/4/4 (dưới
  breakpoint FE hạ 2 cột); `comparison_table`/`heatmap` luôn 12; caption theo
  visual đứng trước. Output: `span` mỗi block.
- **Archetype** (`archetypes.py`, 5): `compare · profile · screen · timeline ·
  decompose` — mỗi cái = danh sách slot `{name, frame_shape, widget, required}`
  + thứ tự section mặc định. Model chọn → server kiểm slot. Không chọn →
  `profile`.
- **Lint** (`lint.py`) trả điểm + lỗi: `visual_ratio ≥ 0,7` · narrative ≤
  1.200 ký tự · KPI 3–6 · ≥ 2 loại widget · 0 frame vẽ hai lần · refs 100%.
  Ngưỡng là hằng có docstring "đặt lại từ phân bố phase 09".
- **Auto-compose** (`auto_compose.py`): từ tập frame của Turn → board
  `profile`: frame 1 hàng → KPI; còn lại theo bảng shape; caption **không**
  sinh (server không viết câu — quyết định 3); `autoComposed: true`.
  Kích ở hai chỗ: (a) `render_signal_desk` fail lint sau **một** lượt sửa;
  (b) loop cuối Turn mode `signal_desk` có frame mà không board.
- Spec v2 lưu `signal_desk_spec = {specVersion: 2, title, archetype, kpis[],
  sections[{heading, blocks[{…, span}]}], appendix, lint, autoComposed}`;
  KPI/caption đã **resolve giá trị + unit + label** lúc lưu (replay không cần
  frame lookup); v1 giữ nguyên đọc được.
- Roles vocab dùng của phase 02 (`winner/loser/benchmark/warning/stale`).
- Non-functional: validator + composer thuần hàm, < 50 ms; `MAX_SIGNAL_DESKS_
  PER_TURN = 2` giữ; `MAX_BLOCKS` 6 → thay bằng ba trần trong grammar.

## Architecture
```
render_signal_desk(v2) ── grammar.validate ── resolve refs (frames_buffer) ── composer.infer_widget
   ── archetypes.check ── layout.assign ── lint.score ──┬ pass → store_composition(spec v2)
                                                        └ fail → error có tên (lượt 1) / auto_compose (lượt 2)
loop._finish (mode signal_desk) ── frames∧¬board → auto_compose → signal_desk.ready{autoComposed}
```

## Related Code Files
- Create: `apps/api/src/studies/{grammar,composer,layout,archetypes,lint,auto_compose}.py`
- Modify: `apps/api/src/agent/tools/studies.py:94-135` (schema v2), `:513-631`
  (handler → pipeline trên), `:656-677` (`_presentation` dùng composer)
- Modify: `apps/api/src/studies/frames_buffer.py:154-178`
  (`store_composition` nhận spec v2), `:52-56` (bỏ `MAX_BLOCKS`, thêm ba trần)
- Modify: `apps/api/src/studies/contracts.py:339-378` (`SignalDeskSpec` v2:
  `kpis`, `sections`, `appendix`, `lint`, `spec_version`)
- Modify: `apps/api/src/agent/loop.py` (**một** hook auto-compose; cập nhật
  `SIGNAL_DESK_NOTE:356-366` ở phase 08, không ở đây)
- Modify: `apps/api/src/agent/messages.py:833` (`signal_desk_of` truyền
  `autoComposed`, `lint`)
- Modify: `apps/api/src/studies/widgets.py:50-137` (thêm `grouped_bar@1`,
  `comparison_table@1`, `donut@1`, `waterfall@1`, `bullet@1`, `text_card@1`,
  `kpi_strip@1`, `caption@1`), `contracts/signal-desk-widget-catalog.json`
  sinh lại
- Tests: `apps/api/tests/studies/test_grammar.py`, `test_composer_shape.py`
  (bảng fixture shape → widget), `test_layout.py`, `test_archetypes.py`,
  `test_lint.py`, `test_auto_compose.py`, `tests/test_agent_study_tools.py`
  (v2 end-to-end, lượt sửa, fallback), `tests/test_agent_loop.py` (hook cuối
  Turn), `tests/studies/test_widget_catalog.py`

## Implementation Steps
1. `contracts.py` spec v2 + `to_payload`; v1 đọc được (`spec_version` mặc
   định 1).
2. `grammar.py`: dataclass DSL + `validate(spec, frames) → list[Violation]`;
   regex chữ số ngoài placeholder; test bảng ≥ 30 case.
3. `composer.py`: `shape_of(frame)` (thời gian? entity? phần-của-tổng? 1
   hàng?) + `infer_widget`; fixture 12 frame thật chụp từ store.
4. `layout.py` + `archetypes.py` + test.
5. `lint.py`: điểm + lỗi; hằng ngưỡng có docstring.
6. `auto_compose.py`; test với tập frame VIC/VCB thật → board hợp lệ.
7. `tools/studies.py`: schema v2 (`_widget_guide` giữ), handler pipeline, resolve
   ref (format số theo `unit` — VND rút gọn `tỷ`, `%` một chữ số lẻ — trong
   `studies/format.py` mới, cũng FE dùng cùng luật qua JSON đã resolve).
8. `frames_buffer.store_composition` v2; `read` v1/v2.
9. Hook loop cuối Turn; test: Turn `signal_desk` có 2 frame, model trả lời
   không render → artifact `autoComposed`.
10. Widgets catalog + JSON + test sync.
11. Bộ test end-to-end: câu VIC vs VCB qua `query → compute → render v2` với
    `agent_tool_world` → board có `comparison_table`, `grouped_bar`, KPI 4,
    caption 2, lint pass.

## Success Criteria
- [x] Grammar: 30 case bảng đúng; `caption_has_digit` bắt cả năm.
      **38 test** ở `tests/studies/test_grammar.py`; năm bị bắt bởi
      `test_a_year_is_a_digit_like_any_other`.
- [x] Shape → widget: 12 fixture đúng; pie > 5 hạ; table cho series nâng.
      **13 fixture** ở `tests/studies/test_composer_shape.py` (thêm ma trận).
- [x] Layout: mọi section tổng span = 12 mỗi hàng — `test_layout.py`
      khẳng định cho mọi số block từ 1 tới 12, và cho cả dải KPI.
- [x] Auto-compose ra board hợp lệ từ mọi tập ≥ 1 frame; 0 prose trong mode
      `signal_desk` trên test loop. Board tự dựng qua **chính grammar của nó**
      ở mọi cỡ tới quá trần (`test_auto_compose.py`, parametrize 1..11).
- [x] Spec v2 lưu đã resolve; artifact cũ v1 vẫn đọc — `specVersion` nay có
      trên **cả hai** payload, nên không nơi nào phải suy ra phiên bản.
- [x] End-to-end VIC vs VCB đạt mô tả ở plan Success Criteria #1
      (`tests/test_agent_composition.py::test_vic_against_vcb_compiles_into_the_board_the_plan_describes`).

## Ghi chú thi công (2026-08-30)

- **Schema v2 tốn +1.006 token** so với schema block phẳng (763 → 1.769, đo
  sau `strict_parameters`). Vượt ngưỡng +600 của phần Risk, nên đã **rút
  description** đúng như plan dặn: `_ref_schema` bỏ mô tả từng trường (tám bản
  sao trên một schema), và enum widget bỏ ba tên **không phải là hình vẽ của
  một frame** — `kpi_strip`, `caption`, `data_table` — vì mọi lần model chọn
  chúng đều ra một violation. Không rút một luật nào.
- **`visual_ratio ≥ 0,7` khiến board hai hình không mang nổi một caption.**
  Hệ quả số học của ngưỡng, không phải lỗi: 2/3 = 0,667. Chính vì thế
  `comparison_table` **phải** phát ra companion `grouped_bar` — luật đã viết
  trong plan mà bản đầu để treo — và câu ví dụ VIC vs VCB mới hợp lệ. Ghi lại ở
  `test_lint.py::test_two_pictures_and_a_caption_is_under_the_floor`.
- **Lint đo board *đã biên dịch*, không đo kế hoạch của model.** Hai thứ lệch
  nhau đúng bằng những hình server thêm vào; chấm trên kế hoạch sẽ trừ điểm một
  board vì một biểu đồ đang nằm trên nó.
- **`bucket` không phải trục thời gian.** Bản đầu xếp nó vào `_TIME_NAMES` và
  biến profile thanh khoản trong phiên thành `line_series` — hàm ý có liên tục
  giữa 11:30 và 13:00, lúc thị trường đóng. Study đã vẽ nó bằng `bar_series`
  từ đầu, và đó là câu trả lời đúng.
- **Sàn KPI được miễn cho board server dựng** (`validate(..., authored=False)`).
  Server có frame, không có câu trả lời; tự chọn ba số để dẫn dắt là server
  quyết định đâu là trọng tâm — đúng việc nó không được làm.
- **`MAX_BLOCKS = 6` đã gỡ** khỏi `frames_buffer`, thay bằng ba trần trong
  `grammar.py`. `store_composition` nhận cả payload spec thay vì danh sách
  block, vì đã có hai cách viết và tầng đó không phải nơi biết là cách nào.

## Risk Assessment
- Schema v2 dài → token schema tăng; đo bằng `estimate_tokens` trước/sau,
  ghi report; > +600 token → rút `description` enum, không rút luật.
- Model đặt `row` sai → KPI sai nhãn nhưng **số vẫn thật**; lint không bắt
  được ngữ nghĩa — chấp nhận, ghi ở phase 09 là mục LLM-judge tương lai của C4.
- Hook loop là surface nhạy (C2 đang đo) — đúng một hàm, không đọc context.
