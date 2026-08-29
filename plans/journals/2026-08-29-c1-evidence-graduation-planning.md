---
title: C1 evidence graduation planning
date: 2026-08-29
summary: Defined a fail-closed successor plan that reconciles C1 graduation with the completed C1 and C5 plans.
---

# C1 evidence graduation planning

## What happened

Reviewed `docs/roadmap.md`, the completed C1/C5 plans, the current golden grader, scan persistence path, tests, and the three C1 artifacts. C1 runtime work is complete, but graduation evidence is not: read-depth wording conflicts, the numeric grader lacks bounded derivation witnesses, and scan persistence is not proven end to end.

## Decision

Created `plans/260829-1945-c1-evidence-graduation/` as the C1 successor. It freezes the case-specific read-depth gate at at least 16/20, keeps flat fetch depth diagnostic, calibrates a provenance-aware numeric witness evaluator against valid derivations and fabricated mutations, and verifies scanner verdict persistence without changing C5 attribution.

## Next steps

Execute Phase 1 only after completed C1/C5 prerequisite changes are committed or safely isolated from the dirty shared worktree. C2 remains closed until all four phases pass and C1 is explicitly promoted to Current.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
