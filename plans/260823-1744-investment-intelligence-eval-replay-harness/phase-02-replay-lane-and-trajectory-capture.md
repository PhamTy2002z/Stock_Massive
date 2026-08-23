---
title: "Phase 2: Replay lane and trajectory capture"
status: done
priority: P1
effort: 20h
depends_on: [1]
---

# Phase 2: Replay lane and trajectory capture

## Context links

Use the current lifecycle seams in `TurnService.create`, `produce_analysis`,
`analysis_producer`, and `LLMClient.complete`. The inner `AgentLoop` and Analysis
evidence loop remain real. Preserve one-call-one-result, persistence ordering,
bounded recovery, tool ordering, budget, and fail-open invariants.

## Overview

Build an Evaluation lane that invokes both real orchestrators against a frozen
world. Swap only unstable boundaries: model route, external provider response,
clock, and case-local store. Observe public protocol objects; don't fork loops,
read private mutable state, or record hidden reasoning.

## Key insights

- `LLMClient.complete` already carries request, completion, usage, finish
  reason, and provider request ID.
- `TurnService` persists intent before execution and settles through one
  terminal transaction; grade its stored assistant message, not `TurnOutcome`
  alone.
- `analysis_producer` injects client/session/clock and selects the real evidence
  loop; `produce_analysis` owns run state and publish ordering. Grade the
  published `Analysis` row and persisted tool-call rows.
- Registry state is process-global. Run eval in a dedicated CLI process and
  restore state in tests to prevent cross-case leakage.

## Requirements

- [x] One typed runner dispatches by surface and returns one normalized
      observable outcome contract.
- [x] Conversation invokes `TurnService.create`, awaits its owned task, and
      reads the settled turn/message through `AgentPersistence`.
- [x] Analysis invokes `produce_analysis` with a real `analysis_producer`, then
      reads the immutable published `Analysis` and run/tool trace.
- [x] Fixture tools preserve real names, descriptions, strict schemas,
      toolsets, display metadata, provenance, and output limits.
- [x] Trusted user/thread/symbol/as-of scope enters via `TurnRequest`,
      `RuntimeContext`, or `ToolContext`, never model arguments.
- [x] Any undeclared provider/store/network access fails closed in eval mode.
- [x] A recording client captures request metadata, normalized completion,
      usage, latency, typed failure, and request ID for every attempt.
- [x] Tool trajectory captures call ID/order, sanitized arguments, status,
      evidence references, duration, and typed error without chain-of-thought.
- [x] Scripted completions drive offline smoke and fault tests; paid mode uses
      the configured real route only with explicit authorization and ceiling.
- [x] Every case has isolated state, deterministic clock, bounded deadline,
      cancellation, and cleanup.

## Architecture

`FixtureWorld` loads compact snapshots into a case-local throwaway store and
installs fixture-backed external handlers behind real `ToolEntry` contracts.
`RecordingLLMClient` decorates a scripted or real reserved client. `EvalRunner`
constructs lane input, invokes the existing lifecycle, then normalizes only the
persisted outcome and observable trajectory. Analysis execution runs off the
event-loop thread, matching `analysis_producer`'s production contract.

The case-local Postgres schema also owns `llm_call_usage`. Build
`SpendAdmission` with that session factory, so Turn/Analysis owner ceilings and
ledger behavior are real while no eval row or charge enters the development
application database. A run-level guard wraps the reserved client and sums the
same worst-case `SpendRequest` values before delegation; it doesn't add an
`OwnerType` or budget lane.

Wrap materialization and every trial in the existing
`src.core.provider_access.store_only_execution()` boundary. It fails before
FiinQuant credentials, VNStock quota arbitration, or network access. Don't add
an eval-specific provider quota lane.

Never add `eval_mode` branches inside `TurnService`, `AgentLoop`, `ToolExecutor`,
`produce_analysis`, or Analysis generation.
If an observation isn't available through current results, callbacks, or
persisted trace, record a Stage 1 contract gap instead of reaching into private
state.

## Related code files

| Action | File | Change |
|---|---|---|
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/world.py` | Case-local store/provider/tool environment and cleanup. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/recording.py` | Recording/scripted client, publisher, and trace redaction. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/src/eval/runner.py` | Surface dispatch, trial outcome, modes, and ceilings. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/tests/eval_world.py` | Compact builders shared by eval tests. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_eval_recording.py` | Attempt, usage, latency, failure, and redaction tests. |
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_eval_runner.py` | Lane integration, isolation, and fault tests. |
| Reuse | `/Users/typham/Dev/Stock_Massive/apps/api/tests/throwaway_db.py` | Existing test DB lifecycle; don't duplicate it. |

No production file changes unless implementation proves a missing public seam.
That requires a separate contract decision and focused regression tests.

## Implementation steps

1. Write runner tests with scripted completions and one compact snapshot for
   each surface.
2. Decorate `LLMClient.complete`; preserve typed exceptions and retry semantics.
3. Redact trajectory using an allowlist projection. Exclude credentials, raw
   headers, private memory, and hidden reasoning.
4. Implement `FixtureWorld` context management: per-case store, external map,
   deterministic clock, registry isolation, isolated admission ledger,
   `store_only_execution()`, and cleanup.
5. Run Conversation through `TurnService.create` with eval-local persistence
   and the production loop factory. Await settlement and grade the stored
   assistant message; assert stream/checkpoint/message consistency.
6. Run Analysis off-loop through `produce_analysis` and an injected
   `analysis_producer`. Grade the committed payload only after run status is
   `ready`; retain named refusal/failure states otherwise.
7. Add scripted malformed arguments, missing/duplicate result, timeout, output
   cap, context overflow, cancellation, and untrusted content.
8. Prove smoke makes no network call and live mode refuses without explicit
   route and run ceiling.

## Todo

- [x] Write recording and runner tests first.
- [x] Implement recording/scripted model adapters.
- [x] Implement compact fixture world and registry isolation.
- [x] Integrate real Conversation and Symbol Analysis entry points.
- [x] Add faults, cancellation, cleanup, and no-network assertions.
- [x] Prove FiinQuant/VNStock fakes are never invoked in any runner mode.

## Test scenarios

| Priority | Scenario | Expected result |
|---|---|---|
| Critical | Model calls outside case capabilities | Settled blocked/unknown result; no live access. |
| Critical | A path attempts FiinQuant or VNStock | `ProviderSourceAccessForbidden` before quota/network; trial is incomplete. |
| Critical | External content includes injection and secret-like token | Remains untrusted; artifact redacts token. |
| Critical | Analysis tool settles, then model fails | Incomplete trial with trace; no invented artifact. |
| High | Parallel read calls | Results retain call order and settle once. |
| High | Case A mutates registry/memory | Case B starts clean. |
| Medium | Repeat scripted smoke | Stable outcome/trace after volatile fields. |

## Success criteria

- `pytest tests/test_eval_recording.py tests/test_eval_runner.py -q` passes.
- One Conversation and one Analysis case traverse real lifecycle, persistence,
  orchestrators, schemas, and validation with no network.
- Every model attempt and tool call settles in the normalized trajectory.
- Eval changes no runtime behavior when its CLI isn't running.

## Risk assessment

The main risk is measuring a mock. Substitute only manifest-declared unstable
boundaries and assert real entry points/resolved schemas. Default-deny all
unrecorded provider access to control the opposite risk.

## Security considerations

Paid eval uses production admission/route policy plus a run ceiling. Never log
keys/provider bodies. Fixture handlers can't read another case's symbol, user,
or as-of scope.

## Next steps

Phase 3 defines executable financial outcome checks and fills the 16-case set.
