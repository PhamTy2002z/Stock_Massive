---
phase: 5
title: "Dạy model gọi tool song song"
status: complete
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

## Không còn bị chặn

Bản đầu của phase này ghi "blocked" vì `CLAUDE.md` § Eval gate đòi một bar đo cho PR chạm
prompt. Commit `1974c24` (2026-08-22) đã **xoá hẳn** Eval Battery / Eval Gate / Eval Report,
và `CLAUDE.md:49` nay ghi thẳng: *"PR chạm agent loop, tool schema hay prompt **không** còn
cổng đo nào."*

Nên phase này chạy được — nhưng cái nó cần vẫn là một phép đo, chỉ là không còn harness nào
làm sẵn. Đo bằng tay theo mục "Đo gì" dưới đây, và ghi số vào `plans/reports/`. Bump
`PROMPT_VERSION` (`prompt/sections.py:29`, hiện `2.2.0`) mà không có số nào bên cạnh thì
đúng là thay hành vi mù.

## Thay đổi

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

## Đã làm

- `agent/prompt/sections.py`: thêm đoạn *"Gộp lượt, không tra thêm"* vào mục
  `TOOLS`, ngay sau *"Tra có mục đích"*. Mở đầu bằng chính tính chất phải giữ,
  vì một đoạn chỉ nói *hãy gộp* sẽ dạy model gộp cả những call phụ thuộc nhau.
  `PROMPT_VERSION` `2.2.0` → `2.3.0`.
- `tests/test_agent_prompt.py`: test khẳng định câu đó nằm trong `prefix()`,
  tức nửa cacheable — token trả một lần, không trả mỗi lượt.

Số đo: `plans/reports/measurement-260822-1940-parallel-tool-guidance.md`.
48 lượt thật, 24 mỗi arm, chạy đan xen theo block. Round −13,7 %, tool call
−4,7 %, call/round +10,5 %, 24/24 lượt `complete` ở cả hai arm. Bar *"cùng số
call, ít round hơn"* đạt; biên độ nhỏ vì model đã tự batch ở 20/24 lượt arm
`before` trước khi được dạy. Ngưỡng revert cho lần đo sau ghi trong report.

## Risk / rollback

- **Risk chính**: prose khuyến khích batch làm model tra bừa nhiều hơn. Chống bằng chính bar
  đo ở trên — tính chất là *ít round hơn với cùng số call*.
- **Risk**: `MAX_EXTERNAL_TOOL_CALLS = 6` bị tiêu hết trong một round nếu model batch mạnh.
  Đó là hành vi đúng (`loop.py:259` đã lường: *"one round may fan out to five searches"*), và
  Phase 3 đã đặt trần fan-out 8 nên không có đường bùng.
- **Rollback**: một đoạn prose + một số version. `git revert` và hạ `PROMPT_VERSION` lại.
