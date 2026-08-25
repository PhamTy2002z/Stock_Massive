---
title: "Resolved Capability Contract v1 — Phase 1–2 progress"
date: 2026-08-24
status: completed
plan: ../260823-2104-resolved-capability-contract-v1/plan.md
phases: [1, 2]
---

# Resolved Capability Contract v1 — Phase 1–2 progress

## Outcome

Phase 1 and Phase 2 are complete. The agent registry now declares conservative,
typed capability facts and resolves them into an immutable, ordered surface with
deterministic identity, bounded synchronized caching, sanitized availability,
and generation-consistent handler/policy snapshots. All eight shipped tools
declare their behavior explicitly.

The plan remains in progress at Phase 3. Consumer migration, duplicate policy
owner removal, cross-lane evaluation, and graduation are intentionally not
claimed by this delivery.

## Scope delivered

- Characterized the existing tool catalogue, lane exposure, schema ordering,
  transport behavior, provider boundary, and conservative unknown defaults.
- Corrected VNStock fundamentals documentation to the executable three-request
  flow without changing provider behavior.
- Added typed effect, idempotency, access, trust, concurrency, availability,
  handler identity, version, output, and display facts.
- Added frozen `ResolvedTool` and `ResolvedToolSurface` values, exact schema
  projection, deterministic ordered identity, and selected-only lookup.
- Added generation/toolset-aware TTL + bounded LRU caching with synchronized
  mutation and retry protection against concurrent catalogue changes.
- Split provider-boundary proof into a static isolated suite that imports no
  provider package and performs no credential, quota, or network operation.

## Verification

- Latest focused rerun: 41 passed.
- Focused implementation matrix: 99 passed.
- Nine-suite agent/provider compatibility matrix: 240 passed; 4
  network-marked tests deselected.
- Broadened matrix: 821 passed.
- Default offline suite: 2786 passed, 1 intentional skip, and 1 unrelated
  pre-existing failure in `test_deployment_topology.py`; that test still
  requires `docs/streaming-topology.md`, which had already been deliberately
  deleted before this work.
- Isolated static provider test: passed with no `vnstock` or provider-client
  import and zero provider/network calls.
- Scoped `git diff --check`: passed.
- AgentKit plan validation: passed.
- Final code review after three bounded passes: 9.5/10, no critical, warning,
  or blocking findings.

## Documentation impact

No evergreen documentation update is required. This delivery preserves public
API and SSE bytes, setup and commands, database shape, provider execution, and
user-visible behavior. The implementation plan and this stateful progress
record are the smallest owning documentation surfaces.

## Workspace note

The worktree contains unrelated realtime, DNSE, migration, roadmap, and test
changes owned by other work. They were preserved and are excluded from this
phase completion claim.

## Next phase

Phase 3 may now migrate Conversation and Analysis consumers onto one resolved
surface per task and remove duplicate name-based policy owners while retaining
the Phase 1 compatibility baseline.

## Unresolved questions

None for the completed Phase 1–2 scope.
