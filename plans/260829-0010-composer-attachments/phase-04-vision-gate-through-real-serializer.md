---
phase: 4
title: "Cổng vision qua serializer thật"
status: done
priority: P1
effort: "3h"
dependencies: [3]
---

# Phase 04: Cổng vision qua serializer thật

## Overview

Trả lời một câu: route đang cấu hình có đọc được ảnh không. **Cổng chặn** của cả
plan. Đứng sau phase 03, không trước — một cổng đo payload thô không chứng minh gì
về payload `as_wire` sinh ra.

## Requirements

- Functional: một phép đo chạy trên route thật **qua `Message`/`as_wire`**, với
  `prompt_cache_control` cả tắt và bật; kết quả kèm câu trả lời nguyên văn; một cờ
  năng lực có chủ rõ ràng.
- Non-functional: không tăng chi phí boot; không bao giờ chặn boot; cờ có ghi
  model nó được đo trên.

## Architecture

### Vì sao không phải một check thứ sáu trong `CapabilityProbe`

`enforce_capability_probe` (`probe.py:325-338`) **raise** khi bất kỳ check fail và
`alpha_desk_enabled`; `ProbeResult.ok` là `all(...)` (`:86-88`) — không có tầng tư
vấn. Một route thiếu vision sẽ làm API không boot, tức một năng lực phụ giết cả
sản phẩm. Thêm nữa probe đã chạy 5 lượt LLM thật mỗi restart.

### Vì sao đo qua serializer thật

Bản đầu cho script *"dựng payload thô để đo"* trong khi bước 1 của nó nói dùng lại
đường gọi — hai câu loại nhau. Payload thô vòng qua đúng hai hàm định hình request
production: `as_wire` (thứ tự block, hình dạng list) và `_mark_tail_breakpoints`
(`cache_control`). Tiền lệ ở chính repo: `JsonSchemaFormat` (`protocol.py:298-305`)
ghi *"a gateway was measured silently dropping `response_format`"*. Một cổng đo
payload khác payload production gửi tái tạo đúng loại lỗi đó, một tầng sâu hơn.

### Cờ có chủ, và có xuất xứ

`loop.py` có **0** lần gọi `get_settings()` — mọi config biên đến qua `LLMConfig`,
dựng trong singleton `_service` (`agent/service.py`). Nên cờ vision thuộc
`LLMRoute`, cạnh `prompt_cache_control`, chứ không phải một `get_settings()` đọc
giữa loop.

Và `_cached_result` (`probe.py:102`) là process-global **không key theo model**, nên
"drift fail-closed" của bản đầu không đúng: đổi `LLM_MODEL_SESSION` mà không ai
tắt cờ thì cờ vẫn bật cho một model chưa đo. Chữa: ghi **model string đã đo** cạnh
cờ, và log cảnh báo lúc startup khi model cấu hình khác model đó.

## Related Code Files

- Create: `apps/api/scripts/probe_vision.py`
- Modify: `apps/api/src/core/config.py` — `llm_vision_enabled` (mặc định `False`) + `llm_vision_measured_model`
- Modify: `apps/api/src/core/llm/config.py` — `LLMRoute` mang năng lực vision
- Modify: `apps/api/src/main.py` — một dòng log cảnh báo khi model lệch model đã đo
- Modify: `apps/api/Makefile` — một lệnh gọi script
- Modify: `.env.example`

## Implementation Steps

1. Script dựng một `CompletionRequest` **qua `Message` + content part của phase 03**,
   gửi bằng `LLMClient` như `probe.py:167-180` làm, với `SpendRequest` mang
   `OwnerType.CAPABILITY_PROBE` + `BudgetLane.EMERGENCY`.
2. Chạy **hai** lần: `prompt_cache_control` tắt và bật. Lần bật là lần kiểm
   `_mark_tail_breakpoints` của phase 03 không dập marker lên block ảnh theo cách
   gateway không nhận.
3. Ảnh test sinh trong script, mang một dữ kiện **không đoán được từ câu hỏi** —
   một số hoặc một màu random lúc chạy. Model tả đúng nó thì ảnh đã tới; tả trượt
   thì fail, không cho "có lẽ nó thấy" thành pass.
4. In ra: pass/fail · câu trả lời nguyên văn (kiểu `_render`, `probe.py:312-323`) ·
   **`usage.input_tokens`**. Con số cuối là thứ chốt hằng số chi phí ảnh của phase
   03 và trần bytes của phase 05.
5. Cờ: `llm_vision_enabled` ở `Settings`, đọc vào `LLMRoute`. `llm_vision_measured_model`
   giữ model string đã đo. `main.py` log warning khi hai cái lệch.
6. Ghi kết quả thành `plans/reports/probe-{date}-vision-route.md`, gồm cả
   `usage.input_tokens` cho một ảnh và cho hai ảnh — hai điểm đủ để suy hệ số.
7. Cập nhật hằng số chi phí ảnh của phase 03 từ số đo, bỏ nhãn "tạm".

## Success Criteria

- [ ] Phép đo chạy **qua `Message`/`as_wire`**, không dựng dict thô
- [ ] Chạy pass cả `prompt_cache_control` tắt và bật
- [ ] Ảnh test mang dữ kiện random lúc chạy; model phải tả đúng
- [ ] Report có `usage.input_tokens` cho một ảnh và hai ảnh
- [ ] `llm_vision_enabled` mặc định `False`; `LLMRoute` là chủ; `loop.py` vẫn 0 `get_settings()`
- [ ] Startup log cảnh báo khi model cấu hình lệch model đã đo
- [ ] Thời gian boot API không đổi
- [ ] Hằng số chi phí ảnh phase 03 đã chốt từ số đo
- [ ] `make test` pass

## Fork đã định trước

**Nếu pass:** `LLM_VISION_ENABLED=true`, đi tiếp 05→10 nguyên phạm vi.

**Nếu fail:** cờ ở lại `False` và phạm vi thu như sau, không bàn lại:

| Phase | Khi route không đọc được ảnh |
|---|---|
| 02, 03 | **đã xong và vẫn đúng** — đường nhị phân và content part vẫn cần cho tệp |
| 05 | nguyên vẹn; trần bytes chốt theo kích thước tệp, không theo token ảnh |
| 06 | nguyên vẹn — ranh giới tin cậy là chuyện của tệp text trước hết |
| 07 | đính kèm ảnh lưu được, replay được, **không** thành content part |
| 08 | picker nhận cả ảnh; ảnh hiện được, **kèm câu nói rõ model không đọc được ảnh** |
| 09 | **hoãn** — chụp màn hình mà model không đọc được là một nút vô nghĩa; row giữ badge |
| 10 | không đổi |

## Risk Assessment

**Rủi ro: proxy nhận payload ảnh nhưng bỏ ảnh trong im lặng.** Đã quan sát ở chính
route này với `response_format`.
*Tín hiệu:* model trả lời chung chung, không nêu được dữ kiện random.
*Phản ứng đã định:* bước 3 là cách chặn. Fail thì đi fork.

**Rủi ro: đo một lần rồi cờ sống mãi qua một lần đổi model.**
*Tín hiệu:* warning ở bước 5 xuất hiện trong log startup.
*Phản ứng đã định:* warning là tín hiệu, không phải cổng — nó không được chặn boot
(cùng lý lẽ vì sao đây không phải check thứ sáu). Ai thấy warning thì chạy lại
phép đo.

**Rủi ro: ngân sách emergency lane từ chối phép đo.** `BudgetRefusal` với
`probe_budget_exhausted` được `_check` re-raise (`probe.py:154-156`).
*Tín hiệu:* script dừng với `probe_budget_exhausted`.
*Phản ứng:* `LLM_BUDGET_*` đang `0` cho route thuê bao, nên đây là dấu cấu hình
sai chứ không phải hết tiền.
