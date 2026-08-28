---
phase: 6
title: "Long conversation ergonomics"
status: todo
priority: P2
effort: ""
dependencies: [2]
---

# Phase 06: Long conversation ergonomics

## Overview

Ba gap trong bảng "Những phần còn thiếu" của critique: **Long conversation**
(new-content / scroll-to-latest), **Recovery** (copy failure feedback), và
**Composer** (keyboard hint). Cộng một bug thật mà scout tìm được: nhãn copy đổi
sang "đã sao chép" **kể cả khi clipboard fail**.

Scroll của repo mạnh hơn critique tưởng: có auto-follow ngưỡng 120px, có pin câu
hỏi mới lên đỉnh viewport bằng spacer, có reduced-motion (`view-chat.tsx:50`,
`:189-250`). Cái thiếu là đúng một thứ: khi user cuộn lên, **không có gì** nói
answer đang tiếp tục và không có đường về cuối.

## Requirements

Functional:

- Khi cuộn ra khỏi vùng auto-follow: hiện nút về cuối.
- Khi có nội dung mới trong lúc đang cuộn lên: nút mang tín hiệu "có nội dung
  mới", phân biệt được với trạng thái tĩnh.
- Copy thất bại → user thấy; nhãn **không** báo thành công.
- Keyboard hint "Enter gửi · Shift+Enter xuống dòng" hiện ở composer.

Non-functional:

- Không phá auto-follow, pin-to-top, hay reduced-motion đang hoạt động.
- Nút về cuối không che nội dung câu trả lời cuối và không va composer.

## Architecture

**Ba trạng thái, không phải hai.** Nút về cuối thường bị làm thành boolean
(hiện/ẩn). Ở lane này có ba trạng thái thật và chúng nói ba điều khác nhau:

| Trạng thái | Điều kiện | Hiển thị |
|---|---|---|
| `following` | trong ngưỡng 120px | không render |
| `detached` | ngoài ngưỡng, không có nội dung mới kể từ lúc rời | mũi tên xuống, im |
| `detached_new` | ngoài ngưỡng, đã có `content.delta` kể từ lúc rời | mũi tên + dấu hiệu nội dung mới |

`detached_new` là cái critique thật sự đòi ("user cuộn lên vẫn biết answer đang
tiếp tục"). Nó cần một cờ đặt khi delta đến **và** `following == false`, reset
khi về cuối. Cờ này thuộc component scroll, không thuộc reducer shell — nó là
state của viewport, không phải của phiên làm việc.

**Không dùng số lượng.** "3 tin mới" là sai vốn từ cho streaming: một answer đang
chảy không phải 3 tin. Dấu hiệu là định tính (một dot), không định lượng.

**Reduced-motion.** Nút xuất hiện bằng opacity, không bằng translate, khi
`prefers-reduced-motion`. Cơ chế đã có ở `view-chat.tsx` — dùng lại, không thêm.

**Copy: sửa bug trước, thêm feedback sau.** **Bốn** chỗ copy — bản đầu nói ba,
red-team tìm được cái thứ tư — cả bốn swallow lỗi:

- `view-chat.tsx:28-30` — assistant. **Nhãn optimistic đổi kể cả khi fail.** Đây
  là bug: nó nói dối user. Sửa: `await` clipboard, chỉ đổi nhãn ở nhánh thành
  công.
- `view-chat.tsx:506-515` — user bubble. Đúng hơn nhưng vẫn im khi lỗi.
- `apps/web/src/components/alpha/message/message-actions.tsx:64-67` — cùng vấn đề.
  (Ở `components/alpha/message/`, **không** `components/shell/` — bản đầu ghi sai.)
- `apps/web/src/components/settings/account-section.tsx:28` — caller thứ tư, ngoài
  shell. Nếu bỏ nó thì criteria grep của phase này đỏ.

Rút thành **một** helper `copy-to-clipboard.ts` trả `Promise<boolean>`, ba caller
dùng chung (DRY, và chỉ một chỗ cần test). Thất bại → nhãn đổi sang trạng thái
lỗi ngắn ("không sao chép được") trong ~2s, cùng khuôn thời gian với trạng thái
thành công. Không toast — copy là hành động cục bộ, feedback nên ở chính nút.

Clipboard fail thật khi: không có `navigator.clipboard` (http không phải
localhost), permission bị chặn, hoặc document không focus. Cả ba đều có thể xảy
ra ở production.

**Keyboard hint.** Composer đã xử lý Enter/Shift+Enter (`composer.tsx:113-118`)
nhưng không nói ra. Đặt hint ở footer composer, cỡ `micro`, ink bậc thấp. Ẩn trên
touch (không có Enter cứng) — kiểm bằng media query `(hover: hover) and
(pointer: fine)`, không bằng user-agent.

⌘K đã có ở listener toàn cục (`shell-state.tsx:351`) nhưng cũng không được nói ra
ở đâu. Thêm nó vào cùng hint — đây là mục "Flexibility and Efficiency" 2/10 của
critique, và nói ra một shortcut đã tồn tại là cách rẻ nhất để nâng nó.

## Related Code Files

Modify:

- `apps/web/src/components/shell/view-chat.tsx` — trạng thái scroll ba nhánh,
  nút về cuối; sửa bug copy `:28-30`; dùng helper mới ở `:506-515`
- `apps/web/src/components/alpha/message/message-actions.tsx:64-67` — dùng helper mới
- `apps/web/src/components/settings/account-section.tsx:28` — caller thứ tư
- `apps/web/src/components/shell/composer.tsx` — keyboard hint ở footer

Create:

- `apps/web/src/lib/copy-to-clipboard.ts`
- `apps/web/src/components/shell/scroll-to-latest.tsx`
- `apps/web/src/lib/copy-to-clipboard.test.ts`
- `apps/web/src/components/shell/scroll-to-latest.test.tsx`

## Implementation Steps

1. `copy-to-clipboard.ts`: một hàm, trả boolean, không throw. Test ba nhánh lỗi
   (thiếu API · reject permission · document không focus).
2. Sửa `view-chat.tsx:28-30` dùng helper và **chỉ** đổi nhãn khi `true`. Test
   khẳng định: mock clipboard reject → nhãn **không** thành "đã sao chép".
3. Lan helper ra hai caller còn lại. Xoá ba khối try/catch cũ.
4. `scroll-to-latest.tsx` với ba trạng thái. Cờ `hasNewSinceDetach` đặt ở delta,
   reset khi về cuối.
5. Ghép vào `view-chat.tsx` **không** đụng auto-follow/pin logic hiện có. Test
   hồi quy: 3 case pin hiện tại (`view-chat-pin`) phải còn xanh.
6. Keyboard hint ở composer, ẩn trên touch, gồm cả ⌘K.
7. Cổng đầy đủ web.

## Success Criteria

- [ ] Mock clipboard reject → nhãn báo lỗi, **không** báo thành công (test cho cả
      **bốn** caller, gồm `components/settings/account-section.tsx:28`)
- [ ] Một helper duy nhất; grep `navigator.clipboard` trong `apps/web/src/` chỉ
      còn trong helper — phạm vi grep là `src/`, không chỉ `components/`, vì caller
      thứ tư nằm ngoài shell
- [ ] Cuộn lên trong lúc stream → nút hiện ở trạng thái `detached_new`
- [ ] Cuộn lên khi không stream → nút hiện ở trạng thái `detached`, không có dot
- [ ] Bấm nút → về cuối, cờ reset, nút biến mất
- [ ] `prefers-reduced-motion` → nút xuất hiện không có translate
- [ ] 3 case `view-chat-pin` hiện có vẫn xanh (test hồi quy)
- [ ] Keyboard hint hiện trên desktop, ẩn khi `(pointer: coarse)`
- [ ] Nút không che message cuối và không va composer ở 768px cao
- [ ] `pnpm test` xanh

## Risk Assessment

**Ghép nút vào scroll làm hỏng pin-to-top.** Logic pin dùng spacer và đo vị trí
(`:189-250`); thêm một element `position: sticky`/`absolute` vào cùng container
có thể đổi phép đo. Tín hiệu: 3 case `view-chat-pin` đỏ. Phản ứng: nút render
**ngoài** container scroll (overlay tuyệt đối theo viewport của cột chat), không
nằm trong luồng đo. Nếu vẫn đỏ thì dừng và đọc lại `:189-250` trước khi sửa test
— test pin là cái giữ hành vi user thấy được.

**`document.hasFocus()` false trong test env.** Nhánh lỗi thứ ba khó mock. Phản
ứng: helper nhận một cửa (dependency injection cho `navigator`/`document`) để test
được, thay vì đọc global trực tiếp.

**Hint chiếm chỗ composer.** Footer composer sau phase 02 đã có nhãn tier; thêm
hint có thể làm hai dòng ở màn hẹp. Phản ứng: hint là thứ **rơi trước** — ẩn ở
breakpoint hẹp, giữ nhãn tier.

Rollback: additive + một bug fix. Revert được từng commit; bug fix nên giữ lại
kể cả khi revert phần scroll.
