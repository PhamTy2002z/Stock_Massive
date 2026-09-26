---
phase: 10
title: "Scale, sandbox và delegation có điều kiện"
status: pending
priority: P2
effort: "Estimate riêng khi trigger mở; chưa nằm trong 69–104 ngày"
dependencies: [9]
---

# Phase 10: Scale, sandbox và delegation có điều kiện

Context: [Plan](./plan.md) · [Architecture](./architecture-and-contracts.md) · [Validation](./validation-strategy.md)

## Overview

Kế hoạch toàn diện cho các năng lực roadmap P10–P12, giữ trigger riêng. Hoàn tất W1–W9 không tự động bật cả ba; trạng thái pending nghĩa chưa triển khai, không phải debt bắt buộc.

## Requirements

- Mỗi capability có đo baseline, owner, amendment/gate, rollback và phiên bản plan thực thi riêng trước code.
- Không mở shell trên host, unrestricted MCP, multi-agent mặc định hoặc side effects chỉ vì có thư viện.
- Runtime guard/budget/cancel/rights invariants phải truyền xuống mọi nhánh.

## Architecture and triggers

| Branch | Trigger đề xuất | Work / outcome |
|---|---|---|
| Scale / roadmap P10 | >1k MAU hoặc đo được per-domain/admission capacity bị chạm; lock numeric threshold khi mở | Shared public evidence cache/coalescing, fleet quota, admission queue, SSE fanout, tenant envelopes |
| Sandbox / roadmap P11 | Frozen quantitative family fail vì phép tính ngoài W5; controlled benchmark cho uplift | Ephemeral isolated execution on accepted evidence, no network by default, bounded resources, derived provenance |
| Delegation/MCP / roadmap P12 | Workload độc lập single-agent không đạt; multi-agent controlled comparison vượt overhead | Durable child sessions, capability allowlist, inherited deny, global tree budgets/cancel; MCP schema/auth boundary |

Branches độc lập sau W9; không tạo dependency cycle. Mỗi branch cần chọn ngưỡng uplift/latency/cost trước thử nghiệm. Nếu không đủ evidence mở, ghi not-opened hoặc rejected-with-measurement, không gọi capability completed.

## Related Code Files

| Branch | Existing owners to extend after approval |
|---|---|
| Scale | `apps/api/src/core/web_lane.py`, `agent/persistence.py`, `turns.py`, `events.py`, deployment compose |
| Sandbox | `agent/registry.py`, `executor.py`, `evidence/contracts.py`, `core/config.py`; new isolated runtime adapter only after runtime choice |
| Delegation | `agent/loop.py`, `messages.py`, `turns.py`, `persistence.py`, registry/executor; new child-session capability contract |
| Tests | Existing fault-injection/loop/permission/budget suites extended by branch-specific load/adversarial tests |

## Implementation Steps

1. Capture trigger measurement and owning workload, select branch; draft detailed phase plan with exact integration inventory and approved outcome.
2. Scale: distinguish public shareable evidence from private docs/memos and restricted vendor datasets; cache key includes rights/basis/version/cutoff. Request coalescing never shares personalized answer.
3. Scale: load test 10× measured pilot burst, durable queue admission, honest progress, cancellation and fleet domain ceilings. Lock target concurrency and p95 before run.
4. Sandbox: choose runtime by measured isolation/ops needs; immutable evidence inputs, no host mounts/secrets/network; timeout/memory/process/output cap; terminate whole process tree.
5. Sandbox: write execution as CALCULATION lineage, preserve code/evaluator version per permitted retention; stdout untrusted. Compare against W5/current reasoning on same corpus.
6. Delegation: child created durably before dispatch, fresh scoped context, parent-deny inherited, no extra secrets/memory/write or recursive delegation by default.
7. Delegation: enforce token/cost/deadline/depth/concurrency across whole tree; parent cancel settles children, restart reconciles orphan intents.
8. MCP: explicit server/capability allowlist and schema/auth/version validation; annotations are not authorization; no generic marketplace.
9. Side effects only if separately requested later: consent, idempotency/reconciliation and capability-specific threat model. Order execution remains outside this product plan.
10. Stage release behind independent kill switch; close only branch with actual gate evidence, leave others conditional.

## Test Matrix and gates

| Branch | Mandatory gate |
|---|---|
| Scale | 10× agreed burst, 0 lost/duplicated Turns, 0 tenant leak, no expired/cutoff-wrong evidence, domain ceilings held |
| Sandbox | 0 escape/forbidden egress/secret access in adversarial suite; deterministic lineage; paired eval uplift above predeclared bar |
| Delegation | 0 orphan children, 0 permission escalation, 0 tree-budget escape; paired quality uplift exceeds overhead |
| MCP | Unknown capability/version/auth denied; injection cannot change permissions; disconnect settles safely |

## Success Criteria

- [ ] Selected branch has measurable trigger and accepted detailed sub-plan.
- [ ] Safety/reliability gates pass and quality/load uplift measured on intended workload.
- [ ] Unopened branches remain disabled and not presented as existing capability.
- [ ] Rollback rehearsed without losing parent Turn or audit trail.

## Validation

Do not invent commands for unbuilt sandbox/load systems. When branch opens, add an owned runnable command and predeclared numeric gate to the existing verification surface before runtime implementation.

## Risk Assessment

Architectural expansion without benefit → reject branch with measurements and keep single-agent design. Global cache rights mistakes or child inheritance bugs → fail closed and disable branch; never relax trust to achieve uplift.

## Rollback / handoff

Disable branch admission, drain/cancel tracked work, reconcile terminal states; restore existing single-agent path. No broad process kill or destructive database cleanup. Report selected/not-opened/rejected status per capability.
