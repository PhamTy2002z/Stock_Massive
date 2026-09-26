---
phase: 1
title: "Baseline, quyết định và handoff"
status: pending
priority: P1
effort: "4–6 engineer-days"
dependencies: []
---

# Phase 1: Baseline, quyết định và handoff

Context: [Plan](./plan.md) · [Decision register](./decisions-and-dependencies.md) · [Validation](./validation-strategy.md)

## Overview

Khóa outcome, đo hiện trạng và quyết định mở capability trước implementation. W1 của plan này không phải roadmap Phase 1; roadmap P1 đã có golden, phải reuse.

## Requirements

- Phủ năm nhóm: BCTC/chất lượng lợi nhuận, tin/sự kiện, thông tin ngách, phản ứng thị trường, stress-test/mâu thuẫn.
- Không sửa code sản phẩm trong bước quyết định; không làm live run khi chưa có ceiling.
- Nhận graduation từ Signal Desk plan cũ; kiểm chứng working tree thay vì giả định report cũ đúng với commit mới.

## Architecture

Existing golden corpus → per-case requirements + source ground truth → baseline artifact → failure taxonomy → accepted scope. D1–D10 ở [decision register](./decisions-and-dependencies.md) là đầu vào, không tự động accepted.

## Related Code Files

| Action | Owner |
|---|---|
| Read/verify | `CLAUDE.md`, `docs/roadmap.md`, plan Signal Desk và graduation report |
| Modify khi thực hiện baseline extension | `apps/api/golden/release.json`, `graders.py`, `thresholds.json`, `README.md`, tests/golden tương ứng |
| Create trong implementation | `plans/reports/deviation-<date>-financial-research.md`, baseline report/artifact theo convention golden |
| Không tạo | Golden runner thứ hai, dashboard mới, data store mới |

## Implementation Steps

1. Ghi commit + dirty-diff fingerprint, versions model/prompt/provider, test baseline; bảo toàn user edits và không coi chúng đã merge.
2. Kiểm tra bằng fixture ba nguy cơ source: verifier rejection bị nâng, omitted claim mất denominator, retrieval time bị dùng làm historical cutoff. Không khẳng định đã tái hiện trước khi test.
3. Lấy danh sách family/threshold đang có; bổ sung case thiếu, không thay toàn corpus. Khởi đầu 20 câu phân bố 5 family × 4 case, cộng hard/adversarial và corpus cũ.
4. Ghi expected requirements, evidence version/cutoff, answerable/unanswerable, material observations, ground truth reviewer; không tạo golden answer bằng model rồi tự chấm.
5. Chạy offline grade trước, sau đó baseline 3 trial **đề xuất** với ceiling được owner cấp. Trial replay đo variance model; live canary riêng đo provider freshness/availability.
6. Đọc lỗi theo discovery/download/parse/semantics/source coverage/planning/verification/visualization; đo task fulfillment riêng refusal.
7. Duyệt D1–D10 và điều chỉnh roadmap trước implementation vượt catalog/public contract/compute; giữ ranh research/advice.
8. Đóng hoặc nhận handoff plan Signal Desk theo gate của nó; không đổi nhãn để vượt blocker. Ghi proposed/accepted/rejected từng quyết định.
9. Khóa soft thresholds từ baseline và human review; sửa gate unmeasurable trước khi mở phase 2.

## Success Criteria

- [ ] Mọi family có denominator và case thật; không có mandatory dimension BLIND.
- [ ] Một baseline artifact đầy đủ, hoặc ghi rõ chưa có live data và **phase chưa đạt**.
- [ ] Có source-grounded triage, owner quyền dữ liệu/finance reviewer, ngân sách và acceptance thresholds.
- [ ] Signal Desk handoff đạt; amendment được duyệt bằng văn bản; không còn dependency mơ hồ.

## Validation

`make -C apps/api test-one T=tests/golden/test_graders.py`; `make -C apps/api test-one T=tests/golden/test_release_corpus.py`. Paid/replay commands tại [validation strategy](./validation-strategy.md), không chạy trong lượt planning.

## Risk Assessment

Thiếu finance reviewer → ground truth không đáng tin → dừng graduation, mời reviewer. Provider không còn tái hiện tape → tách frozen baseline và live canary, không sửa expected để pass. Nếu owner không duyệt compute/source expansion, ghi family bị giới hạn và replan acceptance, không tự cắt rồi gọi comprehensive complete.

## Rollback / handoff

Giữ baseline artifact và corpus version cũ. Chỉ revert thay đổi corpus của phase khi sai schema; không xóa failure case hợp lệ. Bàn giao decision register đã duyệt + baseline hash + failure shortlist.
