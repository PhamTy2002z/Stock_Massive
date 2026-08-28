---
phase: 12
title: "Verification & re-score"
status: todo
priority: P1
effort: ""
dependencies: [4, 5, 6, 7, 9, 10, 11]
---

# Phase 12: Verification & re-score

## Overview

Phase đóng plan. Nó không thêm feature. Ba việc: chốt lớp a11y mà các phase trước
mỗi cái chỉ lo phần của mình, dựng e2e cho luồng người dùng thật ở ba viewport, và
**đo lại** bằng chính critique đã sinh baseline 22/40.

Nó cũng dọn hai món nợ đã biết từ plan Study — chúng nằm ở e2e và sẽ làm cổng của
phase này đỏ vì lý do không liên quan.

## Sửa sau red-team (2026-08-28)

Ba điều chỉnh:

**1. Phase này nhận thêm mọi phép đo pixel** mà các phase trước không đo được: hit
area ≥44px và vị trí cụm mở đầu. jsdom trả `getBoundingClientRect()` toàn **0**, nên
mọi assertion pixel trong vitest **luôn xanh** và không kiểm gì. Chuyển sang e2e
Playwright, nơi rect là thật.

**2. Cognitive load ≤1 fail không cam kết được.** Critique đo "minimal choices" trên
**toàn sidebar** (`docs/text.md:177,185`, ~18 item). Sau phase 05 (ba nhóm recency +
nhóm ghim + "Đã xoá" + nút "Xem thêm" mỗi nhóm) con số có thể **>20**. Nên tiêu chí
đổi thành: đếm lại theo đúng định nghĩa của critique, và **nêu rõ tiêu chí nào không
đạt kèm lý do** — không cam kết một con số chưa được kiểm là đạt được.

**3. Thêm một lane test mà bản đầu không có: đối chiếu lời hứa UI với prompt
contract.** Trust line của phase 04 (đã sửa ở S9) hứa cái hệ thống làm; nếu ai sửa
`prompt/sections.py` mà không sửa trust line thì hai chỗ lệch và không test nào bắt.
Test đọc cả hai và khẳng định trust line không hứa điều prompt cấm.

## Requirements

Functional:

- Menu custom có semantics bàn phím đầy đủ ở **mọi** menu, không chỉ menu mới.
- Contrast đạt AA trên cả theme dark và `.light`.
- e2e phủ 4 luồng chính ở 3 viewport, **cộng** hai phép đo pixel chuyển từ phase
  01 và 04.
- Nợ e2e đã biết được dọn.
- Test đối chiếu trust line với prompt contract.

Non-functional:

- Design Health ≥32/40, mọi heuristic ≥3.
- Cognitive load: đếm lại và báo cáo, không cam kết ≤1 fail.
- Route `/` First Load ≤235 kB (214 + 10%).

## Architecture

**Menu keyboard: một lần cho tất cả.** Critique (persona Sam) ghi: "Custom menu
thiếu arrow-key semantics hoàn chỉnh". Sau các phase trước, repo có nhiều menu:
thread menu (sidebar + TopBar), tier selector (phase 09), dialog Share (phase 11).
Nếu mỗi phase tự cài thì có bốn cách xử lý bàn phím khác nhau.

Phase này rút thành một hook `use-menu-keyboard.ts`, và mọi menu dùng nó:

| Phím | Hành vi |
|---|---|
| ↓ / ↑ | item kế / trước, vòng ở hai đầu |
| Home / End | item đầu / cuối |
| Escape | đóng, focus về trigger |
| Enter / Space | kích hoạt item |
| Tab | đóng menu, focus đi tiếp (không bẫy trong menu) |

Roving `tabIndex` — đúng một item có `tabIndex = 0`, còn lại `-1`. Cộng
`role="menu"` / `role="menuitem"` và `aria-activedescendant` nếu focus giữ ở
container.

Tab **không** bị bẫy trong menu (khác drawer của phase 07, nơi bẫy là đúng) —
menu là popup nhỏ, drawer là vùng điều hướng. Hai mô hình khác nhau, và lẫn chúng
là lỗi phổ biến.

**Contrast: đo, không nhìn.** Palette là CSS var HSL tự định (scout web §11):
surface 6 bậc `#101112`→`#26282a`, ink 7 bậc `#fdfdfd`→`#8c8f93`, amber
`--primary` `#f59331`, market `#3fbf6a`/`#e2574f`, board VN ceiling/reference/
floor. `.light` ghi lại toàn bộ (`globals.css:135-181`).

Nghi vấn cụ thể: ink bậc thấp nhất `#8c8f93` trên surface bậc cao `#26282a` cho
tỷ lệ khoảng 3,4:1 — **đạt** AA cho text lớn (≥18,66px bold hoặc ≥24px) nhưng
**không đạt** 4,5:1 cho body. Nhiều nhãn `meta`/`micro` của plan này dùng đúng cặp
đó (trust line, keyboard hint, evidence line, timestamp).

Viết một test tính tỷ lệ contrast từ token, không kiểm bằng mắt: parse cặp
(foreground, background) đang dùng thật, tính WCAG ratio, khẳng định ≥4,5:1 cho
body và ≥3:1 cho text lớn + UI component. Test chạy cho **cả hai** theme.

Nếu cặp nào không đạt: **nâng ink một bậc** cho cặp đó. Không đổi palette — palette
là điểm mạnh critique khen, và đổi nó là scope khác.

**e2e: bốn luồng, ba viewport.** Playwright dựng FastAPI thật
(`apps/api/tests/e2e/server.py`) + production build của Next. Phải tắt `pnpm dev`
trước (memory: production build phá `.next` của dev).

| Luồng | Kiểm gì |
|---|---|
| Empty state → starter → answer | starter gửi thật, không refusal; trust line hiện; chip context |
| History: tạo 3 thread → nhóm → xoá → hoàn tác | nhóm recency đúng; undo trả thread về |
| Mobile drawer ở 390 · 430 | `main` giữ width; Escape đóng; focus về trigger |
| Export: thread có canvas → sao chép | file có trust line, không có `frames` |

Viewport thứ ba (tablet ~834px) chỉ cần một luồng — nó kiểm rằng hành vi inline
không bị phase 07 phá.

**Nợ e2e phải dọn** (ghi trong plan Study §Nợ để lại, đã đo):

- `e2e/market-monitor.spec.ts` — 2 case **đỏ từ trước**, kiểm surface đã bị rip
  2026-08-25. **Xoá file.** Nó không thuộc plan này về nội dung nhưng nó làm cổng
  của plan này đỏ, và nó không có chủ nào khác.
- `e2e/desk.ts::CANONICAL_MARK` — plan Study ghi đã sửa; **xác minh lại** còn đúng
  sau các đổi nhãn của phase 02 và 04 (nút gửi đổi icon, greeting đổi chuỗi).

**Re-score.** Chạy lại đúng critique đã sinh 22/40, cùng target slug
`apps-web-src-components-shell-view-chat-tsx`. Snapshot mới vào
`.impeccable/critique/`. So từng heuristic, không chỉ so tổng.

Baseline theo heuristic (từ `docs/text.md`) và phase nào chịu trách nhiệm:

| # | Heuristic | Baseline | Phase | Kỳ vọng |
|---|---|---|---|---|
| 1 | Visibility of System Status | 3 | 03, 04, 06 | 4 |
| 2 | Match System / Real World | 2 | 02, 04 | 4 |
| 3 | User Control and Freedom | 3 | 08 | 4 |
| 4 | Consistency and Standards | 2 | 02, 12 | 4 |
| 5 | Error Prevention | 2 | 02, 11 | 3 |
| 6 | Recognition Rather Than Recall | 2 | 04, 05 | 4 |
| 7 | Flexibility and Efficiency | 2 | 05, 06, 09 | 3 |
| 8 | Aesthetic and Minimalist | 2 | 02, 04 | 3 |
| 9 | Error Recovery | 3 | 06, 08 | 4 |
| 10 | Help and Documentation | **1** | 04 | 3 |
| | **Tổng** | **22** | | **≥32** |

Heuristic 10 (1/10) là chỗ tăng nhiều nhất và nó phụ thuộc **một** phase (04) —
nếu 04 làm nửa vời thì tổng không đạt dù chín heuristic kia đều lên.

## Related Code Files

Create:

- `apps/web/src/components/shell/use-menu-keyboard.ts`
- `apps/web/src/components/shell/use-menu-keyboard.test.ts`
- `apps/web/src/app/contrast.test.ts`
- `apps/web/e2e/launchpad.spec.ts`
- `apps/web/e2e/history-lifecycle.spec.ts`
- `apps/web/e2e/export.spec.ts`

Modify:

- mọi menu: thread menu (`sidebar.tsx`, `top-bar.tsx`), `tier-selector.tsx`,
  dialog Share (`overlays.tsx`) — dùng hook chung
- `apps/web/src/app/globals.css` — nâng ink bậc cho cặp không đạt contrast
- `apps/web/e2e/desk.ts` — xác minh `CANONICAL_MARK`

Delete:

- `apps/web/e2e/market-monitor.spec.ts` — 2 case đỏ từ trước, kiểm surface đã rip

## Implementation Steps

1. `use-menu-keyboard.ts` + test bảng cho 6 nhóm phím. Lan ra **mọi** menu; grep
   khẳng định không menu nào tự xử lý `keydown` riêng.
2. `contrast.test.ts`: parse token từ `globals.css`, tính WCAG ratio cho các cặp
   đang dùng thật, ở **cả hai** theme. Test đỏ trước là bình thường.
3. Nâng ink bậc cho cặp không đạt. **Không** đổi palette.
4. Xoá `market-monitor.spec.ts`; xác minh `desk.ts::CANONICAL_MARK`.
5. Ba spec e2e mới. Tắt `pnpm dev` trước khi chạy.
6. Đo bundle route `/`.
7. Chạy toàn bộ cổng: `make test` (apps/api, host) + `pnpm type-check && pnpm lint
   && pnpm test && pnpm build && pnpm test:e2e` (apps/web).
8. Re-score critique cùng target slug. So từng heuristic theo bảng trên.
9. Cập nhật CLAUDE.md nếu hành vi user-facing đổi (danh sách endpoint, biến
   `NEXT_PUBLIC_DEV_TOOLS`, tier). Chỉ những gì thật đổi.

## Success Criteria

- [ ] `use-menu-keyboard` test bảng xanh; grep: zero menu tự xử lý `keydown`
- [ ] Tab **không** bị bẫy trong menu; Tab **có** bị bẫy trong drawer (hai test
      riêng, khẳng định hai mô hình khác nhau)
- [ ] `contrast.test.ts` xanh cho cả dark và `.light`; body ≥4,5:1, UI ≥3:1
- [ ] Palette không đổi — chỉ cặp gán đổi (`git diff` khẳng định zero hex mới)
- [ ] `market-monitor.spec.ts` đã xoá; `pnpm test:e2e` **toàn bộ** xanh
- [ ] Bốn luồng e2e xanh ở 390 · 430; một luồng xanh ở 834
- [ ] `make test` (apps/api) pass — không giảm so với 1060
- [ ] `pnpm type-check`, `lint`, `test`, `build` xanh
- [ ] Route `/` First Load ≤235 kB
- [ ] **e2e đo pixel thật**: hit area mọi control tương tác ≥44×44px; cụm mở đầu
      `rect.top < viewportHeight/2` ở 1440×768. Hai phép đo này chuyển từ phase 01
      và 04 vì vitest không đo được
- [ ] Test đối chiếu trust line với `prompt/sections.py` — trust line không hứa
      điều prompt cấm (`:239`, `:363`)
- [ ] Re-score: tổng **≥32/40** và **mọi** heuristic ≥3
- [ ] Cognitive load: đếm lại theo định nghĩa của critique (toàn sidebar) và **báo
      cáo** số thật + tiêu chí nào không đạt kèm lý do. Không cam kết ≤1 fail
- [ ] CLAUDE.md khớp hành vi sau plan

## Risk Assessment

**Re-score không đạt dù mọi test xanh.** Critique là judgment của LLM, không phải
metric (R5 cấp plan). Tín hiệu: điểm thấp mà không chỉ ra được vấn đề nào chưa
sửa. Phản ứng đã định: đọc **lý do** từng heuristic thấp. Nếu lý do trỏ một thiếu
sót thật → mở phase vá. Nếu lý do là ý kiến về thứ plan đã cố ý quyết (ví dụ:
"nên có model selector đầy đủ") → ghi phản biện kèm nguồn SOT, **không** đảo quyết
định đã chốt. Đây là đúng luật `review-audit-self-decision.md`: audit không có
evidence mới không đảo được quyết định đã xác minh.

**Nâng ink phá cảm giác "calm".** Ink sáng hơn làm UI ồn hơn — đúng cái critique
khen là "dark tonal ladder" có kỷ luật. Tín hiệu: heuristic 8 (Aesthetic) **giảm**
sau khi sửa contrast. Phản ứng: chỉ nâng cặp **không đạt**, và ưu tiên nâng
`font-size`/`font-weight` lên ngưỡng "text lớn" (≥18,66px bold) thay vì nâng màu ở
những chỗ chữ vốn đã nhỏ và phụ. Hai đường đều đạt AA; đường thứ hai giữ palette.

**e2e ba viewport chạy chậm và giòn.** Tín hiệu: CI đỏ ngẫu nhiên. Phản ứng: bốn
luồng × ba viewport = 12 tổ hợp là quá nhiều; bảng ở §Architecture đã cắt xuống
4 + 4 + 1 = 9. Không mở rộng thêm. Nếu giòn thì siết selector, không bỏ luồng.

**Nợ e2e không phải của plan này.** Xoá `market-monitor.spec.ts` là dọn thứ người
khác để lại. Chấp nhận: nó chặn cổng của plan này và không ai khác nhận. Ghi vào
commit message lý do xoá (kiểm surface đã rip 2026-08-25), không ghi số phase hay
mã plan (luật `review-audit-self-decision.md` §Stable Code Artifacts).

Rollback: phase này gần như thuần test + a11y. Phần duy nhất đổi hành vi thấy được
là contrast; revert được độc lập.
