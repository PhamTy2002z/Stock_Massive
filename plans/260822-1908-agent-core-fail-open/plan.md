---
title: "Harness core theo kiến trúc Hermes: fail-open, số học tới được, đo được"
status: in-progress
created: 2026-08-22
branch: develop
blocks: [260823-1744-investment-intelligence-eval-replay-harness]
---

# Harness core theo kiến trúc Hermes

Nguồn bài học: `docs/hermes/` (12 report, 3.876 dòng, khảo sát `NousResearch/hermes-agent`
MIT tại HEAD `f43eabe`). Toàn bộ "kế hoạch port" trong bộ research đó viết **trước**
`1e7b936` và phần lớn đã landed — plan này chỉ nhận những gì còn hở, xác minh lại trên
code hiện tại.

## Nguyên tắc chỉ đạo, lấy từ Hermes

1. **Fail-OPEN.** Được phép chậm, rẻ, ồn — không được phép làm trắng màn hình.
2. **Sai hợp đồng thì nudge có trần, không kết thúc Turn** — nhưng chỉ khi có bằng chứng
   để cứu, vì `loop.py:34` đã chọn "No apology call" và lựa chọn đó đúng.
3. **Một concern một chủ.** Ngưỡng và trần phải là **một phép tính**, không phải hai con
   số cạnh nhau (đúng khuôn `loop.py:136-143` đã làm với round/output_tokens).
4. **Đo cái đau nhất trước khi đóng nó.** Một tín hiệu ops không bao giờ nổ là một tín
   hiệu đã chết.

## Outcome

Không Turn nào kết thúc `complete` mà không có gì để đọc. Rung `block`/`halt` của thang
guardrail tới được bằng số học 4 round. Một exception lẻ trong một round không xoá kết
quả của các call còn lại. Ops đếm được cả ba lớp lỗi này — và tín hiệu `unknown_tool`
đang chết được sống lại.

## Constraints

- Không thêm dependency. Không migration (mọi tín hiệu Phase 4 đọc được từ cột đã có).
- Giữ `contract.py::_assert_no_formatting_hole`, `render()` chỉ nhận 5 giá trị typed.
- Giữ "mọi exit path qua `_finish`/`_finish_bare`" (`turns.py`) và "tổng các delta =
  answer đã lưu" (`loop.py:1356`).
- `MAX_TOOL_ROUNDS` × `DEFAULT_MAX_OUTPUT_TOKENS` là một phép tính với `TURN_OUTPUT_TOTAL`.
  Không đổi round budget trong plan này.
- Không đổi tool schema, không đổi 5 tool.

## Non-goals

Không dựng lại grounding/validator/citation đã xoá. Không subagent, không MoA, không skill
tự sinh, không MCP mới. Không đụng Analysis lane / Signal Registry / bảng giá. `apps/web`
chỉ nhận đúng hai dòng copy ở Phase 1 và Phase 4.

## Phase

| # | Phase | Vùng | Chặn bởi |
|---|---|---|---|
| 1 | [Turn rỗng không được là Turn xong](phase-01-empty-answer.md) ✅ | `agent/loop.py`, `apps/web/.../copy.ts` | — |
| 2 | [Thang guardrail tới được bằng 4 round](phase-02-ladder-arithmetic.md) ✅ | `agent/guardrails.py` | — |
| 3 | [Một call chết không kéo cả round](phase-03-executor-fail-open.md) ✅ | `agent/executor.py` | — |
| 4 | [Ops thấy được ba lớp lỗi vừa đóng](phase-04-ops-visibility.md) ✅ | `agent/ops.py`, `agent/loop.py`, `alpha/models.py`, `agent/executor.py` | 1, 2, 3 |
| 5 | [Dạy model gọi tool song song](phase-05-parallel-tool-guidance.md) ✅ | `agent/prompt/sections.py` | — (`1974c24` đã xoá eval gate) |

Cả 5 phase đã implement. Plan vẫn `in-progress` chứ không `complete`: code review nền của
Phase 2–3 (2026-08-22) tìm ra một defect chặn trong `loop.py`/`executor.py` mà chính Phase 3
tuyên bố là "chỉ cần kiểm, không cần viết" — xem câu hỏi 7 dưới đây. Đóng plan là quyết định
sau khi xử lý nó, không phải sau khi năm phase có dấu ✅.

Phase 1–3 độc lập, chạy được song song về mặt file. Phase 4 cần cả ba xong để có cái mà
đếm. Phase 5 bump `PROMPT_VERSION`; eval gate đã bị xoá ở `1974c24` nên không còn cổng chặn,
nhưng phép đo trước/sau vẫn phải làm bằng tay — đổi prompt mà không có số là đổi hành vi mù.

## Acceptance criteria

1. `make test` tại `apps/api` pass; `pnpm type-check` `lint` `test` `build` tại `apps/web` pass.
2. Không có đường nào để một Turn `complete` mà `agent_message` không có hàng — chứng minh
   bằng test, không bằng lời.
3. Rung `block` và `halt` chạm được bằng chuỗi call bình thường qua các round, **không** cần
   fan-out 8 call trong một round.
4. `ops_snapshot` trả về số khác 0 cho `unknown_tool_calls` khi có call tool không tồn tại.
5. `test_a_turn_that_never_speaks_publishes_no_delta` được viết lại — nó đang đóng đinh
   đúng hành vi Phase 1 sửa.

## Câu hỏi chưa giải quyết

1. ~~Bar eval chưa chốt~~ — `1974c24` xoá cả Eval Battery/Gate/Report. Không còn cổng, cũng
   không còn harness đo sẵn: Phase 5 phải tự đo trước/sau.
2. ~~`deadline_expired` không có câu trong `copy.ts`~~ — đã sửa kèm Phase 1.
3. `test_deployment_topology.py` canh `docs/streaming-topology.md`, file đã bị xoá ở
   `b352417`. Đang đỏ từ trước plan này. Phục hồi tài liệu hay bỏ test? Là quyết định về
   tài liệu, không thuộc phạm vi plan này.
4. `ModelRefusal` với `refusal` rỗng vẫn đi đường `COMPLETE` + `model_refusal` và không dựng
   message (`loop.py`, `turns.py:439`). Cùng họ với lớp lỗi Phase 1 nhưng hẹp hơn nhiều.
   Chưa đóng — cố ý, để không nới phạm vi.
5. `rounds_exhausted` vẫn không persist ở đâu, nên ops không đếm được. Cần một cột, tức một
   migration mà plan này đã tuyên bố không làm.
6. Ba lý do lỗi call không tới được `agent_tool_call.error` nên `tool_call_errors` mù với
   chúng: `dispatch_failed` (cố ý), `external_budget_exhausted` (đặt trên `TurnToolCall`
   trong `loop.py::_round`, không qua `executor._record`) và `halted_turn` của các call sau
   halt. Số đo Phase 5 cho thấy `external_budget_exhausted` nổ ở 10/48 lượt, nên đây là tín
   hiệu đang mất thật. Nhóm `"timeout"` cũng chưa có đường ghi. Chi tiết ở phase 4.
7. Code review Phase 2–3 (nền, 2026-08-22) để lại ba việc chưa xử: external budget bị trừ
   *trước* dispatch nên một call bị trần fan-out cắt vẫn mất tiền; `CancelledError` từ con
   trong segment song song bị biến thành `dispatch_failed`; và halt-at-6 cho một route
   external chết chặn luôn cả tool memory phần còn lại của Turn. Không thuộc Phase 4/5.
