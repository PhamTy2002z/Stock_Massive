---
phase: 2
title: "Flint Contract Spike"
status: done
priority: P1
effort: "2h"
dependencies: [1]
---

# Phase 2: Flint Contract Spike

## Context Links

- [microsoft/flint-chart](https://github.com/microsoft/flint-chart) — npm `flint-chart`, latest `0.5.1` (verified 2026-09-05)
- `apps/web/package.json` — vitest 4 đã có sẵn
- `apps/web/src/components/signal-desk/signal-desk-empty.tsx`

## Overview

Trả hai câu hỏi trước khi tiêu 44h vào Phase 3–4: (1) `ChartAssemblyInput` thật
sự có hình dạng gì và validator từ chối kiểu gì, (2) candlestick + volume của
Flint có đọc được ở khổ pane phải không.

Cài đúng package Phase 5 sẽ dùng, một fixture, một test. Không MCP: adapter tạm
để hỏi một thư viện ta sẽ import trực tiếp = thêm process, port, flag, security
surface cho zero thông tin thêm.

## Requirements

- Pin `flint-chart` ở version đã verify trên registry; dùng public export của
  release đó, không đoán tên API từ trí nhớ.
- Một fixture `ChartAssemblyInput` hợp lệ: OHLCV candlestick + volume, dữ liệu
  synthetic bounded, không claim tài chính thật. Fixture là contract Phase 5
  tiêu thụ nên export được từ test file.
- Test: fixture compile thành công; một input thiếu field bắt buộc bị validator
  từ chối và lỗi có shape dùng được cho stop reason `invalid_visual`.
- Không persist ECharts option. Không fork, patch, override template hay hậu xử
  lý output của Flint.
- Không đổi API, DB, SSE. Chưa render trong app.

## File Inventory

| Action | File | Purpose |
|---|---|---|
| Modify | `apps/web/package.json` | Thêm `flint-chart` pinned — đúng dependency Phase 5 cần. |
| Create | `apps/web/src/components/signal-desk/flint-contract.test.ts` | Fixture (exported) + compile + negative case. |
| Modify | Phase doc này | Ghi Findings ở cuối: version, import/type thật, shape lỗi, verdict thị giác. |

Fixture inline trong test thay vì `__fixtures__/*.json`: một file thay vì ba,
và Phase 5 import trực tiếp const đã typed. Bỏ comparison fixture — candlestick
+ volume đã là 2 series 2 axis, chứng minh xong compile/validate; thêm khi
Phase 5 thật sự assemble chart comparison.

## Implementation Steps

1. `pnpm --dir apps/web add flint-chart@<verified version>`; kiểm license và
   public export của bản đã cài.
2. Viết `flint-contract.test.ts`: fixture synthetic OHLCV, assert compile thành
   công, assert input thiếu field bắt buộc bị từ chối.
3. Dump ECharts option ra một trang HTML scratch **ngoài repo**, mở ở khổ pane
   phải, nhìn label/axis/tooltip/legend/resize. Bước duy nhất cần mắt người.
4. Ghi Findings vào cuối file này (không tạo report riêng — cùng nội dung, một
   nơi): version đã pin, import/type Phase 5 phải dùng, shape lỗi validator,
   verdict thị giác đủ/không đủ kèm lý do.

## Verification Commands

```bash
pnpm --dir apps/web test -- src/components/signal-desk/flint-contract.test.ts
pnpm --dir apps/web lint
git status --short
```

## Success Criteria

- [ ] Test xanh: fixture compile, negative case bị từ chối.
- [ ] Visual output là output nguyên bản của Flint, đọc được ở khổ pane phải.
- [ ] Không ECharts option, không source fork nào bị commit.
- [ ] Findings ghi đúng import, type và failure behavior Phase 5 dùng.

## Risks And Rollback

**Package surface khác tài liệu:** dừng, cập nhật phase từ release docs; không
bọc compatibility wrapper quanh API đoán mò.

**Candlestick không đạt baseline thị giác:** đánh dấu plan blocked, xem lại lựa
chọn thư viện bằng một deviation mới. Rollback: gỡ dependency, xoá test;
production không bị chạm.

## Findings

### Version và license

`flint-chart@0.5.1` pinned trong `apps/web/package.json`. License **MIT**,
author Microsoft Corporation. `echarts` là **optional peer dependency** — Phase 2
không cài nó vì compile không cần; Phase 6 sẽ cần khi render.

### Import và type Phase 5 phải dùng

```ts
import { assembleECharts, ecAllTemplateDefs } from "flint-chart/echarts"
```

`assembleECharts(input: ChartAssemblyInput): any`. Trả về ECharts option kèm các
key nội bộ `_width`, `_height`, `_dataLength`, `_transform`, và `_warnings` chỉ
khi có warning.

`ChartAssemblyInput` (từ `core/types`, `chart_spec` là object literal ẩn danh,
không có interface tên `ChartSpec`):

| Field | Bắt buộc | Ghi chú |
|---|---|---|
| `data` | ✅ | `{ values: any[] }` hoặc `{ url: string }` |
| `chart_spec.chartType` | ✅ | tên template, đúng chuỗi trong `ecAllTemplateDefs` |
| `chart_spec.encodings` | ✅ | `Record<string, string \| ChartEncoding \| ...>`; string = tên cột |
| `chart_spec.baseSize` / `canvasSize` | — | `{width,height}`, mặc định 400×320 |
| `chart_spec.title` / `subtitle` | — | |
| `semantic_types` | — | `Record<string, string \| SemanticAnnotation>` |
| `theme_spec`, `options`, `field_display_names` | — | `field_display_names` đổi tên trục và series |

### Candlestick **không có channel volume**

```
Candlestick Chart → channels: x, open, high, low, close, column, row
```

Giả định của plan ("candlestick + volume là 2 series 2 axis") **sai**. Giá và
khối lượng là **hai `ChartAssemblyInput` và hai option**, không phải một chart
hai trục. Gộp lại sau khi compile = sửa output của Flint, điều plan cấm. Phase 5
assemble hai input; Phase 6 xếp chồng hai container.

Test khoá lại điều này: nếu bản sau thêm channel `volume`, test đỏ và quyết định
hai-chart được xem lại có chủ đích.

### Shape lỗi — **Flint không validate**

Đây là finding quan trọng nhất và nó đổi thiết kế Phase 5.

| Input | Hành vi thật |
|---|---|
| `chartType` không tồn tại | **Throw** `Error: Unknown ECharts chart type: X. Use ecAllTemplateDefs to see available types.` |
| Thiếu `chart_spec` | Throw `TypeError` — message là lỗi truy cập thuộc tính, không phải lỗi contract |
| **Thiếu channel bắt buộc** (không có `close`) | **Không throw.** Trả option có `series === undefined` |
| **Encoding trỏ vào cột không row nào có** | **Không throw, không warning.** Trả series `candlestick` bình thường — nhìn như đã chạy đúng |
| `values: []` | Không throw; `_dataLength === 0` |

Hệ quả: **gate `invalid_visual` là của host, không phải của Flint.** Phase 5 phải
validate trước khi gọi `assembleECharts`:

1. mọi channel bắt buộc của chartType đó đều được encode (Flint không khai
   channel nào bắt buộc — host tự khai, cho đúng hai chart type ta dùng);
2. mọi field được encode đều có mặt và hữu hạn trên **mọi** row.

Quy tắc này đã viết và chứng minh trong test (`gives the host a checkable rule
for all three`) nên Phase 5 chép được nguyên vẹn thay vì suy lại.

Điều này ăn khớp với ràng buộc evidence: một field không có trong data thì không
thể có evidence ID, nên gate visual và gate provenance là **một** kiểm tra.

### Verdict thị giác (render thật, headless Chrome, khổ pane phải)

Scratch page ngoài repo: `/tmp/flint-scratch/pane.html`, ảnh
`/tmp/flint-scratch/pane.png` (volume 120px) và `pane2.png` (volume 200px).

**Đạt, có ba điều kiện cho Phase 6:**

1. **Candlestick 388×240 đọc tốt.** Nến, râu, gridline, tick giá và tick ngày
   thưa hợp lý; không chồng chữ. Màu mặc định xanh tăng / đỏ giảm, khớp quy ước
   Việt Nam.
2. **Volume 120px là hỏng, ≥200px thì đạt.** Ở 120px nhãn trục y chồng thành
   vệt không đọc được và nhãn x xoay 90° ăn hết chiều cao, cột bị bẹp. Ở 200px
   cả hai trục sạch. Phase 6 cấp tối thiểu 200px cho volume.
3. **`baseSize` không phải là ràng buộc cứng.** Hỏi 388×240 thì `_width/_height`
   trả 409×301; thêm `canvasSize` cũng vậy. Đây là *gợi ý* — kích thước thật do
   container DOM quyết định. Phase 6 set kích thước bằng CSS container và coi
   `_width/_height` là gợi ý, không phải hợp đồng.

Hai điểm copy cho Phase 6 (không chặn phase này):

- Nhãn trục y của candlestick là `Price` — chuỗi tiếng Anh Flint tự sinh cho
  nhóm OHLC, `field_display_names` cho `open/high/low/close` **không** ghi đè
  được. `field_display_names.time` thì có tác dụng (trục x hiện `Phiên`).
- Nhãn x của volume là `2026-08-10` xoay dọc. Rút ngắn giá trị cột `time` **ở
  data trước khi assemble** (host chuẩn bị input — hợp lệ), không phải sửa option
  sau khi compile.
