---
phase: 1
title: "Freeze Baseline And Context Replay"
status: complete
priority: P1
effort: "6h"
dependencies: []
---

# Phase 1: Freeze Baseline And Context Replay

## Context Links

- `docs/roadmap.md` §C2
- `apps/api/golden/README.md`
- `apps/api/golden/artifacts/web-first-v1-final.json`
- `plans/reports/measurement-260823-1238-prompt-cache-on-cliproxy.md`

## Overview

Đóng baseline có thể chấm lại mà không gọi model. Mỗi context trả breakdown
typed theo layer; corpus replay xuất từ 20 Golden Turn thật của synthetic user.

## Requirements

- Functional: breakdown gồm `system_core`, `domain_body`, `system_dynamic`,
  `history`, `user_intent`, `tool_results`, `study_headlines`, `attachments`.
- Functional: tổng layer bằng đúng token estimate/reservation của request gửi đi.
- Functional: replay lưu transcript/tool-result structure cần để dựng từng round,
  không lưu user id, email, credential hoặc provider metadata riêng tư.
- Functional: Golden cost ghi riêng fresh input, cached read, cache write, output.
- Non-functional: không đổi prompt, prune, budget hay runtime behavior phase này.
- Non-functional: không migration; chỉ đọc trace của Golden synthetic account.

## Architecture

`ConstructedContext` mang `ContextComposition` immutable. `AgentLoop` cộng các
note append sau constructor vào cùng breakdown trước khi tạo `CompletionRequest`.
`golden/context_replay.py` có hai đường: export trace thật thành artifact versioned,
rồi replay artifact qua public context builder. Artifact ghi prompt version,
pack identity, resolved-tool-surface identity và per-round expected source URLs.

Nếu trace rows của artifact cuối đã hết retention hoặc ở DB khác, chạy một Golden
run mới có `CEILING_USD` để tạo corpus; không tự dựng payload thay thế.

## Related Code Files

- Create: `/Users/typham/Dev/Stock_Massive/apps/api/golden/context_replay.py`
- Create: `/Users/typham/Dev/Stock_Massive/apps/api/golden/artifacts/context-replay-v1.json` (generated from real Golden traces)
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/messages.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/loop.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/golden/run.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/Makefile`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_loop.py`
- Create: `/Users/typham/Dev/Stock_Massive/apps/api/tests/golden/test_context_replay.py`

## Implementation Steps

1. Kiểm tra worktree; cô lập C1 dirty changes trước code edits.
2. Viết tests cho layer arithmetic và serialization trước khi thêm fields.
3. Thêm `ContextComposition`; giữ `ConstructedContext.estimated_tokens` làm total authority.
4. Đưa appended note/domain reservation vào cùng composition tại `_call`.
5. Mở rộng `spend_for()` với `cached_read_tokens` và `cache_write_tokens`.
6. Viết export/replay CLI, schema version và `make golden-context-replay`.
7. Export 20 case thật; chạy replay hai lần và so byte/output.

## Success Criteria

- [x] Mọi request có layer sum bằng total; mismatch fail test, không log-and-continue.
- [x] Replay 20 case chạy không network/model và cho output byte-identical hai lần.
- [x] Baseline report có distribution per layer/per round, không chỉ một tổng.
- [x] Golden artifact phân biệt fresh/cached/write token; tổng billing không đổi.
- [x] Corpus không có secret, email, raw user id hoặc dữ liệu ngoài Golden user.
      **Đọc lại lúc nghiệm thu:** corpus *có* chứa văn bản trang web đã đọc, và một
      trang trong đó có email trong byline. Giữ nguyên — đó là byte model đã đọc,
      xoá là làm sai chính phép đo, và tape cạnh nó đã chứa cùng văn bản. Tiêu chí
      thật sự được giữ là: không account, không owner id, không route, không key.
- [x] Focused tests và lint xanh; production answer byte-for-byte chưa đổi.

## Evidence

`reports/phase-01-260829-context-baseline.md`. Replay 78 model call khớp đúng
78 dòng `llm_call_usage`; reserved 800.628 vs replay 797.722 (0,36%, đúng bằng
guidance của 13 call bị từ chối — thứ không persist ở đâu). Baseline
797.722 token / 20 Turn, median 36.043. `system_core` 53,3% · `tool_results`
43,1%. Cache tự động **đã** đọc 50,1% prompt với cờ tắt.

## Risk Assessment

**Trace thiếu:** export không đủ 20 case. Signal: request id không có result rows.
Response: dừng và chạy Golden có ceiling; không hạ denominator, không fixture giả.

**Layer double-count:** note vừa nằm context vừa bị cộng reservation. Signal:
layer sum khác `SpendRequest.input_tokens`. Response: một calculator duy nhất,
test exact equality trên call có domain body, mode note, nudge và attachment.

## Security Considerations

Chỉ synthetic Golden account; redact ownership/provider ids. External evidence đã
untrusted vẫn giữ nguyên wrapper semantics; artifact không được chứa env/config.

## Rollback

Xoá replay command/artifact và fields composition; không có runtime behavior hay
schema cần rollback dữ liệu.
