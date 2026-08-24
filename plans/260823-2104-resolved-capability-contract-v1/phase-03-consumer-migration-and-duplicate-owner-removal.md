---
phase: 3
title: "Consumer Migration and Duplicate Owner Removal"
status: pending
priority: P1
effort: "16h"
dependencies: [2]
---

# Phase 3: Consumer Migration and Duplicate Owner Removal

## Context links

- [Plan](./plan.md)
- [Phase 2](./phase-02-resolved-capability-model-and-resolver.md)
- [Target capability plane](../../docs/Harness/target-architecture.md#capability-plane)

## Overview

Pass one resolved surface through Conversation and Analysis lower seams. Migrate
execution, budget, trust, display, and trace one consumer at a time; remove only
duplicate generic owners proven unused afterward.

## Requirements

### Functional

- [ ] Conversation resolves one surface at turn start; Analysis resolves one at
      run start. Both send its schemas and dispatch through its handlers/policy.
- [ ] Executor plans parallel/serial segments from declared effect/concurrency,
      admits external/store fanout from access class, and uses resolved output
      limits. Unknown names retain conservative settled errors.
- [ ] Turn aggregate external budget, `TurnBudget` registry rung, call summaries,
      result projection, untrusted wrapping, and current-task trace metadata read
      the same surface.
- [ ] Remove `PARALLEL_SAFE_TOOLS`. Replace generic name branches only where an
      existing declaration-owned projector reproduces exact output.
- [ ] Preserve explicit policy names: `CHAT_TOOLSETS`, Analysis `signals`,
      `PRICE_CHECK_TOOL`, and `_STATUS_BY_ERROR` remain intentional owners.
- [ ] Availability revocation after offer returns `tool_unavailable`; no alternate
      provider/tool/handler attempt.
- [ ] A globally registered name outside the selected surface cannot dispatch,
      even if a model/provider fabricates it. It settles once with the existing
      conservative unknown/unavailable vocabulary.

### Non-functional

- [ ] No public SSE/event/version, endpoint, prompt, durable model, migration,
      timeout, fanout ceiling, or output-budget arithmetic change. The only
      intentional behavior change is closing lane-unselected dispatch.
- [ ] No dual dispatch or shadow execution; comparison is metadata/test-only.
- [ ] No loop merger. Conversation and Analysis retain distinct lifecycle and
      persistence ownership.

## Architecture

```text
resolve once
   |
   +--> model schemas
   +--> TurnBudget limits / external admission
   +--> ToolExecutor handler + effect + concurrency
   +--> summary/display + untrusted wrapper
   +--> trace/ops classification

live availability recheck --> allow same handler | settled unavailable
```

Durable reconnect continues using the registry-backed conservative projection
where a historical call has no captured resolved metadata. Stable persisted
capability identity belongs to the next typed-lifecycle plan; v1 must not smuggle
in a database or SSE change.

## File inventory

| Action | File | Change | Test impact |
|---|---|---|---|
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/executor.py` | Consume surface; derive segments/admission/dispatch; remove allowlist. | Executor suite. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/loop.py` | Resolve/inject surface; project budgets, summaries, trust and trace. | Loop suite. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/alpha/analysis_loop.py` | Same surface for schemas/executor/result caps; preserve signals-only. | Analysis suite. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/messages.py` | Surface-backed summary/display/trust; conservative legacy fallback. | Message + transport. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/untrusted.py` | Accept resolved trust; keep registry/unknown fallback. | Untrusted tests. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/ops.py` | Enumerate generic classes from declaration; preserve price metric. | Ops tests. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/service.py` | Update composition call only if confirmed by flow trace. | Service/turn tests. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_tool_executor.py` | Handler atomicity, planning, revocation, unknown fallback. | Focused. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_tool_budget.py` | Preserve result-limit precedence and aggregate rebalance. | Focused. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_loop.py` | Same surface across schema/budget/execution/display. | Existing 68 retained. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_analysis_loop.py` | Same surface and exact signals behavior. | Existing 35 retained. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_transport.py` | Exact transcript/SSE parity. | Existing 31 retained. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_untrusted_results.py` | Resolved trust, delimiter defanging, conservative fallback. | Security-focused. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_ops_query.py` | External and price-check classifications stay stable. | Ops-focused. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_signal_tools.py` | Evidence metadata survives store-tool result. | Existing 56 retained. |

Delete no file unless final `rg` proves the symbol unreferenced. Preserve
compatibility projections that remain legitimate APIs.

## Interface checklist

- [ ] `ToolExecutor` receives resolved lookup and revocation check separately.
- [ ] `plan_segments` uses effect + concurrency, never tool names.
- [ ] Per-round/per-turn external counts use one access classification.
- [ ] `TurnBudget` uses resolved limits with unchanged precedence.
- [ ] Summary, display/outcome, and wrapper use resolved entry for current calls.
- [ ] `TurnToolCall.as_wire()` field set/version stays exact.
- [ ] Analysis trace states and one-call-one-result settlement stay exact.

## Implementation steps

1. Migrate executor first under focused tests. Remove
   `PARALLEL_SAFE_TOOLS` only after all classifications pass.
2. Migrate Conversation schema, aggregate budget, executor, and message
   construction. Compare Phase 1 wire fixtures byte-for-byte.
3. Migrate Analysis schema, executor, result limit, and trace. Keep exact
   `list_fields`/`get_field` model surface.
4. Migrate untrusted/display/ops generic classification; retain conservative
   fallback for historical/unknown records.
5. Search all consumers. Remove duplicate helpers/tables only when no caller
   remains; update exports/comments to name true owner.
6. Run focused suites after each consumer, then agent/Analysis/transport group.
   Fix regressions; never weaken exact contract tests.

## Test scenarios

| Priority | Scenario | Expected result |
|---|---|---|
| Critical | Registry re-registers name after model offer | Current task uses original resolved handler/policy. |
| Critical | Availability revoked before dispatch | One sanitized unavailable result; no fallback. |
| Critical | External content includes delimiter/injection | Defanged and wrapped from resolved trust. |
| Critical | Unknown call | Sequential/external/untrusted settled error; siblings preserved. |
| Critical | Analysis fabricates a registered web/memory name | Not in selected surface; never dispatches. |
| High | Parallel-safe web/memory reads | Overlap; issued result order exact. |
| High | Signal/read/write batch | Current serialized barriers/fanout preserved. |
| High | Disconnect/reconnect transcript | Exact current payload and SSE v2. |
| Medium | Ops snapshot | External and price-check counts unchanged. |

## Dependency map

```text
Phase 2 surface -> executor -> Conversation + Analysis -> display/trust/ops -> Phase 4 eval
```

## Success criteria

- [ ] Focused executor/loop/Analysis/message/untrusted/ops/transport suites pass.
- [ ] `rg` finds no `PARALLEL_SAFE_TOOLS` or new generic name-policy table.
- [ ] Schemas/order, errors, traces, budgets and wire bytes match Phase 1.
- [ ] Both lanes use same resolver without sharing lifecycle.
- [ ] Lane-unselected registered tools are non-dispatchable and covered by a
      hard security regression case.
- [ ] No provider adapter, quota owner, DB schema, public API, or web code changed.

## Risk assessment

- **Offered differs from dispatched.** Signal: re-registration test observes new
  handler. Response: surface stores handler; live check revokes only.
- **Budget/trust diverges.** Signal: one call gets different classifications.
  Response: pass resolved entry; unknown/historical fallback conservative.
- **Concurrency broadens.** Signal: Signal calls or writes overlap. Response:
  preserve matrix; optimize only in later measured work.
- **SSE fixture changes.** Signal: field/version/bytes differ. Response: restore;
  public-contract change is outside scope.
- **Registry mutation races.** Signal: production mutates after startup.
  Response: stop/replan explicit generation/lock.

## Security considerations

Toolset allowlists remain authority boundaries. Unknown, missing and legacy
metadata never becomes trusted or parallel. Metadata does not replace handler
authorization or let model arguments select trusted scope.

## Next steps

Phase 4 stamps the contract into eval identity and proves baseline parity.
