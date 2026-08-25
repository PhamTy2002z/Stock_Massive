---
title: "Phase S3 trades, bars, and foreign-flow MVP"
description: >-
  Deterministic trade-derived bars, reconciliation, source-neutral projections,
  signal inputs, and bounded realtime APIs for the configured Universe
status: completed
priority: P1
effort: "5d"
tags: [system, market-data, realtime, bars, foreign-flow, api]
created: 2026-08-24
blockedBy: [260824-s1-dnse-adapter-conformance]
---

# Phase S3 trades, bars, and foreign-flow MVP

## Outcome contract

Deliver the complete S3 vertical slice from admitted DNSE round-lot and odd-lot
trades through deterministic bars, reconciliation, foreign-flow and trade
projections, source-neutral APIs, and the existing share-denominated foreign
flow signal contract. Live and replay processing must produce identical outputs
for identical normalized evidence.

Constraints:

- Preserve S0 identities, units, board distinctions, provenance, and typed
  quality states; never rewrite one provider with another.
- Reuse the S2 event store, ingestion spine, and replay order. Keep
  `provider_snapshots` as the historical EOD owner.
- Limit ingestion to the configured Universe while keeping the full-market
  security-definition refresh independent.
- Keep public windows and page sizes bounded, and expose evidence, freshness,
  units, and quality on every response.
- Keep S1 live-market claims ungraduated until its controlled market-hours probe
  passes. Do not weaken, skip, narrow, or delete tests.

Non-goals:

- S4 depth, auction, session-state, index, and market-pulse work.
- S5 derivatives, historical session controls, or model features.
- S6 frontend surfaces or a new transport. No UI change is planned, so
  Impeccable remains inactive unless implementation evidence changes this scope.
- Production activation before the S1 live probe and S3 reconciliation gates.

## Phases

1. [Event-derived bars and query boundary](./phase-01-start.md)
2. [Reconciliation and quality](./phase-02-reconciliation-and-quality.md)
3. [Source-neutral projections and signal bridge](./phase-03-source-neutral-projections-and-signal-bridge.md)
4. [Bounded APIs, replay, and graduation](./phase-04-bounded-apis-replay-and-graduation.md)

## Acceptance criteria

- [x] G1 and G4 trades retain board-specific share units and never merge their
  identities.
- [x] One-minute and accepted higher-resolution bars are deterministic across
  live and replay, respect Vietnamese session boundaries, and retain their input
  evidence and method versions.
- [x] Trade-to-minute, minute-to-DNSE-daily, and DNSE-to-FiinQuant comparisons
  preserve both sources and emit quality states instead of adjusted data.
- [x] Session VWAP, signed flow, trade intensity, volume acceleration, foreign
  flow, and UPCOM prior-day round-lot continuous VWAP are served through
  source-neutral contracts.
- [x] `foreign_flow_pressure.net_volume_over_adtv` uses stored DNSE share counts
  through its existing field registration and refuses incomplete windows.
- [x] Bars, trades, foreign flow, and health APIs enforce Universe membership,
  bounded windows, stable cursor pagination, and no provider call on read.
- [x] Full-market instrument refresh remains separate from Universe-filtered
  realtime subscriptions and serving.
- [x] Focused S3 tests, S0-S2 regressions, backend compile/tests, and final diff
  review pass with no new public-contract or security regression.

## Validation

Run focused deterministic tests after each phase, then the complete realtime
suite and affected signal/API tests. Compare live-path processing with replay
from the same fixtures byte-for-byte after excluding observation timestamps that
are intentionally different. Attribute pre-existing backend failures; never hide
or waive a new failure.

## Dependency and recorded decision

S3 implementation is complete, but production activation remains blocked by
the S1 market-hours probe. On August 24, 2026 the owner approved immutable
exact-zero v1 tolerances for price, volume, and value in shadow mode. Mismatches
are appended to durable audit evidence and reduce audit quality without
blocking ingestion or changing either source. A non-zero v2 requires evidence
from 10–20 live sessions.

<!-- slug: phase-s3-trades-bars-foreign-flow-mvp -->
