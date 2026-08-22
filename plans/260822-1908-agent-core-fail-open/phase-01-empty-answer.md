---
phase: 1
title: "Turn rỗng không được là Turn xong"
status: complete
---

# Phase 1 — Turn rỗng không được là Turn xong

## Lớp lỗi đang mở

`loop.py:831`:
```python
if final or not completion.tool_calls:
    return await self._ended(state, TurnStatus.COMPLETE, None, rounds_exhausted=exhausted)
```

Completion không có text và không có tool call → `TurnStatus.COMPLETE`, `terminal_reason=None`.
`turns.py:439` rồi bỏ luôn message: `message = assistant_message(...) if text else None`.

**Người đọc thấy: một Turn đã xong, không một chữ nào, không lý do.** Và đã trả tiền —
`client.py:267-305` retry tới `MAX_ROUTE_ATTEMPTS=4`, swap model một lần, log
`"nothing left to try"`, rồi trả về completion rỗng đó. Client làm đúng phần của nó;
loop coi completion rỗng là câu trả lời hoàn chỉnh.

Đúng lớp sự cố Hermes đã đóng: NS-503 (*"charged ~$2.33 for an empty answer"*) và #9400
(model yếu trả rỗng sau tool call). Xem `docs/hermes/hermes-core-loop-260820-2352.md` §3.

Hành vi này **đang được test đóng đinh**: `tests/test_agent_loop.py:322`
`test_a_turn_that_never_speaks_publishes_no_delta`.

## Hai ca con, thuốc ngược nhau

**Điều kiện là `state.answer`, không phải `state.text`.** `prompt/sections.py:171` bắt model
viết một câu ngắn **trước mỗi lượt gọi tool**, và `_append_text` xếp câu đó vào `thoughts`
chứ không vào `answer` (`loop.py:1370`). Nên khi tool đã chạy thì `state.text` gần như không
bao giờ rỗng, và lớp lỗi thật không phải "Turn không nói gì" mà **"Turn chỉ nói phần dẫn"**:
`turns.py:242` fail-open `"answer": text if answer is None else answer` biến câu *"Để tôi tra
đã."* thành toàn bộ câu trả lời, status `complete`. Vô dụng y như màn hình trắng, và trông
như cố ý.

| Ca | Trạng thái | Thuốc | Vì sao |
|---|---|---|---|
| Chưa gọi tool nào | `state.tool_rounds == 0`, `state.answer` rỗng | Kết thúc `incomplete` reason `empty_answer`. **Không** mua thêm lời gọi | Không có bằng chứng nào để cứu. Mua một lời gọi để xin lỗi là đúng thứ `loop.py:34` cấm |
| Tool đã chạy, chỉ có phần dẫn | `state.tool_rounds > 0`, `state.answer` rỗng | Đúng **một** nudge rồi gọi lại. Vẫn rỗng → `incomplete` + `empty_answer`, message dựng từ narration đã có | Tới 6 external call đã tiêu, kết quả đã nằm trong transcript. Một lời gọi biến nó thành câu trả lời — chính là chỗ Hermes đặt nudge #9400 |

## Thay đổi

### `agent/loop.py`

1. Hằng mới, cạnh `ROUNDS_EXHAUSTED_NOTE`:
   - `EMPTY_ANSWER = "empty_answer"` — thêm vào nhóm reason ở `loop.py:154-186`.
   - `MAX_EMPTY_NUDGES = 1` — trần, và trần thấp như Hermes (`_post_tool_empty_retried`
     là cờ một lần).
   - `EMPTY_AFTER_TOOLS_NOTE` — nội dung nudge. Nói **thiếu gì và phải làm gì**, không xin
     lỗi. Mẫu Hermes `_EMPTY_TOOL_RESPONSE_NUDGE`: *"You just executed tool calls but
     returned an empty response. Please process the tool results above and continue."*
     Viết lại cho hình dạng của ta, tiếng Việt, và kèm đường ra: nếu kết quả không đủ thì
     nói rõ thiếu gì.

2. `_TurnState`: thêm `empty_nudges: int = 0`. Per-Turn, không per-call — cùng lý do
   `compressions`/`output_reductions` là per-Turn.

3. Chỗ nudge nằm **trong `_call`**, cạnh `_compress` và `_lower_output_cap`, không trong
   `_run`. Lý do: `_run` dùng `for round_index in range(...)` nên `continue` ở đó ăn một
   round, và nudge trên round cuối sẽ rơi ra khỏi vòng lặp vào `raise RuntimeError`.
   `_call` đã có sẵn `while True` với đúng ngữ nghĩa "cùng round, gọi lại", và `state.note`
   đã là kênh chuyển note (halt đang dùng, `loop.py:1291`).

   Sau `completion = await self._complete(...)` thành công:
   ```
   nếu completion không có tool_calls và state.answer vẫn rỗng:
       nếu state.tool_rounds > 0 và state.empty_nudges < MAX_EMPTY_NUDGES:
           state.empty_nudges += 1
           state.note = EMPTY_AFTER_TOOLS_NOTE
           log warning (model, finish_reason, tool_rounds)
           continue
   ```
   Trần thời gian đã có: `_round_spent(started)` — dùng nó như hai recovery kia để một
   nudge không đẩy round qua `ROUND_TIMEOUT_MULTIPLE`.

4. `_run`, tại `loop.py:831`: khi `state.answer` vẫn rỗng → `_ended(state,
   TurnStatus.INCOMPLETE, EMPTY_ANSWER)` thay vì `COMPLETE`.

   Narration **không** bị ném đi: `state.text` vẫn mang nó, nên `turns.py:_finish` vẫn dựng
   message. Người đọc thấy phần dẫn cộng câu nói rõ lượt này dừng vì tuyến mô hình không
   trả về câu trả lời — thay vì thấy phần dẫn được trình bày như câu trả lời hoàn chỉnh.

### `apps/web/src/lib/alpha-desk/copy.ts`

Thêm vào `TERMINAL_REASONS`:
- `empty_answer` — câu nói thẳng: tuyến mô hình không trả về nội dung nào, và mời thử lại.
- `deadline_expired` — reason backend ghi thật (`loop.py:183`) nhưng bảng chưa có, đang rơi
  vào `UNNAMED_REASON`. Cùng file, cùng một lần sửa.

## Validation

Test mới tại `apps/api/tests/test_agent_loop.py`:

1. Completion rỗng ở round đầu → `status is INCOMPLETE`, `terminal_reason == "empty_answer"`,
   và `len(client.requests) == 1` — **không** có lời gọi thứ hai.
2. Tool chạy round 0, round 1 rỗng → đúng 3 lời gọi (round0, round1, retry), request thứ ba
   mang `EMPTY_AFTER_TOOLS_NOTE`, và nếu retry trả lời được thì `COMPLETE` với answer đó.
3. Cùng ca trên nhưng retry cũng rỗng → `INCOMPLETE`/`empty_answer`, `empty_nudges == 1`,
   và **mọi `tool_calls` của round 0 vẫn còn trong outcome** — bằng chứng đã trả tiền không
   bị ném đi.
4. Tool chạy, model chỉ viết câu dẫn rồi round sau không có reply, retry cũng không →
   `INCOMPLETE`/`empty_answer`, **và `outcome.text` vẫn chứa câu dẫn** (narration không bị
   ném đi, `turns.py` vẫn dựng được message).
5. Viết lại `test_a_turn_that_never_speaks_publishes_no_delta`: giữ khẳng định
   `publisher.deltas == []` (không có delta là đúng — không có chữ nào), đổi khẳng định về
   status/reason.

Test tại `apps/web`: `copy.ts` có câu cho `empty_answer` và `deadline_expired`, và
`terminalSentence` không trả `UNNAMED_REASON` cho hai reason đó.

Cổng: `make test`, rồi 4 cổng web.

## Risk / rollback

- **Risk**: một nudge thêm một lời gọi trả tiền trên Turn xấu. Bounded: trần 1, chỉ ở ca đã
  có tool chạy, và `_round_spent` chặn ở trần thời gian round. Ca không có bằng chứng —
  chính là ca rẻ nhất để nudge — cố tình **không** được nudge.
- **Risk**: `empty_answer` làm `incomplete_rate` trong ops nhảy lên. Đó là *đo được thay vì
  vô hình*, không phải hồi quy. Ghi rõ khi báo cáo để không ai đọc sai con số.
- **Rollback**: một commit, ba hằng và một nhánh. `git revert`.

## Đã làm (2026-08-22)

`loop.py`: `EMPTY_ANSWER`, `MAX_EMPTY_NUDGES = 1`, `EMPTY_AFTER_TOOLS_NOTE`,
`_TurnState.empty_nudges`, `AgentLoop._nudge_empty`, nhánh terminal ở `_run`, và một đoạn
docstring module nói rõ nudge này **là** ngoại lệ có chủ đích của "No apology call".
`copy.ts`: câu cho `empty_answer` và `deadline_expired`.

Một lỗi đã tự bắt trong lúc làm, ghi lại vì nó là cái bẫy của chỗ này: `_nudge_empty` chạy
**bên trong** `_call`, trước `_append_text`, nên `state.answer` còn là trạng thái của các
round *trước*. Bản đầu chỉ đọc `state.answer` → nudge nổ trên mọi Turn bình thường. Điều
kiện đúng phải gồm `completion.text`.

`test_the_round_ceiling_is_the_constant_and_the_last_call_answers` phải sửa: script cũ toàn
`wants()` không có prose nào, nên dưới luật mới nó là một Turn `empty_answer` thật. Cho nó
một câu trả lời thật — chủ đề của test là cái trần, không phải sự rỗng.

Cổng: `tests/test_agent_loop.py` 65/65 pass; toàn bộ `apps/api` 2267 passed, 1 failed
(`test_deployment_topology.py::test_the_topology_is_written_down_where_the_next_reader_will_look`
— **có trước** thay đổi này: `docs/streaming-topology.md` bị xoá ở `b352417`, test canh nó
còn nguyên). 4 cổng web pass.
