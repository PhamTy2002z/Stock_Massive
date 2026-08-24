---
title: "Realtime ingestion spine"
description: >-
  Durable normalized-event ingestion, hot projections, recovery, health, and
  replay
status: completed
priority: P1
effort: "4d"
tags: [system, market-data, realtime, storage, redis, replay]
created: 2026-08-24
---

# Realtime ingestion spine

## Outcome contract

Create one bounded, restart-safe path from admitted S1 normalized events to a
dedicated PostgreSQL event store, Redis hot projections, durable checkpoints,
queryable health, and deterministic replay. Keep the EOD
`provider_snapshots` path unchanged.

Constraints:

- Preserve S0 event models, provenance, units, provider time, and observation
  time without storing DNSE wire payloads or credentials.
- Use at-least-once delivery with idempotent writes; never claim exactly-once.
- Bound memory and expose queue pressure, spill, degraded state, and shutdown.
- Keep Redis rebuildable from PostgreSQL and treat it as a projection, not the
  durable owner.
- Do not admit S1 event families or units that remain live-unverified.
- Do not weaken or skip tests, and do not modify UI or product APIs.

Non-goals:

- S3 bar aggregation, signal calculations, public product endpoints, or UI.
- Changing historical EOD ownership or `provider_snapshots` semantics.
- Production enablement, SLO selection, or claiming live-market capacity.

## Phases

1. Add dedicated realtime event, checkpoint, and spill tables with an Alembic
   migration and strict event serialization.
2. Implement idempotent durable writes, partitioned replay order, checkpoint
   resume, and Redis hot projections for every S0 event family plus health.
3. Implement the bounded ingestion worker, durable spill recovery, degradation,
   graceful shutdown, and DNSE REST/WebSocket coordinator seams.
4. Prove restart, reconnect, duplicate, replay, backpressure, and resource
   envelopes with deterministic and load tests; review docs and contracts.

## Acceptance criteria

- [x] Realtime events persist outside `provider_snapshots`, partitioned by
  trading day and event family and ordered deterministically for replay.
- [x] Duplicate delivery, retry, reconnect, spill recovery, and restart cannot
  create a second durable event or double-apply a projection.
- [x] Redis exposes current session, latest trade, book, foreign flow, auction,
  index, closed bar, security definition, and feed/data health projections.
- [x] Durable checkpoints resume at-least-once processing without an
  exactly-once claim.
- [x] Queue overflow spills durably and marks the feed degraded; shutdown drains
  within its bound or leaves recoverable spill records.
- [x] REST bootstrap/backfill/reconciliation and WebSocket live delivery share
  the same parser, store, projection, checkpoint, and health path.
- [x] Replay never calls DNSE and yields identical ordered normalized events for
  an identical partition.
- [x] Restart/reconnect tests prove no unexplained gap or projection inflation.
- [x] Load tests remain inside explicit queue, latency, CPU, and memory bounds.
- [x] Focused tests, shared realtime regressions, migration checks, compile,
  configured quality checks, and final review pass.

## Validation

Run focused ingestion tests first, then all S0/S1 realtime tests. Validate the
Alembic graph and upgrade/downgrade SQL offline. Run deterministic load tests
with a fixed event set and explicit resource thresholds. Broader backend
failures must be attributed rather than hidden.

The S0-S2 regression suite passes 76 tests. The focused owner and blast-radius
suite passes 113 tests. The full backend run passes 2,661 tests and has
the same unrelated baseline failures as the prior S1 run: configured Upstash
registration throttling, the missing `docs/streaming-topology.md`, and a
credential-dependent FiinQuant expectation. Alembic recognizes the realtime
migration as the single head, and its isolated upgrade and downgrade SQL both
generate successfully. Docker Compose development and production configuration
validate with their required production placeholders supplied. The repository
does not configure Ruff, Black, mypy, or Pyright in the active environment;
compile and executable contract tests are the available Python quality gates.

On August 24, 2026, the local Docker Compose backend was rebuilt from the full
API source and migrated from `b7f4e9c21a08` to `c8f2a6d31e04`. The root health
check returned `200`, the realtime route appeared in OpenAPI, all four realtime
tables existed, and the deployed runtime reported
`REALTIME_INGESTION_ENABLED=false`. A verified pre-migration PostgreSQL backup
is recorded in [the deployment runbook](../../docs/deployment.md).

## Risks and rollback

- Redis and PostgreSQL can diverge after a partial failure; replay rebuilds hot
  state from the durable event order and health remains degraded until recovery.
- A full queue can otherwise lose evidence; durable spill owns overflow before
  the worker acknowledges it.
- Event schema drift can break replay; family-discriminated strict decoding
  refuses unknown payloads instead of guessing.
- Rollback removes the isolated ingestion package and reverses its migration;
  S0/S1 contracts and EOD snapshots remain intact.

## Unresolved questions

The local backend deploy target and command are now recorded in
[the deployment runbook](../../docs/deployment.md). The repository still
does not define a remote production environment or public backend URL. S1
live-market validation remains required before production activation; S2 stays
disabled by default until that gate passes.
