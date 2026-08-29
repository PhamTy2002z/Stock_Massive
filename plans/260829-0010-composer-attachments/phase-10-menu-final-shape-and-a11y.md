---
phase: 10
title: "Hình dạng cuối của menu và a11y"
status: done
priority: P2
effort: "3h"
dependencies: [9]
---

# Phase 10: Hình dạng cuối của menu và a11y

## Overview

Đóng menu về hình dạng đã chốt, viết **test đầu tiên** cho `AttachMenu` (nó chưa có
cái nào), và làm phần code để contract a11y đã hẹp ở phase 01 thật sự thoả được.

## Requirements

- Functional: menu có sáu row đúng bảng dưới; mọi row `disabled` có
  `aria-describedby` trỏ tới badge của nó; copy phân biệt được "nghiên cứu sâu" với
  control độ sâu của `260827-2325/phase-09`.
- Non-functional: không row nào mang badge cho một năng lực đã bật.

## Architecture

### Hình dạng cuối

| # | Row | Trạng thái |
|---|---|---|
| 1 | Thêm tệp hoặc ảnh | chạy thật (phase 08) |
| 2 | Chụp màn hình | chạy thật (phase 09) |
| 3 | Nghiên cứu sâu | `disabled` → badge |
| 4 | Thêm vào danh mục | `disabled` → badge |
| 5 | Mẫu phân tích | `disabled` → badge |
| 6 | Nguồn dữ liệu kết nối | `disabled` → badge |
| — | ~~Tra tin tức thị trường~~ | **gỡ** — user chốt 2026-08-29 |

### Vì sao gỡ row tin tức

`web_search` và `fetch_url` **đã luôn** trong tay model mọi lượt chat: bundle `web`
trong `CHAT_TOOLSETS` (`toolsets.py:98`), `check_fn` đọc
`web_tools_enabled and tavily_api_key` (`tools/web.py:346-347`), cả hai đã set trong
`.env`. Badge *Sắp ra mắt* trên một năng lực đang chạy là một câu sai nói với người
đọc.

Red-team nêu đúng rằng đây là quyết định chưa hỏi và câu trả lời #4 của user nói
*"mấy cái còn lại vẫn giữ Sắp ra mắt"*. Đã hỏi lại 2026-08-29; user chốt **gỡ hẳn**.

### `aria-describedby`: chỗ hai plan gặp nhau

`MenuItem` vẽ badge là một `<span>` trần (`primitives.tsx:184-189`) — không `id`,
không liên kết. `260827-2325/phase-02` mandate một test khẳng định mọi control
`disabled` phải được mô tả; phase 01 đã hẹp assertion đó từ *"không có control
disabled"* thành *"control disabled phải được mô tả"*. Phase này làm phần code:
badge nhận một `id` sinh theo item, và button nhận `aria-describedby` trỏ tới nó.

Đây không phải việc thêm — nó là điều đúng dù có plan kia hay không: một badge chỉ
nhìn thấy được bằng mắt không nói gì với screen reader về việc row này vì sao không
bấm được.

### Nghiên cứu sâu ≠ độ sâu

`260827-2325/phase-09` biến cụm "Visgnite Pro" thành control chọn **độ sâu của một
câu trả lời** — đổi chi phí và thời gian của một lượt. Row 3 ở đây là **một chế độ
nhiều bước**: nhiều Study, nhiều vòng, một báo cáo. Copy phải không thể lẫn. Nếu lúc
làm thấy vẫn lẫn, đó là dấu một trong hai tên sai — nêu ra, đừng chọn tên mờ hơn cho
cả hai.

## Related Code Files

- Modify: `apps/web/src/components/shell/composer.tsx` — `AttachMenu`
- Modify: `apps/web/src/components/shell/primitives.tsx` — `id` cho badge + `aria-describedby`
- Create: `apps/web/src/components/shell/attach-menu.test.tsx` — **test đầu tiên của menu này**
- Modify: `apps/web/src/lib/alpha-desk/copy.ts`
- Modify: `docs/roadmap.md` — kiểm ghi chú phase 01 còn đúng sau khi copy chốt

## Implementation Steps

1. Gỡ row "Tra tin tức thị trường" + icon `Globe` nếu không còn chỗ dùng. Thay bình
   luận cũ bằng một bình luận nói vì sao **không** có row cho web search: năng lực
   đã bật, và một công tắc cho thứ đã bật là một công tắc gây hiểu sai.
2. Thêm row "Nghiên cứu sâu" ở đầu nhóm thứ hai, `disabled`, `ChevronRight` như các
   row có nhánh con.
3. `MenuItem`: badge nhận `id`, button nhận `aria-describedby` khi `disabled`. `id`
   sinh bằng `useId` để hai menu trên cùng trang không đụng.
4. **`attach-menu.test.tsx` — test đầu tiên.** Grep xác nhận trước:
   `AttachMenu|Thêm tệp|attachOpen` toàn `src` + `e2e` trừ `composer.tsx` = **0 kết
   quả**, nên không có gì để hồi quy và mọi thứ dưới đây là net mới:
   - mở menu cho đúng sáu row;
   - đúng **bốn** row mang badge, **hai** row không (một `getByText` không bắt được
     việc badge lan sang row đã chạy);
   - không row nào có chữ về web search;
   - mọi button `disabled` có `aria-describedby` trỏ tới một element tồn tại;
   - hai row sống bấm được và gọi đúng handler.
5. Nghiệm thu bằng mắt: mở menu, đọc sáu dòng, kiểm không dòng nào hứa sai.

## Success Criteria

- [x] Menu có sáu row đúng bảng trên
- [x] Không còn row nào cho web search
- [x] `attach-menu.test.tsx` tồn tại và phủ năm khẳng định ở bước 4
- [x] Mọi row `disabled` có `aria-describedby` trỏ tới badge tồn tại
- [x] Copy row 3 không lẫn với control độ sâu của `260827-2325/phase-09`
- [x] `pnpm type-check` `lint` `test` `build` pass

## Risk Assessment

**Rủi ro: người dùng đọc việc gỡ row tin tức là mất năng lực.**
*Tín hiệu:* câu hỏi "sao không tra tin được nữa".
*Phản ứng đã định:* năng lực không đổi. Nếu câu hỏi này xuất hiện, cái thiếu không
phải row mà là **hiển thị việc model đã tra** — việc của panel Nguồn, không phải của
menu đính kèm. Đừng trả row về.

**Rủi ro: badge lan sang row đã chạy sau một refactor `MenuItem`.** Badge vẽ tự động
từ `disabled` (`primitives.tsx:184-189`).
*Tín hiệu:* test đếm badge ở bước 4 fail.
*Phản ứng:* đó chính là lý do test đó tồn tại — và lý do bản đầu không an toàn, vì
nó tưởng `shell.test.tsx:1041` là lưới trong khi test đó chỉ render `MenuItem` trần.

**Rủi ro: `aria-describedby` làm screen reader đọc "Sắp ra mắt" hai lần.** Badge vừa
là nội dung nhìn thấy vừa là mô tả.
*Tín hiệu:* nghe thử bằng VoiceOver.
*Phản ứng:* nếu đọc trùng, đặt `aria-hidden` trên badge nhìn thấy và để
`aria-describedby` trỏ tới một `<span class="sr-only">` nói đủ câu — mô tả cho tai
không nhất thiết là chuỗi cho mắt.

## Kết quả thi công — 2026-08-29

Cổng web: `type-check` · `lint` · `test` (**817 pass**, 63 file) · `build` — cả bốn
xanh. `attach-menu.test.tsx`: **11 test**, đúng như plan nói, đều là net mới —
grep xác nhận trước khi viết rằng `AttachMenu|Thêm tệp|attachOpen` không khớp gì
ngoài `composer.tsx`.

**Một xung đột thật, và nó không nằm ở chỗ plan dự đoán.** Plan lo copy row 3 lẫn
với control độ sâu của `260827-2325/phase-09`. Cái thực sự đỏ là khác:
`shell.test.tsx` đã có một test khẳng định **không** được có row *"Nghiên cứu sâu"*,
kèm lý do — nó từng là calque tên tính năng của đối thủ cho việc mà công tắc Signal
Desk đã làm, và một menu item nhân đôi một công tắc nhìn thấy được là hai control
cho một hành vi.

Giải: **đảo assertion, và viết ra vì sao đảo.** Lần gỡ trước đúng với nghĩa lúc đó.
Row quay lại mang một nghĩa công tắc **không** làm: một chế độ nhiều bước — nhiều
Study qua nhiều vòng, kết thành một báo cáo. Công tắc đổi thứ *một* Turn sản xuất;
cái này đổi *có bao nhiêu* Turn. Nên thứ được canh không còn là sự vắng mặt mà là
sự phân biệt: row inert, có badge, và không phải cái radio ở control row. Điều này
khớp với ghi chú phase 01 đã viết vào `docs/roadmap.md` §S2 — *"plan này dựng năm
row còn lại và để đúng row này chờ ở đây"*.

**Badge được đếm, không chỉ được tìm.** `MenuItem` vẽ badge tự động từ `disabled`,
nên một row ngừng chạy là một row bắt đầu hứa — và `getByText` sẽ vẫn xanh vì vẫn
tìm thấy *một* badge. Test đếm **đúng bốn**, và đếm **năm** khi trình duyệt không
chụp được màn hình. Đó là lý do test này tồn tại.

**`aria-describedby` sinh bằng `useId`, không bằng nhãn.** Hai menu trên cùng trang
và hai row cùng chữ đều có thật; test render hai `AttachMenu` cạnh nhau và khẳng
định **8 id, không trùng cái nào**.

**Chuỗi badge đặt tên một lần** (`primitives.ts::COMING_SOON`): giờ có hai thứ đọc
nó — badge cho mắt và mô tả cho tai — và hai bản sao là hai chỗ để một cái trôi
khỏi cái kia.

**Row tin tức gỡ, và chỗ nó ngồi giờ là một bình luận nói vì sao không có row nào
cho web search.** `web_search` và `fetch_url` nằm trong toolset của lane chat mọi
lượt, nên badge *Sắp ra mắt* trên chúng là một câu sai; một công tắc cho thứ đang
chạy là một công tắc gây hiểu sai. Test khẳng định không row nào nhắc *tin tức*,
*web*, *tìm kiếm*.

**Một separator, không hai.** Nó tách hai row chạy thật khỏi bốn row còn hứa —
đúng ranh giới người đọc cần thấy.

**`AttachMenu` được export** để có test đầu tiên. Nó nhận props thuần
(`onPickFile` · `onCapture` · `supported`) nên test render trần, không cần provider.

## Nghiệm thu bằng mắt — 2026-08-29, xong

Mở menu trên `localhost:3000`. Sáu dòng, đúng bảng:

| # | Row | Badge |
|---|---|---|
| 1 | Thêm tệp hoặc ảnh · `⌘U` | không |
| 2 | Chụp màn hình | không |
| — | *separator* | |
| 3 | Nghiên cứu sâu | SẮP RA MẮT |
| 4 | Thêm vào danh mục | SẮP RA MẮT |
| 5 | Mẫu phân tích | SẮP RA MẮT |
| 6 | Nguồn dữ liệu kết nối | SẮP RA MẮT |

Không dòng nào hứa sai: hai dòng không badge là hai dòng bấm được thật, bốn dòng
badge là bốn dòng chưa có gì phía sau. Không còn row tin tức.
