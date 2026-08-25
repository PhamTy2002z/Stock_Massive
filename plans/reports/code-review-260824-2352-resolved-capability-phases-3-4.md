---
title: "Code Review: Resolved Capability Contract v1 Phases 3-4"
date: 2026-08-24
scope: "Stage 2 code-quality review of Conversation/Analysis consumers and eval identity"
status: pass-with-minor-concern
base: d7c40d38034f48a8104a41db6828c9a10f604325
---

# Code Review: Resolved Capability Contract v1 Phases 3-4

## Findings

### Critical

None.

### Important

None.

### Minor

1. **Eval catalog installation is intentionally sequential but not protected
   against concurrent use.**

   `apps/api/src/eval/world.py:49-79` and
   `apps/api/src/eval/world.py:141-196` snapshot, clear, replace, and restore the
   process-global tool registry, toolset map, and resolver caches without a lock
   or task-local ownership. Two concurrent eval identities/runs in one process
   could therefore observe each other's catalog or restore the wrong snapshot.
   This is not a current correctness blocker: `EvalHarness.run` executes cases
   sequentially, `_identity` resolves case catalogs sequentially, and the
   authorized smoke evidence used that path. Keep eval execution single-flight
   until a future requirement introduces in-process parallel cases; add an
   explicit lock or task-local registry before enabling concurrency.

## Requirement Matrix

### Phase 3 — Consumer Migration and Duplicate Owner Removal

| Requirement / criterion | Result | Evidence |
|---|---|---|
| Resolve one frozen surface per Conversation turn and Analysis run; use it for schema and dispatch | Pass | `agent/loop.py:796-815`; `alpha/analysis_loop.py:262-272`. Both lanes bind `offered_schemas` and `ToolExecutor.surface` to the same resolved object. |
| Plan segments from effect/concurrency; admit fanout from access; use resolved result limits | Pass | `agent/executor.py:156-180,204-256`; `agent/loop.py:798-815`; `alpha/analysis_loop.py:335-341`. Unknown classification remains network/serialized. |
| Budget, summary, display kind, trust wrapping, trace, and result projection use the task snapshot | Pass | `agent/loop.py:1345-1375`; `agent/messages.py:172-220,225-266,398-416`; `agent/untrusted.py:54-110`. Domain-specific `display_results`/`outcome_of` remain intentional domain projections, not duplicated generic execution policy. |
| Remove `PARALLEL_SAFE_TOOLS`; retain explicit policy owners | Pass | Repository search reported zero matches. `CHAT_TOOLSETS`, Analysis `signals`, `PRICE_CHECK_TOOL`, and `_STATUS_BY_ERROR` remain in their existing roles. |
| Lane-unselected registered names cannot dispatch | Pass | `agent/executor.py:190-203,300-332` looks up through `surface.by_name`; the Analysis security regression and focused executor tests pass. |
| Initially unavailable cannot widen; live state can revoke only; frozen handler/policy cannot swap | Pass | `agent/executor.py:315-332,396-406`; resolved handler is captured in `ResolvedTool`. Focused regressions cover initial unavailability, revocation, and re-registration. |
| Access and content trust stay orthogonal, including legacy calls | Pass | `agent/executor.py:204-229`; `agent/messages.py:182-220`; `agent/untrusted.py:54-110`; four-combination regression at `tests/test_agent_untrusted_results.py:137-190`. Budget/wire kind use access; wrapping uses trust. |
| Unknown stays conservative and settles exactly once | Pass | `agent/executor.py:162-180,204-229,300-314`; unknown remains external, serialized, unavailable to dispatch, and yields the existing settled error while preserving sibling/order behavior. |
| Preserve Conversation/Analysis lifecycle, ordering, budgets, traces, transcript/SSE v2 and fail-open behavior | Pass | Focused groups: 409 passed; exact turn lifecycle: 26 passed; transport coverage included in the green group. No public wire field was added (`resolved_tool` is explicitly excluded from `as_wire`). |
| No loop merger, dual dispatch, provider fallback, DB/API/SSE/env/provider semantic change | Pass | Scoped diff retains separate orchestrators and one dispatch path. No scoped provider adapter, migration, endpoint, route, or public event model changed. Concurrent stocks/realtime/DNSE/docs/system edits were excluded from attribution. |
| Hypothetical read-only tool requires registration plus intentional toolset selection only | Pass | `tests/test_agent_capability_contract.py:151-218` proves schema, dispatch, limit, summary, wire kind, and trust without consumer name-table edits. |

### Phase 4 — Cross-Lane Eval and Graduation Gate

| Requirement / criterion | Result | Evidence |
|---|---|---|
| Deterministic full resolved execution identity | Pass | `agent/definitions.py:83-125`; `eval/versions.py:152-229`. Schema, availability, effect, idempotency, access, trust, concurrency, limits, display/summary identity, stable handler identity, contract version, ordered selection, resolver version, case id, and lane all affect the digest. |
| Redact callables, secrets, raw probe/env/account state, and volatile identity | Pass | Identity is built from an explicit allowlist in `ResolvedToolSurface.identity_payload`; callable values, `requires_env`, `check_fn`, expiry and object repr are excluded. Mutation/redaction tests pass. |
| Preserve ordered case/lane surface membership and conflicting same-name declarations | Pass | `eval/versions.py:196-229` hashes an ordered list of `{case_id, lane, surface}` records. It does not flatten declarations before hashing; the flattened names are display metadata only. Membership-move regression passes. |
| Each behavior-changing field changes compatibility identity | Pass | `tests/test_eval_contracts.py:389-469` covers execution fields, handler/schema, availability, ordering, and case/lane membership. `eval/baseline.py:13-21` includes `tools` among compatibility fields. |
| Import-only validation does not touch network | Pass | `eval/cli.py:37-53` defers the runtime-world import; exact socket sentinel test passed with zero connection attempts. |
| Fixture world installs/restores registry, toolsets, and caches without sequential leakage | Pass with minor concern | `eval/world.py:38-79,141-196` restores entries/toolsets and clears both caches on normal and exceptional exits. Sequential behavior is covered; concurrent use is the Minor finding above. |
| Real Conversation and Analysis lifecycles run offline; every call settles; provider calls remain zero | Pass | Two offline smoke runs completed 16/16 each (Conversation 10, Analysis 6), with zero hard failures and zero provider calls. Canonical content was stable after excluding run id/timestamps/digest. |
| Provider boundary and unavailable/fallback semantics remain intact | Pass | No scoped provider behavior changed. Fixture execution remains under store-only enforcement, and provider-attempt regressions mark trials incomplete before live access. |
| Focused/broad quality gates | Pass with unrelated repository failure | 409 focused passed; lifecycle 26 passed; 77 touched Python files compiled; `git diff --check` clean. Full suite: 2,828 passed, one unrelated missing `docs/streaming-topology.md` failure, one skipped. |
| Approved candidate-vs-baseline comparison and whole-slice graduation | Operationally blocked, not a code finding | The required paid/live comparison was intentionally not authorized or run. Therefore the plan must not graduate and evergreen Harness docs correctly remain unchanged. |

## Standards Review

The scoped changes follow existing module ownership and keep compatibility
fallbacks localized. No enforced lint/type/syntax issue, unjustified abstraction,
duplicate generic policy table, public-contract drift, or scope creep was found.
The one possible global-state smell is bounded to the sequential eval harness and
recorded above rather than overstated as a production race.

## Blast-Radius Assessment

- Conversation: one surface is resolved after slot admission and retained across
  every round; schema, dispatch, budget, trace metadata, summary, wire kind and
  trust use it without changing public payload fields.
- Analysis: remains a distinct store-only lifecycle with exact signals selection,
  existing trace status vocabulary, output limits, and final-generation behavior.
- Eval: compatibility now includes execution policy and case/lane authority;
  baseline comparison fails closed on a tool identity mismatch.
- Public/API/storage/provider: no scoped endpoint, SSE version, durable model,
  migration, environment contract, provider selection, quota, or fallback change.

## Merge-Readiness Verdict

**Code-review gate: PASS WITH MINOR CONCERN.** The Phase 3 implementation and
code-owned Phase 4 implementation are merge-ready. The sequential eval-global
mutation limitation is proportional to the current sequential harness and does
not block this change.

**Graduation verdict: BLOCKED OPERATIONALLY.** Do not mark the plan or Harness
slice graduated, and do not update evergreen docs, until the repository-owned
candidate-versus-approved-baseline comparison is run under its approved route,
ceiling, and policy and reports compatible, complete, zero-provider-call, and no
new hard regression.

## Unresolved Questions

None for merge. Future in-process parallel eval execution must first define
single-flight or task-local ownership for the mutable registry/toolset fixture.
