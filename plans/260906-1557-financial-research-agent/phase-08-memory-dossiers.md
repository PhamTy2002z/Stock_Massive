---
phase: 8
title: "Memory, consent và dossier doanh nghiệp"
status: pending
priority: P1
effort: "6–10 engineer-days"
dependencies: [7]
---

# Phase 8: Memory, consent và dossier doanh nghiệp

Context: [Plan](./plan.md) · [Architecture](./architecture-and-contracts.md) · [Validation](./validation-strategy.md)

## Overview

Agent giữ bối cảnh hữu ích giữa các lượt, cho user xem/sửa/xóa và chủ động đối chiếu nghiên cứu cũ. Memory không trở thành nguồn sự thật thị trường.

## Requirements

- Owner/tenant scope từ auth context, không từ tool args hoặc model.
- Per-purpose opt-in cho giả định tài chính user tự khai; không suy diễn risk profile.
- Thread/dossier theo symbols và research history; rerun theo yêu cầu, không global watchlist/scheduler.
- Retention/expiry/delete/consent withdrawal propagate to recall and UI.

## Architecture

Existing session_search/remember_fact/recall_facts + persistence → consent-bound user context.
Thread dossier references immutable old memos and new Turn comparisons. Public finance observations remain evidence with freshness; memory facts never receive privileged instruction role.

## Related Code Files

| Action | Files |
|---|---|
| Modify existing memory tools | `apps/api/src/agent/tools/memory.py`, `apps/api/src/alpha/models.py` only if fields absent |
| Modify API/persistence | `apps/api/src/agent/persistence.py`, `router.py`, `schemas.py` |
| Modify UI/types | `apps/web/src/lib/alpha-desk/api.ts`, `types.ts`, existing thread/shell surfaces |
| Create proposed | Small memory consent/manage panel under existing shell; owner-scoped CRUD surface after contract approval |
| Tests | `apps/api/tests/test_agent_memory_tools.py`, thread lifecycle/authorization tests, web panel tests |

## Implementation Steps

1. Inventory current memory row fields, retrieval filters, delete paths and thread metadata; extend existing tables rather than duplicate.
2. Define purposes and consent record version/time; only explicit horizon/intent/declared cost-basis context if product/legal accepted, never model-inferred personalization.
3. Provide per-item view/edit/delete and withdrawal as easy as opt-in; use explicit user data, provenance and expiry (roadmap suggests ~90 days, lock exact value with owner).
4. Server enforces permission/consent/expiry on write and recall. Untrusted web cannot trigger durable write or change scope; preserve existing guardrails.
5. Recall banner in memo states assumptions used and update action; new source conflicting with recalled fact wins and conflict is explained.
6. Dossier keyed by thread symbols/entity mapping; user rerun creates new Turn comparing evidence/claims/assumptions across versions and cutoffs.
7. Define deletion cascade: memory index/cache, dossier links and queued work; audit minimal consent metadata retention reviewed separately from content deletion.
8. Test private data never enters shared evidence cache, telemetry or another owner recall, including after delete/withdraw and cached results.

## Test Matrix

| Case | Outcome |
|---|---|
| User never opted in | No cross-session assumption write |
| Expired fact | Excluded or reconfirmed, never silently current |
| Withdraw/delete with cached recall | Next read cannot return deleted data |
| Source injection asks to remember policy | Denied; memory cannot alter policy |
| New report contradicts remembered number | Evidence wins; memory is not market provenance |
| Rerun dossier | New Turn, old memo unchanged, no scheduled job |

## Success Criteria

- [ ] Isolation/delete/withdraw/expiry/injection suite passes.
- [ ] Consent UI and audit event match write/recall behavior.
- [ ] Recall improves selected task success without unsupported-claim regression on paired replay.
- [ ] Dossier rerun reports meaningful changes with old/new source versions.

## Validation

Memory tool suite + API authorization/CRUD tests + browser consent flow; affected golden cross-turn cases. Migration only after backup/restore plan and user-approved data contract.

## Risk Assessment

Consent/legal boundary unresolved → keep assumptions thread-local and cross-session feature off; phase not marked complete. Memory convenience must not turn research support into personalized advice.

## Rollback / handoff

Disable cross-session recall/write; retain user management/delete access. Rollback cannot reinstate revoked consent. Handoff consent schema, delete/retention matrix, scope tests and recall evaluation.
