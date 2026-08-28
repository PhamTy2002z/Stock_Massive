---
phase: 7
title: "Mobile drawer & responsive"
status: todo
priority: P1
effort: ""
dependencies: [2]
---

# Phase 07: Mobile drawer & responsive

## Overview

Giải P1 #5: "Mobile navigation chưa có mô hình drawer đúng". Critique đo được:
trên viewport 390px, mở sidebar làm `main` còn khoảng **116px** thay vì giữ
nguyên width và để drawer phủ lên.

Scout xác nhận nguyên nhân và một chi tiết quan trọng: **Inspector đã là `fixed`**
(`app-shell.tsx:49`, `right-0`, `main` bù `paddingRight`), còn Sidebar là **flex
row + wrapper co width** (`sidebar.tsx:42-55`). Nên mô hình phủ đã tồn tại trong
repo — phase này áp nó cho sidebar, không phát minh mới.

Chi tiết thứ hai: fold dưới 768px nằm **trong reducer** (`shell-state.tsx:288-290`)
và là **một chiều** — nới rộng lại không tự mở. Nghĩa là bug không phải "reducer
sai" mà "reducer không biết có hai chế độ layout".

Chi tiết thứ ba, là bug a11y thật: sidebar đặt `aria-hidden={!open}` nhưng button
bên trong **vẫn focusable** (scout web §12). Screen reader không thấy nhưng Tab
vẫn vào — trạng thái tệ nhất của cả hai.

## Requirements

Functional:

- Dưới 768px: sidebar là drawer phủ lên, `main` **không đổi width**.
- Drawer có scrim, đóng bằng Escape và bằng bấm scrim.
- Focus trap khi mở; focus trở về trigger khi đóng.
- Khi đóng: nội dung drawer không focusable, không đọc được bằng screen reader.
- Safe-area (notch) và virtual keyboard không cắt composer.
- Hit area quan trọng ≥44px (đã có luật từ phase 01, phase này kiểm trên touch).

Non-functional:

- Từ 768px lên: hành vi inline hiện tại **không đổi** một chút nào.
- Không thêm dependency (không headless-ui, không radix cho một drawer).

## Architecture

**Reducer học hai chế độ layout.** Thêm `layoutMode: "inline" | "drawer"` dẫn
xuất từ viewport width, và tách nó khỏi `sidebarOpen`. Hiện `foldSidebarIfCramped`
(`shell-state.tsx:188-195`, hằng `SIDEBAR 274`, `CONVERSATION_MIN 520`) trộn hai
khái niệm: "không đủ chỗ" và "đóng lại". Sau phase này:

- `layoutMode === "inline"` → sidebar chiếm chỗ, `main` co (hành vi hôm nay,
  giữ nguyên, gồm cả fold khi chật).
- `layoutMode === "drawer"` → sidebar `fixed`, `main` **không nhận
  `paddingLeft`**, scrim phủ.

Fold một chiều hiện tại trở thành đúng: ở `inline` nó vẫn fold khi chật; khi
xuống `drawer` thì `sidebarOpen` đặt về `false` và mở lại **không** ăn chỗ. Nới
màn hình rộng lại → `layoutMode` về `inline`, sidebar giữ trạng thái đóng (không
tự bung — đó là hành vi hiện tại và nó không sai).

**Ngưỡng.** 768px giữ nguyên (đã dùng ở reducer). Nhưng `layoutMode` **không**
chỉ phụ thuộc width: nếu `CONVERSATION_MIN 520` không đạt được kể cả khi đóng
sidebar thì cũng là `drawer`. Viết thành một hàm thuần `layoutModeFor(width)` để
test được, không rải điều kiện.

**Focus trap không cần thư viện.** Cần đúng bốn thứ: (1) lấy danh sách element
focusable trong drawer, (2) `keydown` Tab/Shift+Tab vòng lại ở hai đầu, (3)
Escape đóng, (4) lưu `document.activeElement` lúc mở và trả focus về lúc đóng.
Khoảng 40 dòng. Một thư viện drawer mang theo cả animation system không cần.

**Khi đóng: `inert`, không phải `aria-hidden`.** Đây là cách sửa đúng bug scout
tìm được. `inert` (thuộc tính HTML) loại cả focus **và** accessibility tree trong
một lần. Support: mọi browser hiện đại. Fallback nếu cần: `aria-hidden` + gán
`tabIndex={-1}` cho mọi focusable. Ưu tiên `inert`; test khẳng định Tab không vào
được.

**Virtual keyboard.** Composer ở cuối viewport; bàn phím ảo đẩy nó lên hoặc che
nó. Dù`100dvh` (dynamic viewport height) thay `100vh` cho container chat. Đây là
đổi một đơn vị, không phải một cơ chế. Kiểm thật trên Safari iOS — `dvh` đúng ở
đó nhưng `vh` thì không.

**Safe area.** `env(safe-area-inset-bottom)` cho padding composer,
`env(safe-area-inset-top)` cho TopBar. Cần `viewport-fit=cover` trong meta viewport
(`layout.tsx`) — không có nó thì `env()` trả 0.

**Ba viewport phải test cùng lúc** (critique yêu cầu): 390px (iPhone thường),
430px (iPhone Pro Max), và tablet ~834px — cái thứ ba nằm **trên** ngưỡng 768 nên
nó kiểm rằng hành vi inline không bị phase này phá.

## Related Code Files

Modify:

- `apps/web/src/components/shell/shell-state.tsx:188-195,288-290` —
  `layoutMode`, `layoutModeFor(width)`, tách fold khỏi đóng
- `apps/web/src/components/shell/app-shell.tsx:42-55` — sidebar theo
  `layoutMode`; `main` không nhận padding ở chế độ drawer
- `apps/web/src/components/shell/sidebar.tsx:42-55` — wrapper `fixed` khi drawer,
  `inert` khi đóng
- `apps/web/src/app/layout.tsx` — `viewport-fit=cover`
- `apps/web/src/app/globals.css` — `dvh`, safe-area

Create:

- `apps/web/src/components/shell/use-focus-trap.ts`
- `apps/web/src/components/shell/drawer-scrim.tsx`
- `apps/web/src/components/shell/drawer.test.tsx`
- `apps/web/src/components/shell/shell-state-layout-mode.test.ts`
- `apps/web/e2e/mobile-drawer.spec.ts`

## Implementation Steps

1. `layoutModeFor(width)` là hàm thuần + test bảng: 320 · 389 · 390 · 767 · 768 ·
   834 · 1440. Test **trước** khi đụng component.
2. Reducer: thêm `layoutMode`, tách fold khỏi đóng. Test hồi quy: 34 case
   `shell` hiện có phải còn xanh — nếu đỏ thì reducer đã đổi hành vi inline, sai.
3. `app-shell.tsx`: nhánh drawer. `main` không padding. Sidebar `fixed`.
4. `drawer-scrim.tsx` + bấm scrim đóng.
5. `use-focus-trap.ts` (4 việc ở §Architecture) + Escape.
6. `inert` khi đóng. Test: `Tab` từ TopBar không vào được drawer đóng.
7. `dvh` + safe-area + `viewport-fit=cover`.
8. e2e `mobile-drawer.spec.ts` ở 390 · 430 · 834: mở drawer → đo width của `main`
   **không đổi**; Escape đóng; focus về trigger.
9. Cổng đầy đủ web + `pnpm test:e2e mobile-drawer.spec.ts` (tắt `pnpm dev` trước).

## Success Criteria

- [ ] `layoutModeFor` test bảng 7 giá trị xanh
- [ ] 34 case `shell` hiện có còn xanh (hành vi inline không đổi)
- [ ] Ở 390px và 430px: mở drawer → `main` giữ **đúng** width như lúc đóng
      (e2e đo `getBoundingClientRect().width`, sai số 0px)
- [ ] Ở 834px: hành vi vẫn inline, `main` co như cũ
- [ ] Scrim hiện khi drawer mở, bấm scrim đóng
- [ ] Escape đóng drawer; focus trở về trigger
- [ ] Tab vòng trong drawer, không thoát ra `main`
- [ ] Drawer đóng → `Tab` không vào được nội dung drawer (`inert` hoặc fallback)
- [ ] Composer không bị bàn phím ảo che (kiểm thật trên Safari iOS, ghi kết quả)
- [ ] Safe-area: không nội dung nào nằm dưới notch/home indicator
- [ ] `pnpm test` xanh · e2e drawer xanh · `pnpm build` xanh

## Risk Assessment

**Đổi reducer phá 34 case đang xanh.** Đây là rủi ro chính của phase. Tín hiệu
rõ ràng và sớm (bước 2). Phản ứng đã định: nếu case nào đỏ, đọc case đó và xác
định nó assert hành vi inline hay assert cấu trúc nội bộ của reducer. Assert hành
vi đỏ → **reducer sai, sửa reducer**. Assert cấu trúc nội bộ đỏ → cập nhật test.
Không đảo thứ tự hai phán quyết này.

**`inert` không hỗ trợ ở browser trong CI.** Tín hiệu: test Tab đỏ ở CI nhưng
xanh cục bộ. Phản ứng: fallback `aria-hidden` + `tabIndex={-1}` đã ghi ở
§Architecture — implement **cả hai** ngay từ đầu, không đợi CI đỏ.

**`dvh` không kiểm được trong vitest.** jsdom không có viewport thật. Phản ứng:
`dvh` và safe-area kiểm bằng e2e + một lần kiểm tay trên thiết bị thật. Ghi kết
quả kiểm tay vào phase này khi làm — nếu không kiểm được trên iOS thật thì nói
rõ là chưa kiểm, đừng đánh dấu xanh.

**Focus trap tự viết bỏ sót element focusable.** Danh sách focusable dễ thiếu
(`[contenteditable]`, `audio[controls]`, `summary`). Phản ứng: selector lấy từ
danh sách đã biết + test có một `contenteditable` trong drawer. Nếu sót nhiều hơn
kỳ vọng thì mới xét thư viện — với một drawer, tự viết vẫn rẻ hơn.

Rollback: `layoutMode` là nhánh mới; đặt `layoutModeFor` luôn trả `"inline"` là
về hành vi cũ trong một dòng. Đây là kill switch của phase, ghi vào code.
