---
title: "Resolved Capability Contract v1"
description: "Unify the declared and resolved tool contract consumed by model schema, execution, budget, trust, trace, and display without changing public contracts or provider semantics."
status: completed
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
| 1 | [Freeze contracts and provider boundary](./phase-01-start.md) | Completed | Stage 0 graduation |
| 2 | [Resolved capability model and resolver](./phase-02-resolved-capability-model-and-resolver.md) | Completed | Phase 1 |
| 3 | [Consumer migration and duplicate owner removal](./phase-03-consumer-migration-and-duplicate-owner-removal.md) | Completed | Phase 2 |
| 4 | [Cross-lane eval and graduation gate](./phase-04-cross-lane-eval-and-graduation-gate.md) | Completed | Phase 3 |

## Success criteria

- [x] All eight shipped tools have explicit, test-locked effect, idempotency,
      access, trust, concurrency, output, display, handler, and version facts.
- [x] Offered schema and dispatched handler/policy come from one frozen surface;
      dispatch rechecks revocation without swapping handler/policy mid-task.
- [x] `PARALLEL_SAFE_TOOLS` and generic name-based result/display branches are
      removed where declaration-owned; lane allowlists and domain metrics remain.
- [x] Conversation and Analysis retain names, ordering, results, errors, budgets,
      traces, transcript/SSE v2 wire bytes, and fail-open behavior.
- [x] A globally registered but lane-unselected name settles as unavailable/
      unknown and never dispatches; this is the only intentional narrowing.
- [x] Provider mismatches resolve as named unavailable/gap states; no implicit
      FiinQuant/VNStock fallback and zero provider calls in eval.
- [x] Approved baseline comparison/reset has no new hard regression; quality,
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

### Phase 3–4 implementation and offline gate — 2026-08-24

- Phase 3 is completed. Phase 4's code-owned and offline criteria are complete;
  its approved candidate comparison and graduation remain open.
- Fresh focused integration passed 414 tests. Two offline smoke runs each
  completed 16/16 cases (Conversation 10, Analysis 6), with zero hard failures,
  zero provider calls, and identical stable canonical content.
- Code review reported no Critical or Important findings. See the
  [test report](../reports/test-260824-2303-resolved-capability-phases-3-4.md)
  and [review report](../reports/code-review-260824-2352-resolved-capability-phases-3-4.md).
- Paid candidate `e78715254eb08800` completed 48/48 with zero hard failures and
  zero provider calls. The approved baseline differs only in the intentionally
  expanded tool identity; the fail-loud comparison was resolved by an explicit
  owner-reviewed reset on 2026-08-25. The accepted artifact is now the approved
  baseline and the smallest clean Harness authority surface links its evidence.
  No commit, push, or PR was performed. This plan is completed; it does not
  claim typed lifecycle, evidence identity, recovery, or all of H1 complete.

### Phase 1–2 delivery — 2026-08-24

- Phase 1 and Phase 2 are completed; Phase 3 and Phase 4 remain pending.
- Focused, compatibility, broadened, and default-offline verification is
  recorded in [the progress report](../reports/pm-260824-2301-resolved-capability-phases-1-2.md).
- The plan remains `in-progress` and advances to Phase 3. No whole-plan
  graduation or Harness H1 completion is claimed.

### Roadmap reconciliation — 2026-08-24

This audit separates plan preparation from implemented Harness progress.

- This plan maps only to the first resolved-capability slice of Harness Phase
  H1. Completing it does not graduate H1's evidence identity, recovery, context,
  or durable lifecycle work.
- DNSE adapters and normalized market events remain in System phases S0–S3 and
  are not added to this plan. Future DNSE tools must register through the
  resolved surface after this plan graduates.
- At the time of this pre-implementation audit, status was `pending`: H0 had
  not graduated, all four phases were pending, and no `ResolvedTool` or
  `ResolvedToolSurface` implementation existed.

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
