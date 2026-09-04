---
phase: 6
title: "Signal Desk Right Panel"
status: todo
priority: P1
effort: "10h"
dependencies: [5]
---

# Phase 6: Signal Desk Right Panel

## Context Links

- `apps/web/src/components/shell/inspector.tsx:224` — `Body`, đúng chỗ `if (signalDesk) return <SignalDeskEmpty />`
- `apps/web/src/components/shell/shell-state.tsx` — `state.signalDesk` đã tồn tại
- `apps/web/src/components/signal-desk/signal-desk-empty.tsx` — docstring đã tham chiếu `SignalDeskPanel`'s skeleton
- `apps/web/src/lib/alpha-desk/api.ts:118` — `createTurn` body, chưa có `mode`
- `apps/web/src/components/shell/desk-state.tsx::DeskProvider`
- Phase 5 `VisualPart` + `compile-visual.ts`

## Overview

Nối mode Signal Desk (đã có trên composer) với backend, và thay **đúng một
nhánh** ở `Body`: `signalDesk` đang trả `<SignalDeskEmpty />` thì giờ trả panel
khi Thread có visual hoặc đang chạy Turn. Cột chat vẫn text-only.

Geometry, resize, sources toggle, compact behavior của pane đã có và không đổi.

## Một file, không phải hai

Bản trước tách `signal-desk-panel.tsx` (state switch) và `flint-chart-view.tsx`
(compile/render boundary). Cả hai cùng vòng đời, cùng client-only, và
`compile-visual.ts` của Phase 5 đã là boundary thật với Flint. Một file
`signal-desk-panel.tsx` giữ state switch + error boundary + lazy render.

Cũng cắt "retry render control" khi compile lỗi: refresh là retry, và một nút
retry cho một hàm pure compile chỉ chạy lại đúng cùng input.

## Requirements

- `createTurn` gửi `mode` là một enum value; server default vẫn `chat` cho
  client cũ.
- Chat mode render transcript y như hiện tại và **không load runtime chart**.
- Signal Desk mode hiện bốn trạng thái ở pane phải: chưa hỏi, đang chạy, có
  chart, xong nhưng không có chart.
- Trạng thái "xong nhưng không có chart" suy ra từ state đã có (Turn terminal ở
  mode signal_desk + không có key `visual`) — không cần field mới từ backend.
- Turn Signal Desk mới không được để chart cũ đứng làm kết quả hiện tại.
- Refresh và switch Thread chọn đúng visual của Thread đang mở; không leak
  chart của Thread khác.
- Sources vẫn tới được qua đường pane/header hiện có; chart không nhân đôi
  evidence prose.
- Dùng nguyên output Flint của Phase 5. CSS chỉ set width/height/padding và
  khung loading/error.
- Accessibility: pane và figure có label ổn định, loading/error announce được,
  keyboard resize/close giữ nguyên, reduced motion được tôn trọng.
- Responsive: desktop dùng pane phải; compact dùng đúng inspector behavior hiện
  có, không viết layout thứ hai.

## UI State Table

| Turn state | Right pane | Chat column |
|---|---|---|
| Chưa có câu hỏi Signal Desk | `SignalDeskEmpty` hiện có | Transcript hiện có |
| Turn Signal Desk đang chạy | Skeleton/progress gọn; chart cũ không mang nhãn "hiện tại" | Text/thought/tool progress bình thường |
| Xong + có visual | Flint chart, title/as-of/số nguồn | Chỉ text answer |
| Xong + không có visual | Một dòng ngắn: câu trả lời này không có chart đủ bằng chứng | Text refusal + ledger gaps |
| Compile lỗi | Error trong pane, isolated | Chat vẫn dùng được |
| Chat mode | Desk đóng, hoặc dòng `noDeskView` hiện có | Hành vi hiện tại, không mount Flint |

## File Inventory

| Action | File | Purpose |
|---|---|---|
| Modify | `apps/web/src/lib/alpha-desk/api.ts` | Gửi `mode` khi tạo Turn. |
| Modify | `apps/web/src/components/shell/desk-state.tsx` | Snapshot mode lúc submit; chọn visual theo Thread. |
| Modify | `apps/web/src/lib/alpha-desk/live-turn.ts` | Mang visual/progress qua terminal refetch, không fallback về chart cũ. |
| Create | `apps/web/src/components/signal-desk/signal-desk-panel.tsx` | State switch + error boundary + lazy Flint render. |
| Modify | `apps/web/src/components/shell/inspector.tsx` | Một nhánh ở `Body`. |
| Modify | `apps/web/src/components/signal-desk/signal-desk-empty.tsx` | Chỉ copy phân biệt "chưa hỏi" với "không có chart"; không redesign. |
| Create | `apps/web/src/components/signal-desk/signal-desk-panel.test.tsx` | Mode, state, thread, replay, a11y. |
| Modify | `apps/web/src/components/shell/shell.test.tsx` | Geometry, toggle, sources, compact. |
| Modify | `apps/web/src/lib/alpha-desk/api.test.ts` | Mode compatibility. |

Không sửa `transcript.ts` (xem Phase 5: nó chỉ đọc key nó biết) và không sửa
`read-content.ts` (Phase 5 đã thêm `readVisual`).

## Implementation Steps

1. Test API client trước: default chat, explicit chat, signal_desk, mode sai,
   và retry giữ đúng mode gốc.
2. Snapshot `signalDesk` tại submit/queue/resend và mang theo request object;
   không đọc lại toggle lúc request thật sự dispatch.
3. Selector thuần cho visual (live → persisted → không có), scope theo Thread.
   Test switch Thread và Turn mới xoá nhãn "hiện tại" của chart cũ.
4. `signal-desk-panel.tsx`: bốn state, error boundary, `compile-visual.ts` của
   Phase 5, không transform option/theme.
5. Gắn ở `Inspector.Body`, giữ nguyên geometry và sources toggle.
6. Test compact/reduced-motion/keyboard/ARIA + một production build để bắt lỗi
   import ECharts phía server.
7. Chạy một Turn Signal Desk thật, refresh giữa lúc chạy và sau khi xong, rồi
   switch Thread; ghi screenshot vào phase report.

## Test Matrix

| Scenario | Expected |
|---|---|
| Toggle off + submit | `mode=chat`; không mount, không load chart runtime. |
| Toggle on + submit | `mode=signal_desk`; pane hiện progress. |
| Toggle đổi khi đang queue | Request dùng snapshot lúc submit. |
| Turn mới sau chart cũ | Chart cũ mất nhãn hiện tại; loading rồi chart mới. |
| Refresh giữa lúc chạy | Reattach Turn/progress; không tạo Turn hay tool call trùng. |
| Refresh sau khi xong | Cùng assembly compile lại, không backend work. |
| Switch Thread | Chỉ visual của Thread đang chọn. |
| Turn xong không có visual | Dòng ngắn trong pane; text answer nguyên vẹn. |
| Visual persisted hỏng | Chỉ pane lỗi; chat vẫn đọc được. |
| Flint compile throw | Error boundary nằm trong pane. |
| Compact/keyboard/reduced motion | Behavior và label inspector hiện có pass. |

## Verification Commands

```bash
pnpm --dir apps/web test -- src/lib/alpha-desk/api.test.ts src/lib/alpha-desk/live-turn.test.ts src/components/signal-desk/signal-desk-panel.test.tsx src/components/shell/shell.test.tsx
pnpm --dir apps/web lint
pnpm --dir apps/web type-check
pnpm --dir apps/web build
git diff --check
```

Build production trong worktree dev đụng `.next` — dùng
`E2E_NEXT_DIST_DIR=.next-verify pnpm build` để không phải dừng dev server.

## Success Criteria

- [ ] Một prompt Signal Desk thật cho text ở Chat và **chỉ** Flint visual ở pane phải.
- [ ] Chat mode không request, không parse vào transcript, không mount visual;
      chunk chart không nằm trong bundle của chat path.
- [ ] Refresh/reconnect/switch Thread giữ đúng ownership, chọn visual
      deterministic, không backend work trùng.
- [ ] Output Flint không bị sửa; compile failure isolated trong pane.
- [ ] Sources drawer, pane resize, compact layout và a11y test hiện có còn xanh.

## Risks And Rollback

**Mode race:** queued send đọc toggle hiện tại thay vì giá trị lúc submit. Chặn
bằng request object immutable + regression test.

**Chart bundle lọt vào Chat:** dynamic import bị eager. Kiểm bằng build chunk +
spy mount ở chat mode. Rollback: `Body` trả lại `SignalDeskEmpty` và ngừng gửi
`signal_desk`; đường text/evidence backend vẫn hợp lệ.
