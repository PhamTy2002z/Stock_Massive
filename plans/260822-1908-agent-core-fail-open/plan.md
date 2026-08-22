---
title: "Harness core theo kiến trúc Hermes: fail-open, số học tới được, đo được"
status: in-progress
created: 2026-08-22
branch: develop
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
| 1 | [Turn rỗng không được là Turn xong](phase-01-empty-answer.md) | `agent/loop.py`, `apps/web/.../copy.ts` | — |
| 2 | [Thang guardrail tới được bằng 4 round](phase-02-ladder-arithmetic.md) | `agent/guardrails.py` | — |
| 3 | [Một call chết không kéo cả round](phase-03-executor-fail-open.md) | `agent/executor.py`, `agent/loop.py` | — |
| 4 | [Ops thấy được ba lớp lỗi vừa đóng](phase-04-ops-visibility.md) | `agent/ops.py`, `agent/loop.py` | 1, 2, 3 |
| 5 | [Dạy model gọi tool song song](phase-05-parallel-tool-guidance.md) | `agent/prompt/sections.py` | quyết định bar eval |

Phase 1–3 độc lập, chạy được song song về mặt file. Phase 4 cần cả ba xong để có cái mà
đếm. Phase 5 bump `PROMPT_VERSION` nên **chạm eval gate đang treo** trong `CLAUDE.md`.

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

1. Bar eval cho trợ lý tổng quát chưa chốt (`CLAUDE.md` § Eval gate). Phase 5 bị chặn ở đó,
   không phải ở code.
2. `deadline_expired` là reason backend ghi thật nhưng `copy.ts` không có câu cho nó → rơi
   vào `UNNAMED_REASON`. Sửa kèm Phase 1 hay tách? Plan này gộp vào Phase 1 vì cùng một file.
