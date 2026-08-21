---
title: "Nâng cấp Agent theo bài học Hermes"
description: "Đưa harness Alpha Desk từ fail-closed sang fail-open, sửa hố đen taxonomy route, và dựng lane hội thoại đạt bar tham chiếu — dựa trên khảo sát 349.505 dòng của nousresearch/hermes-agent"
status: in-progress
priority: P1
effort: "3-4 tuần"
tags: [agent, llm, grounding, route-resilience, presentation]
created: 2026-08-21
supersedes: [260820-2333-chat-first-answer-layer]
---

# Nâng cấp Agent theo bài học Hermes

## Overview

Chatbot hiện trả về màn hình trắng cho những câu đơn giản nhất. Đo được: **58%
Turn kết thúc `grounding_failed`**, **category B (câu hỏi hợp lệ đơn giản nhất)
0/30**, **36% Turn chết vì route**. Phiên live 2026-08-20: ba câu hỏi → hai màn
hình trắng.

Khảo sát toàn bộ `nousresearch/hermes-agent` (365 file / 349.505 dòng, phủ
UNASSIGNED = 0) cho một kết luận: **không bê khung** — Hermes là coding agent
terminal, `ADR-0011` đã từ chối lớp đó. Nhưng học một nguyên tắc (**guard
fail-OPEN**) và một cơ chế (**nudge có trần thay cho kết thúc Turn**).

Plan này **không xoá** store, Signal Registry, `core/llm`, SSE, widget registry,
hay Eval Battery. Ba thứ ta đang **hơn** Hermes và phải giữ: Eval Battery có
grader/rubric (họ không có), `turns.py` gom mọi exit qua 2 cửa (họ tự thừa nhận
không phủ hết), chống SSRF trong `web.py` (chắc hơn họ).

Nguồn: `plans/reports/hermes-synthesis-260821-0030.md` + 9 report vùng.

## Con số then chốt

| Đo | Giá trị | Nguồn |
|---|---|---|
| Mã lỗi grounding kết thúc Turn | **16 / 24** | `grounding.py` — `DEGRADABLE_GATE_CODES` chỉ có 8 |
| Turn chết `grounding_failed` | 58% (100/171) | `docs/eval/2026-08-17-1.4.0.json` |
| Category B | 0/30 (bar ≥90%) | cùng nguồn |
| Turn chết vì route | 36% (4/11) | ops snapshot 7 ngày |
| `GatewayTimeout` có log | **0** | `loop.py:739` — nhánh trần trụi |
| Nhánh 400 được phân loại | **0** | `core/llm/errors.py:294` catch-all |
| `MAX_TOOL_ROUNDS` | **4** (docstring nói 8) | `loop.py:124` vs `:21` |
| `cache_control` được set | **0** | `core/llm/*` |

## Goals

| # | Goal | Priority |
|---|------|----------|
| 1 | Không câu hỏi hợp lệ nào ra màn hình trắng | P1 |
| 2 | Mọi lỗi route được phân loại và có hành động phục hồi | P1 |
| 3 | Câu hỏi thường trả lời như bar tham chiếu: số + citation chip + timeline thật + follow-up | P1 |
| 4 | Gate còn hiệu lực đúng nơi có hậu quả tài chính: block khuyến nghị có giá | P1 |
| 5 | Một gate run Eval Battery làm baseline mới, trả món nợ eval gate | P1 |
| 6 | Ký ức xuyên phiên qua đường tool, không phá bất biến prompt typed | P2 |
| 7 | Quét pattern injection trên nội dung web | P2 |

## Non-goals

- Không bê code Hermes. Không commit nào là "copy từ Hermes".
- Không xoá `grounding.py`, Signal Registry, store, `core/llm`, SSE, widget registry.
- Không chèn free-text vào system prompt (giữ `_assert_no_formatting_hole`).
- Không subagent, không MoA, không skill tự sinh, không sandbox mới.
- Không realtime intraday.

## Phases

| # | Phase | Status |
|---|-------|--------|
| 1 | [Phase 1: Chẩn đoán trước mọi thứ](./phase-01-start.md) | **Complete** |
| 2 | [Phase 2: Grounding fail-open](./phase-02-grounding-fail-open.md) | **Complete** |
| 3 | [Phase 3: System Prompt Contract](./phase-03-system-prompt-contract.md) | **Complete** |
| 4 | [Phase 4: Độ bền tuyến LLM](./phase-04-route-resilience.md) | **Complete** |
| 5 | [Phase 5: Lane hội thoại và trình bày](./phase-05-conversation-lane-and-presentation.md) | Pending |
| 6 | [Phase 6: Ngân sách tool và thang guardrail](./phase-06-tool-budget-and-guardrail-ladder.md) | Pending |
| 7 | [Phase 7: Ký ức và quét injection](./phase-07-memory-and-injection-scan.md) | Pending |
| 8 | [Phase 8: Cổng Eval và baseline](./phase-08-eval-gate-and-baseline.md) | Pending |

Phụ thuộc: 1 → 2 → 3 → (4 ∥ 5) → 6 → 7 → 8. Phase 4 và 5 độc lập về file, chạy
song song được. Phase 8 chốt toàn bộ.

## Cổng phê duyệt bắt buộc

Ba quyết định **không** được làm lặng lẽ. Mỗi cái là một quyết định đã ghi trong
ADR/spec, phải amend chứ không trái.

| # | Quyết định | Ở đâu | Phase | Trạng thái |
|---|---|---|---|---|
| G1 | Đưa prose chống bịa vào Contract | `ADR-0015` nói thẳng *"refuses to let the Contract be an enforcement mechanism"* | 3 | **Chốt 8/21** → `ADR-0022` |
| G2 | Đảo mặc định 16 mã lỗi từ block sang degrade | `ADR-0015` + `ADR-0018` | 2 | **Chốt 4/20** → `ADR-0021` |
| G3 | Đổi `MAX_TOOL_ROUNDS` 4 → N | `docs/specs/0003` §6 | 1 | **Chốt: giữ 4, sửa docs** |

## Eval gate (bắt buộc theo CLAUDE.md)

Plan này chạm **cả bốn** surface mà `CLAUDE.md` liệt kê: System Prompt Contract,
tool schema/`tool_catalog_version`, agent loop, Recommendation Validator. Nên:

- PR của Phase 2, 3, 6 **bắt buộc** đính Eval Report (run id, điểm từng category,
  diff so baseline) — không merge vào `develop` nếu thiếu.
- Phase 1, 4 chỉ chạm `core/llm` + logging → không cần.
- Phase 5 phần UI/widget → không cần; phần Contract → cần.
- Baseline hiện tại đã lỗi thời (1.4.0, contract nay là **1.8.0** sau Phase 3).
  Phase 8 tạo baseline mới; các phase trước so với 1.4.0 và ghi rõ là so sánh
  xuyên phiên bản.
- **Nợ còn lại sau Phase 3**: Contract 1.8.0 đã vào `develop` theo quy ước commit
  thẳng (không PR) nên chưa có Eval Report đính kèm. Món nợ này gộp vào gate run
  của Phase 8; Eval Fixture **không** phải đóng băng lại (fixture chỉ phụ thuộc
  dữ liệu thị trường, không phụ thuộc `prompt_version` — `docs/agents/eval-battery.md`).

Quy trình: `docs/agents/eval-battery.md`.

## Success Criteria

- [ ] 12 câu Golden Question Set (`docs/specs/0004` §4) — không câu nào ra màn hình trắng
- [ ] Category B ≥ 90% trên gate run mới
- [ ] `grounding_failed` < 5% số Turn (tripwire mà validator tự đặt ra)
- [ ] `answer_kinds.analysis` > 0
- [ ] Mọi Turn chết vì route có log đủ để phân loại nguyên nhân
- [ ] `route_error` không còn là catch-all: mọi 400 có mã riêng
- [ ] "Tình hình chứng khoán VN hôm nay" → số + citation chip + 3 follow-up
- [ ] "Về STB thì sao" → số từ store + widget + tin từ web
- [ ] "Hey bro" → trả lời hội thoại, không tool call
- [ ] "Có nên mua STB" → Gate còn hiệu lực: đủ điều kiện, hoặc nói rõ thiếu gì
- [ ] `make test` tại `apps/api`; `pnpm type-check lint test build` tại `apps/web`
- [ ] `pnpm test:e2e` (cổng streaming) xanh
- [ ] Eval Report đính vào PR của mọi phase chạm 4 surface trên

## Rủi ro toàn plan

| Rủi ro | Tín hiệu nó xảy ra | Phản ứng đã định |
|---|---|---|
| Hạ cấp quá tay → model bịa số lọt ra | `downgraded_blocks` tăng vọt, rubric blind-score phát hiện figure sai | Đưa mã đó về nhóm block; đây là lý do Phase 8 phải chạy |
| Lane hội thoại thành cửa sau lách Gate | Câu "có nên mua" đi qua lane nhẹ | Chặn ở validator theo hình dạng block, không ở prompt (`ADR-0015`) |
| Sửa route làm hỏng `StreamAssembler` | `pnpm test:e2e` đỏ | Phase 4 tách commit theo từng nhánh lỗi |
| Không đủ quota chạy gate run | Gate run bỏ dở | Chủ sản phẩm đã xác nhận ngân sách LLM không phải rào cản |
| Docstring tiếp tục trôi khỏi code | Review bắt được | Phase 1 sửa docstring `loop.py`; thêm luật vào CLAUDE.md |

<!-- slug: agent-upgrade-hermes-lessons -->
