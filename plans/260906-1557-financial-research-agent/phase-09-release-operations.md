---
phase: 9
title: "Đánh giá, vận hành và phát hành"
status: pending
priority: P1
effort: "8–12 engineer-days"
dependencies: [8]
---

# Phase 9: Đánh giá, vận hành và phát hành

Context: [Plan](./plan.md) · [Architecture](./architecture-and-contracts.md) · [Validation](./validation-strategy.md)

## Overview

Hợp nhất quality/reliability/privacy/rights thành release gate có artifact và rollout thực. Instrumentation cần thiết vẫn được thêm trong từng phase, không đợi phase này mới quan sát.

## Requirements

- Một golden release workflow; all mandatory dimensions measured, no skipped dimension treated as pass.
- Metrics theo successful task, per-family coverage, extraction/verifier failures, source freshness và cost.
- Raw user/private content không vào trace mặc định; TTL/redaction/access controls.
- Customer release có nguồn hợp lệ, backup/restore, rollout và rollback đã thử.

## Architecture

Turn → model/tool/pass/evidence/claim/coverage trace → aggregate metrics → existing golden regression + human finance audit.
Existing flag endpoint → reviewed triage → confirmed failure becomes frozen corpus case. Không cần SaaS observability vendor mới nếu existing traces đủ.

## Related Code Files

| Action | Files |
|---|---|
| Modify eval | `apps/api/golden/release.json`, `graders.py`, `release.py`, `gate.py`, `thresholds.json`, `README.md` only owning changes |
| Modify telemetry owner | `apps/api/src/agent/loop.py`, `turns.py`, `persistence.py`, `flag_router.py` |
| Modify deployment/config | `apps/api/src/core/config.py`, `docker-compose.yml`, `docker-compose.prod.yml`; discover existing ops docs before edits |
| Tests | Golden suites, fault-injection, source security, visual artifacts, web E2E |
| Create planning/runtime artifacts | Release manifest, finance audit sample, restore/rollback drill report in approved report locations |

## Implementation Steps

1. Consolidate emitted typed cause/owner fields; correlate Turn/model attempt/tool/source/parser/version/claim without storing chain-of-thought.
2. Record per-family denominators: requested requirements, answered requirements, verified claims, omissions, correct refusals, unsupported facts. Keep precision, usefulness and refusal separately visible.
3. Freeze corpus and thresholds before candidate runs; include independent holdout finance cases. Source tape replay isolates model variance; live canaries measure source availability and freshness separately.
4. Run candidate ≥3 trials as W1-approved configuration; no incomplete run can pass. Human reviewer adjudicates material finance facts and disagreeing automated judgments.
5. Gate malformed tool calls, unit/time/semantic false verification, injection/leakage, rights denial, cancellation/restart and replay consistency.
6. Production triage: user flag→owner→confirmed/duplicate/not-bug reason→sanitized regression case; sample periodic finance audit even without user flags.
7. Set source-health alerts and per-domain quotas; measure capacity with documented pilot concurrency. Use actual expected load; scale-out only when W10 trigger opens.
8. Backup before schema changes; restore to isolated environment; verify row/attachment/evidence/version relationships and prior reader compatibility.
9. Rollout: internal cohort → invited beta with entitled data → wider release after stable observation window (proposed 7 days and >=50 reviewed tasks; insufficient volume means extend, not waive).
10. Exercise kill switches independently for document/OCR/provider/calculation/adaptive planner/visual/memory. User-facing degraded state must preserve honest partial answer and typed terminal settlement.
11. Update smallest owning product/setup/ops docs against shipped code only; close completed phases with artifact links and no stale capability statements.

## Success Criteria

- [ ] Existing hard gates pass, no mandatory BLIND/skip; new per-family thresholds frozen before run.
- [ ] Human-reviewed material accuracy and task fulfillment pass W1 acceptance with denominator/confidence interval.
- [ ] Source rights/freshness and private data isolation pass on live deployment.
- [ ] Backup restore and capability rollback drills pass; no orphaned work or double settlement.
- [ ] Customer beta observation window/task count achieved or release remains pending.

## Validation

Use [validation strategy](./validation-strategy.md) for exact existing commands. Full API/web suite, build and fault tests; paid release only with ceiling. Migration dry-run + isolated restore if migrations exist. Never run destructive recovery on production as a test.

## Risk Assessment

Judge self-evaluation overstates success → independent human labels and holdout, record disagreement. Source evolves after release → canary/quota/kill switch; frozen replay alone cannot detect it. Low beta volume → extend observation, not invent statistically strong accuracy.

## Rollback / handoff

Versioned release manifest ties commit/model/prompt/policy/parser/provider/evaluator/corpus. Revert rollout flags or application version, preserve compatibility readers and data. Operational ownership and incident escalation named before customer release.
