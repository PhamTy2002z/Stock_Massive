---
phase: 2
title: "Resolved Capability Model and Resolver"
status: completed
priority: P1
effort: "12h"
dependencies: [1]
---

# Phase 2: Resolved Capability Model and Resolver

## Context links

- [Plan](./plan.md)
- [Phase 1](./phase-01-start.md)
- [Capability architecture research](./research/capability-architecture-report.md)
- [OpenCode lessons](../../docs/opencode/opencode-lessons-for-stock-massive.md)

## Overview

Extend the existing registry and definitions boundary with an immutable resolved
surface. Preserve exact schemas/order/cache behavior while making all current
execution classifications explicit and conservatively defaulted.

## Requirements

### Functional

- [x] Add typed current-behavior dimensions: effect, idempotency, access class,
      content trust, concurrency/ordering, contract version, handler identity,
      output limit, and existing display projection.
- [x] Add frozen `ResolvedTool` and ordered `ResolvedToolSurface`; surface owns
      every selected entry plus availability state, an offered-schema projection,
      selected-only by-name lookup, sanitized unavailable reasons, registry
      generation, expanded tool names, and TTL/expiry identity.
- [x] Resolve toolsets once per task. Cache by registry generation, ordered
      expanded names, and availability TTL; toolset-only membership mutation
      cannot serve a stale surface.
- [x] Keep `get_tool_definitions()` as a projection from the resolved surface;
      it must not rebuild or recalculate policy.
- [x] Resolve handler/policy atomically. Dispatch may recheck current
      availability/revocation, but cannot swap to a re-registered handler.
- [x] Make every shipped registration explicit. Defaults exist only for legacy,
      test, or unknown inputs and take the conservative direction.

### Non-functional

- [x] No principal-aware/global authorization cache in v1. Toolset selection and
      handler-enforced `ToolContext` checks remain current policy owners.
- [x] No remote provider probe, blocking network probe, cache serialization,
      provider import, or unbounded cache.
- [x] Prompt schema bytes and stable registration order remain unchanged.

## Architecture

```text
ToolEntry (declared, registry generation)
        + selected toolsets -> ordered expanded names
        + cached availability verdicts
                         |
                         v
ResolvedToolSurface (frozen per task)
   | schemas | by_name | limits | display | policy classes
   +--------------------------+--------------------------+
                              v
              consumers receive one snapshot
```

Use no more than two new domain types: `ResolvedTool` and
`ResolvedToolSurface`. Typed enums are values, not services. Keep display
callables directly on the declaration/resolved entry; do not introduce a new
projector framework.

### Classification mapping that preserves behavior

| Tools | Access/trust/effect | Concurrency |
|---|---|---|
| `web_search`, `fetch_url` | network / untrusted / read / idempotent | parallel-safe |
| `session_search`, `recall_facts` | store / trusted structured / read / idempotent | parallel-safe |
| `remember_fact` | store / trusted structured / write / unknown idempotency | serialized |
| `list_fields`, `get_field`, `check_price_claim` | store / trusted structured / read / idempotent | preserve current serialized behavior |
| unknown/incomplete | network / untrusted / unknown effect / non-idempotent | serialized |

Do not optimize Signal Field calls to parallel in this plan; that is a measured
behavior change for a later candidate.

## File inventory

| Action | File | Change | Test impact |
|---|---|---|---|
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/registry.py` | Typed declaration fields, frozen resolved entry, sanitized availability, compatibility accessors. | Registry + mutations. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/definitions.py` | `resolve_tool_surface`, frozen surface, cache owner, schema projection. | Definitions/cache. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/toolsets.py` | Expose ordered expansion identity; keep lane policy static. | Toolset suite. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/tools/web.py` | Explicit web classifications/version. | Web tests. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/tools/memory.py` | Explicit read/write/idempotency classifications. | Memory tests. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/tools/signals.py` | Explicit store/trust/effect/concurrency/version. | Signal tests. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/tools/price_check.py` | Explicit store/trust/effect/concurrency/version. | Price-check tests. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/src/core/llm/protocol.py` | Accept immutable schema sequences while preserving exact model wire output. | Capability contract + protocol suites. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_tool_registry.py` | Defaults, serialization, availability reasons. | Focused. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_tool_definitions.py` | Surface/cache/invalidation/atomicity. | Focused. |
| Modify | `/Users/typham/Dev/Stock_Massive/apps/api/tests/agent_tool_world.py` | Test factories declare or intentionally default classifications. | Shared isolation. |

No provider, persistence, API, web, prompt, or eval file changes.

## Interface checklist

- [x] `ToolEntry.as_schema()` remains exact.
- [x] Registry generation changes on registration/deregistration.
- [x] `resolve_tool_surface(toolsets, now=...)` returns ordered immutable state.
- [x] `get_tool_definitions()` projects from the same cached surface.
- [x] Availability reason is typed/sanitized; env names and exceptions never
      enter model/UI output.
- [x] Handler identity/version is deterministic; no callable repr/address.
- [x] Surface wire/digest excludes credentials, callables, raw probe text.

## Implementation steps

1. Extend Phase 1 tests to fail on absent/unsafe resolved metadata.
2. Define typed enums and conservative defaults; retain direct `ToolEntry(...)`
   compatibility while requiring shipped-registration conformance.
3. Implement deterministic `ResolvedTool` projection from one `ToolEntry`.
4. Implement ordered `ResolvedToolSurface` and cache. Key by registry generation
   plus expanded ordered names so test/eval catalogue mutation cannot go stale.
5. Project existing definitions/accessors from resolved/static owners without a
   second facts table.
6. Populate all real registrations explicitly; run narrow suites before moving
   any consumer.

## Test scenarios

| Priority | Scenario | Expected result |
|---|---|---|
| Critical | Tool re-registers after resolution | Surface retains original handler/policy; later surface gets new generation. |
| Critical | Credential/flag revoked after resolution | Dispatch recheck can refuse; it never swaps handler. |
| Critical | Missing classification | Conservative external/untrusted/serialized/non-idempotent. |
| High | Toolset contents mutate with same selected name | Expanded-name key prevents stale membership. |
| High | Availability probe raises | Tool unavailable with sanitized reason; sibling tools remain. |
| High | Surface digest repeated | Stable bytes; no callable repr/secrets. |
| Medium | Toolset order reversed | Schema order follows request; prompt behavior preserved. |

## Dependency map

```text
Phase 1 fixtures -> registry types -> definitions resolver/cache -> Phase 3 consumers
```

## Success criteria

- [x] Registry, toolset, definitions, and contract tests pass.
- [x] Schema names/order/wire equal Phase 1 baseline.
- [x] One cached surface owns all metadata projections.
- [x] All shipped registrations explicit; legacy/unknown defaults conservative.
- [x] No consumer behavior changes yet.

## Risk assessment

- **Cache observes wrong catalogue.** Signal: same toolset name resolves stale
  member names. Response: key by expanded names; if production runtime mutation
  appears, stop and design generation/locking.
- **Availability snapshot weakens revocation.** Signal: disabled tool still
  invokes. Response: live fail-closed recheck bound to resolved entry.
- **Handler identity unstable.** Signal: identical code gives new digest from
  address/order. Response: explicit version + module/qualified name only.
- **Metadata overstates authorization.** Signal: declaration says protected but
  handler does not enforce it. Response: keep handler/`ToolContext` as owner.

## Security considerations

Unknown stays maximally conservative. Resolver cache is not user-dependent and
cannot grant principal-specific visibility. Tool arguments never supply trusted
identity.

## Next steps

Phase 3 migrates consumers and removes duplicate owners only after parity tests.

## Validation log

### 2026-08-24

- Focused capability/registry/definitions/provider verification: 99 passed.
- Nine-suite agent/provider compatibility matrix: 240 passed, 4 explicitly
  network-marked tests deselected.
- Broadened verification: 821 passed. Default offline suite: 2786 passed with
  one unrelated pre-existing documentation-topology failure and one intentional
  skip; the failure requires a file deliberately deleted before this work.
- Regression tests cover recursive immutability, registry mutation during an
  availability probe, descriptor-bypass resistance, synchronized bounded LRU
  access, deterministic identity, and exact schema wire parity.
- Three review passes ended at 9.5/10 with no critical, warning, or blocking
  findings. Public API, SSE, database, provider executable behavior, and
  credential/network boundaries remain unchanged.
