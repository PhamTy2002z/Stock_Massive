# Phase 05 — Web canvas panel + widget registry v1

Nhóm A, chốt vertical slice. **Hai nửa (audit N1):** bước 0 (widgets trên
fixture) chỉ cần contracts của 01 — chạy song song 02–04, chart nhìn thấy
được từ ngày đầu; phần wiring SSE/fetch phụ thuộc 04.

## Context

Layout đã có ba vùng (`app-shell.tsx`: sidebar · transcript · inspector
resizable). Canvas = **tab thứ hai trong inspector**, cạnh Sources — không
layout mới. Quyết định #34 đảo có phạm vi: panel nhiều widget; transcript
text-trước, ≤1 widget inline (v1: transcript chỉ hiện **card mở canvas**,
chưa render widget inline — trần inline để dành khi có nhu cầu thật).

Bài học `docs/research/web-viz-inventory.md` (bắt buộc áp): widget nhận
`{categories, series}` + label trong series; top-N là policy caller; empty
state nói ra; palette token `--chart-1..5`/`--positive`/`--negative`, cấm
white-on-white; widget hiển thị dữ liệu store **mang tuổi dữ liệu**.

## Requirements

- Dep mới: `pnpm --dir apps/web add recharts` (^3.x — đã vet 3.10.1 trước
  rip-out). Duy nhất dep này.
- Widget registry: `Map<"name@version", Component>`; props chuẩn
  `{frame, options, provenance}`. Unknown `(name, version)` hoặc frame
  malformed → render `DataTableWidget` fallback + ghi chú "Hiển thị dạng
  bảng" — transcript không bao giờ crash (luật #34 giữ).
- 4 widget v1: `stat_tiles` (không chart lib) · `bar_series` (recharts) ·
  `session_heatmap` (**SVG tự vẽ**: grid phiên × bucket, thang 4 mức tô theo
  share; có bảng dữ liệu tương đương cho screen reader) · `ranked_bars`
  (recharts, horizontal).
- Provenance strip trên đầu canvas: `source · asOf · sessionsUsed ·
  health` — reopen thread hiển thị đúng ngày cũ, kèm nhãn tuổi ("dữ liệu
  ngày …"), không re-fetch slice mới (as-of đóng băng).
- SSE: thêm `canvas.ready` vào `EVENT_TYPES` allowlist + case reducer
  (`live-turn.ts`); shell-state: inspector tab `sources | canvas`, auto-mở
  canvas khi event tới **nếu** user chưa pin tab khác.
- Client API: `fetchArtifact(id)` qua alpha proxy; TanStack Query key
  `["artifact", id]`, staleTime Infinity (bất biến theo thiết kế).

## Files

- `src/lib/alpha-desk/api.ts`, `types.ts` — `fetchArtifact`, types
  `CanvasSpec`, `Frame`, `ArtifactPayload`
- `src/hooks/use-live-turn.ts`, `src/lib/alpha-desk/live-turn.ts` — event mới
- `src/components/shell/shell-state.tsx` — inspector tab state
- `src/components/shell/inspector.tsx` — tab bar Sources | Canvas
- `src/components/canvas/canvas-panel.tsx` — fetch + provenance strip + blocks
- `src/components/canvas/widget-registry.ts`
- `src/components/canvas/widgets/{stat-tiles,bar-series,session-heatmap,ranked-bars,data-table}.tsx`
- `src/components/alpha/message/assistant-message.tsx` — card "Xem phân tích
  trên canvas" khi turn có artifact
- Tests: reducer nhận canvas.ready · registry fallback (unknown version →
  data-table, không throw) · canvas-panel render fixture spec · heatmap
  render đúng số ô · reopened-thread giữ asOf (mock artifact cũ)

## Steps

0. **Fixture dev page (audit N1) — bắt đầu ngay sau 01-contracts:**
   `src/components/dev/canvas-fixture.tsx` — dev-only theo đúng khuôn
   `agentation-toolbar.tsx` (NODE_ENV gate, dynamic import, không vào bundle
   prod). Render `contracts/fixtures/artifact-intraday-liquidity.json` qua
   registry thật. Đây là chỗ chỉnh look-and-feel của cả 5 widget mà không cần
   backend chạy — mọi bug render lộ ở đây, trước khi wiring.
1. Types + fetch + reducer + tests reducer.
2. Registry + data-table fallback trước (đường degrade có trước đường đẹp).
   **Contract test (audit N7):** vitest đọc
   `../../contracts/canvas-widget-catalog.json` (repo root), khớp registry FE
   — lệch tên/version với BE → test đỏ, không đợi demo mới lộ.
3. 4 widget; **theme (audit N6): mặc định app là dark** (`defaultTheme="dark"`,
   layout.tsx:86) — chart đầu tiên user thấy là nền tối; màu chỉ qua token
   `--chart-1..5`/`--positive`/`--negative` (đã có sẵn hai theme,
   globals.css:107-175); heatmap thang 4 mức + ô "không có dữ liệu" (null ≠ 0,
   audit N9) phải đạt contrast cả hai nền; test render hai theme là gate.
4. **Perceived speed (audit N4):** nhận `canvas.ready` → mở tab + render
   skeleton theo `blockCount` ngay (<1s), fetch artifact song song; block
   fill dần khi data về — panel không nhảy layout.
5. **Resize không jank (audit N5):** trong lúc kéo handle (shell-state đã có
   drag flag) đóng băng width canvas, re-measure khi thả; widget bọc
   `React.memo` theo `(artifactId, blockIndex)` — cấm deep-compare series
   (bài học lodash isEqual trong web-viz-inventory).
6. Inspector tab + auto-open (tôn trọng tab user đã pin) + card trong
   transcript.
7. **e2e fixture (audit N10):** thêm endpoint artifact + `canvas.ready` vào
   `apps/api/tests/e2e/server.py` — không thì `pnpm test:e2e` đỏ vì thiếu
   backend giả.
8. `pnpm type-check && pnpm lint && pnpm test && pnpm build`; `pnpm test:e2e`.

## Validation

Acceptance #1–#4 của plan.md kiểm ở đây (câu hỏi thật → canvas 4 block;
frames không qua model — test phase 04; reopen giữ asOf; unknown widget →
bảng).

## Risk & rollback

- Recharts 3.x API lệch bản 3.10.1 cũ: pin minor nếu vấp. Rollback: gỡ tab
  canvas (inspector về một tab), backend giữ nguyên — hai chiều độc lập.
