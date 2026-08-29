---
phase: 2
title: "Distill affordance ngõ cụt"
status: todo
priority: P1
effort: ""
dependencies: [1]
---

# Phase 02: Distill affordance ngõ cụt

## Overview

Giải P1 #2 của critique: "Affordance trông dùng được nhưng dẫn tới ngõ cụt".
Đây là phase **xoá và nối**, không phải phase thêm. Nó mua lại niềm tin bằng
diff âm, và nó phải đi trước mọi phase thêm UI — nếu không, phase sau sẽ thêm
control vào một surface mà user đã học là không đáng bấm.

Kiểm kê thực tế (scout web §4, §5, §6, §14): 6 row Attach disabled, 4 item
TopBar menu disabled, 3 item sidebar disabled, 1 chevron giả, 1 dialog Share
không gọi endpoint nào, 1 nút gửi mang icon voice.

## Requirements

Functional:

- Không control nào render ra mà không có handler thật.
- Menu không mở khi không có item khả dụng.
- Nút gửi mang biểu tượng gửi, không phải biểu tượng ghi âm.
- Nhãn tĩnh không mang chevron.
- Dev tooling không xuất hiện trong ảnh chụp cho stakeholder, kể cả ở dev.

Non-functional:

- **Không mất chức năng nào user đang dùng được.** Cái gì có handler ở nơi khác
  thì nối vào, không xoá.
- Bundle route `/` không tăng (phase này chủ yếu xoá code).

## Architecture

**Bốn quyết định xoá/nối, mỗi cái có lý do riêng — đừng xử lý đồng loạt.**

| Chỗ | Hiện tại | Làm gì | Vì sao |
|---|---|---|---|
| `composer.tsx:382-425` AttachMenu | 6 row, **cả 6** disabled | **Xoá các row không có handler; giữ menu và nút** | Sáu lựa chọn không dùng được là ba lỗi cognitive load cùng lúc (minimal choices, progressive disclosure, error prevention). Nhưng hai trong sáu row **có** handler đang được làm — xem khối đảo tiền đề dưới bảng. |
| `top-bar.tsx:73,76,79,83` menu thread | 4 item disabled: Ghim · Đổi tên · **Xuất PDF** · Xoá | **Nối 3, xoá 1** | Sidebar `ThreadMenu` (`sidebar.tsx:382-394`) làm thật đúng **ba** việc — Ghim, Đổi tên, Xoá. **Export không tồn tại ở đâu cả**, và phase 11 làm **Markdown** chứ không PDF. Nên nối ba, xoá item export; phase 11 mang nó về với nhãn "Xuất Markdown". |
| `sidebar.tsx:191,199` | "Bộ lọc cổ phiếu", "Báo cáo đã lưu", "Danh mục theo dõi" disabled | **Xoá** | Roadmap preview trong daily workspace. `plan.md` §Nguyên tắc: đưa ra khỏi workspace. |
| `overlays.tsx:203-268` Share | Dialog mở rồi báo "API chưa có endpoint" (`:250-252`) | **Ẩn nút, giữ code dialog** | Phase 11 làm export thật và dùng lại vỏ dialog này. Xoá rồi viết lại là công thừa. Ẩn = honest ngay, và không mất việc đã làm. |

> **Đảo tiền đề 2026-08-29.** Lý lẽ *"cả 7 disabled, không item nào có handler"*
> đúng khi viết. `plans/260829-0010-composer-attachments/` cho hai row handler
> thật — *Thêm tệp hoặc ảnh* (phase 08) và *Chụp màn hình* (phase 09) — và đặt
> bốn row còn lại là badge có chủ ý, sau khi gỡ hẳn row *Tra tin tức thị trường*
> (năng lực đó đã chạy trong bundle `web` mọi lượt, badge trên nó là một câu sai).
> Menu không còn là ngõ cụt toàn phần, nên phép xoá toàn phần hết cơ sở, và
> contract *"không có control disabled"* đổi thành *"control disabled phải được
> mô tả"*. Phần code cho contract mới nằm ở phase 10 của plan đó
> (`primitives.tsx` cho badge một `id`, button một `aria-describedby`).
>
> Citation của chính bảng trên cũng đã cũ: `composer.tsx:236-276` và *"7 item"*
> — thật là `:382-425` với **sáu** row. Đã sửa tại chỗ.

**"Đã ghim" và cấu trúc nhóm.** `sidebar.tsx:189` nhóm "Đã ghim" hiện chứa
"Danh mục theo dõi" disabled. Phase này: ẩn nhóm khi rỗng, gỡ "Danh mục theo dõi"
khỏi nó.

**Sửa sau red-team:** pin/unpin **đã hoạt động** (`sidebar.tsx:340-343,382-393`).
Bản đầu nói sai là chưa. Contract là `pinned: bool` (`schemas.py:57`), server tự
`coalesce(pinned_at, now())`. Nên phase này chỉ sửa **nhóm**, và phase 05 không
phải làm pin — nó chỉ sắp xếp nhóm ghim theo `pinned_at`.

**Nút gửi.** `composer.tsx:35-54` là `WaveformIcon` — 5 vạch SVG tự vẽ. Waveform
nghĩa là voice input; không có voice input. Thay bằng arrow/paper-plane. Giữ
đúng khuôn SVG hiện tại (`viewBox`, `strokeWidth`) để không đổi nhịp thị giác.

**Nhãn tier tạm thời.** `composer.tsx:182-185` là `<span>` tĩnh mang chevron.
Phase này **chỉ bỏ chevron** — nhãn thành honest ngay. Phase 09 biến nó thành
control thật có chevron thật.

**Luật menu rỗng thành cơ chế, không phải thói quen.** Đặt ở `primitives.tsx`:
component menu nhận danh sách item và **không render trigger** nếu zero item
khả dụng. Sau phase này không còn menu rỗng nào, nhưng luật là cái giữ cho phase
sau không tạo ra menu rỗng mới.

**Dev tooling.** `dev/agentation-toolbar.tsx` và `dev/canvas-fixture.tsx` gate
bằng `process.env.NODE_ENV === "production"` (scout web §14), nên chúng **hiện ở
dev** và đã lọt vào ảnh chụp của critique (góc dưới-trái). Đổi sang opt-in tường
minh `NEXT_PUBLIC_DEV_TOOLS === "1"`: mặc định tắt ở mọi môi trường, ai cần thì
bật. Vẫn giữ `dynamic(ssr:false)` để dead-code-eliminate ở production build.

## Related Code Files

Modify:

- `apps/web/src/components/shell/composer.tsx` — trong AttachMenu (`:382-425`)
  xoá các row không có handler, **giữ menu và nút Attach**; `WaveformIcon`
  (`:35-54`) → `SendIcon`; bỏ chevron (`:182-185`)
- `apps/web/src/components/shell/top-bar.tsx:73-85` — nối 4 item vào handler thật
- `apps/web/src/components/shell/sidebar.tsx:189-199` — xoá 3 item disabled, ẩn
  nhóm "Đã ghim" khi rỗng, gỡ "Danh mục theo dõi" khỏi nhóm ghim
- `apps/web/src/components/shell/overlays.tsx:203-268` — ẩn lối vào Share
- `apps/web/src/components/shell/primitives.tsx` — luật menu rỗng;
  `UnavailableNote` (`:301`) còn caller nào không, nếu zero thì xoá
- `apps/web/src/app/layout.tsx:105-109` — gate dev tooling
- `apps/web/.env.example` (nếu có) — khai `NEXT_PUBLIC_DEV_TOOLS`

Create:

- `apps/web/src/components/shell/affordance.test.tsx` — contract test

## Implementation Steps

1. Viết `affordance.test.tsx` **trước**: render shell ở 3 trạng thái (empty
   state · thread đang chạy · thread đã xong), khẳng định **mọi control
   `disabled` hoặc `aria-disabled` đều được mô tả bằng chương trình** (một
   `aria-describedby` trỏ tới phần tử giải thích vì sao nó không bấm được), và
   zero menu trigger có 0 item khả dụng. Test này đỏ ngay — đó là mục đích.
2. Xoá các row AttachMenu không có handler; **giữ menu và nút Attach**. Kiểm
   `UnavailableNote` còn caller.
3. Nối TopBar menu: rút 4 handler của sidebar lên `DeskProvider`/`ShellProvider`
   (nơi đã giữ thread state) để cả hai surface gọi cùng một hàm — **không**
   nhân bản handler.
4. Xoá 3 item sidebar disabled; ẩn nhóm ghim khi rỗng.
5. Ẩn lối vào Share (giữ file dialog, thêm ghi chú một dòng trỏ phase 11).
6. `WaveformIcon` → `SendIcon`; bỏ chevron khỏi nhãn tĩnh.
7. Luật menu rỗng vào `primitives.tsx`.
8. Đổi gate dev tooling sang `NEXT_PUBLIC_DEV_TOOLS`.
9. `affordance.test.tsx` phải xanh. Cổng đầy đủ: `pnpm type-check && pnpm lint
   && pnpm test && pnpm build`.
10. Đo lại bundle route `/` — kỳ vọng **giảm**, không tăng.

## Success Criteria

- [ ] `affordance.test.tsx` xanh ở cả 3 trạng thái shell
- [ ] Grep `disabled` trong `components/shell/` chỉ còn ở control có lý do
      runtime thật (nút gửi khi draft rỗng) hoặc ở row `AttachMenu` mang badge
      *Sắp ra mắt* **có `aria-describedby`**
- [ ] **3** hành động thread ở TopBar (Ghim · Đổi tên · Xoá) hoạt động thật và gọi
      cùng handler với sidebar (test: click TopBar → cùng mutation)
- [ ] Item "Xuất PDF" **đã xoá** khỏi TopBar — nó không có handler ở đâu cả
- [ ] Nút gửi có `aria-label` nói "gửi", icon không phải waveform
- [ ] Nhãn tier không có chevron, không có `role="button"`
- [ ] Ảnh chụp mặc định ở dev **không** có toolbar góc dưới-trái
- [ ] Bundle route `/` ≤82,2 kB
- [ ] `pnpm test` xanh; `make test` vẫn 1060 (không đụng API)

## Risk Assessment

**Xoá Attach xoá luôn đường nạp file mà phase sau cần.** Attach là cửa cho một
capability chưa tồn tại — không có tool nào trong 12 tool nhận file (scout api
§10). Nếu sau này có, nó sẽ cần cửa mới thiết kế theo capability thật, không
phải cái menu 7 item này. Chấp nhận xoá.

**Nối TopBar menu làm rò state.** Nếu handler nằm ở hai chỗ, hai surface có thể
lệch nhau (ví dụ TopBar rename xong sidebar không cập nhật). Tín hiệu: test
"click TopBar → sidebar phản ánh" đỏ. Phản ứng: đẩy handler lên provider
**trước** khi nối, không nối rồi mới rút lên.

**Ẩn Share làm user tưởng mất chức năng.** Thực tế Share hiện **không** là chức
năng — nó là dialog báo lỗi. Ẩn một thứ chưa từng hoạt động không mất gì. Phase
11 mang lại lối chia sẻ thật trong cùng plan.

**`NEXT_PUBLIC_DEV_TOOLS` mặc định tắt làm dev mất công cụ đang dùng.** Tín
hiệu: có người phàn nàn. Phản ứng: ghi biến vào `.env.example` + một dòng trong
CLAUDE.md §Commands. Không đảo về gate cũ — gate cũ là nguyên nhân dev tooling
lọt vào critique.

Rollback: thuần xoá + rename, `git revert` một commit. Không migration, không
contract API đổi.
