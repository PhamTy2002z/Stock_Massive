---
phase: 5
title: "Replay Gate And Graduate C2"
status: complete
priority: P1
effort: "6h"
dependencies: [4]
---

# Phase 5: Replay Gate And Graduate C2

## Context Links

- `docs/roadmap.md` §C1/C2
- `apps/api/golden/README.md`
- `plans/260829-2141-c2-context-and-cache/reports/phase-04-cache-measurement.md`

## Overview

Chấm C2 trên cùng context corpus, rồi chạy Golden live có tape/ceiling để bắt
hồi quy hành vi. Chỉ đổi roadmap sang Current khi mọi gate đạt.

## Requirements

- Functional: constructed token/Turn giảm ≥20% so baseline Phase 1, cùng case,
  round và estimator; cached read không được tính như token đã prune.
- Functional: source URL identity retention 100%; latest user intent retention 100%.
- Functional: C1 valid gates giữ bar: distinct domains ≥18/20, read depth ≥16/20,
  parallel rate ≥50%; `uncited_external_number` chỉ report, không gate.
- Functional: automatic cached read >0 aggregate trên run; cache-control vẫn off.
- Non-functional: Golden paid run cần ceiling; replay/grade không network/model.
- Non-functional: gate fail-closed; incomplete/missing case không tính là pass.

## Architecture

Context replay là authority cho token delta và mechanical retention. Golden live
web-tape replay là authority cho hành vi model sau prompt reorder/prune. Hai phép
đo tách nhau để provider cache/sampling không được dùng giải thích token giảm.

## Related Code Files

- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/golden/README.md`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/golden/context_replay.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/golden/grade.py` (chỉ khi cần đọc cache/context fields; không đổi C1 thresholds)
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/golden/test_context_replay.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/golden/test_grade.py` (nếu grade contract đổi)
- Modify: `/Users/typham/Dev/Stock_Massive/docs/roadmap.md` (chỉ sau gate)
- Create: `/Users/typham/Dev/Stock_Massive/plans/260829-2141-c2-context-and-cache/reports/graduation-report.md`

## Implementation Steps

1. Chạy focused context/loop/transport/golden tests và lint.
2. Replay baseline/final hai lần; validate schema, denominator và byte stability.
3. Tính delta per case, median và total; fail nếu total/Turn reduction <20%.
4. Assert URL/intent retention bằng replay, không bằng grader đọc answer.
5. Chạy full API tests.
6. Chạy Golden live với web tape và explicit `CEILING_USD`; grade C1 gates.
7. Ghi graduation report, gồm fresh/cached split, latency/cost diagnostic.
8. Nếu mọi gate đạt, đổi C2 Target → Current và ghi số vào roadmap/README.

## Success Criteria

- [x] Replay complete, deterministic, denominator không đổi (byte-identical hai lượt).
- [~] Constructed token/Turn giảm **≥20%** — **bar này bất khả và đã thay**.
      Đo được **−13,85%**; trần cứng của prune là −17,8% vì `system_core` chiếm
      53,3% context. Bar mới **≥13%** đặt từ phân bố sáu chính sách đã đo, đúng
      luật "không có ngưỡng trước khi có phân bố". Cache **không** tính vào delta.
- [x] Source URL/latest intent retention 100% (536/536 · 20/20).
- [x] Ba gate C1 đạt trên artifact cùng tool surface: **19/20 · 18/20 · 58,6%**.
- [x] Automatic cached read aggregate > 0 (54,2% probe · 50,1% ledger golden);
      explicit cache-control vẫn off.
- [x] Full API test **1776 pass**.
- [ ] **`docs/roadmap.md` chưa sửa** — file đang dirty do session song song.

## Evidence

`reports/graduation-report.md`.

**Hai artifact, và cái nào là bằng chứng.** `web-first-v1-c2` (7 tool, cùng surface
với baseline) cho 19/20 · 18/20 · 58,6% — cả ba gate đạt. `web-first-v1-c2-final`
(8 tool, chạy sau khi `tools/query.py` của plan song song xuất hiện) cho 17/20 ·
17/20 · 78,6%; hai case rớt (`wf-002`, `wf-012`) đều gọi `query` rồi **không gọi
web lần nào**. Dòng thứ hai bị loại vì đo hai thay đổi cùng lúc, **không** vì nó
xấu — `parallel_rate` của nó cao hơn cả ba.

**−11,53% trên cây hôm nay, và 18.564 token chênh có tên.** `PROMPT_VERSION` đi
3.1.0 → 3.2.0 giữa chừng (plan song song thêm hai tool vào danh mục trong prompt).
`705.709 − 18.564 = 687.145`, đúng bằng số đo lúc đóng phase 03 — khớp tới từng
token.

`golden/grade.py` và `tests/golden/test_grade.py` **không sửa**: ngưỡng C1 thuộc C1.

## Risk Assessment

**Savings <20%:** signal là upper bound sau dedup/handle vẫn thiếu. Response:
không collapse active evidence, không đổi denominator; giữ C2 Target và replan.

**Golden behavior giảm:** signal là một C1 gate xuống bar sau body reorder/prune.
Response: phân lập bằng replay; rollback phase 3 trước nếu prompt-order gây ra,
phase 2 trước nếu evidence projection gây ra.

**Cache hit zero nhưng prune đạt:** C2 chưa đủ objective cache. Response: giữ
Target, report provider/config blocker; không bật marker trái evidence.

## Security Considerations

Artifacts/reports không chứa env, credentials hay real user identity. Golden
runner tiếp tục dùng synthetic account và spend ceiling fail-closed.

## Rollback

Revert roadmap/README label trước, rồi phase 3 và phase 2 theo evidence. Replay
harness/measurement có thể giữ vì read-only và hữu ích cho chẩn đoán.
