---
phase: 2
title: "Flint Contract Spike"
status: todo
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

_Điền khi phase chạy xong._
