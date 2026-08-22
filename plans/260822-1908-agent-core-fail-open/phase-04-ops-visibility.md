---
phase: 4
title: "Ops thấy được ba lớp lỗi vừa đóng"
status: pending
---

# Phase 4 — Ops thấy được ba lớp lỗi vừa đóng

Chặn bởi Phase 1–3: phase này đếm những thứ ba phase kia tạo ra.

## Lớp lỗi đang mở

### 4a — một tín hiệu ops đã chết

`ops.py:208` đếm:
```python
AgentToolCall.status == TOOL_CALL_UNKNOWN_TOOL   # "unknown_tool"
```

Nhưng cái viết cột đó là `loop.py:_trace_writer`:
```python
"status": "ok" if entry.get("ok") else "error",
```

`executor.UNKNOWN_TOOL = "unknown_tool"` đi vào `ToolResult.error`, rồi vào **cột `error`**,
không bao giờ vào cột `status`. `alpha/models.py:369` còn ghi comment
`# ok | tool_error | timeout | unknown_tool` — bốn giá trị, code ghi hai.

**`unknown_tool_calls` trong ops snapshot luôn bằng 0.** Và `alpha/models.py:455` nói rõ đó
là *"`docs/adr/0011`'s demand trigger — a model reaching for a tool that does not exist is the
evidence for whether sandboxed execution is ever needed"*. Tín hiệu quyết định một câu hỏi
kiến trúc đang đọc từ một cột không ai ghi.

### 4b — hai lớp lỗi mới không có chỗ đếm

- Turn `complete` không có message: sau Phase 1 nó thành `incomplete` + `empty_answer` nên
  **tự động** vào `incomplete_reasons`. Không cần code mới — cần một test khẳng định điều đó.
- Verdict guardrail (`blocked_call`, `halted_turn`) và lỗi executor mới
  (`dispatch_failed`, `round_fanout_exceeded`): tất cả nằm ở cột `error`, chưa ai tally.
  `guardrails.py:63` tự viết: *"tín hiệu module này ngừng hoạt động là halt count đứng ở 0
  mãi mãi"* — và không ai đếm halt.

## Thay đổi

**Không migration.** Mọi tín hiệu đọc được từ cột đã có.

### `agent/loop.py` — `_trace_writer`

Ghi `status` bằng đúng vốn từ mà cột đã khai. Map từ `result.error` sang status:
- `unknown_tool` → `"unknown_tool"`
- `tool_timeout` → `"timeout"`
- mọi error khác → `"tool_error"`
- không error → `"ok"`

Cột là `String(16)` — cả bốn giá trị đều vừa. Đây là chỗ duy nhất phải sửa để 4a sống lại,
và nó làm comment ở `alpha/models.py:369` trở thành đúng thay vì phải xoá.

Giữ nguyên cột `error` mang tên chi tiết (`blocked_call`, `halted_turn`, `dispatch_failed`,
`round_fanout_exceeded`): `status` là bốn nhóm, `error` là lý do cụ thể. Một cột một câu hỏi.

### `agent/ops.py`

Thêm vào `OpsSnapshot` + `read_ops_snapshot`, cùng khuôn `window.tally` đang có:

1. `tool_call_errors` — tally trên `AgentToolCall.error` với `status != "ok"`. Đây là chỗ
   `blocked_call` / `halted_turn` / `dispatch_failed` / `round_fanout_exceeded` /
   `external_budget_exhausted` hiện ra, mỗi cái tự đứng tên.
2. `unknown_tool_calls` — giữ nguyên query, giờ nó trả số thật.

`rounds_exhausted`: **không** thêm. Nó chưa được persist ở đâu (`TurnOutcome.rounds_exhausted`
chỉ sống trong process), và thêm một cột cho nó là một migration mà plan này đã tuyên bố
không làm. Ghi vào phần câu hỏi chưa giải quyết thay vì lặng lẽ bỏ.

### `apps/web` — surface ops

Nếu snapshot đang được vẽ ở đâu thì thêm dòng `tool_call_errors`. Kiểm tra trước:
`grep -rn 'unknown_tool_calls' apps/web/src`. Không có chỗ vẽ thì không thêm gì.

## Validation

Test tại `apps/api/tests/`:
1. Trace của một call tool không tồn tại ghi `status == "unknown_tool"` — test này trước đây
   không thể pass.
2. Trace của một call timeout ghi `status == "timeout"`; call fail thường ghi `"tool_error"`.
3. `read_ops_snapshot` trả `unknown_tool_calls` khác 0 khi có hàng như vậy trong cửa sổ.
4. `read_ops_snapshot` trả `tool_call_errors` có khoá `blocked_call` và `halted_turn`.
5. Turn rỗng của Phase 1 xuất hiện trong `incomplete_reasons` dưới khoá `empty_answer`.

Cổng: `make test`, rồi 4 cổng web nếu có sửa `apps/web`.

## Risk / rollback

- **Risk**: đổi vốn từ cột `status` làm hàng cũ (`"error"`) và hàng mới (`"tool_error"`) không
  đọc chung được. Thật, và chấp nhận: hàng cũ vẫn đếm được qua cột `error`, và cửa sổ ops mặc
  định là 7 ngày nên drift tự hết. Ghi rõ trong commit message, không lặng lẽ đổi.
- **Rollback**: `git revert`. Không migration nên không có gì phải hoàn nguyên ở DB.
