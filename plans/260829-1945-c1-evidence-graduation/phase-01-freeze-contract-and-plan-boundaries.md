---
phase: 1
title: "Freeze contract and plan boundaries"
status: done
priority: P1
effort: "4h"
dependencies: []
---

# Phase 1: Freeze contract and plan boundaries

## Context Links

- `docs/roadmap.md` §3 C1, §6 dependency graph
- `plans/260829-1349-c1-search-and-evidence/plan.md` §Kết quả nghiệm thu
- `plans/reports/phase-08-260829-c1-verification.md`
- `apps/api/golden/README.md` §The thresholds

## Overview

Chốt một graduation contract trước khi sửa grader. Ghi amendment hẹp, bảo vệ
worktree đang có nhiều owner, và phân loại lại năm finding bằng evidence thật.

## Requirements

- Functional: `read_depth` authority là ≥16/20 case đạt `expect.min_pages_read`.
- Functional: `fetch_url >= 2` phẳng ở lại report như diagnostic, không gate.
- Functional: audit từng finding hiện tại; không mặc định mọi số grader gắn cờ
  đều là false positive. `wf-012` phải giữ `100%` unsupported nếu artifact không
  có evidence cho trần room đó.
- Non-functional: không sửa historical report; thêm successor note thay vì
  viết lại kết luận đã đúng tại thời điểm chạy.
- Operational: không cook khi prerequisite C1/C5 còn trộn với thay đổi không
  liên quan trong cùng worktree.

## Architecture

Authority order cho plan này:

```text
case.expect.min_pages_read
        ↓ per-case verdict
apps/api/golden/README.md threshold (>=16/20)
        ↓ graduation decision
docs/roadmap.md label
```

Phase này mở đúng surface trong `CLAUDE.md` trước code: `apps/api/golden/*`,
`apps/api/tests/golden/*`, focused agent tests cho scan persistence, C1 sections
trong roadmap/plan. Không mở prompt, tool budget, web UI, DB schema.

## Related Code Files

- Modify: `/Users/typham/Dev/Stock_Massive/CLAUDE.md` — amendment + freeze limits.
- Modify: `/Users/typham/Dev/Stock_Massive/docs/roadmap.md` — reconcile C1 gate wording only.
- Modify: `/Users/typham/Dev/Stock_Massive/plans/260829-1349-c1-search-and-evidence/plan.md` — successor pointer; preserve history.
- Read: `/Users/typham/Dev/Stock_Massive/apps/api/golden/artifacts/web-first-v1-{baseline,after-03-04,final}.json`.
- Modify: files in this plan directory — decisions and phase status only.

## Implementation Steps

1. Re-read git status and file mtimes; identify current owner of overlapping C1/C5 files.
2. Require a commit/worktree containing both completed prerequisites. Never stash,
   reset, or absorb unrelated edits to manufacture a clean tree.
3. Regrade final artifact unchanged; record grader hash and distribution.
4. Audit every unsupported number against question, external and store evidence.
5. Classify each as direct, unit-scaled, derived, semantic constant, or truly unsupported.
6. Measure smallest witness depth needed by verified derived claims. Do not pick
   a depth from desired pass rate.
7. Amend `CLAUDE.md` and reconcile roadmap/C1 successor wording.

## Todo

- [ ] Prerequisite work isolated or committed without unrelated changes.
- [ ] Five current findings audited from artifact text.
- [ ] `wf-012` not silently waived as a “definition”.
- [ ] Read-depth authority written once and linked everywhere else.
- [ ] Amendment surface matches union of Phases 02–04.

## Success Criteria

- [ ] No plan/document calls both read-depth formulas gating.
- [ ] No C5 metric is attributed to C1.
- [ ] Numeric calibration oracle is evidence-backed, not case-ID policy.
- [ ] Scope table contains every future touched file and no speculative runtime file.

## Risk Assessment

**Prerequisite not isolatable.** Signal: required C1/C5 files remain mixed with
unrelated session work. Response: stop before code; coordinate ownership or make
an isolated worktree from a commit containing prerequisites.

**Historical report disagrees.** Signal: audit disproves “5/5 false failures”.
Response: preserve report; record corrected evidence in successor plan/roadmap.
