---
phase: 1
title: "Chẩn đoán trước mọi thứ"
status: complete
priority: P1
effort: "0.5d"
dependencies: []
---

# Phase 1: Chẩn đoán trước mọi thứ

## Overview

Làm cho mọi lỗi route nói được nó là lỗi gì. Trước phase này, mọi con số về
"36% Turn chết vì route" là phỏng đoán — nhánh gây 3/4 số ca không log gì.

## Requirements

- Functional: mọi đường kết thúc Turn vì lỗi tuyến đều ghi lại route, mã trạng
  thái, số lần thử, thời gian đã trôi, và những gì tuyến nói.
- Functional: phân loại nhánh 400 thành các mã riêng có thể phân nhánh.
- Non-functional: không đổi hành vi người dùng thấy. Đây là phase chỉ thêm quan sát.
- Non-functional: không log secret, không log body chứa API key (`redact` trước khi ghi).

## Architecture

Hai điểm sửa, độc lập nhau.

**1. `loop.py:739`** — hiện tại:

```python
except GatewayTimeout:
    # Already retried with backoff inside the client; a third
    # attempt here would silently double the tabled ceiling.
    return await self._terminal(
        request, TurnStatus.INCOMPLETE, "gateway_timeout", state
    )
```

Nhánh ngay dưới (`except LLMError`) có comment giải thích log là thiết yếu:
*"The only place the route's own words survive… exactly what an operator needs
to act on."* Áp cùng lý lẽ đó cho nhánh này. Mẫu tham chiếu: `stream_diag.py`
của Hermes ghi per-attempt counter, chuỗi exception, edge nào phục vụ, bao nhiêu
byte/chunk nhận được trước khi đứt.

**2. `core/llm/errors.py:294`** — `classify_status()` hiện có 4 nhánh có tên rồi
catch-all. Mọi 400 thành `LLMError` vô hình dạng. Thêm nhánh cho 400 theo
taxonomy `FailoverReason` của Hermes (`error_classifier.py`), giữ tên theo miền
của ta:

| Điều kiện | Lớp mới | Hành động phục hồi (Phase 4) |
|---|---|---|
| context vượt cửa sổ | `ContextOverflow` | nén, **không** failover |
| `max_tokens` vượt | `OutputCapExceeded` | giảm output cap, **không** thu `context_length` |
| content policy | `ContentPolicyBlocked` | terminal, có thông báo riêng |
| model không tồn tại/đã nghỉ | `ModelUnavailable` | đổi model |
| tool schema bị từ chối | `SchemaRejected` | log loud, terminal |
| còn lại | `LLMError` (giữ nguyên) | terminal |

Phân biệt quan trọng, lấy từ `conversation_loop.py:5670`: *"Prompt too long"*
(input vượt cửa sổ → nén) khác *"max_tokens too large"* (input ổn, nhưng
`input + max_tokens > window` → giảm **output cap**). Hai lỗi trông giống nhau,
sửa ngược nhau.

## Related Code Files

- Modify: `apps/api/src/core/llm/errors.py` — thêm lớp lỗi + nhánh trong `classify_status`
- Modify: `apps/api/src/agent/loop.py:739` — log `GatewayTimeout`
- Modify: `apps/api/src/agent/loop.py:21,23` — sửa docstring đã trôi ("Eight" → bốn)
- Modify: `apps/api/src/agent/ops.py` — đếm các mã 400 mới trong ops snapshot
- Modify: `apps/api/tests/test_agent_loop.py`, `tests/test_llm_errors.py` (hoặc file tương đương)

## Implementation Steps

1. Thêm các lớp lỗi mới vào `core/llm/errors.py`, kế thừa `LLMError` để mọi
   `except LLMError` hiện có vẫn bắt được — thay đổi thuần cộng thêm.
2. Thêm nhánh nhận dạng trong `classify_status()`. Nhận dạng dựa trên body +
   header; mỗi nhánh có test với body thật của tuyến hiện tại nếu thu được.
3. Log ở `loop.py:739` theo đúng khuôn nhánh `LLMError` bên dưới, cộng:
   attempt, elapsed, bytes nhận. Chạy qua `redact` trước khi ghi.
4. Mở rộng `ops.py` để ops snapshot đếm từng mã mới, không gộp.
5. Sửa docstring `loop.py` dòng 21 và 23: "Eight tool-call rounds" → bốn, khớp
   `MAX_TOOL_ROUNDS = 4`. Đồng thời mở **G3** cho chủ sản phẩm.
6. Chạy `make test`.

## Success Criteria

- [x] Mọi Turn kết thúc vì lỗi tuyến có một dòng log đủ để phân loại nguyên nhân
- [x] `classify_status()` có test cho từng nhánh 400 mới
- [x] `ops.py` đếm riêng từng mã, không gộp vào `route_error`
- [x] Docstring `loop.py` khớp `MAX_TOOL_ROUNDS`
- [x] Không secret nào xuất hiện trong log mới (test có case body chứa khoá)
- [x] `make test` xanh — 2589 passed
- [ ] Sau 48h chạy, ops snapshot cho biết `route_error` thật sự gồm những gì — **chờ dữ liệu production**

## Đã làm khác plan

**`ops.py` không sửa một dòng.** `incomplete_reasons` là `window.tally(AgentTurn.terminal_reason, …)` — group-by generic, không có allowlist. Năm mã mới tự tách ngay khi `loop.py` phát ra `terminal_reason` riêng. Thay vì sửa code, thêm
`test_the_named_route_conditions_are_counted_apart_from_route_error` giữ tính chất đó.

**G3 chốt: giữ 4, sửa docs.** `MAX_TOOL_ROUNDS = 4` không phải drift mà là một nửa của
đẳng thức `(MAX_TOOL_ROUNDS + 1) × DEFAULT_MAX_OUTPUT_TOKENS ≤ TURN_OUTPUT_TOKENS`, do
`test_the_turn_cannot_outspend_what_it_was_admitted_against` giữ. Commit `097d7f9` đã đo:
8 round buộc hạ output cap về 2.000, đúng cấu hình gây bug truncation. Cái trôi là docs —
đã sửa docstring `loop.py` và `docs/specs/0003` §6, cộng
`test_the_module_docstring_states_the_round_count_the_constant_holds` chặn trôi lại.

**Năm `terminal_reason` mới kèm câu tiếng Việt.** Plan nói "không đổi hành vi người dùng
thấy" nhưng cũng đòi ops đếm riêng — hai cái xung đột vì ops group theo `terminal_reason`.
Chốt: phát reason riêng và thêm 5 câu vào `apps/web/src/lib/alpha-desk/copy.ts`, nên người
đọc nhận câu chính xác hơn thay vì `UNNAMED_REASON` mơ hồ.

**`redact` phải tự viết.** Plan giả định đã có; repo không có hàm nào như vậy. Viết mới
trong `core/llm/errors.py`, nhận dạng theo *hình dạng* credential chứ không theo danh sách
provider, và áp cho cả nhánh `LLMError` cũ (nhánh đó cũng log body).

## Risk Assessment

**Rủi ro**: nhận dạng 400 theo chuỗi trong body là mong manh — tuyến đổi format
thì nhận dạng sai. **Tín hiệu**: một mã mới đột nhiên chiếm gần hết, hoặc về 0.
**Phản ứng**: nhận dạng sai luôn rơi về `LLMError` (fail-open), không bao giờ
gây hành động phục hồi sai; và log giữ body gốc để đối chiếu.

**Rủi ro**: log body lỗi có thể chứa credential. **Tín hiệu**: review bắt được.
**Phản ứng**: bắt buộc qua `redact` — đây là điều kiện nghiệm thu, không phải khuyến nghị.

**Assumption có thể vỡ**: giả định phần lớn `route_error` là ca phục hồi được.
Nếu sau 48h hoá ra tất cả là 400 "invalid request" do ta gửi sai, thì Phase 4
mất phần lớn giá trị và phải replan Phase 4 quanh việc sửa request builder.
