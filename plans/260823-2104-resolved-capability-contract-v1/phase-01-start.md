---
phase: 1
title: "Freeze Contracts and Provider Boundary"
status: pending
priority: P1
effort: "8h"
dependencies: []
---

# Phase 1: Freeze Contracts and Provider Boundary

## Context links

- [Plan](./plan.md)
- [Capability architecture research](./research/capability-architecture-report.md)
- [Provider data-contract research](./research/provider-data-contracts-report.md)
- [Harness target architecture](../../docs/Harness/target-architecture.md)
- [Investment Intelligence contract](../../docs/Harness/investment-intelligence-contract.md)
- [Stage 0 plan](../260823-1744-investment-intelligence-eval-replay-harness/plan.md)

## Overview

Freeze current public and internal behavior before refactoring. Build an
exhaustive declaration/consumer census and executable provider-boundary tests so
later phases cannot silently broaden tool authority or data fallback.

## Requirements

### Functional

- [ ] Refuse implementation until Stage 0 has a complete approved baseline and
      committed gate policy; targeted smoke alone does not satisfy the blocker.
- [ ] Characterize eight shipped tools: names, toolsets, schemas, order,
      availability, handler, read/write behavior, idempotency, external/store
      access, trust wrapping, concurrency, output limit, display, and errors.
- [ ] Pin Conversation `CHAT_TOOLSETS` and Analysis `signals` selection; record
      the current gap that executor lookup is global even when lane exposure is
      narrower. Do not encode that bypass as desired behavior.
- [ ] Pin current model names/schema bytes, transcript/SSE v2 fields, trace
      vocabulary, budget precedence, one-call-one-result, and issued order.
- [ ] Verify provider ownership separately from executable adapters. Cover must
      never imply live fallback or equivalent price/data semantics.
- [ ] Correct the stale VNStock adapter module documentation from two to three
      calls per fundamental symbol; do not change executable provider behavior.

### Non-functional

- [ ] No production behavior, provider/network call, credential read, database
      write, migration, or threshold change.
- [ ] Static and fixture-backed tests only; preserve dirty Stage 0 work until its
      owner finishes it.

## Architecture

This phase protects three distinct layers:

```text
agent ToolEntry/toolset  !=  provider Capability ownership
        |                            |
        v                            v
runtime execution policy      normalized evidence rows
                                     |
                          source/unit/basis/time/health
```

The resolver may later describe how a tool executes, but it never owns
FIinQuant/VNStock field meaning, quota, entitlement, Main/Cover selection, or
point-in-time truth.

### Provider conformance matrix

| Case | Required proof |
|---|---|
| VNStock valuation cover declared, adapter absent | Named unavailable; no fallback. |
| VNStock corporate-action adapter present, ownership row absent | Do not invent `Capability` or Reference semantics. |
| FiinQuant market/current versus VNStock history | Method shape stays distinct. |
| FiinQuant index | No VNStock/current route inferred. |
| VNStock fundamentals | Three calls/symbol; optional cash-flow stays partial, not fabricated. |
| Stored Signal Field | Tool is store-access/trusted-structured; resolver preserves source/unit/as-of/health and any basis/time identity the current result actually emits, without fabricating missing fields. |

## File inventory

| Action | File | Purpose | Test impact |
|---|---|---|---|
| Create | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_capability_contract.py` | Cross-consumer characterization and provider-boundary seam tests. | New focused suite. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_tool_registry.py` | Lock registration and safe unknown behavior. | Existing 14 tests retained. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_tool_definitions.py` | Lock selection/order/cache behavior. | Existing 7 tests retained. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_tool_executor.py` | Characterize barriers, fanout, handler lookup, failure codes. | Existing 25 tests retained. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_transport.py` | Lock exact `tool.call`/snapshot payload and SSE version. | Existing 31 tests retained. |
| Reuse | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_provider_contracts.py` | Main/Cover ownership truth. | No duplicate provider tests. |
| Reuse | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_fiinquant_provider.py` | Adapter/batch/entitlement/basis truth. | No live call. |
| Reuse | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_vnstock_provider.py` | Reference/fundamental/history/action semantics. | No live call. |
| Modify (docs only) | `/Users/typham/Dev/Stock_Massive/apps/api/src/stocks/providers/vnstock_provider.py` | Correct module-level quota/call-shape prose to 3 calls: income, balance, cash flow. | Provider suite proves no behavior change. |

No executable provider logic is modified in this phase.

## Interface checklist

- [ ] `ToolEntry`, `ToolContext`, `register`, `get`, `is_available`.
- [ ] `get_tool_definitions`, `resolve_toolset`, definition cache helpers.
- [ ] `ToolExecutor.run`, `plan_segments`, `_dispatch`, `_record`.
- [ ] `TurnToolCall.as_wire`, `summarise_call`, result projection/wrapping.
- [ ] Conversation and Analysis schema construction/trace settlement.
- [ ] Provider `Capability`, `SourceOwnership`, executable `fetch_*` methods.

## Implementation steps

1. Confirm Stage 0 artifact identity, approved baseline, policy, and dependency
   status. Stop if incomplete or dirty/incompatible.
2. Write characterization tests before production edits. Assert exact current
   tool catalog and lane exposure.
3. Add negative provider-boundary fixtures using static/executable inventory;
   never import a provider library merely to probe availability.
4. Add mutation cases for changed schema/order/classification and ensure the
   owning current test fails.
5. Record focused commands and results in the phase validation log.

## Test scenarios

| Priority | Scenario | Expected result |
|---|---|---|
| Critical | Registration exists but toolset omits it | Not offered; Phase 3 target proves it also cannot dispatch. |
| Critical | Ownership declares VNStock valuation cover | Still unavailable: no executable adapter. |
| Critical | Provider source changes across series | Provider/store rows retain their own source/basis; tool projection is checked for no loss of fields it currently exposes and no invented fields. |
| High | Registry name/schema/order changes | Characterization test fails. |
| High | Unknown tool metadata | External, untrusted, unknown effect, non-idempotent, serialized. |
| Medium | Cash-flow read absent | Fundamental remains partial with `None`, not zero/full refusal. |

## Dependency map

```text
Stage 0 approved baseline -> Phase 1 contract fixtures -> Phase 2 resolver
```

## Success criteria

- [ ] Focused characterization and existing provider contract suites pass.
- [ ] Every future migration claim maps to a test or a named gap.
- [ ] Provider boundary matches current code, including 3 VNStock fundamental
      calls/symbol and non-executable valuation cover.
- [ ] No production or database change exists in the phase diff.
- [ ] VNStock module prose and executable three-call tests agree.

## Risk assessment

- **Stage 0 incomplete.** Signal: no approved compatible baseline/gate artifact.
  Response: stop; do not manufacture thresholds.
- **Research prose drifts from code.** Signal: ownership/call-count assertion
  disagrees with source/tests. Response: source/tests win; update smallest owner.
- **Characterization locks a defect.** Signal: test contradicts verified
  invariant/user decision. Response: separate defect disposition.

## Security considerations

No secrets, env values, provider bodies, private prompts, or portfolio data enter
fixtures. Static inventory makes no network call.

## Next steps

Phase 2 introduces the frozen resolved model under these locked contracts.
