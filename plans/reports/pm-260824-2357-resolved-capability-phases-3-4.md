---
title: "Progress: Resolved Capability Contract v1 Phases 3-4"
date: 2026-08-24
status: completed
plan: 260823-2104-resolved-capability-contract-v1
---

# Resolved Capability Contract v1 — Progress

## Status

| Phase | Status | Checklist | Evidence |
|---|---|---:|---|
| 1 — Freeze contracts | Completed | 19/19 | Prior delivery log |
| 2 — Resolved model | Completed | 21/21 | Prior delivery log |
| 3 — Consumer migration | Completed | 23/23 | 414 focused integration passes; review pass |
| 4 — Eval/graduation | Completed | 20/20 | Owner-reviewed reset accepted |
| Whole plan | Completed | 83/83 (100%) | `ak plan validate`: valid |

## Delivered

- One frozen resolved surface owns Conversation and Analysis schema, dispatch,
  concurrency, access budgets, result limits, trust, summary/display, and trace
  projections.
- Lane-unselected and initially unavailable tools cannot dispatch. Live checks
  only revoke; captured handlers and policy do not swap mid-task.
- Access and content trust remain orthogonal for current and legacy registered
  calls. Unknown names remain conservative.
- Eval compatibility identity includes the ordered case/lane surface and full
  resolved execution contract without secrets, probes, callables, expiry, or
  object identity.

## Verification

| Gate | Result |
|---|---|
| Post-review focused integration | 414 passed, 0 failed |
| Offline smoke run 1 | 16/16 complete; 0 hard failures; 0 provider calls |
| Offline smoke run 2 | 16/16 complete; 0 hard failures; 0 provider calls |
| Stable canonical comparison | Identical after volatile run fields removed |
| Scoped tool identity | `ee10c69a9f909d30` |
| Code review | 0 Critical, 0 Important, 1 non-blocking Minor |
| Earlier full repository suite | 2,828 passed; 1 unrelated missing-doc failure; 1 skipped |
| Paid candidate | 48/48 complete; 0 hard failures; 0 provider calls |
| Paid artifact | `e78715254eb08800`; tool identity `ee10c69a9f909d30` |
| Recorded LLM cost | Candidate USD 0.4975967 + rubric USD 0.133352 |

The review Minor records that eval fixture installation mutates process-global
registry/toolset state and must stay single-flight. Current runner and identity
composition are sequential; parallel in-process eval requires explicit state
ownership first.

## Documentation impact

No evergreen docs update yet. Phase 4 explicitly requires evidence and approved
graduation first; `docs/harness-roadmap.md` is also owned by another active
session. Plan files and reports are the correct status authority meanwhile.

## Graduation decisions

- [x] Repository-owned paid candidate run completed under policy ceiling USD 5.
- [x] Owner accepted reviewed reset lineage from baseline `36bc44f7c00966cd`
      to candidate `e78715254eb08800` for the intentional tool identity change.
- [x] Owner chose the reviewed reset; no second paid candidate was required.
- [x] Owner approved trade-offs: counterargument +0.145833, synthesis -0.125,
      uncertainty unchanged, utility -0.104166, tokens +2.77%, latency +9.38%.
- [x] Updated the smallest clean Harness authority surface and graduated the
      plan. Commit/push/PR remain unrequested.

## Links

- [Active plan](../260823-2104-resolved-capability-contract-v1/plan.md)
- [Test report](./test-260824-2303-resolved-capability-phases-3-4.md)
- [Code review](./code-review-260824-2352-resolved-capability-phases-3-4.md)

## Unresolved questions

None.
