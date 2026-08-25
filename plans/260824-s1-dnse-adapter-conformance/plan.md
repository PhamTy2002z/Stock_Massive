---
title: "Phase S1 DNSE Adapter and Conformance"
description: "Bounded DNSE REST/WebSocket adapter mapped into normalized realtime contracts"
status: in_progress
priority: P1
effort: "3d"
tags: [system, market-data, dnse, adapter, conformance]
created: 2026-08-24
blocks: [260824-2208-phase-s3-trades-bars-foreign-flow-mvp]
---

# Phase S1 DNSE adapter and conformance

## Outcome contract

Deliver every Phase S1 checklist item that can be proven deterministically in
the repository: a TLS-verified, bounded DNSE REST/WebSocket adapter, strict
wire-to-domain parsing, local request validation, opaque idempotent pagination,
endpoint-family rate budgets, duplicate handling, reconnect/resubscribe and
cancellation behavior, sanitized conformance fixtures, and operational metrics.
The controlled live probe is a guarded read-only command whose report records
what was actually observed; it must never claim market-hours completeness when
credentials, market state, or observed payloads are absent.

Constraints:

- Keep the S0 normalized contracts and current EOD `provider_snapshots` path stable.
- Keep credentials, raw payloads, wire field names, and provider exceptions
  inside the adapter boundary.
- Require verified TLS, bounded connect/read/write/pool timeouts, fresh auth
  nonce/date, and explicit API versioning.
- Admit JSON only; refuse MessagePack until a sanitized live fixture proves conformance.
- Never probe by exhausting provider quota or call trading/account endpoints.
- Do not weaken, narrow, skip, or delete tests to make the phase pass.

Non-goals:

- Durable event storage, Redis projections, replay execution, product APIs, or UI.
- Canonical historical EOD ownership changes.
- Trading, accounts, orders, portfolio access, or OTP flows.
- Claiming unmeasured market-hours throughput, subscription limits, or recovery completeness.

## Phases

1. Implement credentials, REST signing, validation, rate budgets, typed
   transport outcomes, and all S1 REST endpoint methods.
2. Implement strict JSON wire parsers, normalized-event mapping, snapshot
   deduplication, sanitized fixtures, and drift/refusal tests.
3. Implement WebSocket authentication, heartbeat, eight-hour rotation,
   reconnect/resubscribe/cancel, bounded queue behavior, and metrics.
4. Add a guarded controlled probe, run focused and backend validation, review
   security/contracts, and update roadmap evidence.
5. After every S1 exit gate passes, deploy all new backend code to the existing
   backend service and verify health plus the read-only DNSE surfaces.

## Acceptance criteria

- [x] REST signatures match official HMAC examples and never reuse nonce/date material.
- [x] All S1 REST endpoint families validate symbols, resolutions, date order,
  one-day event windows, and page size locally.
- [x] Response rate headers update non-exhaustive endpoint-family budgets and
  prevent over-budget calls locally.
- [x] Pagination treats tokens as opaque, detects replay loops, and deduplicates
  repeated pages without double counting.
- [x] Every admitted sanitized REST/WebSocket fixture becomes a valid S0 event;
  malformed, partial, silent-empty, and drifted payloads become typed
  refusals/outcomes without leakage.
- [x] Snapshot identity does not assume provider timestamps are unique.
- [x] WebSocket behavior proves auth, ping/pong, rotation, reconnect, exact
  resubscription, bounded queues, cancellation, and clean shutdown under
  deterministic fakes.
- [x] Metrics expose request/quota latency, disconnect, parse failure,
  duplicate, gap, and queue pressure.
- [x] A guarded read-only probe can capture sanitized evidence and clearly
  reports skipped/unverified market-hours assertions.
- [x] Focused tests, relevant backend tests, compile/import checks, and final
  diff review pass.
- [ ] The graduated S1 code is deployed to the backend service, and post-deploy
  health and read-only DNSE checks pass.

## Validation

Run the narrow S1 suite first, then S0 regressions and repository backend
quality gates discovered from current project tooling. Live verification is
optional unless the environment contains DNSE credentials and the market is
open; absence must remain an explicit unverified gate, not a fabricated pass.

The S1 and S0 regression suite passes 58 tests. The full backend run passes
2,635 tests but remains red on unrelated baseline state: the configured Upstash
registration rate limit, a missing streaming topology document, and a
credential-dependent FiinQuant expectation. The read-only DNSE probe verifies
the four selected REST surfaces, verified WebSocket TLS and HMAC authentication,
and a lower bound of eight simultaneous market-data subscriptions. Its
outside-hours result still leaves live payload, throughput, maximum subscription
limit, quote-scale, ordering, and reconnect-gap evidence open.

## Risks and rollback

- Provider docs and wire payloads may drift; strict fixture parsing and typed
  drift refusal contain the blast radius.
- A reconnect can replay snapshots; collision-safe payload hashing plus
  explicit dedupe prevents inflation.
- Provider quota headers may be absent; conservative published defaults remain
  enforced and unknown families learn only from returned headers.
- Rollback is removal of the isolated `stocks.realtime.dnse` package, its
  tests/fixtures, and the S1 dependency declaration; S0 contracts remain
  intact.

## Unresolved questions

None for implementation. Actual market-hours limits, payload throughput, quote
quantity scale, and reconnect gap size remain empirical exit evidence and
cannot be honestly closed outside a controlled open-market run. The repository
does not identify the remote backend platform or service; resolve that target
before the post-graduation deployment.

## Deferred operational validation

The owner accepted continuing outside-hours development into S2 on August 24,
2026. This does not waive or pass the remaining S1 live gate. Run the guarded
probe during the next open-market window, attach the sanitized report, then
graduate and deploy only after the measured assertions pass.
