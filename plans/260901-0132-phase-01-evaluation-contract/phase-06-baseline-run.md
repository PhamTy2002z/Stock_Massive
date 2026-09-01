---
phase: 6
title: "Record run, curate ngày, baseline nhiều trial"
status: partial
priority: P1
dependencies: [5]
approved: "product owner chốt 2026-09-01: baseline 3 trial, ceiling $9 + judge $2"
---

# Phase 6: Record run, curate ngày, baseline nhiều trial

## Context

- Preflight §2: **không tồn tại artifact hậu-teardown**. Mọi tuyên bố "grader
  đọc field có thật" chỉ hợp lệ sau phase này.
- Named assumption A1: Tavily không trả publication time, nên ngày phải curate
  từ tape sau khi record, không bịa trước.
- `golden/README.md` §The runner runs on the host — env host khác env container.

## Requirements

- Một record run trọn corpus release, `TRIALS=1`, ghi tape.
- Curate `evidence_dates` vào `release.json` từ chính tape đã ghi (đọc ngày
  trong nội dung trang), chỉ cho family cần temporal.
- Điền `ground_truth.values` của `material_claim_accuracy` từ nguồn primary
  trong tape.
- Baseline `TRIALS=3` chạy replay tape, mỗi dimension có tỷ lệ pass và Wilson CI.
- Report vào `plans/reports/`: số đo từng dimension, dimension nào đỏ và **ai
  sở hữu** (phần lớn hard dimension đỏ thuộc Phase 6 evidence engine của
  roadmap, không phải bug của Phase 1).
- Threshold soft chỉ được khoá **sau** khi nhìn distribution, và ghi vào
  `thresholds.json` kèm số đã đọc.

## Steps

```bash
set -a && . ../../.env && set +a
export LLM_BASE_URL="http://127.0.0.1:8317/v1"
export DATABASE_URL="postgresql://postgres:postgres@<LAN-IP>:5432/stockmassive"
make golden-release CEILING_USD=<owner chốt> TRIALS=1   # record
make golden-release CEILING_USD=<owner chốt> TRIALS=3 GOLDEN_ARGS="--replay"
```

## Risk

Baseline đầu tiên nhiều khả năng **đỏ** ở `material_claim`, `multi_source_label`
và `temporal_validity`: runtime chưa có claim ledger, chưa có luật đa nguồn,
chưa có source policy — đó là công việc Phase 6 của roadmap. Đỏ ở đây là số đo,
không phải lỗi thi công của Phase 1.

## Rollback

Artifact và tape là file cục bộ; xoá là xong. Không có state nào rời khỏi thư
mục `golden/artifacts/` ngoài các row của tài khoản `golden-runner@`.

## Kết quả 2026-09-01

Record + baseline 3 trial đã chạy: `plans/reports/phase-01-260901-release-baseline.md`.
Chi $3,47/$9, 120/120 Turn terminal, 0 tape miss.

Còn lại, và cả hai đều là việc của Phase 6 roadmap chứ không của harness:

1. `ground_truth.values` cho bốn case `material_claim_accuracy`.
2. Publication time thành field runtime trích được — đo được là 0/981 source có
   `published_at`, nên `temporal_validity` đứng BLIND.

Threshold soft vẫn chưa khoá; số quan sát nằm ở `golden/thresholds.json` dưới
`observed`.
