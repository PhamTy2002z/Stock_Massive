---
title: "Investment Intelligence Eval & Replay Harness v1"
description: "Restore measurement authority with frozen finance cases, outcome-first graders, multi-trial replay, and a reproducible release report."
status: in-progress
priority: P1
effort: 72h
branch: develop
tags: [feature, backend, eval, critical]
blockedBy:
  - 260822-1908-agent-core-fail-open
  - 260822-2010-evidence-adjudicating-loop
blocks:
  - 260823-2104-resolved-capability-contract-v1
created: 2026-08-23
---

# Investment Intelligence Eval & Replay Harness v1

## Overview

Restore Stage 0 of the Harness Source of Truth: every prompt, tool, model,
context, and loop change gets reproducible evidence before release. The harness
runs the current Conversation and Symbol Analysis lanes against compact,
point-in-time fixtures, grades financial outcomes before style, and compares a
candidate with an approved baseline across quality, safety, cost, and latency.

This is a measurement system only. It doesn't change answer architecture,
introduce specialists, add MCP, or create a second production runtime.

## Why the previous harness failed

Commit `1974c24` is the primary failure record. It removed `src/eval`, eight
test modules, five Make targets, the eval budget lane, the `eval_run` table, and
more than one million lines of frozen fixture data. The root causes were
architectural, not a lack of implementation effort:

1. The battery graded grounding, citation, and recommendation contracts that
   the replacement assistant no longer produced. The exam and runtime had
   different product contracts, so the gate became impossible to satisfy.
2. The fixture captured broad relational tables and coupled replay identity to
   store schema. Re-freezes produced 160,000-190,000-line files each and made
   ordinary product changes expensive to review.
3. Eval state, budget, and ownership were inserted into production persistence
   and admission. Removing the battery then required a migration and runtime
   budget changes, proving the evaluation lane was not isolated.
4. Threshold and baseline mechanics were sophisticated, but they measured the
   obsolete exam. Operational correctness couldn't rescue semantic mismatch.

## Anti-repeat contract

The new harness may reuse only proven patterns: content digests, fail-loud
version mismatch, real runtime entry points, multi-trial retention, spend
ceilings, blind rubric review, and incomplete-run refusal. It must not restore
the old package wholesale.

These are implementation blockers, not preferences:

- No eval import from production `src.agent`, `src.alpha`, app startup, or API
  routes. Eval depends inward on public runtime seams; runtime never depends on
  eval.
- No eval database table, Alembic migration, production budget lane, or server
  lifecycle hook in v1. Run records are immutable local artifacts; existing
  Turn/Analysis usage rows live only in the case-local database.
- No full-store capture. Each snapshot contains only rows and external results
  reachable by declared cases, with a reviewed size budget and orphan check.
- No live FiinQuant or VNStock request in validation, smoke, paid trials,
  baseline, comparison, or dataset materialization. Repeating a case never
  repeats a data-provider call.
- No grader for a contract the current runtime doesn't emit. Every expectation
  maps to an observed outcome, trace field, or evidence reference proven in
  code before the case enters the battery.
- No fixed prose answer and no exact trajectory lock unless safety or protocol
  requires it. Outcome properties admit multiple valid research paths.
- No threshold before a clean baseline distribution is reviewed. Candidate
  flags can never weaken repository-owned policy.
- No model judge for deterministic financial facts, time, evidence identity,
  tool settlement, or authorization.
- No “green” partial run. Missing cases, spend exhaustion, unavailable grader,
  version mismatch, or unrecorded external access stays explicit.

## Scope decision

The requested scope is held. Existing protocol tests and ops metrics remain in
place, but they don't answer whether a model produced a correct, timely, useful
financial outcome.

The v1 boundary is four task families and 16 cases:

- 4 fact, unit, and as-of cases;
- 4 multi-axis synthesis cases;
- 4 sparse, refused, and conflicting-evidence cases;
- 4 adversarial, untrusted-content, and policy cases.

## Architecture decision

`src.eval` is an Evaluation lane around existing seams, not a dependency of
`src.agent` or `src.alpha`. A dedicated CLI process installs fixture-backed
adapters behind the real tool contracts, wraps the real `LLMClient`, invokes the
real lifecycle entry points, and records observable outcomes and trajectories. Hard
graders run before any rubric judge. JSON is the canonical artifact; Markdown
is a deterministic review projection.

## Development provider boundary

Stage 0 must reflect what the two current data packages can actually serve,
without spending their scarce allowance during evaluation.

| Capability | Current executable owner | Development limit | Eval v1 decision |
|---|---|---|---|
| Market/current | FiinQuant main; VNStock history cover | FiinQuant entitlement can expire; realtime free tier is capped at 33 symbols; adapter caps historical batches at 100. | Replay frozen normalized snapshots. Never call FiinQuant during a trial. |
| Market index | FiinQuant only | No VNStock cover is implemented because price-basis semantics differ. | Run only with a frozen FiinQuant index series; otherwise assert a named data gap. |
| Valuation | FiinQuant implementation only | Ownership declares VNStock cover, but no VNStock valuation adapter exists. | Don't assume fallback. Freeze FiinQuant valuation when available; otherwise refuse. |
| Reference/share/foreign room | VNStock main | One batched board call is affordable; FiinQuant free tier has empty share counts and 403 foreign-room behavior. | Replay persisted VNStock-normalized data. Don't infer outstanding from listed shares. |
| Fundamentals | VNStock main | No batch; three live calls per symbol (income and balance required, cash flow degradable); community response exposes at most eight periods. | Keep cases narrow/frozen. Missing periods and fields remain explicit gaps. |
| VNStock account quota | Shared Redis arbiter | 20 requests/min guest, 60/min keyed, 3,000/hour; collector lease excludes other lanes; Redis failure fails closed. | Eval consumes zero live-provider quota. Materialization reads persisted rows under `store_only_execution()`. |

The gate measures harness/model behavior over a known evidence boundary. It
doesn't benchmark provider uptime or breadth. Provider conformance and collector
health remain separate suites. Dataset refresh may read only rows already
admitted and persisted by normal collection; it never fetches providers.

```text
versioned dataset + frozen evidence
              |
              v
fixture world -> TurnService / produce_analysis -> persisted outcome + trace
              |                        |
              +------------------------+
                           |
                           v
 deterministic graders -> optional blinded rubric -> trial aggregation
                           |
                           v
              canonical JSON -> Markdown report -> release decision
```

## Cross-plan dependencies

| Relationship | Plan | Required state |
|---|---|---|
| Blocked by | [`260822-1908-agent-core-fail-open`](../260822-1908-agent-core-fail-open/plan.md) | Resolve or explicitly accept remaining `loop.py`/`executor.py` defects before baseline freeze. |
| Blocked by | [`260822-2010-evidence-adjudicating-loop`](../260822-2010-evidence-adjudicating-loop/plan.md) | Integrate evidence tools, Analysis loop, trace schema, and migration; disposition the live HPG check. |
| Blocks | Harness Stage 1 and later stages | No capability-plane expansion graduates without measurement authority. |

Phase 1 can start while dependency disposition is being completed. A baseline
cannot be approved from a dirty or partially integrated runtime.

## Phases

| # | Phase | Status | Depends on |
|---|---|---|---|
| 1 | [Contracts, compact fixtures, and version identity](./phase-01-start.md) | Done | Dependency contracts understood |
| 2 | [Replay lane and trajectory capture](./phase-02-replay-lane-and-trajectory-capture.md) | Done | Phase 1 |
| 3 | [Deterministic graders and golden battery](./phase-03-deterministic-graders-and-golden-battery.md) | Done | Phases 1-2 |
| 4 | [Multi-trial reports, baseline, and release gate](./phase-04-multi-trial-reports-baseline-and-release-gate.md) | In Progress | Phases 1-3; blockers stabilized |

## Success criteria

- [x] One repository-owned command runs all 16 cases against one frozen dataset
      and emits reproducible JSON and Markdown artifacts.
- [x] Conversation uses `TurnService.create` and its persisted assistant
      message; Symbol Analysis uses `produce_analysis` with `analysis_producer`
      and its published immutable payload. Both retain current model/tool/
      evidence/budget contracts underneath.
- [x] Every artifact stamps code SHA, dirty state, dataset digest, case
      contract, prompt, tool catalog, model route, pricing/config, and trials.
- [x] Deterministic graders cover figures, units, as-of, evidence references,
      refusal/uncertainty, terminal settlement, and policy.
- [x] A blinded rubric covers synthesis, counterargument, uncertainty, and
      decision utility without deciding deterministic financial facts.
- [x] Baseline-versus-candidate output separates hard regressions from quality,
      cost, and latency trade-offs and shows failed samples.
- [x] Smoke validation is offline and free; a paid multi-trial run requires an
      explicit model mode and a run-level LLM spend ceiling. Data-provider
      spend remains zero in every mode.
- [x] No eval package is imported by production, no migration is added for eval
      state, and no raw private trajectory is retained by default.
- [ ] Initial numeric thresholds are committed only after baseline review; a
      candidate cannot supply or weaken its own gate policy.
- [ ] The clean paid 3 x 16 baseline hard-passes all 48 trials with every
      expected hard fact reachable through the offered frozen tool surface;
      prose quality remains visible in the blinded rubric, not a keyword gate.

## Non-goals

- General subagents, specialist routing, MCP, autonomous goals, or compaction.
- New market-data providers, financial-statement persistence, or graph DB.
- Exact tool-sequence grading except for safety and protocol invariants.
- A composite score that lets quality hide safety or temporal failure.
- Production telemetry containing prompts, tool bodies, or portfolio content.

## Validation strategy

Run focused eval tests first, then the API suite. Run a smoke battery twice and
compare canonical artifact content after excluding run identity and timestamps.
Run the first paid baseline only after dependency and budget approval. Stage 0
is incomplete until a maintainer reproduces the report from the committed
dataset and approved gate policy.

## Risks and controls

| Risk | Control |
|---|---|
| Harness tests a lookalike runtime | Invoke `TurnService.create` and `produce_analysis(..., analysis_producer(...))`; grade persisted user-facing artifacts, not inner fragments. |
| Fixture becomes another million-line dump | Store reachable rows/results only; content-address snapshots; enforce reviewed byte/row budgets. |
| Judge model self-certifies facts | Deterministic graders own figures, units, time, evidence, settlement, and policy. |
| Candidate games the gate | Dataset/policy are repository-owned; candidate flags cannot override hard dimensions. |
| Model variance creates noisy decisions | Use paired multi-trial runs, report counts/intervals, preserve failed samples. |
| Eval leaks private data | Commit synthetic/public cases only; redact artifacts by schema; keep trajectories out of Git. |
| Eval burns development data quota | Wrap materialization/runs in `store_only_execution()` and fail before credentials, quota arbitration, or network. |

## Validation log

### Paid-baseline contract audit — 2026-08-24

- Clean commit `8f9cb06` completed all 48 paid trials with zero provider calls,
  but only 10 hard-passed. Conversation was 0/30 and Analysis 10/18.
- The result exposed an exam defect rather than an approvable model baseline:
  the fixture catalog did not expose production-equivalent discovery and some
  case facts were not reachable from their pinned snapshots. Keyword-based
  semantic expectations also contradicted the no-fixed-prose contract.
- Phase 4 is reopened for contract repair and a clean 48/48 rerun. Existing
  lifecycle, spend, isolation, report, and zero-provider-call evidence remains
  valid.

### Harness remediation — 2026-08-24

- Production-equivalent signal discovery/lookup contracts now drive replay;
  every hard figure is validated as reachable from frozen results before any
  paid call. Fixture toolsets expose only backed tools and restore global state
  after each case.
- Keyword-based semantic expectations moved out of the hard policy. Numeric,
  unit, evidence, entity-scope, lifecycle, temporal, settlement, and policy
  graders remain deterministic and mutation-tested.
- Validation: 277 blast-radius tests passed; offline smoke completed 16/16 with
  zero hard failures; the paid diagnostic completed 48/48 with 48 hard passes
  and zero provider calls (`9f40fe732d9a85b9`).
- Full API suite passed 2,661 tests with one skipped and one pre-existing stale
  topology-doc assertion: `docs/streaming-topology.md` was already absent from
  `HEAD` and is unrelated to this harness diff.
- The diagnostic manifest is intentionally marked dirty. Phase 4 remains
  `in-progress` until these changes are committed, reproduced from the clean
  commit, and explicitly approved as the baseline/policy.

### Phases 3-4 — implementation complete; paid approval pending (2026-08-23)

- Phase 3 deterministic graders, blinded rubric, and 16-case golden battery are
  complete. Phase 4 multi-trial harness, canonical reports, compatibility,
  gate policy, CLI/Make surfaces, and offline release checks are implemented.
- Full Phase 1-4 eval suite: 162 passed. An invalid cold-race cancellation test
  sentinel was corrected; the cancellation coverage and full suite are green.
- `make eval-validate`: 16 cases, 3 snapshots, 9 hard graders; dataset digest
  `8e829faa380d64f2`.
- Two full offline smokes completed 16/16 cases each with `hard_failures=0`,
  `rubric.available=16`, and `data_provider_calls=0`. Canonical content was
  identical after excluding run identity and artifact digest.
- `py_compile` and CLI-import network capture were clean. Independent code
  review completed with no concerns. Teardown left no eval database or process.
- Paid baseline/threshold approval was intentionally not run without the
  required approved paid route, spend ceiling, and owner review. Phase 4 stays
  `in-progress`, the plan stays `in-progress`, and Stage 0 stays Target.
- Current checklist progress: 68/70 (97%); 3/4 phases done.

### Phase 2 — done (2026-08-23)

- Replay and trajectory capture implemented in `src/eval/recording.py`,
  `src/eval/world.py`, and `src/eval/runner.py`, with builders and coverage in
  `tests/eval_world.py`, `tests/test_eval_recording.py`, and
  `tests/test_eval_runner.py`.
- Focused Phase 2 suite: 37 passed. Phase 1+2 eval suite: 106 passed. Broader
  blast-radius suite: 277 passed.
- Independent review clean: no actionable findings.
- Teardown verification clean: no leftover throwaway database or process; the
  development LLM usage ledger remained unchanged.
- Plan progress: 37/70 checklist items (52%); 2/4 phases done. Phases 3-4 remain
  pending, so the plan stays `in-progress`.
- Docs impact: none. This eval-only internal lane changes no user setup,
  commands, or public production contract.

### Phase 1 — done (2026-08-23)

- 69 tests across `test_eval_contracts.py` / `test_eval_dataset.py` pass.
- Shell manifest `investment-intelligence-v1` loads with digest
  `e6806c3785fb81be`; budgets committed at review time (64 KiB / 250 rows per
  snapshot, 512 KiB / 2 000 rows total).
- Provider-capability identity derived by parsing adapter source with `ast`
  (never importing): fiinquant executes market/market_index/valuation; vnstock
  executes reference/fundamental/corporate_action; valuation's declared
  vnstock cover is reported unavailable, matching the plan boundary table.
- Boundary proof: no production module imports `src.eval`.
- Pre-existing develop failures (25 failed / ~70 errors in transport, auth,
  analysis-reads, message-flags, on-demand-lane suites) reproduce without this
  change and are unrelated.

### Planner verification results

- **Tier:** Standard (4 phases)
- **Claims checked:** 28
- **Verified:** 28
- **Failed:** 0
- **Unverified:** 0

Verified owners include `AgentLoop.run`, `generate_fragment_in_loop`,
`LLMClient.complete`, `Usage`, `ToolContext`, tool registry/toolsets, prompt
versions, Analysis trace reads, `apps/api/Makefile`, and current test fakes. Git
history confirms both the size and semantic-removal rationale of `1974c24`.

<!-- slug: investment-intelligence-eval-replay-harness -->
