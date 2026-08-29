---
title: "C1 Evidence Graduation"
description: "Đóng C1 bằng một graduation contract không còn mâu thuẫn và kiểm thử injection đầu-cuối; grader số suy diễn đo ra là bất khả nên tiêu chí citation chuyển sang C4."
status: done
priority: P1
effort: "19h"
branch: "develop"
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
| 01 | [Freeze contract and plan boundaries](./phase-01-freeze-contract-and-plan-boundaries.md) | **Done** | — |
| 02 | [Evidence witness grader](./phase-02-evidence-witness-grader.md) | **Blocked — dừng có chủ đích** | 01 |
| 03 | [Adversarial scan persistence](./phase-03-adversarial-scan-persistence.md) | **Done** | 01 |
| 04 | [Regrade and graduate C1](./phase-04-regrade-and-graduate-c1.md) | **Done** | 03 (02 dừng) |

## Execution Strategy

Phases 02 và 03 độc lập về file sau Phase 01, nhưng mặc định chạy tuần tự vì
worktree đang có thay đổi chưa commit của nhiều session. Không dùng parallel
worktree cho tới khi prerequisite C1/C5 được commit hoặc cô lập an toàn.

## Success Criteria

- [x] `read_depth` dùng đúng một gate: ≥16/20 case đạt `min_pages_read` (**18/20**);
      metric phẳng `fetch_url >= 2` (14/20) chỉ diagnostic.
- [~] **Grader witness — không đạt và không được đạt.** Đo cho thấy witness tree
      hữu hạn nhận 92,7–100% mọi giá trị ở bốn trên năm case; tiêu chí chuyển sang
      C4. Xem phase 02.
- [~] **Calibration — cùng lý do.** 39/40 mutation bịa qua được ở mọi mức siết.
- [x] Threat scan `high|low|unknown` đi executor → wire → persisted assistant
      message → reopened thread; scan text **không** vào model transcript. 11 test,
      non-vacuity chứng minh bằng mutation.
- [x] Ba artifact regrade deterministic bằng cùng code, byte-identical; 0 USD.
- [x] C1 → `Current` khi ba gate đo được đạt; **C5 giữ nguyên trạng thái**.
- [x] Focused (107) + full API test (**1690 passed**) + lint xanh; web gates
      **không áp dụng** — 0 file dưới `src/` hay `apps/web/` bị sửa.

## Kết quả — 2026-08-29 · **ĐÓNG**

**C1 tốt nghiệp `Target` → `Current`.** Ba gate đạt (`distinct_domains` 19/20 ·
`read_depth` 18/20 · `parallel_rate` 63%); lớp quét injection chứng minh đầu-cuối;
tiêu chí citation **chuyển sang C4** dưới dạng claim-provenance contract, kèm
bằng chứng nó bất khả với một grader đọc văn bản. **0 file production sửa.**

Hai concern của phase 03 đã đóng: `ADVERSARIAL_PAGE` gom về
`tests/agent_tool_world.py`; `executor._dispatch` **giữ nguyên** không bọc `try`
— `scan_for_threats` total theo hợp đồng, guard sẽ là nhánh chết. Không còn gap.

Báo cáo: [`reports/graduation-report.md`](./reports/graduation-report.md) ·
đo derivation depth: [`reports/phase-01-260829-derivation-depth.md`](./reports/phase-01-260829-derivation-depth.md).

## Unresolved Questions

1. **Claim-provenance contract có hình dạng gì** — runtime suy provenance, hay
   prompt buộc model trưng phép tính rồi grader verify. Thuộc plan của C4.
2. **`read_depth` phẳng chưa chứng minh ở n = 20** — không chặn (diagnostic), nhưng
   cache `WebLane` khiến chạy thêm lượt trong ngày không tăng n hiệu dụng.
3. **Chưa đo lớp quét trên trang thật mang injection** — test dùng payload dựng sẵn.
4. **Ai sở hữu và chấm Golden Set** — nợ cũ, corpus vẫn do C4-lite tự viết.

<!-- slug: c1-evidence-graduation -->
