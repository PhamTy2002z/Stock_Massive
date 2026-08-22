---
phase: 5
title: "Dạy model gọi tool song song"
status: blocked
blocked_by: "bar eval cho trợ lý tổng quát chưa chốt (CLAUDE.md § Eval gate)"
---

# Phase 5 — Dạy model gọi tool song song

## Lớp lỗi đang mở

`executor.py` được xây quanh việc chạy một batch song song — `PARALLEL_SAFE_TOOLS`,
`plan_segments`, `asyncio.gather`. `loop.py:_complete` gửi `parallel_tool_calls=True`.

`prompt/sections.py` mục `TOOLS` **không có một câu nào** bảo model phát các call độc lập
cùng một lượt. Nó dạy ngược lại: *"Một truy vấn tốt rồi đọc kỹ tốt hơn năm truy vấn gần
giống nhau"* — đúng về chất lượng, nhưng đọc như lời khuyên gọi ít call, và với
`MAX_TOOL_ROUNDS = 4` thì gọi một call mỗi round là trần với thật sự chỉ còn 4 lần tra.

Hermes ghi rõ lý do khối này tồn tại (`docs/hermes/hermes-core-loop-260820-2352.md` §4.1):
*"The runtime already executes a batch of tool calls concurrently when they are independent …
The missing piece was telling the **model** to emit those calls together in the first place."*
Và nó là vấn đề **chi phí** trước cả độ trễ: mỗi round thêm là một lần gửi lại toàn bộ hội
thoại.

Đây là thay đổi rẻ nhất trong plan và tăng tầm với nhiều nhất.

## Vì sao bị chặn

Bump `PROMPT_VERSION` (`prompt/sections.py:29`, hiện `2.2.0`) → PR chạm System Prompt.
`CLAUDE.md` § Eval gate: PR chạm agent loop, tool schema hoặc prompt **vẫn phải nói rõ đã đo
gì**, và bar mới cho trợ lý tổng quát chưa được chốt. Eval Battery cũ chấm groundedness /
citation / recommendation — ba tính chất vừa bị xoá — nên nó không đo được cái này.

Không lặng lẽ trái. Chốt bar trước, hoặc chốt rằng phase này đo bằng cái khác và ghi lại.

## Thay đổi (khi được mở)

### `agent/prompt/sections.py`

Thêm vào mục `TOOLS`, sau đoạn *"Tra có mục đích"*, một đoạn ngắn — ngắn có chủ đích, vì
Hermes ghi lý do: *"This block is shipped to every user, every session, in the cached system
prompt — token cost is paid once and then amortised via prefix caching."*

Nội dung phải nói đúng ba điều, không hơn:
1. Việc tra nào **không phụ thuộc kết quả của việc tra khác** thì phát cùng một lượt.
2. Việc tra nào **cần kết quả trước mới biết tra gì** thì để lượt sau.
3. Số lượt là có hạn (đã nói ở đoạn dưới) — gộp được là mở rộng được tầm với.

Bump `PROMPT_VERSION` → `2.3.0`. `PROMPT_HASH` tự đổi theo (`contract.py:19` đã lo).

### Đo gì

Bar đề xuất, để chốt: chạy một tập câu hỏi web-first cố định, so **số round dùng** và **số
tool call** trước/sau. Tính chất cần chứng minh là *cùng số call, ít round hơn* — không phải
*nhiều call hơn*. Nếu số call tăng mà round không giảm thì đoạn prose này làm hại, revert.

## Validation

1. `tests/test_agent_prompt*.py`: `PROMPT_VERSION` đã bump; `_assert_no_formatting_hole` vẫn
   pass; `prefix()` vẫn chứa mục `TOOLS` (đoạn mới phải nằm trong nửa **ổn định** để được
   cache, không nằm ở phần runtime).
2. Test khẳng định `render()` vẫn chỉ nhận 5 giá trị typed — đoạn mới là prose tĩnh, không
   phải chỗ nhồi free-text.
3. Số đo trước/sau theo bar đã chốt, ghi vào `plans/reports/`.

Cổng: `make test`, 4 cổng web (prompt không chạm web nhưng contract version có thể lộ ra
snapshot test).

## Risk / rollback

- **Risk chính**: prose khuyến khích batch làm model tra bừa nhiều hơn. Chống bằng chính bar
  đo ở trên — tính chất là *ít round hơn với cùng số call*.
- **Risk**: `MAX_EXTERNAL_TOOL_CALLS = 6` bị tiêu hết trong một round nếu model batch mạnh.
  Đó là hành vi đúng (`loop.py:259` đã lường: *"one round may fan out to five searches"*), và
  Phase 3 đã đặt trần fan-out 8 nên không có đường bùng.
- **Rollback**: một đoạn prose + một số version. `git revert` và hạ `PROMPT_VERSION` lại.
