---
title: "Red-team review — Resolved Capability Contract v1"
date: 2026-08-23
status: resolved
---

# Red-team review — Resolved Capability Contract v1

## Summary

Adversarial review found one security-significant ambiguity and two
implementability/data-contract gaps. All three were corrected in the plan. No
unresolved blocker remains, but implementation remains blocked on Stage 0
graduation and must reconcile final eval file owners before Phase 4.

## Findings

### High — lane selection did not equal dispatch authority

**Evidence:** Conversation/Analysis offer schemas via selected toolsets
(`agent/loop.py:796`, `alpha/analysis_loop.py:461-478`), but
`ToolExecutor.lookup` defaults to global `registry.get`
(`agent/executor.py:184-220`). A globally registered tool omitted from the
Analysis `signals` surface can therefore be dispatched if a provider produces
its name.

**Correction applied:** plan and Phases 1–3 now distinguish current observation
from desired contract. `ResolvedToolSurface.by_name` contains selected entries
only; lane-unselected names settle once and never dispatch. This is the plan's
only intentional behavior narrowing and receives a hard security regression
case.

### High — evidence metadata requirement overclaimed current output

**Evidence:** provider/store contracts retain source and `price_basis`, but
`EvidenceFigure.as_wire()` exposes source, unit, health and `asOf` without a
generic `price_basis` field (`alpha/envelope.py:121-174`). VNStock
fundamentals also lack publication/ingestion timestamps.

**Correction applied:** plan now requires preservation only of fields the owning
result emits and forbids the resolver from fabricating missing basis or temporal
identity. Missing publication/ingestion remains a named evidence-plane gap.

### Medium — test/file inventory omitted direct budget/trust/ops owners

**Evidence:** result-limit precedence is pinned in
`test_agent_tool_budget.py`; delimiter security is owned by
`test_agent_untrusted_results.py`; external/price-check observer behavior is
owned by `test_agent_ops_query.py`.

**Correction applied:** Phase 3 inventory and Phase 4 validation commands now
include all three. `src/eval/world.py` is also a conditional Phase 4 owner for
resolved-cache isolation after Stage 0 finalizes.

### Medium — final eval paths are not yet authoritative

**Evidence:** Stage 0 is pending and its worktree currently contains in-progress
Phase 2 files. `test_eval_harness.py`, gate policy and final Make targets are
later Stage 0 deliverables.

**Disposition:** accepted, not patched into guessed APIs. The new plan is
`blockedBy` Stage 0; Phase 4 explicitly re-reads final owners and updates the
plan before edit. Conditional file actions are labeled.

## Rejected concerns

- **“Use provider Main/Cover as resolved fallback.” Rejected.**
  `SourceOwnership` says cover is explicit semantic coverage, not runtime
  fallback; VNStock valuation has no executable adapter.
- **“Put price basis/quota/tier on static tool metadata.” Rejected.**
  Those facts vary per evidence row/account/provider owner and would duplicate
  truth or become stale.
- **“Merge Conversation and Analysis loops.” Rejected.** They share the lower
  resolver/executor seam but have distinct lifecycle, persistence and user scope.
- **“Persist resolved metadata now.” Rejected.** Public/durable lifecycle is the
  next Stage 1 slice; this plan intentionally has no migration/SSE version bump.
- **“Parallelize Signal Field reads while touching concurrency.” Rejected.**
  Current behavior is serialized; any optimization needs a separate measured
  candidate.

## Verification results

- **Tier:** Standard (4 phases)
- **Claims checked:** 40 (10 per phase)
- **Verified after corrections:** 40
- **Failed:** 0
- **Unverified:** 0

Checked claims cover source paths/symbols, registry consumers, direct
`ToolEntry` constructors, cache keys/TTL, eight shipped registrations, toolset
selection, executor global lookup, result budget precedence, SSE exact-shape
tests, provider ownership/executable mismatch, VNStock three-call fundamentals,
corporate-action ownership gap, and Stage 0 dependency state.

## Whole-plan consistency sweep

- Files reread: `plan.md`, all four phase files, both research reports.
- Decision deltas checked: 4.
- Reconciled stale references: 6.
- Unresolved contradictions: 0.

## Unresolved questions

None. Runtime toolset mutation remains unsupported production behavior; display
projection stays on existing declaration callables; handler authorization stays
the enforcing owner until a later contract can truthfully centralize it.
