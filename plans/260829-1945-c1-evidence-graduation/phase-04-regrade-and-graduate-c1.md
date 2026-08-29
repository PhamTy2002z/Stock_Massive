---
phase: 4
title: "Regrade and graduate C1"
status: done
priority: P1
effort: "3h"
dependencies: [3]  # 02 dừng có chủ đích — xem phase-02
---

# Phase 4: Regrade and graduate C1

## Context Links

- `apps/api/golden/artifacts/web-first-v1-baseline.json`
- `apps/api/golden/artifacts/web-first-v1-after-03-04.json`
- `apps/api/golden/artifacts/web-first-v1-final.json`
- `docs/roadmap.md` §3 C1, C2; §6 dependencies

## Overview

Tái chấm miễn phí ba artifact bằng cùng grader, chạy quality gates, rồi đổi C1
thành `Current` chỉ khi contract đã đóng và mọi gate thật sự đạt.

## Requirements

- Functional: same grader revision on all artifacts; artifact schema cũ vẫn đọc được.
- Functional: report direct vs derived vs unsupported counts, read-depth,
  domains, parallel rate, scan distribution, latency and cost.
- Functional: default không chạy `golden-run`; paid run chỉ khi artifact không
  thể trả lời một gate và user cấp ceiling tường minh.
- Functional: C5 status không đổi; không thêm store-first corpus trong plan này.
- Non-functional: docs update nhỏ nhất, links/claims verified against artifacts/tests.

## Architecture

Graduation decision là fail-closed:

```text
phase 02 numeric calibration green
             +
phase 03 persistence/security green
             +
final artifact: domains >=18/20
                read-depth >=16/20 per-case
                parallel rounds >=50%
                valid numeric-claim verdicts
             ↓
       C1 Target → Current
```

Metric phẳng `fetch_url >= 2` vẫn báo cáo để thấy drift, nhưng không phủ định
case-specific gate đã chốt. Không dùng số từ prompt 2.10.0 để quy delta cho code
chạy prompt 3.0.0.

## Related Code Files

- Create: `/Users/typham/Dev/Stock_Massive/plans/260829-1945-c1-evidence-graduation/reports/graduation-report.md`.
- Modify: `/Users/typham/Dev/Stock_Massive/docs/roadmap.md` — C1 label/evidence and dependency wording only.
- Modify: `/Users/typham/Dev/Stock_Massive/CLAUDE.md` — close amendment, record current behavior.
- Modify: `/Users/typham/Dev/Stock_Massive/plans/260829-1349-c1-search-and-evidence/plan.md` — successor result link only.
- Modify: this plan and phase files — status/evidence.

## Implementation Steps

1. Run focused tests for numeric evaluator and scan persistence.
2. Regrade all three artifacts twice; compare serialized reports byte-for-byte.
3. Build graduation table with real denominators and prompt-version confound note.
4. Run `make test-one` focused, then full `make test` and `make lint` in `apps/api`.
5. If any public wire field changed conditionally, run web type-check/lint/tests;
   otherwise record why web gates are not applicable.
6. Write plan-scoped graduation report; verify every link and number.
7. If all gates pass, update roadmap C1 to `Current`, close amendment and plan.
8. If any gate fails, keep C1 `Target`, mark exact blocker, stop before C2 plan.

## Todo

- [ ] Three artifacts regraded with one grader revision.
- [ ] Two identical runs produce identical reports.
- [ ] Graduation table uses actual denominators.
- [ ] Full API gates green.
- [ ] C1/C5 attribution boundary explicit.
- [ ] Roadmap label matches evidence.

## Success Criteria

- [ ] Numeric calibration and security persistence gates pass.
- [ ] Final artifact meets domains ≥18/20, per-case read-depth ≥16/20,
      parallel-rate ≥50%; unsupported findings are evidence-backed.
- [ ] No paid call without explicit `CEILING_USD` authorization.
- [ ] C1 `Current` unlocks C2 planning; C4/S1 remain gated by their other deps.
- [ ] Whole-plan consistency sweep finds zero stale gate wording.

## Risk Assessment

**Regrade changes historical distribution.** Signal: direct/derived counts move.
Response: expected only where witness classification changed; explain every case,
never compare outputs from different grader revisions without regrading both.

**Gate still fails.** Signal: valid unsupported claims remain or mutation
calibration fails. Response: keep C1 `Target`; do not lower threshold or open C2.
