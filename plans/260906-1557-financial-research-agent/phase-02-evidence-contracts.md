---
phase: 2
title: "Evidence contracts và tính đúng của verifier"
status: pending
priority: P1
effort: "7–10 engineer-days"
dependencies: [1]
---

# Phase 2: Evidence contracts và tính đúng của verifier

Context: [Plan](./plan.md) · [Decision register](./decisions-and-dependencies.md) · [Validation](./validation-strategy.md)

## Overview

Đóng các đường verified giả trước khi mở thêm nguồn. Bổ sung observation identity và phiên bản bằng chứng trên contracts hiện có.

## Requirements

- Semantic support, structural validity và source confidence là điều kiện riêng; không nâng semantic rejection vì primary ID.
- Account tất cả draft material claims kể cả verifier omitted/timeout; không mất denominator.
- Phân biệt thời điểm biết thông tin, kỳ dữ liệu và retrieval; lịch sử cần đúng phiên bản.
- Wire changes additive/versioned; round-trip được message cũ và evidence cũ.

## Architecture

Reuse `EvidenceRef`/`EvidenceLocation`/`VerifiedClaim`/`ClaimLedger`. Schema observation trong [architecture](./architecture-and-contracts.md). Trust hiện tại được siết theo D6–D8 đã duyệt; không đổi enum/public semantics lén.

## Related Code Files

| Action | Owner / responsibility |
|---|---|
| Modify | `apps/api/src/agent/evidence/contracts.py`: observation/version/support fields |
| Modify | `evidence/pipeline.py`: candidate_ledger, evidence_from_calls; `evidence/ledger.py`: validation/render |
| Modify | `agent/persistence.py`, `messages.py`, `turns.py`: checkpoint/store round-trip |
| Modify consumers | `agent/visual.py`, web `lib/alpha-desk/types.ts`, `read-content.ts`, golden graders |
| Tests | `test_agent_evidence_contract.py`, `test_agent_evidence_pipeline.py`, `test_agent_evidence_renderer.py`, `test_agent_evidence_store.py` |

Paths abbreviated above resolve under `apps/api/src/agent/`, `apps/api/tests/` or `apps/web/src/` as labeled; verify every caller at implementation commit.

## Implementation Steps

1. Inventory serializers, constructors, persistence and visual consumers for the four types; capture actual caller list before signature edits.
2. Write regression fixtures for semantic UNSUPPORTED + primary support, verifier missing one material claim, duplicate/unknown claim IDs, and failure of entire verifier.
3. Make acceptance monotonic: semantic failed/unknown cannot become verified; mechanical checks may downgrade. Represent unjudged claims explicitly with reason, not silent deletion.
4. Add typed observations using decimal strings and exact source locators; preserve unknown entity/basis/unit rather than infer.
5. Define temporal field meaning once. Allow retrieval after cutoff only if source version was available then; date-only publication cannot imply pre-open availability; newly restated document stays unavailable for older cutoff.
6. Record information origin, avoid counting syndication as independence; user-uploaded issuer-looking PDF stays user document unless authenticity actually established.
7. Extend rendering tests across claim body, assumptions/gaps/invalidations and labels; fact/inference/scenario visible; model material=false cannot suppress numeric checks for material facts.
8. Version payloads, read old versions conservatively; add migration only when existing JSON storage cannot support scope/retention requirements. Backup first if migration needed.
9. Run focused suites and source mutation tests, then full API/web contract tests.

## Test Matrix

| Input | Required outcome |
|---|---|
| Same number, different entity/period/unit/metric | Unsupported, not verified by numeric coincidence |
| Primary ID + semantic rejection | No verified badge |
| Verifier omitted one claim | Claim unverified + coverage gap persists |
| Retrieval today, authentic historical version | Historical admissibility depends on availability, not fetch clock |
| Latest restatement of old period | Excluded from earlier cutoff |
| Two articles copying one filing | One origin, not two independent confirmations |
| Old message/ledger JSON | Replay works or explicit legacy state, no invented metadata |

## Success Criteria

- [ ] 0 false verified states on all negative fixtures; all claims accounted.
- [ ] 0 look-ahead on historical/version fixtures.
- [ ] Mutation matrix fails when identity changes despite same numeric value.
- [ ] Existing ledger/UI replay tests pass; original data remains readable.

## Validation

`make -C apps/api test-one T=tests/test_agent_evidence_contract.py`, then evidence pipeline/renderer/store files using same target. Web read-content tests + type-check for changed wire fields; affected golden. No statistical accuracy claim from unit fixtures.

## Risk Assessment

Changing timestamp interpretation may alter old memo eligibility → preserve original snapshot/version and label legacy ambiguity; do not revalidate old answers against latest facts silently. Full semantic understanding remains probabilistic → grounded eval and human audit, not promise 100%.

## Rollback / handoff

Dual-read/one-write and capability release flag; roll back writer to prior version while keeping new records readable. Handoff sample old/new payloads, policy versions, mutation evidence and finance observation contract.
