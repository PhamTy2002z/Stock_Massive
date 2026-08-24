---
title: "Phase S0 Data Contracts"
description: "Normalized realtime market-event contracts and policy gates"
status: completed
priority: P1
effort: "1d"
tags: [system, market-data, contracts, dnse]
created: 2026-08-24
---

# Phase S0 data contracts

## Overview

This plan delivers every unchecked item and exit gate in Phase S0 of
[`docs/system-roadmap.md`](../../docs/system-roadmap.md). It establishes a
source-neutral realtime boundary before any DNSE adapter or persistence path is
built.

## Outcome contract

The outcome is an immutable, strict contract layer that rejects ambiguous event
identity, time, unit, board, price basis, quality, and duplicate semantics before
persistence. It also records source ownership, reconciliation provenance, and
retention decisions as executable policy.

Constraints:

- Keep current EOD `provider_snapshots` behavior and public REST schemas stable.
- Keep provider wire fields and credentials outside normalized events.
- Preserve each source as separate evidence; never overwrite disagreements.
- Use timezone-aware timestamps, Vietnamese trading dates, exact decimal prices,
  and integer share quantities.
- Do not weaken, skip, narrow, or delete tests to make the phase pass.

Non-goals:

- DNSE REST/WebSocket authentication, parsing, subscriptions, or rate limiting.
- Realtime persistence, Redis projections, replay execution, APIs, or UI.
- Changes to canonical historical EOD ownership.

## Phases

| # | Phase | Status | Dependency |
|---|---|---|---|
| 1 | [Event contract foundation](./phase-01-start.md) | Completed | None |
| 2 | [Normalization, outcomes, and provenance](./phase-02-normalization-outcomes-and-provenance.md) | Completed | Phase 1 |
| 3 | [Contract, mutation, and security tests](./phase-03-contract-mutation-and-security-tests.md) | Completed | Phases 1-2 |
| 4 | [Documentation, review, and quality gates](./phase-04-documentation-review-and-quality-gates.md) | Completed | Phases 1-3 |

## Dependencies

Existing Harness and evaluation plans remain independent. S0 creates a new
`stocks.realtime` boundary and does not modify their files or contracts.

## Acceptance criteria

- [x] Eight requested normalized event types validate required metadata and
  event-specific invariants.
- [x] Versioned board/unit rules normalize admitted DNSE values once and refuse
  unknown or incompatible rules.
- [x] All nine roadmap outcomes are typed and distinguish retry/refusal/quality
  behavior.
- [x] Reconciliation preserves both evidence identities and source provenance.
- [x] Retention classes are explicit, immutable, and documented.
- [x] Contract and mutation tests reject wrong unit, board, timestamp, identity,
  price basis, and duplicate semantics before persistence.
- [x] Security tests prove secrets and raw payloads cannot enter normalized
  event contracts or serialized diagnostics.
- [x] Focused tests and the relevant backend suite, lint/static checks, and
  compile/import checks pass.
- [x] The S0 roadmap checklist links each completion claim to code, tests, or a
  durable policy artifact.

## Risks

- A single universal board multiplier would corrupt odd-lot data. Rules are
  keyed by version, product group, and board, and unknown combinations refuse.
- Snapshot timestamps are not provider sequence numbers. Identity includes a
  raw payload hash and source, while duplicate classification remains explicit.
- Index and derivative prices are not VND. Event validators bind product groups
  to compatible canonical units.

## Unresolved questions

None. The roadmap, live DNSE audit, and current source-ownership contracts
provide enough evidence for S0 without a new product decision.

<!-- slug: phase-s0-data-contracts -->
