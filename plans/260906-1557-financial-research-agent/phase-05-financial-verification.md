---
phase: 5
title: "Ngữ nghĩa tài chính và phép tính truy nguồn"
status: pending
priority: P1
effort: "8–12 engineer-days"
dependencies: [4]
---

# Phase 5: Ngữ nghĩa tài chính và phép tính truy nguồn

Context: [Plan](./plan.md) · [Decision register](./decisions-and-dependencies.md) · [Validation](./validation-strategy.md)

## Overview

Đọc đúng ý nghĩa số liệu và thực hiện arithmetic hữu hạn có provenance, sau D4 được duyệt. Không mở sandbox tổng quát hoặc indicator engine.

## Requirements

- Phân biệt LNST toàn tập đoàn/cổ đông mẹ, quarter/YTD, consolidated/separate, stock/flow, %/percentage points.
- Every derived result bound to explicit input observation IDs, operation and version.
- Không dùng numeric coincidence hoặc brute-force tìm phép tính để hợp thức hóa số.
- Không nâng trust của input khi tính toán.

## Architecture

Accepted observations → compatibility validation → bounded deterministic evaluator → CALCULATION evidence → semantic claim verifier → existing ledger.
Reuse numbers normalization và contracts; phép tính là host operation nhỏ, không DSL/coding tool.

## Related Code Files

| Action | Files |
|---|---|
| Modify | `apps/api/src/agent/evidence/contracts.py`, `numbers.py`, `ledger.py`, `pipeline.py` |
| Modify | `apps/api/src/agent/domain/vn_equity.py`, `pack.py` for financial guidance |
| Create proposed | `apps/api/src/agent/evidence/calculations.py` for approved finite operations only |
| Tests | `apps/api/tests/test_evidence_numbers.py`, evidence pipeline/contract/renderer suites |
| Create proposed | `apps/api/tests/test_agent_financial_calculations.py` with finance edge-case matrix |

## Implementation Steps

1. Confirm D4 scope; if rejected, do not execute arithmetic in another helper name. Keep reported-figure support; mark quantitative family as not delivered.
2. Normalize extracted observations and keep original values/labels; reconcile report discrepancies without choosing newest for historical queries.
3. Define operations needed by frozen corpus: difference, bounded sum, ratio, compatible growth, Q4 from FY/9M, base-index price return and benchmark-relative difference.
4. Use Decimal or equivalent exact decimal; specify rounding only at output; validate unit/period/entity/basis and denominator before computing.
5. Persist operation, ordered operand IDs, version/result/units. Recompute from references, never accept model-proposed numeric output as authoritative.
6. Match Q4 operands on fiscal year/consolidation/restatement; no subtracting restated FY from incompatible original 9M. Label zero/negative-base growth as not meaningful and explain loss→profit without fake percent.
7. For event reaction, align publication to first knowable session, benchmark and corporate actions; annotate observation vs causal inference.
8. Teach playbook decomposition for profit quality: operating vs one-off, cash conversion, related-party/notes; bank/insurance metrics separate.
9. Close ungrounded-number paths in titles, scenarios, assumptions and visual annotations. User-supplied hypothetical amounts get explicit user provenance, not market truth.
10. Add human-reviewed multi-trial cases showing arithmetic uplift over reported-only baseline; no algorithmic claim of finance correctness from unit tests.

## Test Matrix

| Case | Expected |
|---|---|
| VND/thousand/million/billion | Exact normalization, no ×1000 drift |
| Null/dash versus 0 | Missing stays missing |
| Q4 FY−9M mismatched basis | Refuse derivation |
| Growth negative/zero base | Explicit undefined/not meaningful semantics |
| Duplicate calculation paths | Same source lineage, not independent support |
| Split/ex-dividend | Return uses declared basis; no causal claim from mechanical adjustment |
| Model supplies correct-looking result with wrong operands | Reject or recompute, never accept result alone |

## Success Criteria

- [ ] All finite-operation boundary tests pass; no arbitrary code/network execution.
- [ ] Replay identical operands/version returns identical result; mutation breaks expected lineage/value.
- [ ] Material finance fixtures correctly discriminate metric/entity/period/basis.
- [ ] Paid finance family meets W1 thresholds with full denominators and disclosed uncertainty.

## Validation

Focused numbers/calculation tests, then evidence suites and affected golden. Compare baseline and candidate on same frozen evidence. Paid ceiling required.

## Risk Assessment

Different vendors revise historic data → version operands and label as-of basis; if no prior version, historical conclusion stays unverified. General scenario models exceed finite operations → conditional sandbox phase, not hidden expansion.

## Rollback / handoff

Disable calculation capability, continue reported values; persisted derived evidence remains renderable with evaluator version. Handoff operation contract, unit table and ground-truth review.
