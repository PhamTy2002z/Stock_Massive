---
phase: 4
title: "Effective Cache Measurement And Safe Configuration"
status: complete
priority: P1
effort: "5h"
dependencies: [3]
---

# Phase 4: Effective Cache Measurement And Safe Configuration

## Context Links

- `plans/reports/measurement-260823-1238-prompt-cache-on-cliproxy.md`
- `apps/api/src/core/llm/transport.py::_usage`
- `apps/api/src/core/llm/probe.py::_prompt_cache_breakpoint`
- `apps/api/src/core/config.py::Settings.llm_prompt_cache_control_enabled`

## Overview

Đo automatic cache trên session model và prefix C2 thật. Không đảo quyết định
đã kiểm chứng: explicit `cache_control` giữ tắt vì route OpenAI-shaped đã cache tự động.

## Requirements

- Functional: probe nhiều call cùng stable prefix, tail khác nhau; báo fresh,
  cached read, cache write, hit count, aggregate ratio và model.
- Functional: dùng actual core/domain prefix đủ dài, không pad prompt để chạm ngưỡng.
- Functional: mọi paid probe cần ceiling explicit và owner ledger hợp lệ.
- Functional: Golden output cộng đủ cached counters, không gọi fresh input là total.
- Non-functional: không gate từng call; proxy hit best-effort và đã đo 3/8.
- Non-functional: không đổi default/config flag; zero aggregate hit là stop/replan.

## Architecture

Một script vận hành dùng public LLM client và C2 prefix builder, chạy bounded
sample dưới cache-control off. Nó không boot-block API và không thay Capability
Probe generic. Output JSON/Markdown chỉ mang model, prompt identity hash và usage
counters. Cache economics đọc aggregate từ `llm_call_usage`, không assumptions.

## Related Code Files

- Create: `/Users/typham/Dev/Stock_Massive/apps/api/scripts/probe_prompt_cache.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/Makefile`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/golden/run.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_llm_transport.py`
- Create: `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_probe_prompt_cache.py`
- Create: `/Users/typham/Dev/Stock_Massive/plans/260829-2141-c2-context-and-cache/reports/phase-04-cache-measurement.md`

## Implementation Steps

1. Freeze old measurement as comparison; do not reinterpret per-call miss as failure.
2. Viết probe aggregation tests với mixed hit/miss usage và all-zero usage.
3. Implement bounded script + `make probe-prompt-cache`; redact route/key.
4. Chạy session model với core-only và core+domain-body prefix, cache-control off.
5. Đối chiếu ledger counters với probe total; discrepancy là blocker.
6. Ghi report: ratio, prefix size, hit distribution, cost; không sửa flag.

## Success Criteria

- [x] Probe cần ceiling và không thể chạy paid sample không giới hạn.
- [x] Aggregate cached read > 0 cho **cả hai** prefix family; per-call miss hợp lệ.
- [x] Ledger và probe agree fresh/cached/write totals — khớp tuyệt đối.
- [x] Body prefix không làm fresh tokens tăng ngoài body cost đo được.
- [x] `llm_prompt_cache_control_enabled` vẫn `False`; wire không có Anthropic marker.
- [x] Report đủ dữ kiện để so lại khi route/model đổi.

## Evidence

`reports/phase-04-260830-cache-measurement.md` + `plans/reports/probe-260830-prompt-cache.md`.
**54,2%** cached read tổng (24.320 token, 5/8 hit, `cache_write = 0`); ledger khớp
chính xác. Độc lập: ledger golden cho **50,1%** trên 78 lượt Turn thật.

Tính chất phase 03 được dựng để có, giờ là số đo: `core` và `core+domain-body`
đọc lại **đúng cùng 4.864 token** — biên cache rơi bên trong core, trước body, nên
thêm body không dịch một byte nào của khối đã cache.

`tests/test_llm_transport.py` **không sửa**: `_usage` đã tách cached/cache-write
từ trước và hai test đã giữ luật đó.

**Phát hiện vận hành ngoài phạm vi C2:** boot Capability Probe tiêu 242.538/250.000
µUSD hạn mức ngày qua 85 lượt gọi — ~17 lần restart là hết. Probe giờ kiểm hạn mức
trước khi gửi gì.

## Risk Assessment

**Cache aggregate = 0:** có thể route/model đổi hoặc load-balancer quá phân tán.
Response: giữ flag off, C2 vẫn Target, replan provider/config; không pad prompt.

**Probe tự làm nóng và overstate:** signal là traffic thật thấp xa probe ratio.
Response: gate cache bằng cả probe và Golden ledger aggregate; report cả hai.

## Security Considerations

Không log base URL có credential, API key, user content hoặc raw prompt. Identity
chỉ hash; probe owner riêng để không trộn cost với user Turn.

## Rollback

Xoá script/Make target/report. Runtime config và transport không thay đổi.
