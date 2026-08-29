---
phase: 3
title: "Content part không-text và chi phí token"
status: done
priority: P1
effort: "6h"
dependencies: [1]
---

# Phase 03: Content part không-text và chi phí token

## Overview

Mở đường cho một block không phải text đi tới route, và — quan trọng hơn — làm nó
**nhìn thấy được** với `estimate_tokens`. Đây là phase khó nhất của plan, và là
chỗ bản đầu sai nặng nhất.

## Requirements

- Functional: một message mang được ảnh; `as_wire` sinh đúng block OpenAI;
  `estimate_tokens` tính chi phí thật của ảnh; `_mark_tail_breakpoints` không dập
  `cache_control` lên block không-text.
- Non-functional: `ContentSegment` giữ đúng một nghĩa; đường text hiện có không
  đổi một byte payload nào và không đổi một token estimate nào.

## Architecture

### Một type mới, không nhồi `ContentSegment`

`ContentSegment(` có đúng **4 site**, cả bốn là ranh giới cache system prompt:
`probe.py:294-295`, `messages.py:678-679`. Docstring `:204-218` nói nó tồn tại cho
System Prompt Contract — *"a caller that knows where the stable part ends says so
here"*. Nhồi ảnh vào làm một frozen type mang hai nghĩa và `__post_init__` mang
hai luật. Thay vào đó: một type content-part riêng cho ảnh, và `Message` mang nó
ở một trường riêng.

### Invariant được thoả bằng cách kể đúng

`protocol.py:238-246` bắt `segments` nối lại đúng bằng `content` vì *"route đọc
block và ledger đo string phải đang đọc cùng một prompt"*. Ảnh vẫn góp một
**placeholder** vào `content`, ví dụ `[ảnh: bang-gia.png]`, nên `content` còn là
bản kể trọn prompt. Nhưng — đây là chỗ bản đầu dừng lại và sai — placeholder
**không** phải câu trả lời cho kế toán.

### `estimate_tokens` là thứ quyết định context, không phải `admission`

```
build_messages (messages.py:806)  →  sum(estimate_tokens(m))
                                        vs ContextBudget.max_tokens = TURN_CONTEXT_PER_CALL
loop.py:1178                      →  SpendRequest(input_tokens=context.estimated_tokens + …)
admission.py:682-686              →  refuse if input_tokens > TURN_CONTEXT_PER_CALL
admission.py:308                  →  refuse if owner_input + input_tokens > TURN_INPUT_TOTAL
admission.py:483-491              →  reconcile từ usage.input_tokens  ← chỉ SAU call
```

`estimate_tokens` (`messages.py:652-659`) là `MESSAGE_OVERHEAD_TOKENS +
ceil(len(text)/3)` với `text = message.content or ""`. Một placeholder 19 ký tự =
11 token cho một ảnh 1.500-3.000 token. Hệ quả, cả ba đều im lặng:

1. `build_messages` tưởng còn chỗ nên **không xuống thang giảm** — không collapse
   tool result nào, không bỏ Turn nào.
2. Trần trước call (`turn_context_per_call`, `turn_input_total`) tính trên số hư cấu.
3. Khi route trả context overflow, `loop.py:1311` so
   `smaller.estimated_tokens >= context.estimated_tokens`, thấy "nothing was given
   up" và **re-raise**. Thang phục hồi bị vô hiệu, Turn chết mà người đọc không
   được bảo rằng bỏ một ảnh là cách chữa.

Nên: content part ảnh mang một `estimated_tokens` khai báo, và `estimate_tokens`
cộng nó vào. Hằng số lấy từ phép đo phase 04, không đoán.

### `transport.py` là chỗ thứ hai dập `cache_control`

`_mark_tail_breakpoints` (`transport.py:483-513`) lấy `content[-1]` của hai message
không-system cuối và thêm `cache_control`. Message có ảnh thường **là** message
cuối, và block ảnh thường **là** block cuối. Test unit của `as_wire` sẽ pass trong
khi wire thật sai. Tiềm ẩn vì `llm_prompt_cache_control_enabled = False`
(`config.py:115`) — một dòng config bật lên là lỗi hiện ra.

Và tín hiệu bản đầu ghi ("probe cache check fail lúc boot") **không bao giờ nổ**:
check đó (`probe.py:288-300`) gửi message system-only, không có ảnh.

## Related Code Files

- Modify: `apps/api/src/core/llm/protocol.py` — content part mới, `Message`, `as_wire`, `_content_block`
- Modify: `apps/api/src/core/llm/transport.py` — `_mark_tail_breakpoints` bỏ qua block không-text
- Modify: `apps/api/src/core/llm/config.py` — `LLMRoute` mang năng lực vision (xem phase 04)
- Modify: `apps/api/src/agent/messages.py` — `estimate_tokens` cộng chi phí content part
- Modify: `apps/api/tests/` — test cho cả bốn file trên

## Implementation Steps

1. Type content part mới ở `protocol.py`: media type + dữ liệu (hoặc data URI đã
   dựng) + `estimated_tokens` + placeholder text. Frozen dataclass. **Không** sửa
   `ContentSegment`.
2. `Message` mang một trường mới cho các content part không-text. `__post_init__`
   kiểm placeholder của từng part có mặt trong `content` — invariant giữ nguyên
   nghĩa gốc, chỉ mở rộng phạm vi.
3. `_content_block` sinh `image_url` với data URI. `as_wire` thêm nhánh: có content
   part không-text → `payload["content"]` luôn là list block, bất kể `cache_control`.
   Viết bình luận nói vì sao: một route nhận string không nhận được ảnh.
4. `_mark_tail_breakpoints`: khi `content` là list, đi **ngược** tìm block `text`
   cuối cùng thay vì lấy `content[-1]` mù. Nếu message không có block text nào thì
   bỏ qua message đó.
5. `estimate_tokens`: cộng `estimated_tokens` của từng content part. Giữ nguyên
   đường text — một message không có part nào phải cho **đúng con số cũ**.
6. Hằng số chi phí ảnh: đặt ở một chỗ, có bình luận dẫn từ phép đo phase 04. Ở
   phase này nó là một giá trị tạm có ghi rõ là tạm; phase 04 chốt.
7. Test, theo thứ tự quan trọng giảm dần:
   - message text thuần: payload **và** `estimate_tokens` **y như cũ** (chống hồi
     quy im lặng — hai test riêng);
   - message có ảnh: `estimate_tokens` > placeholder của nó, và > 500;
   - `Message` có content part mà `content` thiếu placeholder → `ValueError`;
   - `as_wire` sinh `image_url` khi `cache_control=False`;
   - **wire dựng qua `transport._messages` với `cache_control=True` + một message
     có ảnh: `cache_control` nằm trên block text, không trên block ảnh.** Không
     phase nào của bản đầu có test này.
8. Chưa nối vào Turn ở phase này. Chỉ tầng protocol/transport/estimate + test.

## Success Criteria

- [ ] `ContentSegment` không đổi; type mới là type riêng
- [ ] Message text thuần: payload không đổi **và** estimate không đổi (hai test)
- [ ] Message có ảnh: `estimate_tokens` > 500 và > estimate của placeholder
- [ ] Invariant placeholder có test cho cả trường hợp thiếu
- [ ] `cache_control=True` + ảnh → marker trên block text, không trên block ảnh
- [ ] Hằng số chi phí ảnh có bình luận nói nó là tạm và ai chốt nó
- [ ] `make test` pass

## Risk Assessment

**Rủi ro: sửa `estimate_tokens` đổi con số của mọi Turn đang chạy.** Nó là hạ tầng
của cả thang context.
*Tín hiệu:* test "message text thuần estimate không đổi" fail.
*Phản ứng đã định:* chi phí cộng thêm **chỉ** từ content part; đường text không
được chạm. Nếu test đó fail thì revert bước 5 trước, không sửa tiếp.

**Rủi ro: hằng số chi phí ảnh đặt sai bậc.** Đặt thấp thì lại mù như cũ; đặt cao
thì thang giảm cắt oan tool result.
*Tín hiệu:* `usage.input_tokens` route trả về lệch hằng số quá một hệ số đã nêu.
*Phản ứng đã định:* phase 04 đo và ghi cả hai con số vào report. Success criterion
cấp plan yêu cầu estimate nằm trong một hệ số đã nêu so với usage thật — đó là
phép kiểm, không phải cảm giác.

**Rủi ro: `_mark_tail_breakpoints` đi ngược tìm block text làm mất breakpoint cache
của message không có text.**
*Tín hiệu:* check `prompt_cache_control` của probe vẫn pass (nó không có ảnh), nên
tín hiệu phải là test ở bước 7.
*Phản ứng:* bỏ qua message đó là đúng — một message toàn ảnh không có gì đáng cache
theo prefix.
