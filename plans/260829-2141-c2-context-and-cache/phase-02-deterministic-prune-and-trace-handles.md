---
phase: 2
title: "Deterministic Prune And Trace Handles"
status: complete
priority: P1
effort: "8h"
dependencies: [1]
---

# Phase 2: Deterministic Prune And Trace Handles

## Context Links

- `apps/api/src/agent/messages.py::_collapsed_result`
- `apps/api/src/agent/messages.py::_reductions`
- `apps/api/src/agent/loop.py::_shown_calls`
- `apps/api/src/agent/persistence.py::tool_result`

## Overview

Giảm text model đọc mà không sửa trace gốc: duplicate search result biến mất
trong context projection; result cũ thành handle có arguments và source URLs.

## Requirements

- Functional: dedup `web_search.results` theo `dedup_key`, scope toàn Turn,
  thứ tự first-seen; không dedup `fetch_url` theo URL vì `looking_for` có thể khác.
- Functional: `TurnToolCall.result_text` vẫn đúng full result đã trace; model đọc
  `context_text` projection nội bộ, field này không vào SSE/public wire.
- Functional: collapsed handle giữ `tool_call_id`, tool name, arguments và tối đa
  năm canonical source URLs; latest user Turn không bị drop.
- Functional: prune deterministic chạy trước summary và trước overflow retry.
- Non-functional: scanner vẫn chạy đúng một lần trên full result; untrusted wrapper
  vẫn bao đúng projection gửi model.
- Non-functional: không thêm retrieval tool; trace hiện có là audit path.

## Architecture

Executor tiếp tục normalize, scan và persist full payload. Khi result về loop,
một pure projection tạo `context_text` từ structured payload với set
`state.context_sources` riêng; không reuse `shown_sources` của UI. TurnBudget và
`shown_result()` dùng projection, persistence dùng full result. `_collapsed_result`
trở thành explicit trace handle nhưng tool message vẫn giữ protocol call id.

## Related Code Files

- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/messages.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/loop.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_loop.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_persistence_paths.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_untrusted_results.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/golden/test_context_replay.py`

## Implementation Steps

1. Viết regression tests: duplicate across two search calls, same-round parallel,
   different `looking_for`, full trace unchanged, collapsed URLs retained.
2. Thêm internal `context_text` với fallback `result_text` cho legacy/test callers.
3. Dùng structured payload để tạo model projection; không parse provider JSON lần hai.
4. Thêm `context_sources` per-Turn; xử lý results theo call order ổn định.
5. Chuyển TurnBudget/token estimate sang projection thực model đọc.
6. Làm explicit trace handle ở rung collapse; giữ URL gốc để UI/citation click đúng.
7. Replay baseline và ghi savings từng layer; chưa thay gate ở phase này.

## Success Criteria

- [x] Duplicate URL/snippet chỉ xuất hiện một lần trong model context của Turn.
- [x] Hai fetch cùng URL nhưng `looking_for` khác giữ cả hai excerpt.
- [x] Full persisted trace byte-identical trước/sau projection.
- [x] Scanner invocation count không tăng; scan verdict không vào model text.
- [x] Mọi source URL trước prune còn ở full result đang active hoặc trace handle
      — đo trên **text model đọc**, không trên projection hiển thị: **536/536**.
- [x] Existing 4-rung, summary và overflow tests xanh (`make test` 1732 pass).

## Amendment — rung ageing chủ động, và ngưỡng của nó

Overview của phase này viết "result cũ thành handle" nhưng Requirements không
định nghĩa "cũ". Dedup một mình đo được **−1,1%**, nên "cũ" phải có định nghĩa.

Chốt 2026-08-29 sau khi đo sáu phương án trên chính corpus: `SELECTION_CALLS = 1`
(kết quả `web_search` thành handle sau đúng lượt đã dùng nó để chọn trang —
prompt §5 đã tự nói snippet không phải bằng chứng) và `RESULT_CALLS = 2` (trang
đã fetch giữ nguyên văn hai lượt). Kết quả **−13,85%**, mất **0** URL.

**Tuổi đếm từ lượt đọc đầu tiên, không từ vòng.** Bản đầu tính sai và biến kết
quả search thành handle ngay ở lượt lẽ ra phải đọc nó — không phải prune mà là
không tìm kiếm. `test_a_result_is_never_a_handle_on_the_call_that_first_reads_it`
giữ luật này.

## Evidence

`reports/phase-02-260829-prune-and-handles.md`. 797.722 → **687.269** token
(**−13,85%**), median/Turn 36.043 → 31.878, `tool_results` −31,9%. URL retention
536/536, intent retention 20/20. Replay byte-identical hai lượt.

**Gate ≥20% của plan không đạt được** — trần cứng là −17,8% vì `system_core`
chiếm 53,3% context và prune không chạm được nó. Phase 05 đặt lại bar từ phân bố.

## Risk Assessment

**Dedup evidence khác nhau cùng URL:** signal là two-query test mất excerpt cần
thiết. Response: chỉ dedup search item duplicate; không dedup fetched passage.

**Budget đo sai projection:** signal là provider input vượt reserved estimate.
Response: `TurnBudget.add` và `shown_result` đọc cùng `context_text`, không copy
logic hoặc giữ hai phép normalize.

## Security Considerations

Projection không bypass `wrap_result`; full content vẫn scan trước projection.
Không dùng raw trace content làm system text hoặc public payload.

## Rollback

Bỏ `context_text`/`context_sources`, trả TurnBudget về `result_text`; trace rows
không cần đổi vì chưa từng bị mutate.
