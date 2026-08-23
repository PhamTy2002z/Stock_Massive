---
title: "Phase 1: Contracts, compact fixtures, and version identity"
status: done
priority: P1
effort: 12h
depends_on: []
---

# Phase 1: Contracts, compact fixtures, and version identity

## Context links

Implement the frozen-environment contract from
[`quality-safety-and-operations.md`](../../docs/Harness/quality-safety-and-operations.md)
and the Evaluation lane from
[`target-architecture.md`](../../docs/Harness/target-architecture.md). Treat
commit `1974c24` and its former `src/eval` package as failure evidence, not a
restore point.

## Overview

Define the smallest stable data model that makes a run reproducible. A dataset
contains case intent, point-in-time evidence references, accepted outcome
properties, known traps, and lane identity. Snapshots are content-addressed and
compact. Version identity derives from actual code/contracts where possible.

## Key insights

- Reuse the old fixture digest and fail-loud mismatch pattern.
- Reject the old broad table capture and production `eval_run` persistence.
- Finance replay distinguishes effective, publication, ingestion, and task
  `as_of` time.
- A case describes valid outcome properties, not one golden sentence.

## Requirements

- [x] Strict, versioned schemas for dataset, case, evidence snapshot, expected
      outcome, trial outcome, trajectory event, grade, and run manifest.
      (`src.eval.contracts`; wire key `schema`, generation-tagged Literals,
      `extra="forbid"`, frozen.)
- [x] Case identity includes surface, family, prompt/Analysis input, entity
      scope, `as_of`, user context, expectations, traps, and snapshot digests.
- [x] Evidence includes source, entity, unit, value, health, effective time,
      publication time, ingestion time, provenance, price basis, and capability.
- [x] Loader recomputes digests; rejects edits, missing/orphan references,
      unknown schemas, and unavailable post-`as_of` evidence before spend.
      (`src.eval.dataset.load_dataset` collects every violation into one
      `DatasetInvalid`.)
- [x] Run manifest stamps Git SHA/dirty state, dataset/case/snapshot digest,
      prompt content/version, resolved tool schemas, model/route, pricing,
      relevant config, grader/rubric versions, and trial count. (Schema defined;
      runtime stamping lands with the Phase 4 runner.)
- [x] Dataset has explicit per-snapshot and total byte/row budgets. Validation
      fails when growth exceeds reviewed limits.
- [x] Generated runs live outside committed dataset paths and are Git-ignored
      (`apps/api/.artifacts/`).
- [x] No production module imports `src.eval`. (Repository scan proof below.)
- [x] Preflight verifies each provider/capability pair against declared
      ownership and executable adapters. A declared but unimplemented cover is
      unavailable, not an assumed fallback. (AST-derived inventory — parsing,
      never importing adapters.)

## Architecture

Create a deep `src.eval.contracts` module for immutable types and wire format.
Keep digest/loader logic in `src.eval.dataset`; keep derived runtime identity in
`src.eval.versions`. Dataset data selects generic expectations; it doesn't
contain grader implementation.

```text
apps/api/eval/datasets/investment-intelligence-v1/
  manifest.json
  cases/*.json
  snapshots/*.json
apps/api/eval/baselines/        # approved summaries only
apps/api/.artifacts/eval/       # generated and ignored
```

Snapshots store only reachable store rows and external results. Shared evidence
uses one content digest. Canonical JSON has sorted keys and stable arrays.

## Related code files

| Action | File | Change |
|---|---|---|
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/__init__.py` | Eval-only package boundary, no side effects. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/contracts.py` | Immutable case, evidence, outcome, trajectory, grade, and manifest contracts. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/dataset.py` | Canonical loader, digest, reference, temporal, and size validation. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/versions.py` | Derive code, prompt, tool, config, model, grader, and dataset stamps. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/eval/datasets/investment-intelligence-v1/manifest.json` | Dataset contract and indexes. |
| Modify | `/Users/typham/Dev/Stock_Massive/.gitignore` | Ignore generated eval artifacts only. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_eval_contracts.py` | Strict schema and serialization tests. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_eval_dataset.py` | Digest, temporal, reference, size, and mutation tests. |

No file is deleted. No database migration is created.

## Implementation steps

1. Write failing tests for canonical round-trip, stable digest, altered payload,
   missing/orphan snapshot, unknown field/schema, post-`as_of` evidence, secret
   shape, and size-budget rejection. ✅
2. Define strict enums and frozen data classes. Refuse unknown fields rather
   than silently dropping them. ✅ (Pydantic v2 frozen models mirroring
   `InternalSnapshot`.)
3. Implement canonical JSON and content-addressed case/snapshot digests. ✅
4. Implement complete preflight that reports all invalid cases before spend. ✅
5. Derive provider-capability identity from ownership, executable adapter
   inventory, and normalized metadata. Never probe a provider to derive it. ✅
6. Derive tool identity from resolved `ToolSchema.as_wire()`, selected toolsets,
   and availability outcomes. ✅
7. Derive prompt identity from actual rendered/stable contract content plus
   `PROMPT_VERSION`/`LOOP_PROMPT_VERSION`; include Git dirty state. ✅
8. Add the manifest shell only. Populate cases after Phase 3 graders define
   executable expectations. ✅

## Todo

- [x] Add contract and dataset tests first.
- [x] Implement strict wire contracts and canonical serialization.
- [x] Implement digests, temporal checks, and size budgets.
- [x] Implement runtime version derivation.
- [x] Add executable provider-capability matrix validation.
- [x] Add artifact ignore rule; verify datasets remain tracked.
- [x] Prove production paths don't import `src.eval`.

## Test scenarios

| Priority | Scenario | Expected result |
|---|---|---|
| Critical | Snapshot value changes without digest update | Refuse before spend. |
| Critical | Publication time is after case `as_of` | Refuse unless explicitly marked as an unavailable trap. |
| Critical | Fixture exceeds byte/row budget | Refuse and identify the owning case/snapshot. |
| High | Tool description/schema changes | Catalog digest changes automatically. |
| High | Prompt changes without manual bump | Prompt content digest changes. |
| Medium | Cases share a snapshot | One digest resolves for both. |

All six scenarios have executable tests; all pass.

## Success criteria

- [x] `pytest tests/test_eval_contracts.py tests/test_eval_dataset.py -q`
      passes (69 tests).
- [x] Loading twice yields identical digests.
- [x] Mutating evidence, time, prompt, or schema changes identity or fails
      preflight.
- [x] Fixture budget prevents a repeat of the deleted million-line capture.
- [x] Repository search proves production code has no `src.eval` import
      (only match is `core.llm.breaker` importing Redis's `eval_script`,
      which is unrelated).

## Risk assessment

Avoid designing a universal evidence ontology before cases exist. Limit v1 to
fields used by the four families and typed extension metadata. Never mirror all
database tables.

## Security considerations

Commit synthetic/public market evidence only. Reject credentials and known
secret-key shapes. User contexts use synthetic IDs and exclude production
prompts, holdings, and memory.

## Next steps

Phase 2 consumes these contracts to build the isolated fixture world and record
real lane outcomes.
