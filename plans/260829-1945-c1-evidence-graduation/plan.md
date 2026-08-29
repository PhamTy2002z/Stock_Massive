---
title: "C1 Evidence Graduation"
description: "Đóng C1 bằng grader số có witness, kiểm thử injection đầu-cuối và một graduation contract không còn mâu thuẫn."
status: pending
priority: P1
effort: "19h"
branch: "feat/study-canvas-runtime"
tags: [harness, measurement, security, backend, critical]
blockedBy: []
blocks: []
relatedTo:
  - 260829-1349-c1-search-and-evidence
  - 260829-1435-c5-domain-pack
created: 2026-08-29
---

# Plan: C1 Evidence Graduation

## Overview

Tiếp nối plan C1 đã thi công xong 8/8 nhưng chưa tốt nghiệp. Plan này sửa đúng
ba lỗ bằng chứng còn lại: contract `read_depth` mâu thuẫn, grader không hiểu số
suy diễn, và threat scan chưa được chứng minh qua đường persist/reopen.

## Delivery Contract

- **Outcome:** C1 đổi `Target` → `Current` bằng evidence tái lập; nếu calibration
  không đủ chính xác, dừng và replan thay vì nới grader.
- **Constraints:** không sửa prompt/tool budget; không model call trả phí mặc
  định; giữ prompt C5 `3.0.0`; không rewrite lịch sử report.
- **Non-goals:** C2 cache/prune · C4 LLM judge/CI · C5 store-first graduation ·
  rail warning UI · tenant/entitlement.
- **Acceptance:** một read-depth authority; derived claim có witness kiểm được;
  fabricated mutation vẫn fail; injection verdict sống qua reopen; C1 chỉ đổi
  nhãn khi mọi gate đạt.

## Cross-Plan Dependencies

| Relationship | Plan/roadmap phase | Contract |
|---|---|---|
| Successor | `260829-1349-c1-search-and-evidence` | Reuse 3 artifacts + C1 runtime; không sửa lại 8 phase đã đóng |
| Baseline | `260829-1435-c5-domain-pack` | Regrade trên prompt `3.0.0`; không quy delta C5 cho C1 |
| Unblocks when graduated | C2 | Context/prune mới được đo bằng citation gate hợp lệ |
| Still blocked after this plan | C4, S1 | C4 còn cần C5 graduation; S1 còn cần C4 |

Không có plan unfinished trên đĩa cần `blockedBy` hai chiều. Composer Attachments
và Price Basis đã đóng; plan này không chạm surface riêng của chúng.

## Phases

| # | Phase | Status | Dependency |
|---|---|---|---|
| 01 | [Freeze contract and plan boundaries](./phase-01-freeze-contract-and-plan-boundaries.md) | Pending | — |
| 02 | [Evidence witness grader](./phase-02-evidence-witness-grader.md) | Pending | 01 |
| 03 | [Adversarial scan persistence](./phase-03-adversarial-scan-persistence.md) | Pending | 01 |
| 04 | [Regrade and graduate C1](./phase-04-regrade-and-graduate-c1.md) | Pending | 02, 03 |

## Execution Strategy

Phases 02 và 03 độc lập về file sau Phase 01, nhưng mặc định chạy tuần tự vì
worktree đang có thay đổi chưa commit của nhiều session. Không dùng parallel
worktree cho tới khi prerequisite C1/C5 được commit hoặc cô lập an toàn.

## Success Criteria

- [ ] `read_depth` dùng đúng một gate: ≥16/20 case đạt `min_pages_read`; metric
      phẳng `fetch_url >= 2` chỉ diagnostic.
- [ ] Grader giải thích mỗi số được phủ bằng raw evidence hoặc witness tree hữu hạn.
- [ ] Calibration giữ số thật/suy diễn hợp lệ và vẫn bắt claim không có evidence.
- [ ] Threat scan `high|low|unknown` đi executor → wire → persisted assistant
      message → reopened thread; scan text không vào model transcript.
- [ ] Ba artifact cũ regrade deterministic bằng cùng code; không cần network/DB/model.
- [ ] C1 chỉ thành `Current` khi gate đạt; C5 vẫn giữ trạng thái riêng.
- [ ] Focused tests + full API test/lint xanh; web gates chỉ bắt buộc nếu wire shape đổi.

## Unresolved Questions

None. Phase 01 đo derivation depth thật rồi đóng cap; không đoán trước.

<!-- slug: c1-evidence-graduation -->
