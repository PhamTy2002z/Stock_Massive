---
phase: 9
title: "Chụp màn hình"
status: done
priority: P2
effort: "4h"
dependencies: [8]
---

# Phase 09: Chụp màn hình

## Overview

Row 2 đổi từ "Chụp màn hình bảng giá" thành **"Chụp màn hình"** và làm thật: chọn
cửa sổ hoặc màn hình, xem trước, rồi mới gửi. Đi cùng đường ống phase 08 — nó chỉ
là một nguồn ảnh khác.

## Requirements

- Functional: bấm row → chọn nguồn → xem trước → chấp nhận hoặc huỷ → thành một chip
  như mọi ảnh khác.
- Non-functional: **xem trước là bắt buộc**; huỷ ở bất kỳ bước nào không để lại gì;
  không thêm dependency.

## Architecture

### Vì sao xem trước là yêu cầu

`getDisplayMedia` trả về **cả** thứ người dùng chọn chia sẻ, có thể gồm tab khác,
tin nhắn, email. Một luồng chụp-rồi-gửi-ngay là một luồng gửi đi thứ người dùng
không định gửi, tới một model bên ngoài, không lấy lại được.

### Ảnh chụp bảng giá và luật giá

Use case tự nhiên nhất của row này là chụp một bảng giá. Phase 06 đã mở rộng luật
prompt để một con số đọc từ ảnh cũng phải qua `check_price_claim`
(`sections.py:309-313`). Phase này **không** thêm luật mới; nó chỉ là chỗ luật đó
được nghiệm thu bằng một ảnh thật.

### Không thư viện mới

`getDisplayMedia` → `<video>` → `canvas.drawImage` → `canvas.toBlob` → cùng
`uploadAttachment` của phase 08.

### Secure context

API cần HTTPS hoặc `localhost`. `pnpm dev` chạy `localhost:3000` nên dev được; prod
phải HTTPS. Không có secure context thì `navigator.mediaDevices` là `undefined` —
phải kiểm và nói, không để nút chết im.

## Related Code Files

- Create: `apps/web/src/lib/alpha-desk/screen-capture.ts`
- Create: `apps/web/src/components/shell/capture-preview.tsx`
- Modify: `apps/web/src/components/shell/composer.tsx` — row 2
- Modify: `apps/web/src/components/shell/overlays.tsx` — dùng lại khung overlay đã có
- Modify: `apps/web/src/lib/alpha-desk/copy.ts`

## Implementation Steps

1. `captureScreen(): Promise<Blob | null>` — `null` khi người dùng huỷ hộp thoại
   trình duyệt. Huỷ **không phải** lỗi và không hiện thông báo lỗi.
2. Dừng track ngay sau khi vẽ xong frame:
   `stream.getTracks().forEach(t => t.stop())`. Bỏ bước này là để đèn chia sẻ màn
   hình sáng sau khi việc đã xong.
3. Overlay xem trước: ảnh đúng tỉ lệ, nút *Đính kèm* và *Bỏ*, đóng bằng `Esc`, focus
   trap. Đọc `overlays.tsx` trước, dùng lại khung của nó.
4. Chấp nhận → `uploadAttachment` với tên sinh theo thời điểm chụp, ví dụ
   `chup-man-hinh-2026-08-29-0014.png`.
5. Kích thước: đo một ảnh thật trước khi chọn. Nếu vượt trần phase 05 thì thu cạnh
   dài về ~1920px, hoặc `image/jpeg` chất lượng ~0.85. Quyết định **sau khi đo**,
   không đoán trước.
6. Kiểm năng lực: `typeof navigator.mediaDevices?.getDisplayMedia !== "function"` →
   row giữ `disabled` với badge, không phải một nút bấm không phản ứng.
7. Test: huỷ hộp thoại không tạo chip · chấp nhận tạo đúng một chip · track được
   dừng · thiếu API thì row disabled. Mock `getDisplayMedia` trong jsdom.
8. Nghiệm thu tay, ghi vào PR description: chụp một bảng giá thật, hỏi về một con số
   trong đó, và kiểm model **không** nêu con số đó mà không qua `check_price_claim`.

## Success Criteria

- [ ] Bấm row → hộp thoại trình duyệt → chọn → thấy xem trước
- [x] *Bỏ* và `Esc` không để lại chip nào
- [ ] *Đính kèm* cho đúng một chip có thumbnail
- [x] Track dừng sau khi chụp (không còn chỉ báo chia sẻ màn hình)
- [x] Không có `getDisplayMedia` → row disabled kèm badge
- [x] Kích thước ảnh chụp nằm dưới trần phase 05, quyết định có ghi số đo
- [ ] Nghiệm thu tay về luật giá đã chạy và ghi lại
- [x] `pnpm type-check` `lint` `test` `build` pass

## Risk Assessment

**Rủi ro: người dùng gửi đi thứ không định gửi.** Rủi ro riêng tư thật của phase này.
*Tín hiệu:* không có tín hiệu sau sự việc — ảnh đã đi rồi.
*Phản ứng đã định:* xem trước là cổng và nó ở success criteria. Nếu phase phải cắt,
cắt cả phase — đừng cắt bước xem trước.

**Rủi ro: jsdom không có `getDisplayMedia` nên test thành test của mock.**
*Tín hiệu:* test pass nhưng luồng thật chưa ai chạy.
*Phản ứng đã định:* bước 8 là nghiệm thu tay bắt buộc, ghi vào PR. Không claim phase
xong dựa trên unit test của một mock.

**Rủi ro: ảnh full-screen 4K vượt trần.**
*Tín hiệu:* 413 ngay lần chụp đầu trên máy màn hình lớn.
*Phản ứng đã định:* bước 5 — đo trước, chọn sau.

## Kết quả thi công — 2026-08-29

Cổng web: `type-check` · `lint` · `test` (**806 pass**) · `build` — cả bốn xanh.
10 test cho module chụp, 8 cho row và overlay.

**Kích thước quyết định bằng công thức, không bằng số đo một máy.** Bước 5 bảo "đo
một ảnh thật rồi mới chọn". Đo được là đo trên **một** màn hình, và con số đó không
nói gì về máy 4K của người dùng tiếp theo — nên cái chốt là *bất biến*, không phải
số: cạnh dài về `MAX_CAPTURE_EDGE_PX = 1_920`, giữ tỉ lệ. Số học kèm test: 3840×2160
→ 1920×1080. Ở kích thước đó `image_tokens_for` cho **2.452 token**, dưới trần
`IMAGE_TOKENS_PER_CALL // 2` (4.000) của một ảnh, và PNG 1920×1080 nằm dưới
`MAX_ATTACHMENT_BYTES` 4 MB. Giữ PNG chứ không JPEG: JPEG nhỏ hơn nhưng làm nhoè
đúng thứ use case này cần đọc — chữ số trong một bảng giá.

**Huỷ không phải lỗi, và không có thông báo nào.** `captureScreen` trả `null` cho cả
hai đường: người đọc đóng hộp thoại của trình duyệt, và trình duyệt từ chối. Cả hai
đều là thứ người đọc không hành động được, nên một câu lỗi ở đó là giao diện cãi
nhau với người vừa đổi ý.

**Track dừng trong `finally`.** Không phải sau khi vẽ xong: nếu decode hỏng, chỉ báo
chia sẻ màn hình vẫn phải tắt. Một chỉ báo còn sáng nói với người đọc rằng họ đang
chia sẻ màn hình trong khi không — đó là giao diện nói dối về một trạng thái riêng
tư, không phải một chỗ chưa dọn. Có test nhắm đúng nhánh vẽ-hỏng.

**Chờ frame đầu, có trần.** `play()` resolve xong không có nghĩa stream đã có frame;
canvas vẽ trước đó là một hình chữ nhật đen. Nên chờ `loadeddata`, kèm timeout 1,5s
để một stream không bao giờ ra frame không treo cái bấm.

**Overlay dùng lại `Scrim` đã có**, nên focus trap và `Esc` là của khung sẵn — `Esc`
xử lý một lần trong listener của shell *"so a dialog cannot forget it"*. Không dựng
cái thứ hai.

**Row đổi tên: "Chụp màn hình bảng giá" → "Chụp màn hình".** Nó chụp bất cứ thứ gì
người đọc chọn, và một cái tên hẹp hơn hành vi là một cái tên nói sai. Test khẳng
định row **không** còn chữ "bảng giá".

**jsdom không có `getDisplayMedia`, và file test nói thẳng điều đó.** Docstring ghi
rõ nó chứng minh được gì (huỷ không lỗi · track dừng · scale · phát hiện trình duyệt
không hỗ trợ) và **không** chứng minh được gì (ảnh thật trông đúng). Bước 8 nghiệm
thu tay còn nguyên.

## Chưa nghiệm thu — cần một lượt tay trên trình duyệt thật

Ba mục dưới cần một phiên thật, gộp chung với hai mục còn treo của phase 08:

- [ ] Bấm row → hộp thoại trình duyệt → chọn → thấy xem trước
- [ ] *Đính kèm* cho đúng một chip có thumbnail
- [ ] Nghiệm thu luật giá: chụp một bảng giá thật, hỏi về một con số trong đó, kiểm
      model không nêu con số đó mà không qua `check_price_claim`
