---
phase: 7
title: "Evidence Desk và Signal Desk theo câu hỏi"
status: pending
priority: P1
effort: "10–15 engineer-days"
dependencies: [6]
---

# Phase 7: Evidence Desk và Signal Desk theo câu hỏi

Context: [Plan](./plan.md) · [Architecture](./architecture-and-contracts.md) · [Validation](./validation-strategy.md)

## Overview

Hoàn thành memo/evidence UX và visualization hữu ích trên dữ liệu đã được chấp nhận. Signal Desk là pane của cùng research Turn, không board engine.

## Requirements

- Verdict, as_of, fact/inference/scenario, contradictions, gaps và watch items đến từ typed data.
- Citation mở đúng evidence; calculated values mở operands/operation; partial/source-rights state rõ.
- Chart input do host bind; model không gửi numeric data hoặc HTML/React/ECharts.
- UI keyboard/screen-reader, responsive, table alternative; refresh/thread switch/cancel đúng.

## Architecture

Claim ledger + requirement outcome → existing typed message content/parts → memo projection.
Optional visual intent: allowed chart type + observation IDs/fields + semantic roles. Host chooses compatible data, validates entitlement/time/unit → versioned ChartAssemblyInput → official Flint → ECharts. Persist input and lineage, never compiled output.

## Related Code Files

| Action | Files |
|---|---|
| Modify backend | `apps/api/src/agent/visual.py`, `evidence/ledger.py`, `turns.py`, `schemas.py`, `events.py` only if new typed events required |
| Modify wire/replay | `apps/web/src/lib/alpha-desk/types.ts`, `read-content.ts`, `desk-visual.ts`, `live-turn.ts` only if events added |
| Modify shell/pane | `components/shell/inspector.tsx`, `desk-state.tsx`, `composer.tsx`, `components/signal-desk/signal-desk-panel.tsx` |
| Modify visual compiler | `apps/web/src/lib/flint/compile-visual.ts` and contract tests |
| Modify evidence/feedback UI | `components/alpha/message/source-chips.tsx`, `source-list.tsx`, `question-card.tsx`, `flag-action.tsx` |
| Create proposed UI boundaries | Evidence card/memo section components next to existing message components only where real complexity warrants |
| Tests | Existing visual/read-content/desk-visual/panel/live-turn tests and `apps/api/tests/test_agent_visual.py` |

## Implementation Steps

1. Map existing UI to roadmap P7 objects and inspect design docs/current components; do not redesign shell wholesale.
2. Add typed memo data only where ledger currently cannot express UI; update backend/client contracts atomically, preserve old markdown message fallback.
3. Implement cutoff banner, premise verdicts, claims/type labels, invalidations, watch items, source/claim/unverified counts. All user-visible numeric statements need ledger provenance.
4. Evidence card shows page/cell/span, source, publication/retrieval dates, report basis/version, conflict, derived operands. Do not expose private provider credentials or filesystem locators.
5. Preserve question answered/skipped/superseded and real pass timeline through reconnect; no fabricated progress percentage.
6. Define supported chart families from real accepted datasets: price/volume; normalized performance vs benchmark; financial multi-period bars/lines; segment mix; timeline of evidenced events if Flint supports suitable template.
7. Run pinned Flint fixture spike per proposed family. If required family unsupported, render accessible evidence table/timeline in memo rather than patch compiler; capability limitation explicit.
8. Host handles incompatible basis, missing periods, series alignment, axis unit and cardinality. Raw prices must not be labeled comparative performance; percentages/returns require W5 lineage.
9. D9 permits model choose type/fields only. Validate field/observation references, value finiteness, row/series/byte cap, unit and time compatibility before persist; ensure labels/annotations grounded.
10. Distinguish no visual requested, insufficient data, unsupported chart, expired entitlement, compiler failure and current Turn still running. Never show old chart as new Turn output.
11. Wire claim-level report-wrong to existing message flag path with versioned claim ID metadata, after accepted schema update; no duplicate feedback system.
12. Exercise keyboard, mobile layout, table view, F5 mid-run, switch thread, cancel, old payload versions and rights revocation.

## Test Matrix

| Scenario | Required outcome |
|---|---|
| Compare stock performance | Normalized return/basis label, not raw price comparison |
| Revenue eight quarters | Correct period/basis/units and source for every bar |
| Material observation absent from narrative | Visual inclusion governed by explicit validated evidence admission, not incidental prose wording; D9 defines semantics |
| Unsupported Flint template | Table with reason, no compiler output patch |
| Private evidence or revoked data right | Cannot leak through pane/replay/export |
| Reconnect / old schema | Same accepted input; no research rerun |
| Chart compiler error | Memo remains usable, meaningful visual state |

## Success Criteria

- [ ] Every chart number/annotation maps to accepted observation/derivation with rights.
- [ ] Memo/evidence/question flows match typed state without parsing markdown for application state.
- [ ] Flint contract tests pass; no fork/post-process or persisted ECharts option.
- [ ] End-to-end question→evidence→visual→refresh/thread switch verified on real stack.
- [ ] Accessibility basics and all existing mode isolation/visual replay gates pass.

## Validation

API visual/renderer tests; web lint/type-check/test/build; relevant browser E2E discovered from package scripts. Golden persisted artifact compiler test must execute on a real visual artifact, not skip.

## Risk Assessment

Official Flint cannot express desired composition → keep table fallback and record unsupported capability; changing renderer requires separate evidence-backed decision. Visual admission change could weaken trust → validate all observations directly under same time/rights/source rules, never use raw successful tool status as acceptance.

## Rollback / handoff

Feature-flag new visual version; keep reader for old versions; no persisted compiled options to migrate. Handoff UI state matrix, accessibility results, source-to-pixel lineage fixtures and screenshots from live acceptance.
