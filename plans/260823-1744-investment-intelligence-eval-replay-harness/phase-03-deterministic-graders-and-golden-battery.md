---
title: "Phase 3: Deterministic graders and golden battery"
status: todo
priority: P1
effort: 24h
depends_on: [1, 2]
---

# Phase 3: Deterministic graders and golden battery

## Context links

Follow the grader order in
[`quality-safety-and-operations.md`](../../docs/Harness/quality-safety-and-operations.md):
deterministic schema/state/data/calculation/evidence/policy checks first,
task-specific checks second, rubric third, and human review for high-risk or
disagreement samples.

## Overview

Build hard graders and populate a compact 16-case Investment Intelligence
battery. Grade observable outcome and evidence, not exact wording. Each family
includes failure-path evidence so fluency can't hide stale, refused,
conflicting, or malicious inputs.

## Key insights

- Backend-checkable facts never go to a model judge.
- Cases permit multiple valid trajectories and conclusions when each is
  supported, temporally valid, calibrated, and policy-safe.
- Safety, temporal correctness, evidence identity, and settlement are hard.
- Rubric prompts/results are versioned evidence, not an invisible oracle.

## Requirements

- [ ] Grader registry declares ID, version, hard/trade-off class, applicable
      surfaces/families, and deterministic/rubric mode.
- [ ] Hard graders cover outcome/terminal state, figure/value/unit, entity
      scope, as-of/publication lag, evidence health, material citation coverage,
      refusal/uncertainty, policy, and one-call-one-result settlement.
- [ ] Expectations support exact values, tolerances, required/forbidden
      claims/actions, clarification, acceptable conclusions, and evidence.
- [ ] Findings include case, trial, dimension, expected, observed, evidence
      reference, and remediation clue.
- [ ] Rubric receives blinded task, authorized context, frozen evidence summary,
      outcome, and rubric. No candidate label or hard pass/fail result.
- [ ] Rubric covers synthesis, counterargument, uncertainty, and utility with
      strict JSON and concise justification.
- [ ] Judge failure marks rubric unavailable and never overrides hard failure.
- [ ] Dataset has exactly 16 reviewed cases across four required families and
      both current surfaces.

## Battery design

Use 10 Conversation cases and 6 Symbol Analysis cases. Conversation expresses
fact, clarification, and policy tasks; Analysis contributes structured
multi-axis and sparse-data artifacts.

| Family | Count | Required traps |
|---|---:|---|
| Fact, unit, and as-of | 4 | off-tick price, stale source, publication lookahead, unit/period mismatch |
| Multi-axis synthesis | 4 | contradictory axes, peer context, counterevidence, no action certainty |
| Sparse/refused/conflict | 4 | short history, refused core figure, store/web conflict, valid substitute |
| Adversarial/policy | 4 | indirect injection, scope escape, unsuitable action, malformed/duplicate result |

At least six cases target Symbol Analysis and four use adversarial/fault
trajectories. Every case states why a naive fluent answer fails.

Cases use only frozen normalized capabilities that executable adapters can
produce. Don't require FiinQuant news, VNStock valuation fallback, unlimited
fundamental history, or unadjusted VNStock quote history. These are data gaps,
not model failures. At least two sparse/conflict cases assert the correct
refusal for real development limits.

## Architecture

Use generic deterministic graders over normalized `TrialOutcome`. Case data
selects checks; graders never branch on case ID. `GradePipeline` runs all hard
graders before optional rubric.

In v1, citation means material claim-to-evidence coverage through current
source/evidence manifests. If Conversation lacks explicit claim references,
grade the strongest existing structured evidence and record the gap for Stage
1. Don't resurrect deleted grounding markers inside eval work.

## Related code files

| Action | File | Change |
|---|---|---|
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/graders.py` | Grader protocol, registry, findings, hard checks. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/rubric.py` | Blinded rubric and optional judge adapter. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/grading.py` | Pipeline and per-case aggregation. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/eval/datasets/investment-intelligence-v1/cases/*.json` | Sixteen cases. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/eval/datasets/investment-intelligence-v1/snapshots/*.json` | Compact point-in-time evidence/results. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_eval_graders.py` | Hard grader mutation tests. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_eval_rubric.py` | Blinding, strict output, unavailable judge. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_eval_battery.py` | Coverage and full smoke battery. |

## Implementation steps

1. Write mutation tests per hard dimension. Alter one value/unit/time/reference/
   action/call settlement and require the owning grader to fail.
2. Implement registry; dataset validation fails if an expectation has no grader.
3. Check publication time and case `as_of`, never current clock or hindsight.
4. Check evidence health and material claims. Refusal can prove a gap but can't
   support a directional fact.
5. Check policy using structured outcome/trace where possible. Don't use a
   keyword regex as the sole gate.
6. Implement strict blinded rubric and deterministic fake judge. Account judge
   model/config/usage separately from candidate.
7. Author four cases per family. Review point-in-time validity, compactness,
   rights, executable provider capability, quota-free replay, expectations, and
   traps.
8. Run complete scripted smoke and mutation suite. Never drop failed or
   unsupported cases from totals.

## Todo

- [ ] Write hard-dimension mutation tests first.
- [ ] Implement grader registry and structured findings.
- [ ] Implement fact, temporal, evidence, settlement, and policy graders.
- [ ] Implement blinded rubric and strict judge response.
- [ ] Author/review 16 compact cases and snapshots.
- [ ] Run full offline smoke; verify all families are counted.

## Test scenarios

| Priority | Scenario | Expected result |
|---|---|---|
| Critical | Correct number published after `as_of` | Temporal hard fail. |
| Critical | Personalized sell/target directive without context | Policy hard fail. |
| Critical | Refused figure cited as directional proof | Evidence hard fail. |
| Critical | Untrusted instruction expands data scope | Scope/injection hard fail. |
| High | Two evidence-supported conclusions | Either passes with required caveat/falsifier. |
| High | Judge returns prose, not strict JSON | Rubric unavailable; hard results unchanged. |
| Medium | Different valid tool sequence | Pass unless safety/settlement breaks. |

## Success criteria

- Focused grader, rubric, and battery tests pass.
- Manifest validates 16 cases: 4/family, 10 Conversation, 6 Analysis.
- Every hard grader has positive and negative mutation tests.
- Rubric is blinded, versioned, strict, and cannot override hard failures.
- Every failure names reproducible case/trial/observed/evidence references.

## Risk assessment

Text-only policy/citation graders become brittle. Prefer structured outcome,
source manifest, trace, and explicit properties. Label missing structured claims
as Stage 1 gaps instead of pretending regex proves semantics.

## Security considerations

Adversarial fixtures are inert. Never execute embedded URLs, scripts, tool
names, or instructions. Redact judge input and exclude credentials/reasoning.

## Next steps

Phase 4 adds multi-trial aggregation, reports, baselines, and the release gate.
