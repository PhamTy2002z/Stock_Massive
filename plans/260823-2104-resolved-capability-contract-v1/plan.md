---
title: "Resolved Capability Contract v1"
description: "Unify the declared and resolved tool contract consumed by model schema, execution, budget, trust, trace, and display without changing public contracts or provider semantics."
status: pending
priority: P1
effort: 48h
branch: develop
tags: [refactor, backend, ai-harness, critical]
blockedBy:
  - 260823-1744-investment-intelligence-eval-replay-harness
blocks: []
created: 2026-08-23
---

# Resolved Capability Contract v1

## Overview

Deliver the first Stage 1 slice after measurement authority: one immutable,
ordered tool surface per Conversation turn or Analysis run. Model schemas,
handler dispatch, concurrency, budget, content trust, result limits, trace, and
human display project from the same registered facts. Preserve public and
authorized behavior; intentionally close dispatch of a globally registered tool
that the active lane did not select. Deepen the existing `registry.py` /
`definitions.py` seam instead of rewriting either loop.

## Delivery contract

- **Outcome:** adding one read-only financial tool requires one registration and
  intentional toolset selection, not another name/policy table.
- **Constraints:** Stage 0 baseline approved first; no public API/SSE/schema
  change; no database migration; unknown metadata stays external, untrusted,
  unknown-effect, non-idempotent, and serialized; trusted identity remains in
  `ToolContext`.
- **Non-goals:** typed durable lifecycle, evidence-plane redesign, new provider
  or fallback, live provider call, MCP/plugin/subagent, compaction, new tool, or
  increased autonomy.
- **Acceptance evidence:** focused contract/mutation tests, unchanged provider
  conformance, offline eval smoke, and approved-baseline comparison with no new
  hard regression.

## Architecture decision

`ToolEntry` remains the static author-owned declaration. `definitions.py`
becomes the resolved-surface/cache owner and returns frozen `ResolvedTool` and
`ResolvedToolSurface` values. Existing `get_tool_definitions()` remains a
lossless projection, not an independent owner. Chat and Analysis keep separate
orchestrators but consume the same lower seam.

`src.stocks.providers.contracts.Capability` remains a provider data-class
contract. It is not imported or mirrored into the agent resolver. Main/Cover is
explicit coverage, never automatic fallback. Provider source, unit,
`price_basis`, effective/publication/ingestion time, partial health, and evidence
identity remain row/result properties when the owning contract actually emits
them; missing publication/ingestion or basis is a named evidence gap, never a
resolver inference.

## Cross-plan dependencies

| Relationship | Plan | Required state |
|---|---|---|
| Blocked by | [`260823-1744-investment-intelligence-eval-replay-harness`](../260823-1744-investment-intelligence-eval-replay-harness/plan.md) | All phases done; clean baseline and repository gate policy approved. |
| Precedes | Stage 1 typed lifecycle and stable identity | This plan changes no durable state. |
| Precedes | Stage 2 “Explain a material move” | Planner must consume a stable capability/evidence seam. |

## Provider boundary

| Data class | Executable truth to preserve |
|---|---|
| Market/current | FiinQuant main; VNStock history cover only. |
| Market index | FiinQuant history only; no VNStock cover/current inference. |
| Valuation | FiinQuant executable; VNStock cover declaration is unavailable. |
| Reference/share/foreign room | VNStock executable; listed shares never mean outstanding. |
| Fundamentals | VNStock; 3 calls/symbol, 8 periods max, cash-flow may be partial. |
| Corporate action | VNStock adapter exists without standalone provider `Capability`; do not alias to Reference semantics. |

## Phases

| # | Phase | Status | Depends on |
|---|---|---|---|
| 1 | [Freeze contracts and provider boundary](./phase-01-start.md) | Pending | Stage 0 graduation |
| 2 | [Resolved capability model and resolver](./phase-02-resolved-capability-model-and-resolver.md) | Pending | Phase 1 |
| 3 | [Consumer migration and duplicate owner removal](./phase-03-consumer-migration-and-duplicate-owner-removal.md) | Pending | Phase 2 |
| 4 | [Cross-lane eval and graduation gate](./phase-04-cross-lane-eval-and-graduation-gate.md) | Pending | Phase 3 |

## Success criteria

- [ ] All eight shipped tools have explicit, test-locked effect, idempotency,
      access, trust, concurrency, output, display, handler, and version facts.
- [ ] Offered schema and dispatched handler/policy come from one frozen surface;
      dispatch rechecks revocation without swapping handler/policy mid-task.
- [ ] `PARALLEL_SAFE_TOOLS` and generic name-based result/display branches are
      removed where declaration-owned; lane allowlists and domain metrics remain.
- [ ] Conversation and Analysis retain names, ordering, results, errors, budgets,
      traces, transcript/SSE v2 wire bytes, and fail-open behavior.
- [ ] A globally registered but lane-unselected name settles as unavailable/
      unknown and never dispatches; this is the only intentional narrowing.
- [ ] Provider mismatches resolve as named unavailable/gap states; no implicit
      FiinQuant/VNStock fallback and zero provider calls in eval.
- [ ] Approved baseline comparison has no new hard regression; quality,
      cost, and latency changes are reviewed rather than hidden.

## Research

- [Capability architecture inventory](./research/capability-architecture-report.md)
- [FIinQuant versus VNStock data contracts](./research/provider-data-contracts-report.md)

## Rollback

Revert phase by phase. Keep compatibility projections until the final consumer
is migrated. Never dual-dispatch. No schema/data rollback is required because
the plan adds no migration or public wire field.

## Unresolved questions

None for implementation. Corporate-action ownership and filing publication/
ingestion timestamps stay named future evidence-plane decisions, not implicit
choices in this plan.

## Validation log

### Roadmap reconciliation — 2026-08-24

This audit separates plan preparation from implemented Harness progress.

- This plan maps only to the first resolved-capability slice of Harness Phase
  H1. Completing it does not graduate H1's evidence identity, recovery, context,
  or durable lifecycle work.
- DNSE adapters and normalized market events remain in System phases S0–S3 and
  are not added to this plan. Future DNSE tools must register through the
  resolved surface after this plan graduates.
- Status remains `pending`: H0 has not graduated, all four phases remain pending,
  and no `ResolvedTool` or `ResolvedToolSurface` implementation exists.

### Deep planning and red-team — 2026-08-23

- Standard verification: 40 claims checked, 40 verified after corrections, 0
  failed/unverified. See [red-team review](./reports/red-team-review.md).
- Corrected three plan defects: lane-selected schema/global-dispatch mismatch;
  overclaim of basis/publication metadata; missing budget/untrusted/ops tests.
- Whole-plan consistency sweep reread plan + 4 phases + 2 research reports;
  4 decision deltas checked, 6 stale references reconciled, 0 contradictions.
- AgentKit structural validation passes. Execution remains blocked on Stage 0
  baseline and final eval-owner reconciliation.

<!-- slug: resolved-capability-contract-v1 -->
