---
phase: 4
title: "Ops thấy được ba lớp lỗi vừa đóng"
status: complete
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

## Đã làm

- `alpha/models.py`: đặt tên cả bốn giá trị của `agent_tool_call.status`
  (`TOOL_CALL_OK` / `TOOL_CALL_TOOL_ERROR` / `TOOL_CALL_TIMEOUT` /
  `TOOL_CALL_UNKNOWN_TOOL`) cùng `TOOL_CALL_STATUSES`, ở đúng chỗ cột được khai.
  Comment cũ vừa bị lặp dòng vừa trỏ vào `src/agent/tools/catalog.py` — file
  không tồn tại — nên viết lại.
- `agent/loop.py`: `trace_status(ok=…, error=…)` map error sang bốn nhóm, và
  `_trace_writer` dùng nó thay cho `"ok" if ok else "error"`.
- `agent/ops.py`: thêm `tool_call_errors` (tally trên `AgentToolCall.error` với
  `status != "ok"`) và property `tool_call_error_total`.
- `agent/executor.py`: `_over_ceiling` giờ đi qua `_record` và log `warning`.
  Ngoài phạm vi "Thay đổi" ở trên, nhưng bắt buộc: không có nó thì
  `round_fanout_exceeded` không có hàng nào để `tool_call_errors` đếm, tức lời
  hứa của chính phase này là sai. Code review Phase 2–3 độc lập gọi đây là
  blocker.
- `apps/web`: không sửa. `grep -rn 'unknown_tool_calls' apps/web/src` sạch —
  snapshot ops chưa được vẽ ở đâu, kể cả trước phase này.

Test: `tests/test_agent_loop.py` (3 test mới: unknown_tool end-to-end,
verdict-vs-crash cùng status khác error, và mapping bị giữ trong vốn từ đã khai),
`tests/test_agent_ops_query.py` (2 test mới: tally theo reason, và `empty_answer`
trong `incomplete_reasons`). `make test`: 2281 passed, 1 failed — đúng fail có sẵn
của `test_deployment_topology`.

## Còn hở, đã kiểm chứ không đoán

Ba tên trong danh sách "Thay đổi" ở trên **không** tới được cột `error` của
`agent_tool_call`, nên `tool_call_errors` không thấy chúng:

- `dispatch_failed` — cố ý, `_dispatch_failed` không ghi trace vì trace write là
  một trong những thứ có thể chết ở đó. Chỉ còn log.
- `external_budget_exhausted` — đặt trên `TurnToolCall` trong `loop.py::_round`,
  không đi qua `executor._record`. Số đo Phase 5 cho thấy nó nổ ở 10/48 lượt,
  nên đây là tín hiệu đang mất thật, không phải giả thuyết.
- `halted_turn` của `_skipped` — call sau khi halt; call *bị* halt thì có hàng.

Và `"timeout"` chưa có đường nào ghi được: round timeout huỷ `executor.run`
trước khi `_record` chạy, tool tự timeout thành `tool_failed`. Nhóm này tồn tại
vì cột khai nó và loop đã gọi lý do đó bằng tên đó; nó được test qua mapping, chứ
không qua một lượt thật.

## Risk / rollback

- **Risk**: đổi vốn từ cột `status` làm hàng cũ (`"error"`) và hàng mới (`"tool_error"`) không
  đọc chung được. Thật, và chấp nhận: hàng cũ vẫn đếm được qua cột `error`, và cửa sổ ops mặc
  định là 7 ngày nên drift tự hết. Ghi rõ trong commit message, không lặng lẽ đổi.
- **Rollback**: `git revert`. Không migration nên không có gì phải hoàn nguyên ở DB.
