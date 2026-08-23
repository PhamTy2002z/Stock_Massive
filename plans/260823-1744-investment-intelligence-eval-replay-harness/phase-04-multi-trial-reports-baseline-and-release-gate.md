---
title: "Phase 4: Multi-trial reports, baseline, and release gate"
status: todo
priority: P1
effort: 16h
depends_on: [1, 2, 3]
---

# Phase 4: Multi-trial reports, baseline, and release gate

## Context links

Close Stage 0 in
[`ai-capability-roadmap.md`](../../docs/Harness/ai-capability-roadmap.md). Apply
the release matrix and hard/trade-off split from
[`quality-safety-and-operations.md`](../../docs/Harness/quality-safety-and-operations.md).
Don't approve a baseline until both blocking plans are integrated and their
remaining defects are dispositioned.

## Overview

Turn trials into a reproducible decision artifact. Run identical dataset/trial
policy for baseline and candidate, retain every outcome, separate candidate and
rubric spend, and fail release on hard regressions or incomplete measurement.
Quality/cost thresholds remain absent until the first baseline is reviewed.

## Key insights

- Multi-trial retains attempts; it never averages away a safety failure.
- JSON is authority. Markdown is generated and adds no independent facts.
- A stopped or partially funded run has no comparable score.
- Baseline identity includes every behavior-changing version.

## Requirements

- [ ] CLI supports dataset validation, offline smoke, explicit paid run,
      baseline comparison, and report rendering.
- [ ] Paid policy runs at least three trials per case; repository policy owns
      trial count, not candidate flags.
- [ ] Run ceiling stops before overspend and marks incomplete; incomplete runs
      can't pass or become baseline.
- [ ] Canonical JSON contains manifest, trials, findings, rubric, usage, cost,
      latency, failures, completeness, and artifact digest.
- [ ] Aggregation reports counts and uncertainty by case, family, surface, and
      dimension; hard dimensions expose any-trial failure.
- [ ] Baseline comparison requires compatible dataset/case/grader/rubric
      identity or explicit reviewed reset.
- [ ] Gate policy is committed and separately versioned. Candidates can't
      override hard dimensions, trials, ceilings, or thresholds.
- [ ] Initial policy fails on incomplete run and new hard regression. Quality,
      cost, and latency remain report-only until baseline review locks them.
- [ ] Markdown includes reproduction command, environment stamp, comparison,
      failed samples, and artifact digest.
- [ ] Artifacts are private/redacted by default. Approved baseline summaries
      contain no secret/private content.
- [ ] Reports prove `data_provider_calls = 0` and summarize frozen provider,
      capability, price basis, and freshness used by the cases.

## Architecture

`EvalHarness` owns preflight, trial scheduling, ceiling, and completeness.
`baseline.compare` consumes two immutable runs and repository policy. `report`
renders JSON to Markdown. CLI is a thin composition root.

The paid route may be real, but persistence and admission remain case-local.
The run guard computes the next reservation against the gate-policy ceiling
before calling the existing reserved client. This preserves production
Turn/Analysis budget semantics without recreating the deleted eval budget lane
or writing to the application's monthly ledger.

```text
make eval-smoke     # offline contract + scripted battery
make eval-run       # explicit paid run, route and ceiling required
make eval-compare   # immutable candidate versus approved baseline
make eval-gate      # validate + run + compare under committed policy
```

The implementation's live CLI help is authoritative; Make targets are the
stable maintainer surface.

## Related code files

| Action | File | Change |
|---|---|---|
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/harness.py` | Trials, preflight, ceiling, completeness, aggregation. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/baseline.py` | Compatibility, reset contract, comparison. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/report.py` | Canonical persistence and Markdown projection. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/cli.py` | Thin parser and exit-code contract. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/__main__.py` | Module entry point. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/eval/gate-policy.json` | Approved trials, ceiling, hard checks, thresholds. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/eval/baselines/investment-intelligence-v1.json` | Approved clean baseline summary. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/Makefile` | Stable eval targets. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_eval_harness.py` | Trial, ceiling, completeness, aggregation. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_eval_report.py` | Artifacts, compatibility, policy, exits. |
| Modify | `/Users/typham/Dev/Stock_Massive/docs/Harness/README.md` | Link operational Stage 0 only after completion. |
| Modify | `/Users/typham/Dev/Stock_Massive/docs/Harness/ai-capability-roadmap.md` | Record actual Stage 0 evidence/status. |

## Implementation steps

1. Write tests for partial-run refusal, fixed trials, spend exhaustion, baseline
   mismatch, any-trial hard regression, deterministic report bytes, and policy
   override attempts.
2. Schedule sequentially for reproducibility/provider safety. Add bounded
   concurrency only after measured need and proven isolation.
3. Aggregate usage/latency from recorders. Price with stamped config; unknown
   usage stays unknown, never zero.
4. Persist canonical runs atomically with digest. Render Markdown from persisted
   JSON only.
5. Implement baseline compatibility/reset. Reset creates reviewed lineage; it
   doesn't compare incompatible exams.
6. Load gate policy from repository. Reject attempts to lower trials, ceilings,
   or hard checks.
7. Add Make targets. Smoke stays offline; paid gate isn't hidden in `make test`.
8. Add store-only dataset materialization. It reads persisted snapshots and
   never starts collectors/providers; absent evidence stops or becomes a
   reviewed data-gap case.
9. Run focused tests, full API tests, then smoke twice and compare stable fields.
10. After blockers stabilize, run the first clean paid baseline. Present
   distributions, failures, cost, and latency for owner review.
11. Only after approval, commit baseline summary and trade-off thresholds. Run
    candidate comparison, then update Harness SOT status.

## Todo

- [ ] Write harness/report/gate tests first.
- [ ] Implement trials, ceiling, canonical report, and digest.
- [ ] Implement compatibility, reset lineage, and gate policy.
- [ ] Add Make targets and CLI exits.
- [ ] Add store-only materialization and zero-provider-call report assertion.
- [ ] Pass focused/full tests and repeat smoke.
- [ ] Obtain explicit baseline/threshold approval.
- [ ] Commit approved baseline/policy and update Stage 0 status.

## Test scenarios

| Priority | Scenario | Expected result |
|---|---|---|
| Critical | Budget stops after 15/16 cases | Incomplete, no score, non-zero gate. |
| Critical | One trial violates temporal/policy | Hard fail; averages can't hide it. |
| Critical | Candidate requests one trial/weaker policy | Reject override. |
| High | Dataset/grader differs from baseline | Refuse or require reviewed reset. |
| High | Provider omits usage | Cost unknown; no zero-cost claim. |
| Medium | Render same smoke twice | Stable JSON projection and Markdown. |

## Success criteria

- Focused harness/report tests pass.
- `make eval-smoke` is offline, complete, deterministic, and includes all cases
  and trials.
- Full API tests pass except explicitly proven pre-existing failures; none is
  hidden or weakened.
- Paid run can't exceed ceiling or publish partial score.
- One command reproduces baseline/candidate JSON and Markdown from committed
  dataset and policy.
- Stage 0 changes status only after baseline/threshold approval.

## Risk assessment

Paid eval can be slow/expensive. Keep smoke separate, hard-cap run cost, start
sequentially, and report marginal cost per successful case. Don't shrink the
full gate when a candidate is difficult; targeted runs are diagnostic only.

## Security considerations

Artifacts are local/ignored. Write atomically, redact before persistence, and
never publish automatically. Baseline summaries include IDs, scores, usage, and
redacted failure excerpts only.

## Next steps

After Stage 0, start Stage 1 resolved capability and evidence-reference
contracts. “Explain a material move” remains the first user-visible capability.
