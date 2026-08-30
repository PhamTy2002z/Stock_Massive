---
phase: 6
title: "Web grid & widgets"
status: done
priority: P1
effort: "22h"
dependencies: [5]
---

# Phase 6: Web grid & widgets

## Overview
Panel Signal Desk vẽ spec v2: KPI strip, section có heading, grid 12 cột theo
`span` server tính, caption đã resolve, 6 widget mới, badge nguồn `web`/
`derived`, nhãn `autoComposed`. Spec v1 vẫn vẽ như cũ. Cái nhìn Power BI đến
từ design system, không từ model.

## Requirements
- Functional:
  - `signal-desk-panel.tsx`: nhánh `specVersion === 2` → `SignalDeskBoard`
    (mới): header (title · as_of · provenance strip) → `KpiStrip` → sections
    → appendix. v1 → đường cũ không đổi.
  - Grid: CSS grid 12 cột, `grid-column: span N` từ spec; breakpoint < 900px
    → span 4 → 6, 6 → 12 (luật trong `layout.ts` phản chiếu `layout.py`, test
    khớp bảng).
  - Widget mới (mỗi cái `name@1`, test, story-less): `grouped-bar` (recharts
    BarChart nhiều series theo entity, màu role), `comparison-table` (hàng mã ×
    cột metric, ô `winner/loser` tô, cột sort tĩnh theo spec), `donut`
    (PieChart innerRadius, ≤ 5 phần, legend), `waterfall` (Bar stacked
    invisible base), `bullet` (thanh giá trị vs mốc benchmark), `text-card`
    (caption card), `kpi-strip` (ô: label, value formatted, delta ↑↓ theo
    role), `caption` (chữ ≤ 280 đã resolve, `{ref}` render `<mark>` có title
    trỏ frame).
  - `chart-theme.ts::colorFor` thêm `winner/loser/benchmark/warning/stale`
    → token (`--vg-positive`, `--vg-negative`, `--vg-benchmark`, `--vg-warning`,
    `--vg-muted`); test `widget-roles.test.tsx` mở rộng.
  - Badge nguồn trên block: `store` (mặc định, không badge) · `web` (badge
    "Nguồn web" + domain, tooltip URL) · `derived` (badge "Tính từ N frame").
  - `autoComposed` → dòng chú thích nhỏ dưới header ("Board dựng tự động từ
    dữ liệu đã tính").
  - Fallback: widget/version lạ → `data_table` + ghi chú (giữ luật).
  - Export (`signal-desk-export.ts`) hiểu v2: CSV mỗi frame + JSON spec.
- Non-functional: recharts vẫn qua `next/dynamic`; first paint lane chat
  không đổi (đo bundle: chunk signal-desk tăng ≤ 60 KB gzip); a11y: bảng có
  `<th scope>`, chart có `aria-label` từ heading; reduced-motion giữ.

## Architecture
```
use-artifact.ts → artifact{signal_desk_spec} → specVersion?
   1 → SignalDeskPanel (cũ)
   2 → SignalDeskBoard → KpiStrip · Section[] → Block(span) → resolveWidget(name@ver) → Widget(frame, options, provenance)
```
Layout hoàn toàn từ `span` server; FE không tính lại trừ breakpoint collapse.

## Related Code Files
- Create: `apps/web/src/components/signal-desk/{signal-desk-board,kpi-strip,board-section,source-badge,layout}.tsx|ts`
  + test cạnh mỗi file
- Create: `apps/web/src/components/signal-desk/widgets/{grouped-bar,comparison-table,donut,waterfall,bullet,text-card,caption}.tsx` + test
- Modify: `apps/web/src/components/signal-desk/signal-desk-panel.tsx:124-160`
  (nhánh v2), `widget-registry.ts:86-101` (8 entry mới), `widget-registry.test.ts`
- Modify: `apps/web/src/components/signal-desk/widgets/chart-theme.ts:63-101`
  (roles mới), `widget-roles.test.tsx`
- Modify: `apps/web/src/components/signal-desk/{provenance-strip,signal-desk-header,signal-desk-export}.tsx|ts`
- Modify: `apps/web/src/lib/alpha-desk/types.ts` (`SignalDeskSpecV2`, `Kpi`,
  `Caption`, `Section`, `Provenance.source`)
- Modify: `apps/web/src/lib/signal-issues.ts` — chỉ nếu phase 02/04 thêm mã
  refusal mới (`label_missing`, `evidence_*`, `compute_*`) → thêm câu; và
  `src/alpha/reasons.py` phía API cùng lúc (luật "thêm mã thì thêm câu ở cả hai")
- Fixture: `apps/web/src/components/signal-desk/__fixtures__/board-v2-compare.json`
  chụp từ artifact thật phase 05

## Implementation Steps
1. Types v2 + fixture từ artifact VIC vs VCB thật.
2. `layout.ts` collapse rules + test khớp bảng `layout.py`.
3. `KpiStrip`, `BoardSection`, `SourceBadge`, `SignalDeskBoard`; test render
   fixture: đủ KPI, đủ section, span đúng.
4. 7 widget mới, mỗi cái: render fixture, role → màu, fallback kind sai.
5. `widget-registry.ts` 8 entry; test sync với JSON catalog (đã sinh ở phase 05).
6. `chart-theme.ts` roles; `widget-roles.test.tsx`.
7. Panel nhánh v2; v1 snapshot test không đổi.
8. Export v2; header autoComposed.
9. `signal-issues.ts` + `reasons.py` cho mã mới (nếu có).
10. Bốn cổng web + đo bundle chunk.

## Success Criteria
- [x] Fixture VIC vs VCB vẽ: KPI 4 ô có màu winner/loser, `comparison_table`
      span 12, caption có `<mark>` — `signal-desk-board.test.tsx`, 12 test.
      `grouped_bar` là companion của comparison và cùng span 12; `donut` không
      có trên chính board này (frame của nó không phải phần-của-tổng), nên nó
      được giữ bằng test riêng ở `board-widgets.test.tsx`.
- [x] v1 artifact cũ render không đổi — `signal-desk-panel.test.tsx` không sửa
      một dòng và vẫn xanh; nhánh v2 rẽ theo `specVersion`, không theo khoá nào
      có mặt.
- [x] Widget lạ → `data_table` + ghi chú; không khối trắng
      (`widget-registry.test.ts`, không đổi luật).
- [x] `pnpm type-check/lint/test/build` xanh. **Chunk signal-desk: 8.920 →
      11.707 byte gzip = +2.787 B (+2,7 KB)**, đo bằng cách build lại từ HEAD
      (`git stash -u -- apps/web`) và so cùng một chunk async. Trần là 60 KB.
- [x] Catalog JSON ↔ registry TS ↔ `widgets.py` đồng bộ — ba test, và
      `NOT_FRAME_WIDGETS` khai **ra tên** hai mục là thành phần của board chứ
      không phải hình vẽ của một frame, nên tên thứ ba biến mất vẫn là test đỏ.

## Ghi chú thi công (2026-08-30)

- **`cellRoles` chưa từng có trên `Frame` phía TS** — phase 02 thêm nó ở
  Python và không có ai đọc. Đây là chỗ nó được dùng: ô thắng của một so sánh
  là claim per-**ô**, và tô theo hàng chính là câu mà một so sánh sinh ra để
  tránh.
- **Hai token mới trong `globals.css`**: `--widget-benchmark` và
  `--widget-warning`. `winner`/`loser` dùng lại token của cặp thị trường (cùng
  màu, khác nghĩa); `stale` dùng lại `--widget-neutral`.
- **Bề rộng đo từ panel, không từ viewport.** Inspector là một cột người đọc
  kéo được, nên `@media` hỏi sai câu hỏi: ở 420px panel trên màn hình rộng, mọi
  breakpoint đều nói "rộng". `SignalDeskBoardView` gắn `ResizeObserver` lên hộp
  của chính nó và bắt đầu ở giả định **rộng**, để lần vẽ đầu khớp cách server
  xếp và sửa chỉ đi xuống.
- **`kpi_strip` và `caption` không vào `widget-registry`** — chúng không nhận
  một `frame` nên không thể thoả `WidgetProps`. Chúng vẫn ở catalog vì catalog
  là thứ block của board bị kiểm với, và test khai tên chúng thay vì lặng lẽ bỏ
  qua.
- **Export v2 lấy frame của *hình* đầu tiên**, không phải block đầu tiên: một
  board có thể mở đầu bằng caption, và frame mà một câu tình cờ trích không
  phải "dữ liệu đằng sau bảng này".

## Risk Assessment
- Inspector 1120px với 3 cột chật → collapse 2 cột dưới 900px; nếu vẫn chật
  ở 1120 → luật layout server đổi 3→2 cho panel (một hằng), ghi backlog
  "panel toàn màn hình" là non-goal.
- Recharts donut/waterfall cần tính base — test số học trong TS, không tin
  render.
