---
phase: 1
title: "Freeze, contract & a11y baseline"
status: todo
priority: P1
effort: ""
dependencies: []
---

# Phase 01: Freeze, contract & a11y baseline

## Overview

Mở freeze đúng tên file, sửa ba chỗ CLAUDE.md đã lệch thực tế, viết design
contract thành file có thể kiểm bằng test, và vá lớp a11y nền mà mọi phase sau
sẽ dựa lên. Không đổi một hành vi sản phẩm nào — đây là phase làm sạch nền.

Lý do đi trước: phase 02–12 đều thêm control mới. Nếu luật touch target, focus
ring và ngôn ngữ ARIA chưa thành test, mỗi phase sau sẽ tự phát minh lại và plan
kết thúc bằng chín kiểu control khác nhau.

## Sửa sau red-team (2026-08-28)

Bốn điều chỉnh:

1. **Freeze amendment của bản đầu nêu bốn file không tồn tại** (`src/agent/models.py`,
   `src/agent/service.py`) và bỏ sót năm file thật. Danh sách đúng ở `plan.md`
   §Freeze amendment — **dùng bảng ở đó**, không dùng danh sách nào khác.
2. **`message-shell.tsx` và `message-actions.tsx` ở `apps/web/src/components/alpha/message/`**,
   không ở `components/shell/`. Bản đầu ghi sai đường dẫn cho cả hai.
3. **Phase 03 cần freeze mở vào `src/stocks/trading_day.py`** — lịch giao dịch đọc
   bảng đã chết (`plan.md` §S1). Bản đầu không biết điều này nên không mở.
4. **Kiểm hit area bằng vitest là test luôn xanh** — jsdom trả `getBoundingClientRect()`
   toàn 0. Phase này giữ test **class** (kiểm được trong vitest); phép đo pixel
   thật chuyển sang e2e ở phase 12 (`plan.md` §S11).

## Requirements

Functional:

- CLAUDE.md ghi đúng phạm vi freeze mở cho plan này (bảng ở `plan.md`), và đúng ba
  con số đang lệch.
- `docs/design-guidelines.md` tồn tại, ngắn, và mọi luật trong đó **có một test
  tương ứng** — không luật nào chỉ là lời khuyên.
- Hit area mọi control tương tác ≥44×44px trong khi **giữ nguyên mật độ thị
  giác** hiện tại (28–30px là chủ ý thiết kế, không phải lỗi).
- Focus ring hiển thị trên ~9 control đang thiếu.
- Không còn nhãn ARIA tiếng Anh.

Non-functional:

- Zero thay đổi hành vi. Diff không được làm đổi bất kỳ test nào trong 446 case
  hiện có, ngoài các assertion về nhãn ARIA mà chính phase này đổi.
- Không thêm dependency.

## Architecture

**Touch target không đổi kích thước thị giác.** `IconButton` ở
`apps/web/src/components/shell/primitives.tsx:96` dùng `size-7` (28px) và
`size-[30px]`. Nới chúng lên 44px sẽ phá nhịp compact mà critique khen là điểm
mạnh ("dark tonal ladder, amber tiết chế"). Cách giữ cả hai: giữ box thị giác,
mở rộng vùng chạm bằng pseudo-element.

```css
/* Vùng chạm bao ngoài, không đổi layout, không đổi khoảng cách thị giác */
.hit-44::after {
  content: "";
  position: absolute;
  inset: 50%;
  width: 44px; height: 44px;
  transform: translate(-50%, -50%);
}
```

Control cần `position: relative`. Với control nằm sát nhau (`gap` nhỏ), vùng chạm
sẽ chồng lấn — luật đi kèm: **hai control có hit area chồng nhau phải cách nhau
≥8px thị giác**, và test kiểm khoảng cách này, không kiểm kích thước.

**Focus ring thành một token, không phải chín lần copy.** Hiện `IconButton`,
`MenuItem`, `NavRow`, `RenameField` mỗi cái tự viết. Rút thành một utility class
trong `globals.css`, mọi control tương tác dùng nó. Danh sách control đang thiếu
(từ scout web §12): Send, Dừng, Chia sẻ, ThreadRow, tab inspector, palette row,
ScopeRow, FollowUps, CanvasCard.

**Ngôn ngữ ARIA là luật, không phải sở thích.** UI tiếng Việt thì screen reader
phải nghe tiếng Việt. Năm chỗ còn tiếng Anh: `message-shell.tsx:29`,
`inspector.tsx:68`, `:79`, `:100`, `:120`. Test bắt regression bằng cách quét
mọi `aria-label`/`aria-description` trong `components/` và từ chối chuỗi khớp
danh sách từ Anh phổ biến (`Copy`, `Close`, `Open`, `Sources`, `Analysis`...) —
không cố phát hiện ngôn ngữ, chỉ chặn đúng những từ đã gặp cộng những từ dễ lọt.

## Related Code Files

Modify:

- `CLAUDE.md` — freeze amendment + ba số lệch
- `apps/web/src/app/globals.css` — token focus ring, utility hit area
- `apps/web/src/components/shell/primitives.tsx` — `IconButton`, `MenuItem`,
  `NavRow`, `RenameField` dùng token chung
- `apps/web/src/components/alpha/message/message-shell.tsx:29` — nhãn ARIA
  (**không** ở `components/shell/`)
- `apps/web/src/components/shell/inspector.tsx:68,79,100,120` — nhãn ARIA
- 9 file chứa control thiếu focus ring (danh sách ở scout web §12)
- `apps/web/src/lib/greeting.ts:38-40` — xoá docstring trỏ `shell/view-new` đã
  bị xoá (stale reference, không phải hành vi)

Create:

- `docs/design-guidelines.md`
- `apps/web/src/components/shell/accessibility.test.tsx` — contract test

Delete:

- `apps/web/src/hooks/use-mobile.tsx` — scout web §1 xác nhận **không có
  importer**. Phase 07 sẽ cần logic breakpoint nhưng đặt trong reducer, không
  hồi sinh hook mồ côi.

## Implementation Steps

1. Sửa CLAUDE.md: mở freeze theo danh sách file ở `plan.md` §Freeze amendment;
   sửa `PROMPT_VERSION` 2.6.0 → 2.7.0, 8 tool/3 bundle → 12 tool/4 bundle,
   406 → 446 test web. **Xác minh lại từng số bằng grep trước khi ghi**, không
   copy từ plan.
2. Viết `docs/design-guidelines.md`: token palette đang dùng (surface 6 bậc, ink
   7 bậc, amber `--primary` #f59331, market green/red, board VN ceiling/
   reference/floor — trích từ `globals.css:45-114`, **không** phát minh màu mới),
   scale chữ tự đặt (base 15px, eyebrow/micro/meta/control/row), vai trò font
   (Inter body · JetBrains Mono số/nhãn · Newsreader chỉ greeting), và 5 luật
   kiểm được: hit area, khoảng cách, focus ring, ngôn ngữ ARIA, reduced-motion.
3. Thêm token focus ring + utility hit area vào `globals.css`.
4. Refactor `primitives.tsx` dùng token; lan ra 9 control còn thiếu.
5. Đổi 5 nhãn ARIA sang tiếng Việt.
6. Viết `accessibility.test.tsx`: render từng control trong shell, khẳng định
   (a) có accessible name, (b) name không khớp danh sách từ Anh, (c) có class
   focus ring, (d) có class hit area. Test đọc **danh sách control tường minh**
   — một mảng ở đầu file — để khi phase sau thêm control thì test đỏ và người
   thêm phải khai, chứ không im lặng lọt.
7. Xoá `use-mobile.tsx` (xác nhận lại zero importer trước khi xoá).
8. Cổng: `pnpm type-check && pnpm lint && pnpm test && pnpm build`.

## Success Criteria

- [ ] `docs/design-guidelines.md` có 5 luật, mỗi luật trỏ tên test thực thi nó
- [ ] `accessibility.test.tsx` xanh; thêm một control mới không khai → test đỏ
- [ ] Grep `aria-label` trong `apps/web/src/components/` không còn chuỗi tiếng Anh
- [ ] Mọi control tương tác trong shell có **class** hit area, và khoảng cách giữa
      hai control có vùng chạm chồng nhau ≥8px — kiểm được trong vitest. Phép đo
      pixel thật (≥44px) là e2e ở phase 12, **không** khẳng định ở đây: jsdom trả
      rect 0 nên một assertion pixel ở phase này sẽ xanh mà không kiểm gì
- [ ] CLAUDE.md khớp thực tế ở cả ba con số — verify lại bằng grep, không bằng plan
- [ ] `pnpm test` ≥446 case pass (số tăng do test mới, không giảm)
- [ ] `make test` (apps/api) vẫn 1060 pass — phase này không đụng API

## Risk Assessment

**Hit area chồng lấn tạo vùng chết.** Nếu hai control cách nhau 4px và mỗi cái
nhận 44px, vùng chồng nhau sẽ thuộc về control vẽ sau — user bấm vào cái này
trúng cái kia. Tín hiệu: test khoảng cách đỏ ở cụm nào đó (message actions,
composer footer). Phản ứng: nới `gap` cụm đó lên 8px — đây là đổi thị giác nhỏ,
được phép; **không** giảm hit area xuống dưới 44px để tránh nới gap.

**Test quét từ tiếng Anh là heuristic, không phải kiểm ngôn ngữ.** Nó chặn được
regression của đúng những từ đã liệt kê. Chấp nhận: rẻ, không phụ thuộc, và bắt
đúng lỗi đã xảy ra thật. Không đổi thành detect ngôn ngữ.

**Freeze amendment ghi sai thành giấy phép quá rộng.** Nếu ghi "mở
`src/agent/*`" thì mất luôn cái freeze bảo vệ. Phản ứng: liệt kê **tên file**,
không dùng wildcard, trừ hai module mới (`src/market_context/*`,
`src/agent/export/*`) vốn chưa tồn tại nên không có gì để phá.

Rollback: phase này thuần additive + rename. `git revert` một commit là xong;
không có migration, không có contract đổi.
