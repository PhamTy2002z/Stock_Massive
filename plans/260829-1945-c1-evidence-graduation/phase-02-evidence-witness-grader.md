---
phase: 2
title: "Evidence witness grader"
status: pending
priority: P1
effort: "7h"
dependencies: [1]
---

# Phase 2: Evidence witness grader

## Context Links

- `apps/api/golden/grade.py::grade_uncited_external_number`
- `apps/api/tests/golden/test_grade.py`
- `plans/reports/phase-08-260829-c1-verification.md` §4, §8

## Overview

Thay phép so bag-of-numbers bằng evaluator tạo witness hữu hạn. Mỗi số pass phải
trỏ được về raw premise trong question/store/external evidence và phép biến đổi.

## Requirements

- Functional: giữ exact match, locale normalization và rounding đang có.
- Functional: thêm unit scaling và expression tree hữu hạn với `+ - * /`.
- Functional: question numbers được dùng làm premise nhưng không tự trở thành
  external evidence; witness phải giữ provenance từng leaf.
- Functional: không branch theo case ID; cùng logic cho artifact cũ và mới.
- Non-functional: cap lấy từ Phase 01; không unbounded closure, không divide by
  zero, không tổ hợp unit vô nghĩa.
- Non-functional: finding detail ghi raw/derived, operands, operation, depth.

## Architecture

```text
answer claim ──▶ parse quantity + unit
                    │
       direct/round/unit-scale?
                    │ no
                    ▼
 bounded witness search over raw premises
 question | external | store
                    │
          witness found / unsupported
```

`golden.numeric_evidence` là module thuần: không network, DB, model, runtime
imports. `grade.py` chỉ orchestration và re-export helper cũ để giữ test contract.

## Related Code Files

- Create: `/Users/typham/Dev/Stock_Massive/apps/api/golden/numeric_evidence.py` — quantity parsing + bounded witnesses.
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/golden/grade.py` — call evaluator, expose witness detail.
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/golden/test_grade.py` — tests-first calibration + mutations.
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/golden/README.md` — exact grader contract and limits.

## Implementation Steps

1. Write failing tests for unit conversion, cross-source difference, ratio,
   question+store portfolio arithmetic, and unsupported `100%` in `wf-012`.
2. Add mutation tests: perturb valid results; mix operands from unrelated units;
   try accidental combinations from dense evidence; assert unsupported.
3. Extract existing numeric helpers into `numeric_evidence.py`; re-export from
   `grade.py` so current imports remain compatible.
4. Represent raw premises with origin and unit; normalize Vietnamese/English
   magnitude words (`triệu`, `tỷ`, `nghìn tỷ`, `%`, shares, VND).
5. Search only to measured depth, bounded operands and unit-compatible ops.
6. Return one minimal witness; deterministic tie-break by depth, origin, value.
7. Regrade all three existing artifacts and inspect every changed finding.

## Todo

- [ ] Tests red before evaluator changes.
- [ ] Existing exact/round behavior preserved.
- [ ] Valid derivations receive deterministic witness.
- [ ] Fabricated mutations remain unsupported.
- [ ] `wf-012` remains a real finding unless evidence covers `100%`.
- [ ] Grading remains pure and deterministic.

## Success Criteria

- [ ] 100% of Phase 01 verified valid derivations pass with a witness.
- [ ] 100% of calibration mutations and unit-invalid combinations fail.
- [ ] No witness exceeds the frozen depth/operand cap.
- [ ] Running grade twice yields byte-identical JSON.
- [ ] `pytest tests/golden/test_grade.py -q` passes.

## Risk Assessment

**Combinatorial false accepts.** Signal: any fabricated mutation finds a witness.
Response: tighten unit/context/cap; if still non-zero, stop and replan toward an
explicit claim-provenance contract in C4. Never raise depth to make cases green.

**Parser expansion becomes a second NLP engine.** Signal: rules need company or
case vocabulary. Response: reject the rule; grader may understand units and
arithmetic, never domain-specific prose.
