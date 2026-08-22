---
phase: 3
title: "Một call chết không kéo cả round"
status: complete
---

# Phase 3 — Một call chết không kéo cả round

## Hai lớp lỗi đang mở

### 3a — `gather` không `return_exceptions`

`executor.py:156`:
```python
completed = await asyncio.gather(*(self._dispatch(call) for call in segment))
```

`_dispatch` bọc `_parse_arguments` (bắt `ValueError`) và `_invoke` (bắt `Exception`), nhưng
**ngoài mọi try** còn: `self.lookup(call.name)`, `self.availability(call.name)`, và cả ba
đường `await self._record(...)`. `_record` tự bắt exception của writer, nhưng chính nó có
thể raise trước đó không.

Một exception ở những chỗ đó: `gather` huỷ toàn bộ sibling đang chạy → `executor.run` raise →
`_round` chỉ bắt `TimeoutError` (`loop.py:1226`) → thoát ra `turns.py:417`
`except Exception` → `_finish_bare(..., "turn_failed")`.

**Mất sạch kết quả round đã thu**, và reason là `turn_failed` — cái tên nói không được gì.
Trái hẳn nguyên tắc `executor.py:20`: *"Every call produces exactly one result … there is no
path here that drops one."* Đường đó có, chỉ là không nằm trong `_dispatch`.

### 3b — không có trần fan-out

`loop.py` đếm `MAX_EXTERNAL_TOOL_CALLS = 6` cho `web_search`/`fetch_url`, và
`assert_distinct_ids` chỉ kiểm id khác nhau. `session_search`, `recall_facts`,
`remember_fact` **không bị đếm gì**. Một round mang 40 call → 40 read DB đồng thời trong một
`gather`, chỉ bị chặn bởi `TOOL_TIMEOUT_SECONDS = 30` cho **cả round**.

Và nó là chỗ rung `block`/`halt` bị lách: trong một round, `before_call` của cả batch quyết
định trước khi `after_call` nào chạy, nên fan-out là đúng cách để đi qua ladder.

## Thay đổi

### `agent/executor.py`

1. `gather(..., return_exceptions=True)`. Với mỗi phần tử trả về là `BaseException`, dựng
   `ToolResult` mang `error="dispatch_failed"`, `dispatched=False`, text nói rõ call nào và
   lỗi gì. Cùng khuôn `_skipped` đang có. Log `warning`.

   Segment tuần tự cũng phải chịu cùng luật: `[await self._dispatch(call) for call in segment]`
   hiện để exception bay ra. Bọc từng call.

2. Hằng mới `DISPATCH_FAILED = "dispatch_failed"`, export cùng nhóm với `BLOCKED_CALL`,
   `HALTED_TURN`. Một tên riêng vì thuốc riêng: đây là lỗi của **module này**, không phải của
   tool và không phải của route.

3. Trần fan-out. Đặt ở `executor.py` chứ không ở `loop.py`: nó là tính chất của một **batch**,
   và executor là chủ của batch.
   - `MAX_CALLS_PER_ROUND` — chọn theo phép tính, không theo cảm giác: `MAX_TOOL_ROUNDS = 4`
     và `MAX_EXTERNAL_TOOL_CALLS = 6` nghĩa là một Turn hợp lý không cần quá 6 call trong một
     round. Đặt **8**, để chừa chỗ cho một round trộn external với memory mà vẫn chặn được
     fan-out bệnh lý.
   - Call vượt trần: **không dispatch**, trả result mang `error="round_fanout_exceeded"` và
     một câu nói rõ đã bỏ bao nhiêu call và vì sao. Không drop, không raise — đúng luật
     "mỗi call một result".
   - Trần áp **sau** `plan_segments` theo thứ tự model phát ra, nên call đầu được chạy và
     call đuôi bị từ chối: model đọc lại được batch của nó và thấy chỗ bị cắt.

### `agent/loop.py`

`_round` cần biết trần này để `turn_budget.add` vẫn thấy result của call bị từ chối —
đường `if not record.dispatched and record.result_text` (`loop.py:1265`) đã làm đúng việc đó
cho `external_budget_exhausted`, nên chỉ cần result đi qua cùng đường. Kiểm tra, không phải
viết thêm.

## Validation

Test tại `apps/api/tests/test_agent_tool_executor.py`:
1. `lookup` raise cho một call trong batch 3 call → 3 result, hai cái kia **vẫn OK**, cái
   raise mang `error="dispatch_failed"`, `dispatched=False`.
2. Cùng ca trên ở segment tuần tự.
3. Batch 12 call → 8 chạy, 4 trả `round_fanout_exceeded`, tổng vẫn 12 result, thứ tự giữ
   nguyên thứ tự model phát.
4. Trần fan-out không phá test `plan_segments` đang có.

Test tại `apps/api/tests/test_agent_loop.py`:
5. Round mà executor có một call chết → Turn **không** `turn_failed`; kết quả các call còn
   lại nằm trong `outcome.tool_calls` và Turn đi tiếp.

Cổng: `make test`.

## Risk / rollback

- **Risk**: `MAX_CALLS_PER_ROUND = 8` cắt một batch hợp lệ. Đo được: Phase 4 đếm
  `round_fanout_exceeded`. Nếu nó nổ trên traffic lành thì nâng số, và lúc đó có số để nâng
  theo — hiện tại không có.
- **Risk**: `return_exceptions=True` che một bug thật thành một result. Chống bằng log
  `warning` và bằng việc `dispatch_failed` có tên riêng, đếm riêng ở Phase 4. Một bug che mà
  đếm được tốt hơn một bug giết cả round.
- **Rollback**: `git revert`. Không đụng schema, không đụng contract.

## Đã làm (2026-08-22)

`executor.py`: `asyncio.gather(..., return_exceptions=True)` cho segment song song, `_attempt`
bọc từng call của segment tuần tự (chỗ này nằm ngoài gather nên phải viết sàn ra), `_dispatch_failed`
dựng `ToolResult` mang hằng mới `DISPATCH_FAILED` + `dispatched=False` + log `warning`, và
`_over_ceiling` cho trần fan-out `MAX_CALLS_PER_ROUND = 8` với hằng `ROUND_FANOUT_EXCEEDED`.
Trần lấy theo thứ tự model phát (`calls[:MAX_CALLS_PER_ROUND]`) nên đầu batch chạy, đuôi bị từ
chối — `plan_segments` không đổi một dòng. Docstring module nhận thêm hai đoạn: "every call
produces exactly one result" giờ kể cả lỗi của **chính module này**, và một đoạn riêng cho trần
round.

`_dispatch_failed` **không** ghi trace: chính lời gọi trace là một trong những thứ có thể rơi
vào đây, nên nó chỉ log. Đây là chỗ duy nhất lệch khỏi "mọi call attempted đều có một trace entry".

`loop.py`: **không đổi gì**, đúng như plan đoán. Đã kiểm: result của call bị trần từ chối đi qua
`outcome.results` nên vẫn vào `turn_budget.add`; vòng thứ hai trên `planned`
(`if not record.dispatched and record.result_text`) không đếm trùng, vì `planned` giữ bản record
gốc còn `state.calls` mới là chỗ bị `replace`.

Đã đo, không phải suy luận: `asyncio.wait_for` bọc `gather(return_exceptions=True)` vẫn nổ
`TimeoutError` khi hết hạn và gather **không** trả kết quả một phần — đường `TOOL_TIMEOUT` của
`_round` còn nguyên.

Test mới: `test_agent_tool_executor.py` thêm bốn (`lookup` raise trong batch song song 3 call →
hai call kia vẫn OK; cùng ca ở segment tuần tự, và barrier sau lỗi vẫn chạy; batch 12 call → 8
chạy + 4 `round_fanout_exceeded`, đủ 12 result, thứ tự nguyên; batch đúng bằng trần thì chạy
trọn). `test_agent_loop.py` thêm
`test_a_call_the_harness_cannot_dispatch_does_not_end_the_turn` — Turn `COMPLETE`,
`terminal_reason is None`, không còn `turn_failed`. Test này phải `monkeypatch`
`src.agent.loop.ToolExecutor` để tiêm `lookup` lỗi: `lookup` nằm ngoài mọi try của `_dispatch`
nên **không có đường in-band nào** làm nó raise — đó chính là lý do lớp lỗi này sống lâu.

Cổng: toàn bộ `apps/api` 2275 passed, 1 failed — `test_deployment_topology.py::test_the_topology_is_written_down_where_the_next_reader_will_look`, fail có sẵn từ `b352417` (xoá `docs/streaming-topology.md`), không liên quan.
