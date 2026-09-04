---
phase: 1
title: "Roadmap Deviation"
status: todo
priority: P1
effort: "1h"
dependencies: []
---

# Phase 1: Roadmap Deviation

## Context Links

- `CLAUDE.md` — capability catalog và retired-path boundary
- `docs/roadmap.md` §2, §4, §6, §9, Phase 6, Phase 12
- `plans/reports/research-260904-2254-vnstock-personal-to-saas-production.md`
- [Flint](https://github.com/microsoft/flint-chart), [Vnstock](https://github.com/thinh-vu/vnstock)

## Overview

Roadmap đang cấm market-data SDK, chart runtime và mọi output Signal Desk. Đây
là one-way door (capability catalog) nên `CLAUDE.md` bắt buộc một deviation
report được owner chấp nhận trước khi có dòng code nào. Không phase nào sau
được bắt đầu khi mâu thuẫn còn tồn tại.

Documentation-only: không code, không dependency, không schema.

## Deviation Draft

Report phải chứa đúng bảng này cộng rollback; đây là toàn bộ nội dung deviation.

| Quyết định cũ | Evidence mới | Amendment hẹp |
|---|---|---|
| Signal Desk output retired | Owner đã restore mode + pane; Flint có typed assembly/compiler boundary. | Mở visual part ở pane phải. Board/Study/widget vẫn retired. |
| Market SDK prohibited | Live Vnstock probe: OHLCV/quote/trades bounded dùng được cho internal research. | Mở một provider-neutral read tool, internal profile only, production fail-closed. |
| Phase 6 web-only evidence | Structured market values cần unit/time/provenance mà web search không bảo đảm. | Thêm `STORE_FIGURE` evidence; web vẫn là narrative/primary source. |
| MCP chờ Phase 12 | Phase 2 import npm package trực tiếp. | Không amend — lệnh cấm generic MCP giữ nguyên. |

Trade-off phải nêu: chọn Flint thay lieflat cho core, và từ chối agent loop thứ
hai. Rollback: revert amendment, Signal Desk trở lại pane rỗng.

Giữ nguyên: truth contract, one-call-one-result, typed Turn settlement,
permission/budget plane, thứ tự phase tuần tự, `mode=chat` là default
backward-compatible, và Study/Board DSL, widgets, stock store, scheduler,
watchlist, broker/order, generic MCP đều ngoài scope.

Paid quality gate còn lại của Phase 6 evidence engine chuyển vào Phase 7 của
plan này — không chạy hai corpus cạnh tranh.

## Implementation Steps

1. Viết `plans/reports/deviation-260905-signal-desk-flint-vnstock.md` từ bảng trên.
2. **Dừng ở owner decision gate.** Bị từ chối = đóng plan, không code.
3. Sau khi chấp nhận, sửa `CLAUDE.md` và `docs/roadmap.md` trong **cùng một
   commit** để hai file khớp nhau về capability, thứ tự phase và stop condition.

## Verification

```bash
rg -n 'signal_desk|get_market_data|Flint' CLAUDE.md docs/roadmap.md
```

Hai file phải mô tả cùng ba capability. Không chạy test suite: phase này không
chạm production code.

## Success Criteria

- [ ] Owner acceptance nằm trong deviation report.
- [ ] Hai authority file khớp nhau (lệnh `rg` ở trên chứng minh).
- [ ] Không production code, dependency, schema hay API contract nào đổi.

## Risks And Rollback

**Scope creep:** wording mở lại analysis system cũ. Tín hiệu: bất kỳ capability
nào ngoài ba dòng amendment — gỡ trước khi approve.

**Conflicting authority:** sửa một file quên file kia. Phase không đóng cho tới
khi `rg` chứng minh khớp. Rollback là documentation-only.
