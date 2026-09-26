---
title: "Financial Research Agent — kế hoạch toàn hệ thống"
description: "Hoàn thiện research chứng khoán Việt Nam từ nguồn dữ liệu tới câu trả lời kiểm chứng và Signal Desk."
status: pending
priority: P1
effort: "69–104 engineer-days cho phase 1–9; phase 10 conditional"
issue: null
branch: develop
tags: [backend, frontend, api, financial-research, planning]
blockedBy: [260905-0001-signal-desk-visual-harness]
blocks: []
created: 2026-09-06
---

# Financial Research Agent — kế hoạch toàn hệ thống

## Overview

Kế hoạch đề xuất, **chỉ planning; chưa cho phép implementation**. Giữ Hermes/OpenCode làm nguồn học runtime và Flint làm compiler. Tái sử dụng loop, capability, permission, context, persistence và golden hiện có. Xây đầy đủ năng lực tìm tin, đọc BCTC/tài liệu, nghiên cứu thông tin ngách, phân tích phản ứng thị trường, kiểm chứng, visualization, memory và vận hành.

Mặc định lập kế hoạch: internal pilot → customer release; ưu tiên BCTC + sự kiện doanh nghiệp; có thể khảo sát nguồn thương mại nhưng chưa chọn vendor/budget. Ba giả định này chưa được user xác nhận.

Authority hiện tại vẫn là `CLAUDE.md` và `docs/roadmap.md`. Thứ tự dưới đây là work package đề xuất; phase 1 phải duyệt [thay đổi phạm vi](./decisions-and-dependencies.md) trước khi mở công việc vượt roadmap. Không coi bản plan này là amendment đã chấp nhận.

## Goals

| # | Goal | Priority |
|---|------|----------|
| 1 | Trả lời đúng và đủ nhu cầu, dẫn được nguồn/kỳ/đơn vị, biết nói thiếu gì | P1 |
| 2 | Đọc được nguồn gốc và dữ liệu có cấu trúc qua cùng tool plane | P1 |
| 3 | Memo, bảng, chart, dossier cùng dùng evidence có version và quyền truy cập | P1 |
| 4 | Có release gate, privacy, giám sát và rollback trên workload thật | P1 |

## Phases

| # | Phase | Status |
|---|-------|--------|
| 1 | [Baseline, quyết định và handoff](./phase-01-start.md) | Pending |
| 2 | [Evidence contracts và tính đúng của verifier](./phase-02-evidence-contracts.md) | Pending |
| 3 | [Tìm và đọc tài liệu/BCTC](./phase-03-document-research.md) | Pending |
| 4 | [Nguồn dữ liệu structured và quyền sử dụng](./phase-04-structured-data.md) | Pending |
| 5 | [Ngữ nghĩa tài chính và phép tính truy nguồn](./phase-05-financial-verification.md) | Pending |
| 6 | [Nghiên cứu thích ứng theo nhu cầu](./phase-06-adaptive-research.md) | Pending |
| 7 | [Evidence Desk và Signal Desk](./phase-07-evidence-desk-visuals.md) | Pending |
| 8 | [Memory, consent và dossier](./phase-08-memory-dossiers.md) | Pending |
| 9 | [Đánh giá, vận hành và phát hành](./phase-09-release-operations.md) | Pending |
| 10 | [Scale, sandbox, delegation có điều kiện](./phase-10-conditional-capabilities.md) | Pending |

Phase 1→9 tuần tự. Phase 10 chỉ mở từng capability khi trigger đạt; không phải điều kiện phải xây hết để customer release. Effort là khoảng công kỹ thuật, không phải lịch cam kết; không gồm chờ quyền dữ liệu, procurement và human review. Phân bổ ở từng phase.

## Dependencies

Plan Signal Desk hiện tại sở hữu graduation của capability đã làm. Plan này nhận handoff của nó; phase 1 được đối chiếu baseline trước khi handoff xong, nhưng phase 2 trở đi bị chặn. Không bắt plan cũ chờ tính năng tương lai, không tạo dependency cycle. Những plan lịch sử chỉ còn trong index hoặc link roadmap không được coi là file thực thi đang tồn tại.

Đọc [kiến trúc và hợp đồng](./architecture-and-contracts.md), [gate và scenario matrix](./validation-strategy.md), [quyết định/dependency](./decisions-and-dependencies.md), [research đầu vào](../reports/research-260906-harness-and-financial-research-direction.md).

## Success Criteria

- [ ] Mỗi nhóm nhu cầu có case, ground truth và denominator; refusal đúng tách khỏi task success.
- [ ] Claim/observation/derived value truy được tài liệu hoặc provider, entity, kỳ, đơn vị và version.
- [ ] Verifier fail/omission không có nhãn verified; không temporal leakage hoặc rò dữ liệu người khác.
- [ ] Một câu hỏi xuyên suốt trả memo + evidence + chart phù hợp và replay được sau refresh.
- [ ] Customer release chỉ dùng nguồn có quyền phù hợp; không bật Vnstock internal bằng cách đổi profile.
- [ ] Gate cơ học, eval nhiều trial, human finance review và rollback đều có artifact; không dòng BLIND được gọi là pass.

## Review and validation

Planning mode: hard, dùng research/scout đã có và planner counsel bổ sung. Plan chưa được user phê duyệt. Review và kiểm tra tính nhất quán được ghi tại [planning review](./reports/planning-review.md). Checklist chưa đánh dấu vì implementation chưa bắt đầu.

## Unresolved questions

User cần chốt trước execution: rollout internal/SaaS; job đầu tiên; quyền/budget nguồn; ceiling eval; owner ground truth; chấp nhận các amendment tại decision register. Những câu hỏi này không cản việc hoàn thành bản kế hoạch.

<!-- slug: financial-research-agent -->
