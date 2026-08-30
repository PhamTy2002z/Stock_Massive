# Phase 04 — cache tự động, đo trên đúng cái đầu C2 dựng

**Ngày:** 2026-08-30 · Model `gpt-5.6-terra` · `llm_prompt_cache_control_enabled` = **False**
**Report thô:** `plans/reports/probe-260830-prompt-cache.md`

## Kết quả

| Prefix | Token prefix | Lượt | Hit | Fresh | Cached read | Cache write | Tỷ lệ |
|---|---:|---:|---:|---:|---:|---:|---:|
| `core` | 5.695 | 4 | 1 | 16.397 | 4.864 | 0 | 22,9% |
| `core+domain-body` | 6.376 | 4 | **4** | 4.149 | 19.456 | 0 | **82,4%** |
| **tổng** | | 8 | 5 | 20.546 | 24.320 | 0 | **54,2%** |

Ledger khớp **tuyệt đối**: `llm_call_usage` ghi đúng 20.546 / 24.320 / 0 trên 8 dòng.
Chi phí probe: 51.887 µUSD.

## Ba điều đọc được, và điều thứ hai là điều phase 03 được dựng để có

**1. Cache đang đọc, với cờ tắt.** Verdict dương, và nó độc lập với phép đo thứ
hai: ledger của run golden `web-first-v1-final` cho **489.106 fresh / 492.032
cached read** trên 78 lượt gọi Turn thật — **50,1%** prompt token đọc từ cache mà
`llm_prompt_cache_control_enabled` vẫn `False`. Hai mẫu khác nhau, cùng một câu
trả lời. Quyết định 2026-08-23 giữ cờ tắt **vẫn đúng trên cái đầu mới**.

**2. Body pack đứng *sau* core, và đó là lý do thêm body không phá cache.**
Cả hai family đọc lại **đúng 4.864 token** như nhau. Route cache theo block và
biên của nó rơi *bên trong* core, trước body — nên body nằm ở phần fresh
(1.037 vs 452), nhưng **prefix đã cache không suy suyển khi body xuất hiện**.
Nếu body đặt trước core, thêm nó sẽ dịch mọi byte và void toàn bộ khối đã cache.
Đó chính xác là tính chất phase 03 được dựng để có, và giờ nó là số đo chứ không
phải lập luận.

**3. Core dùng chung được giữa các Turn không liên quan.** Family `core` mất 3
lượt để ấm (miss · miss · miss · hit). Family `core+domain-body` chạy sau đó hit
**4/4** ngay từ lượt đầu — nó đọc lại khối core mà family trước vừa làm ấm. Prefix
ổn định không chỉ giúp lượt sau của cùng một Turn; nó giúp Turn của người khác.

## Cái probe cố ý không làm

- **Không gate từng lượt.** Đo 2026-08-23 ghi nhận load balancer phục vụ 3 hit
  trên 8 lượt cùng prefix; lần này family `core` là 1/4 và `core+domain-body` là
  4/4 trên cùng một khối. Một lượt miss không nói được gì; một tổng bằng không
  thì có.
- **Không pad prompt.** Prefix dựng bằng `build_messages` thật, kèm **đủ 12 tool
  schema** — schema đi trong cùng cái đầu với prompt, nên một probe không gửi
  tool sẽ đo một prefix ngắn hơn production tới mấy nghìn token.
- **Không sửa cờ nào.**

## Một phát hiện vận hành, ngoài phạm vi C2

Lượt chạy đầu bị `probe_budget_exhausted` sau đúng 3 lượt: `PROBE_DAILY_MICRO_USD`
= 250.000 µUSD/ngày, và **242.538 trong đó đã bị probe lúc API boot tiêu, qua 85
lượt gọi**. Boot probe chạy 5 lượt LLM thật mỗi lần restart, nên khoảng 17 lần
restart trong một ngày là hết sạch hạn mức — và lần restart thứ 18 sẽ bị từ chối.

Probe giờ **kiểm hạn mức trước khi gửi gì** và dừng với một câu nói rõ, thay vì
phát hiện từng lượt một: một report đầy refusal có mọi counter bằng 0 đọc y hệt
một route đã ngừng cache. Đây là chỗ duy nhất việc đó được viết ra; nó **không**
phải việc của C2 để sửa.

## Trạng thái

- [x] Probe cần ceiling và không chạy được sample vô hạn
- [x] Aggregate cached read > 0 cho **cả hai** prefix family
- [x] Ledger và probe khớp fresh/cached/write **chính xác**
- [x] Body prefix không làm fresh tăng ngoài chi phí đo được của chính body
- [x] `llm_prompt_cache_control_enabled` vẫn `False`; wire không có marker Anthropic
- [x] Report đủ dữ kiện để so lại khi route/model đổi (model · hash danh tính · counter)

## Cái không cần sửa, và vì sao

`tests/test_llm_transport.py` nằm trong Related Code Files nhưng **không sửa**:
`_usage` đã tách `cached_input_tokens` và `cache_write_tokens` từ trước, và hai
test (`test_cached_and_reasoning_tokens_are_not_counted_twice`,
`test_a_cache_write_is_its_own_counter`) đã giữ đúng luật đó. Thêm test thứ ba
cho cùng một hành vi là thêm một chỗ phải sửa khi hành vi đổi.
