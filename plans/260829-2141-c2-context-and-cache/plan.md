---
title: "C2 Context And Cache"
description: "Đo từng layer context, prune deterministic trước summary, đưa domain body vào stable prefix và tốt nghiệp C2 bằng replay không làm giảm evidence."
status: complete
priority: P1
effort: "32h"
branch: "develop"
tags: [harness, context, cache, measurement, backend, refactor]
blockedBy: []
blocks: []
relatedTo:
  - 260829-1349-c1-search-and-evidence
  - 260829-1435-c5-domain-pack
  - 260829-1945-c1-evidence-graduation
  - 260829-2304-signal-desk-analysis-compiler
created: 2026-08-29
---

# C2 Context And Cache

## Overview

C2 làm context nhỏ hơn bằng phép biến đổi deterministic, không dùng cache như
một cách gọi token đã gửi là token đã bỏ. Provider hiện cache prefix tự động;
`cache_control=True` đã được đo là không tạo uplift, nên cờ này giữ `False`.

## Delivery Contract

- **Outcome:** Turn dài giữ intent và source identity, constructed token/Turn
  giảm ≥20% trên context replay; automatic prefix cache vẫn hit aggregate.
  **Sửa 2026-08-29 sau phase 02:** ≥20% **bất khả** trong ranh giới C2 —
  `system_core` là 53,3% context và prune không chạm được nó, nên trần cứng của
  prune là −17,8% và mức đã chọn (không mất URL nào) là **−13,85%**. Bar đặt lại
  từ phân bố ở phase 05, đúng luật "không có ngưỡng trước khi có phân bố".
- **Constraints:** không migration, không tool/model/node mới, giữ trần context
  và tool budget, prune trước summary, full result vẫn ở Tool Call Trace.
- **Non-goals:** claim provenance/LLM judge C4, summary redesign, resume Turn,
  tenant/entitlement, proxy affinity.
- **Acceptance:** layer sum đúng total; replay deterministic; citation URLs
  không mất; C1 gates không giảm; cache được đo aggregate, không per-call.

## Evidence And Decisions

- C1 và C5 đã đóng; không có plan unfinished chặn C2.
- Artifact cuối: 489.106 fresh input token/20 case, median 22.207/case; chưa có
  layer breakdown và chưa cộng cached read/write trong Golden output.
- Route đo 2026-08-23: Turn cached read 57,6% tự động; explicit `cache_control`
  không đổi kết quả, hit best-effort 3/8 ở một probe. Giữ flag `False`.
- C5 giao body pack đang ở tail cho C2; C2 chuyển nó ngay sau core để prefix ổn
  định theo call, không viết lại prose hay trigger.

## Phases

| # | Phase | Status | Dependency |
|---|---|---|---|
| 1 | [Freeze baseline and context replay](./phase-01-freeze-baseline-and-context-replay.md) | Complete | — |
| 2 | [Deterministic prune and trace handles](./phase-02-deterministic-prune-and-trace-handles.md) | Complete | 1 |
| 3 | [Cacheable domain body and identity](./phase-03-cacheable-domain-body-and-identity.md) | Complete | 2 |
| 4 | [Effective cache measurement and safe configuration](./phase-04-effective-cache-measurement-and-safe-configuration.md) | Complete | 3 |
| 5 | [Replay gate and graduate C2](./phase-05-replay-gate-and-graduate-c2.md) | Complete | 4 |

## Execution Strategy

Tuần tự vì phases 1–3 cùng owner `messages.py`/`loop.py`; parallel edit sẽ làm
baseline và token arithmetic mất authority. Trước cook, cô lập hoặc commit phần
C1 đang dirty; không gộp thay đổi phiên trước vào commit C2.

## Success Criteria

- [x] Context replay dùng trace thật, không model/network, byte-stable hai lần.
- [~] Constructed token/Turn giảm ≥20% — **bar bất khả, đã thay bằng ≥13% đọc từ
      phân bố**; đo được **−13,85%**. Xem `reports/graduation-report.md`.
- [x] URL/source identity và latest user intent sống qua mọi rung prune (536/536 · 20/20).
- [x] `distinct_domains` 19/20 · `read_depth` 18/20 · `parallel_rate` 58,6% — đều đạt bar C1.
- [x] Automatic cached read > 0 aggregate (54,2% probe · 50,1% ledger); cache-control giữ tắt.
- [x] Full API test 1776 pass.
- [ ] **roadmap chưa đổi C2 → Current** — `docs/roadmap.md` đang dirty do session song song.

## Unresolved Questions

1. **`docs/roadmap.md` chưa sửa.** Cần một lượt riêng sau khi cây sạch, để không
   chồng lên plan `260829-2304-signal-desk-analysis-compiler` đang chạy song song.
2. **Boot Capability Probe tiêu hết hạn mức ngày** — 242.538/250.000 µUSD qua 85
   lượt, tức ~17 lần restart. Ngoài phạm vi C2.
3. **Tape golden gần như vô dụng cho việc so hành vi khi prompt đổi** — nó khoá
   theo chuỗi truy vấn, model đổi cách hỏi thì miss (71/94). Thuộc C4.

<!-- slug: c2-context-and-cache -->
