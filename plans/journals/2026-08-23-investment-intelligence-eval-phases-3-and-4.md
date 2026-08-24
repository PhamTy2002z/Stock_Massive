---
title: Investment intelligence eval phases 3 and 4
date: 2026-08-23
summary: Delivered deterministic grading and a fail-closed multi-trial release harness; paid baseline approval remains intentionally open.
---

# Investment intelligence eval phases 3 and 4

## What happened

Implemented the 16-case Investment Intelligence battery, nine deterministic hard graders, blinded rubric measurement, sequential three-trial scheduling, run-level spend controls, canonical typed reports, baseline comparison, CLI and Make targets, and real offline replay through TurnService and Symbol Analysis production seams.

Independent review found policy-prose, temporal-lookahead, provider-access, incomplete-baseline, unknown-usage, manifest, rubric integration, and retry-ceiling escapes. Each was fixed with focused regression coverage. The paid rubric lane now performs exactly one admitted provider dispatch, so its worst-case ceiling check matches actual provider attempts.

## Verification

- 162 Phase 1-4 eval tests passed.
- Dataset validation passed: 16 cases, 3 snapshots, 9 hard graders, digest 8e829faa380d64f2.
- Two complete offline smokes were canonically identical after excluding run identity and digest.
- Each smoke recorded 16 rubric results, zero hard failures, and zero data-provider calls.
- Independent code review completed with no remaining concern.
- No eval database, test process, or temporary artifact remained.

## Decision

Phase 3 is done. Phase 4 implementation is complete but remains in progress because the plan forbids creating or approving the first paid baseline without an explicit paid route/spend ceiling and owner-reviewed distributions and thresholds. Stage 0 remains Target; the pending baseline summary fails closed.

## Next steps

Run and review the first paid three-trial baseline under the committed ceiling, then record the approved artifact digest and thresholds and close Phase 4/Stage 0.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
