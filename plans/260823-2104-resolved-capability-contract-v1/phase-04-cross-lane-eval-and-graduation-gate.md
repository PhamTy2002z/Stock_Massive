---
phase: 4
title: "Cross-Lane Eval and Graduation Gate"
status: completed
priority: P1
effort: "12h"
dependencies: [3]
---

# Phase 4: Cross-Lane Eval and Graduation Gate

## Context links

- [Plan](./plan.md)
- [Phase 3](./phase-03-consumer-migration-and-duplicate-owner-removal.md)
- [Eval/replay harness](../260823-1744-investment-intelligence-eval-replay-harness/plan.md)
- [Quality, safety and operations](../../docs/Harness/quality-safety-and-operations.md)
- [Harness roadmap](../../docs/harness-roadmap.md)

## Overview

Make resolved execution policy part of eval identity, run cross-lane regression
proof, and graduate only after baseline comparison shows behavior parity and
provider/data boundaries remain intact.

## Requirements

### Functional

- [x] Stamp deterministic resolved-contract identity: schema, availability
      class, effect, idempotency, access, trust, concurrency, output limit,
      display identity, stable handler identity, contract version, ordered
      toolset selection, and resolver version.
- [x] Exclude callables, secrets, raw env/probe errors, credentials, account
      state, and volatile object identity from artifacts.
- [x] Add mutation tests proving each behavior-changing field changes catalog/
      run compatibility identity.
- [x] Run Conversation and Symbol Analysis through real lifecycle entry points
      with frozen evidence; verify all calls settle and provider calls remain 0.
- [x] Compare candidate versus the approved baseline or fail loud into an
      owner-reviewed identity reset. Any new hard regression or incomplete case
      blocks graduation; cost/latency changes are explicit trade-offs.
- [x] Verify one hypothetical read-only registration requires only its
      registration plus intentional toolset selection and tests—no executor,
      budget, wrapper, trace, or display name-table edit.

### Non-functional

- [x] Offline smoke is deterministic/free. Paid multi-trial comparison uses the
      repository policy and ceiling; candidate cannot weaken it.
- [x] No eval import from production, eval migration, live materialization,
      provider/quota access, or raw private trajectory persistence.
- [x] Update evergreen Harness docs only after evidence exists.

## Architecture

```text
frozen dataset + approved policy
            |
resolved tool surface identity ---- candidate runtime
            |                              |
            +------ real Chat/Analysis ----+
                           |
           hard graders -> rubric -> comparison
                           |
       complete + no hard regression + zero provider calls
                           |
                      graduate Stage 1 slice
```

The eval catalog previously stamped only model-facing `ToolSchema`. This phase
stamps fields that can change execution/safety while keeping handler bodies and
secrets out of canonical artifacts.

## File inventory

| Action | File | Change | Test impact |
|---|---|---|---|
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/versions.py` | Deterministic resolved-surface identity/version stamp. | Eval version tests. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/contracts.py` | Only if completed Stage 0 schema lacks compatible catalog stamp. | Round-trip/mismatch. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/world.py` | Only if final fixture-world isolation must install/restore resolved-surface cache state. | Cross-case isolation. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_eval_contracts.py` | Field mutation and secret/callable exclusion. | Focused. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_eval_runner.py` | Cross-lane same-surface, provider access, settlement. | Focused. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_eval_harness.py` | Completeness/comparison/hard gate if final Stage 0 owner. | Focused. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/eval/gate-policy.json` | Compatibility version only; never weaken policy. | Override tests. |
| Modify | `/Users/typham/Dev/Stock_Massive/docs/Harness/README.md` | Record owner/command only after graduation. | Link/claim check. |
| Modify | `/Users/typham/Dev/Stock_Massive/docs/harness-roadmap.md` | Mark only this H1 slice complete with evidence. | Claim check. |

Paths under `src.eval`, eval tests, and policy must be reconciled against the
completed Stage 0 layout before implementation; do not overwrite its in-progress
untracked files or infer final APIs from current partial work.

## Interface checklist

- [x] Tool catalog/run manifest uses resolved surface, not reconstructed table.
- [x] Serialization is deterministic; offered tool order remains semantic.
- [x] Compatibility mismatch names changed field/version.
- [x] Fixture world installs/restores registry/surface without cross-case leak.
- [x] Provider guard trips before credentials, quota, network, or method.
- [x] Report states provider calls = 0 and frozen source/basis/time.

## Implementation steps

1. Re-read completed Stage 0 files and policy; reconcile final owners before
   editing eval files.
2. Write catalog mutation tests first. Change one resolved field at a time and
   require digest/compatibility change.
3. Replace schema-only identity with deterministic resolved projection. Redact
   by construction, not post-hoc string replacement.
4. Add cross-lane scripted smoke and hypothetical tool-registration proof.
5. Run narrow contract/runner/harness tests, then affected agent/Analysis suites
   and lint/type checks.
6. Run offline smoke twice and compare stable canonical fields/report.
7. Run repository-owned candidate comparison. Stop on incomplete measurement or
   new hard regression.
8. Review quality/cost/latency; update smallest Harness docs surface only after
   approval.

## Test scenarios

| Priority | Scenario | Expected result |
|---|---|---|
| Critical | Effect/trust/concurrency/version changes | Digest changes; compatibility enforced. |
| Critical | Artifact contains env/callable/credential/raw probe | Serialization test fails. |
| Critical | Fixture misses result and code attempts provider | Incomplete; zero provider/quota/network calls. |
| Critical | One hard failure among trials | Gate fails; aggregation cannot hide it. |
| High | Same smoke twice | Stable canonical projection/report. |
| High | Add hypothetical read-only tool | Only registration + toolset selection needed. |
| High | VNStock valuation selected as fallback | Named unavailable; no provider attempt. |
| Medium | Unknown usage/cost | Unknown, never zero. |

## Validation commands

Resolve exact Make/CLI targets from completed Stage 0. Minimum sequence:

```text
pytest tests/test_agent_capability_contract.py tests/test_agent_tool_registry.py tests/test_agent_tool_definitions.py -q
pytest tests/test_agent_tool_executor.py tests/test_agent_tool_budget.py tests/test_agent_loop.py tests/test_analysis_loop.py -q
pytest tests/test_agent_transport.py tests/test_agent_signal_tools.py tests/test_agent_untrusted_results.py tests/test_agent_ops_query.py -q
pytest tests/test_eval_contracts.py tests/test_eval_runner.py tests/test_eval_harness.py -q
make eval-smoke
make eval-compare   # approved baseline/policy; explicit route/ceiling if required
make test
```

If final Stage 0 names differ, live help/Makefile is authoritative; update this
plan before execution rather than inventing a target.

## Dependency map

```text
Phase 3 parity -> catalog mutation proof -> offline smoke -> baseline compare -> docs/graduation
```

## Success criteria

- [x] Focused/broad suites pass; pre-existing failures are dispositioned without
      weakening tests.
- [x] Offline smoke complete/deterministic across two runs on stable fields.
- [x] Candidate is complete, zero-provider-call, and has no new hard regression;
      the owner accepted the fail-loud resolved-identity reset and trade-offs.
- [x] Hypothetical tool proof meets Stage 1 graduation criterion.
- [x] Docs link actual artifacts/commands; no future capability marked complete.

## Risk assessment

- **Stage 0 final API differs from partial files.** Signal: named eval symbol/path
  absent after dependency completion. Response: reconcile phase/plan before cook.
- **Digest churn without behavior change.** Signal: identical surfaces differ by
  callable repr/order. Response: canonical explicit fields/stable versions.
- **Baseline incompatibility bypassed.** Signal: comparison proceeds after
  contract version change. Response: fail loud or reviewed reset.
- **Provider quota consumed.** Signal: access guard/quota metric changes.
  Response: abort incomplete and repair fixture boundary.
- **Clean architecture worsens outcome.** Signal: hard or accepted trade-off
  regression. Response: reject/revert; cleanliness is not release evidence.

## Security considerations

Artifacts are local/redacted: no credentials/account state, private memory/
portfolio, raw private trajectory, or hidden reasoning. Candidate flags cannot
weaken repository policy.

## Next steps

After approval, create a separate plan for typed lifecycle and stable root/
attempt/call/evidence identity. Do not begin Stage 2 planner work here.

## Validation log

### 2026-08-24 — code and offline gate

- Run identity now hashes the ordered case/lane-to-resolved-surface mapping,
  including execution, access, trust, display, availability, handler, version,
  and selection facts while excluding callables, secrets, probes, env names,
  expiry, and object identity.
- Post-review focused integration passed 414 tests. The earlier broad run
  completed with 2,828 passes and one dispositioned out-of-slice failure for
  the absent `docs/streaming-topology.md` file.
- Two fresh offline smoke runs each completed 16/16 cases: Conversation 10,
  Analysis 6, zero hard failures, zero provider calls. Stable canonical JSON
  was byte-identical after removing run ids, timestamps, and artifact digest;
  the scoped tool identity digest was `ee10c69a9f909d30`.
- Code review passed with no Critical or Important finding. Eval registry and
  toolset installation remains intentionally single-flight; in-process parallel
  eval must add explicit ownership before it is enabled.
- Owner-authorized paid candidate `e78715254eb08800` completed 48/48 trials
  with zero hard failures, zero provider attempts, and USD 0.6309487 recorded
  candidate-plus-rubric cost. The old approved baseline differs only in the
  intentionally expanded tool identity, so mechanical comparison fails loud
  and records that a reviewed reset is required.
- Quality review versus the old exam: counterargument mean +0.145833,
  synthesis -0.125, uncertainty unchanged, utility -0.104166; tokens +2.77%
  and mean latency +9.38%. The repository owner accepted the reviewed reset and
  these report-only trade-offs on 2026-08-25.
- Candidate `e78715254eb08800` is now the approved baseline; its canonical JSON
  is promoted as `approved-baseline-e78715254eb08800.json`, and the baseline
  summary records lineage from `36bc44f7c00966cd` plus tool identity
  `ee10c69a9f909d30`.
- The smallest clean Harness authority surface links the paid artifact and
  explicitly graduates only this H1 resolved-capability slice. The concurrently
  edited Harness roadmap was not modified or used to claim all of H1 complete.
