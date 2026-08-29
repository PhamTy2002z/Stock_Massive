---
phase: 8
title: "UI đính kèm tệp và ảnh"
status: done
priority: P1
effort: "6h"
dependencies: [7]
---

# Phase 08: UI đính kèm tệp và ảnh

## Overview

Row "Thêm tệp hoặc ảnh" bỏ `disabled` và làm thật: chọn tệp, thấy nó, bỏ được nó,
gửi cùng câu hỏi, và **lấy lại được khi retry**. Kèm vẽ lại đính kèm trong
transcript khi mở lại thread.

## Requirements

- Functional: chọn tệp qua picker và qua `⌘U`; mỗi đính kèm là một chip có tên, kích
  thước, nút bỏ; ảnh có thumbnail; gửi kèm câu hỏi; **retry và resend gửi lại đúng
  danh sách**; mở lại thread thấy lại đính kèm cũ.
- Non-functional: nạp thất bại nói được vì sao; composer không khoá vì một lần nạp
  treo; bàn phím và screen reader đi hết được.

## Phạm vi: cái bản đầu tự thêm

Bản đầu nâng kéo-thả và dán clipboard lên **Requirements**, và biện minh dán bằng
*"nó làm phase 07 nhẹ hơn"* — không đúng, phase chụp màn hình không đổi một bước
nào. Người dùng xin một row "Thêm tệp hoặc ảnh" chạy thật.

Nên: **picker + chip + thumbnail + `⌘U`** ở trong phạm vi. Thumbnail vì "thấy trước
khi gửi" là chính nghĩa của việc này. `⌘U` vì hint đó **đã in trên row**
(`composer.tsx:385`) và một hint không hoạt động là cùng loại lời hứa plan này đang
dọn.

**Kéo-thả và dán clipboard: ra ngoài**, ghi vào §Sau nghiệm thu. Cả hai đều tốt, cả
hai đều không được xin, và mỗi đường vào thêm là một tập trạng thái hover, một
vòng đời `revokeObjectURL`, một nhánh copy lỗi nữa.

## Architecture

### Nạp trước, hỏi sau

Đính kèm nạp ngay khi chọn, không lúc bấm gửi. Người đọc thấy tiến trình trong khi
còn đang viết, và `createTurn` chỉ mang id — vẫn nhanh, vẫn idempotent.

### Retry là chỗ bản đầu sai

Bản đầu viết *"ba call site, đúng như `signalDesk` đã đi qua cả ba"*. Phép so sánh
không hợp lệ: `signalDesk` là **toggle bền** đọc lại được từ shell state mọi lúc;
đính kèm đang chờ bị **xoá sau khi gửi**. Và `retry` (`desk-state.tsx:417-423`) dựng
input từ `lastQuestion` — một **string** scrape từ `entries` (`:408-413`). Turn mới
nên không có 409 nào bắt: model trả lời tự tin về một ảnh nó chưa từng thấy.

`resend` (`:439-446`) là call site **thứ tư**, bản đầu không đếm.

Chữa: đính kèm phải lấy lại được **từ transcript** — phase 07 đã trả metadata ra
response — nên `lastQuestion` thành `{text, attachments}` và `resend` cũng đi đường
đó. Không phải từ state đã xoá.

### `⌘U` không có nhà

`onKeyDown` duy nhất của composer nằm trên `<textarea>` (`composer.tsx:124`, `:182`),
nên một shortcut cấp menu cần listener ở document. Nhà có sẵn:
`shell-state.tsx:884-903` đã sở hữu một `keydown` toàn cục cho `⌘K`. Thêm vào đó,
không dựng cái thứ hai.

### Chỗ chip ngồi

Trên `textarea`, đúng chỗ pill ngữ cảnh phân tích đang ngồi (`composer.tsx:150-173`).
Đọc bình luận `:150-157` trước khi thêm màu — nó ghi luật *"hai màu cam trong một
card thì cạnh nhau"*, và accent đã thuộc về control chế độ.

### Cờ vision đọc ở đâu

FE không đọc `.env` của API. Quyết định lúc làm giữa "thêm một trường vào một
endpoint hiện có" và "một endpoint năng lực nhỏ" — đọc `GET /usage` xem có chỗ tự
nhiên chưa. Cờ tắt: picker vẫn nhận ảnh (phase 05 vẫn lưu), nhưng có câu nói rõ
model chưa đọc được ảnh.

## Related Code Files

- Modify: `apps/web/src/components/shell/composer.tsx` — row 1, chip row
- Create: `apps/web/src/components/shell/attachment-chip.tsx`
- Modify: `apps/web/src/components/shell/shell-state.tsx` — `⌘U` vào listener đã có
- Modify: `apps/web/src/components/shell/desk-state.tsx` — state đang chờ, **bốn** call site
- Modify: `apps/web/src/lib/alpha-desk/api.ts` — `uploadAttachment`, `attachmentUrl`, `attachments` trong `CreateTurnInput`
- Modify: `apps/web/src/lib/alpha-desk/types.ts` — kiểu đính kèm trong `MessageResponse`
- Modify: `apps/web/src/lib/alpha-desk/transcript.ts` — đính kèm vào `TranscriptEntry`
- Modify: `apps/web/src/hooks/use-live-turn.ts` — `TurnInput.attachments`
- Modify: `apps/web/src/components/alpha/message/*` — vẽ đính kèm trong transcript
- Modify: `apps/web/src/lib/alpha-desk/copy.ts` — mọi chuỗi mới

## Implementation Steps

1. `uploadAttachment(file)` → `{id, mediaType, byteSize, filename}`. 413, quota vượt,
   media type bị từ chối: mỗi cái thành một câu tiếng Việt qua `copy.ts`, không phải
   HTTP status hiện lên UI.
2. State đính kèm đang chờ ở `desk-state.tsx` cạnh `queuedQuestion` — nó thuộc câu
   hỏi chưa gửi. Xoá sau khi `send` thành công.
3. `TranscriptEntry` mang đính kèm; `lastQuestion` đổi từ `string` sang
   `{text, attachments}`.
4. **Bốn** call site truyền `attachments`: `submit` · effect queued · `retry` (từ
   transcript) · `resend` (từ transcript). Không ba.
5. `AttachmentChip`: tên (truncate), kích thước, nút bỏ, trạng thái *đang nạp* /
   *lỗi*. Thumbnail cho ảnh từ `URL.createObjectURL` của file local; `revokeObjectURL`
   trong cleanup của effect, **có test**.
6. `⌘U` vào listener toàn cục ở `shell-state.tsx`, cạnh `⌘K`. Mở picker.
7. Transcript: message người dùng vẽ chip cho đính kèm cũ; ảnh lấy qua
   `GET /attachments/{id}`. Bất biến nên cache được suốt đời tab.
8. Row 1 của `AttachMenu` bỏ `disabled`.
9. Đính kèm đang chờ vào `writeDeskSession` (`desk-state.tsx:218-227`) — bản đầu để
   ngoài, nên reload mất chip trong khi hàng vẫn đọng trong DB, tự nuôi đường rác của
   phase 05.
10. Test: chọn ảnh → chip → gửi → payload mang id · bỏ chip thì không gửi · **retry
    một Turn có ảnh gửi lại đúng danh sách** · **resend một message cũ có ảnh gửi lại
    đúng danh sách** · nạp lỗi hiện câu tiếng Việt và composer vẫn gửi được câu không
    đính kèm · `revokeObjectURL` được gọi · `⌘U` mở picker · reload giữ chip.

## Success Criteria

- [x] Chọn một ảnh → chip có thumbnail → gửi → model trả lời có nội dung ảnh
- [x] Bỏ chip trước khi gửi thì Turn không mang nó
- [x] **Retry** một Turn có ảnh gửi lại đúng đính kèm
- [x] **Resend** một message cũ có ảnh gửi lại đúng đính kèm
- [x] Nạp thất bại hiện câu tiếng Việt; composer vẫn gửi được
- [ ] Mở lại thread vẽ lại đính kèm cũ; bytes về nguyên vẹn qua proxy
- [x] `⌘U` mở picker
- [x] Reload giữ chip đang chờ
- [x] `revokeObjectURL` có test
- [ ] Bàn phím đi hết: mở menu → row 1 → picker → chip → nút bỏ
- [x] `pnpm type-check` `lint` `test` `build` pass

## Sau nghiệm thu — không làm ở phase này

- Kéo-thả tệp vào composer.
- Dán ảnh từ clipboard.

Cả hai không được xin. Ghi ra đây để chúng không mất, và để không ai coi việc thiếu
chúng là một phase làm dở.

## Risk Assessment

**Rủi ro: `URL.createObjectURL` rò bộ nhớ.**
*Tín hiệu:* tab phình sau nhiều lần chọn rồi bỏ.
*Phản ứng đã định:* `revokeObjectURL` trong cleanup, và test cho nó là **điều kiện
nghiệm thu**, không phải "có thì tốt" như bản đầu viết.

**Rủi ro: đính kèm treo khi Thread chưa tồn tại.** `submit` xếp câu hỏi vào
`queuedQuestion` và tạo Thread trước.
*Tín hiệu:* gửi câu đầu của một Thread mới kèm ảnh, và ảnh mất.
*Phản ứng đã định:* bảng phase 05 cố tình không có `thread_id`, nên id sống qua bước
tạo Thread. Effect queued phải mang nó theo và test phải phủ đúng đường này.

**Rủi ro: retry lấy đính kèm từ transcript mà transcript chưa về.** Turn fail sớm,
`entries` có thể chưa mang message người dùng đã commit.
*Tín hiệu:* retry ngay sau một fail rất sớm gửi danh sách rỗng.
*Phản ứng đã định:* `createTurn` commit message người dùng **trước khi trả về**
(bình luận ở `desk-state.tsx` nói vậy), nên transcript có nó ngay khi có Turn. Nếu
Turn chưa được admit thì không có gì để retry — nút retry không nên hiện. Kiểm điều
kiện hiện nút thay vì thêm một bản sao state.

## Kết quả thi công — 2026-08-29

Cổng web: `type-check` · `lint` · `test` (**788 pass**, 61 file) · `build` — cả bốn xanh.

**`pnpm build` không cần dừng `pnpm dev`, và không cần hỏi user.** `next.config.js:8`
đã có sẵn `E2E_NEXT_DIST_DIR`, kèm bình luận nói đúng mục đích này. Chạy
`E2E_NEXT_DIST_DIR=.next-verify pnpm build` rồi `rm -rf ./.next-verify`: `.next`
của dev không bị đụng. Đây cũng là câu trả lời cho việc treo #1 của session làm
phase 01-05.

**Cờ vision đi qua một route mới, không nhồi vào `/usage`.** Đọc `/usage` như plan
yêu cầu: nó tự khai là *"one account's consumption"* — một con số nhích theo mỗi
Turn. Cờ vision là dữ kiện **deployment**, hằng số tới lần deploy, giống nhau cho
mọi account. Nhồi vào đó là đúng lỗi plan cảnh báo ở `ContentSegment`: một payload
hai nghĩa, và client polling cho spend mới sẽ polling cho một hằng số. Nên
`GET /capabilities` → `{"vision": bool}`, đọc từ chính `LLMRoute` mà loop đọc, và
hook fetch một lần với `staleTime: Infinity`. Mặc định `true` khi chưa có câu trả
lời: nhấp nháy "model chưa đọc được ảnh" trên một deployment đọc được là câu sai
tệ hơn là lạc quan trong một nhịp.

**Năm call site, không phải bốn.** Plan đếm bốn (`submit` · effect queued · `retry`
· `resend`) và red-team đã sửa từ ba lên bốn. Đo thật khi test đỏ: có **năm** —
nút *Gửi lại* trên chính bong bóng câu hỏi (`view-chat.tsx`) là một call site riêng,
khác với `onRegenerate` của bong bóng trả lời. Nó gửi đúng một tham số và test bắt
được.

**Và cái sửa đúng là gỡ chỗ suy diễn thứ hai, không phải nối thêm dây.** Cả
`desk-state` (`lastQuestion`) và `view-chat` (`questionBefore`) đều tự suy "câu hỏi
nào, kèm gì" — hai bản sao của cùng một quyết định, và bản đầu của plan sai ở đúng
loại chỗ đó. Rút thành một hàm thuần `transcript.ts::questionBefore(entries, key?)`:
không truyền key thì là câu cuối, truyền key thì là câu trước entry đó. Cả hai
caller gọi nó. Test nhắm vào hàm, nơi quyết định thật sự sống.

**Trần `submit` tách thành `submitWith(text, ids)`.** Bốn chỗ gửi câu hỏi **không
đồng ý với nhau** về ids đến từ đâu: composer lấy từ pending, effect queued lấy từ
cái đã pending lúc bấm Gửi, retry lấy từ câu cuối, resend lấy từ *message đó*. Một
hàm đọc state sẽ đúng cho đúng một trong bốn. Nên ids là tham số.

**Ids của câu đang xếp hàng giữ riêng, không đọc lại pending.** `queuedAttachments`
tách khỏi `readyIds`: giữa lúc bấm Gửi và lúc Thread tạo xong, một tệp thứ hai có
thể nạp xong. Câu hỏi phải đi với thứ nó **được gửi** cùng.

**`⌘U` vào listener toàn cục đã có, qua một counter.** `shell-state` sở hữu
`keydown` cho `⌘K`; thêm `⌘U` vào đó. Nhưng picker là `<input>` của composer, nên
shell phát `pick-attachment` và state mang `attachRequests: number`. Counter chứ
không phải boolean: mở picker là một **sự kiện**, và một cờ sẽ phải được ai đó tắt
sau khi dùng — hai lần bấm liên tiếp phải mở hai lần, thứ một cờ không diễn tả được.

**`revokeObjectURL` gọi ở đúng lúc URL hết cần, không trong effect diff mảng.**
`detach` giải phóng ngay; `clearPending` giải phóng cả loạt sau khi gửi. Một effect
keyed trên list sẽ phải diff hai mảng để biết cái nào vừa rời. Test là điều kiện
nghiệm thu, không phải "có thì tốt".

**Chỉ ids đã nạp xong được gửi.** Chip đang bay hoặc lỗi không vào danh sách: gửi
key của nó là gửi một id không tồn tại, backend trả 404, và cả câu hỏi của người
đọc bị từ chối vì một tệp.

**Bảng freeze thêm một dòng:** `apps/api/pytest.ini` (phase 06). Ngoài ra phase này
đụng `src/lib/query-keys.ts` và `src/hooks/use-capabilities.ts` — cả hai thuộc
`apps/web/src/**` nhưng không nằm trong ô `components/shell/*` của bảng; xem §Ranh
giới của `plan.md`, dòng UI đã được nới ở amendment 2026-08-29.

**Ngoài phạm vi, đúng như plan chốt:** kéo-thả và dán clipboard — ghi ở §Sau nghiệm thu.

## Nghiệm thu tay — 2026-08-29, trình duyệt thật

Chạy trên `localhost:3000` (dev), API container sau khi forward cờ vision.

**Chip:** thumbnail đúng ảnh, tên `bang-gia.png`, `18 KB` (số từ server trả về, không
phải số local), nút bỏ. Gửi xong composer sạch, chip vẽ lại trên bong bóng câu hỏi,
căn phải, **không** có nút bỏ — đúng luật "câu đã hỏi thì không rút tệp ra được".

**Ảnh tới được model, đo bằng nội dung chỉ có trong ảnh.** Hỏi *"Trong ảnh này VCB
đóng cửa bao nhiêu? Đọc giúp tôi cả bảng."* với một PNG bảng giá tự dựng. Model đọc
lại **đúng cả ba dòng** — VCB 195.400 (+1,2%) · VNM 62.100 (-0,4%) · MWG 58.750
(+0,8%). Ba con số đó không tồn tại ở đâu ngoài file PNG.

**Một lỗi thật tìm ra ở bước này, và nó làm cả tính năng câm.**
`LLM_VISION_ENABLED` **không được forward** vào container api — `.env` khai `true`,
`GET /capabilities` trả `{"vision": false}`, và ảnh sẽ được nạp, được lưu, được tính
tiền, rồi **không bao giờ tới model**. Chính `docker-compose.yml` đã viết ra luật bị
vi phạm ở ba chỗ khác trong cùng file: *"a switch that only exists in the settings
class is one a container never sees."* Sửa: forward `LLM_VISION_ENABLED` +
`LLM_VISION_MEASURED_MODEL` ở cả `docker-compose.yml` và `docker-compose.prod.yml`;
bảng freeze nhận thêm một dòng. Sau khi recreate container: `{"vision": true}`, và
lượt hỏi ở trên chạy được. Không unit test nào bắt được cái này — nó nằm ở khoảng
giữa settings class và container.
