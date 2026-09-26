---
phase: 6
title: "Nghiên cứu thích ứng theo nhu cầu"
status: pending
priority: P1
effort: "8–12 engineer-days"
dependencies: [5]
---

# Phase 6: Nghiên cứu thích ứng theo nhu cầu

Context: [Plan](./plan.md) · [Architecture](./architecture-and-contracts.md) · [Validation](./validation-strategy.md)

## Overview

Agent biết xác định cần gì, tìm đâu, đọc đủ chưa và khi nào đổi hướng. Thay batch cứng bằng requirement coverage trong loop hiện có, sau D5 và baseline chứng minh.

## Requirements

- Phủ cả BCTC, tin mới, thông tin ngách, phản ứng thị trường và kiểm chứng luận điểm.
- Query theo entity/alias/industry/source/time, không chỉ ticker và headline.
- Một loop, một guard/budget, một capability plane; research/counterevidence/verification vẫn là pass thật.
- Task coverage không đồng nhất với Turn settlement hoặc model tự khai ready.

## Architecture

Requirement frame nhỏ trong existing checkpoint: requirement ID, materiality, entity/time, acceptable evidence kinds, observation/claim refs, state open/supported/conflicting/unavailable + reason. Đây là dữ liệu nội bộ của pipeline, không DSL hay orchestrator mới. Mọi wire projection mới phải đi typed part lifecycle.

## Related Code Files

| Action | Files |
|---|---|
| Modify planner/loop | `apps/api/src/agent/loop.py`, `evidence/pipeline.py`, `messages.py`, `turns.py` |
| Modify domain guidance | `apps/api/src/agent/domain/vn_equity.py`, `pack.py`, `symbols.py` |
| Protect bounds/context | `agent/guardrails.py`, `lanes.py`, `executor.py` (reuse, edit only measured need) |
| Tests | `test_agent_evidence_pipeline.py`, `test_agent_evidence_elicitation.py`, `test_agent_loop.py`, `test_agent_context_engine.py`, `test_agent_fault_injection.py` |

## Implementation Steps

1. Trace current planner gating and pass transitions; freeze old behavior tests before changing. Do not increase existing 10 rounds/20 external calls/1,800 seconds automatically.
2. Build requirement frame from question + supplied document + thread context. Host validates schema, caps requirement count (proposed max 12) and prevents model dropping requested material requirements later.
3. Choose initial action according to available evidence: fetch supplied URL; extract attached BCTC; search official filing; call entitled structured data for series. No mandatory four searches.
4. Use domain playbooks on demand: earnings/notes, company events, sector/operational indicators, market reaction, conflicting sources. Niche search expands company subsidiaries/project/product aliases when evidence supports identity.
5. Prefer primary source read over multiple snippets; assess new evidence by origin/content/version and affected requirement, not just query string.
6. Run counterevidence against conclusion, not cosmetic alternative wording. Distinguish candidate causal explanation from observed timing.
7. After verification, map failed/unjudged claims back to requirements. At most two targeted recovery cycles initially, all inside original round/call/cost/deadline bounds; persist count so reconnect cannot reset it.
8. Reverify changed claims and any conclusion depending on them; old verified output cannot survive a changed dependency unchecked.
9. Elicitation: scout first, ask only non-discoverable branch-changing context, obey existing question budget/skip/supersede.
10. Context compaction retains user requirements, evidence refs, cutoff, pending gaps and call/result pairs. Store full datasets outside prompt; fetch relevant evidence again by stable permitted refs.
11. On exhausted/no-progress/unavailable source, settle partial/insufficient task outcome with searched/unknown/next-action detail; keep technical Turn terminal contract.
12. Evaluate light lane external facts too: route complex/high-impact finance query into verified path; no unverified light-lane escape around truth policy.

## Test Matrix

| Scenario | Required behavior |
|---|---|
| Filing URL supplied | Reads it directly; no arbitrary four-search failure |
| Earnings + reaction + risk question | Accounts each requirement, not price-only answer |
| Niche subsidiary/project data | Entity links sourced; uncertainty if ambiguous |
| Search variations return same article | No fake progress; bounded change of source/stop |
| New evidence contradicts earlier answer | Invalidate affected conclusions and reverify |
| Cancel/F5 during gap recovery | Persist cycle/budget, exactly one terminal settlement |
| User asks simple fact | Appropriate lane, same grounding obligation for external numbers |

## Success Criteria

- [ ] Requirement completeness and source-read quality meet W1 thresholds per family.
- [ ] Every user-requested material branch supported or explicitly unresolved; omission fails eval.
- [ ] No envelope reset or duplicate side effects/recovery loop on replay.
- [ ] Counterevidence and labeled causal uncertainty appear where applicable; elicitation gates preserved.

## Validation

Focused pipeline/elicitation/loop/context/fault suites; before/after paired frozen-evidence golden. Report cost/latency per successful task and invalid/duplicate call rates without weakening coverage thresholds.

## Risk Assessment

Coverage turns into another planner framework → keep one typed list and existing state. Model misframes the question → rubric compares against human-labeled requirements, not model frame alone. New recovery exhausts budget → partial with explicit gaps, not larger default envelope.

## Rollback / handoff

Feature flag adaptive planner; keep old checkpoint reader. A new Turn can use old planner; in-flight version stays pinned. Handoff requirement schema, transition fixtures, benchmark uplift and no-progress data.
