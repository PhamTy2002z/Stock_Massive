---
title: Realtime ingestion spine outside-hours delivery
date: 2026-08-24
summary: Completed S2 deterministically while preserving the deferred S1 live-market activation gate.
---

# Realtime ingestion spine outside-hours delivery

## What happened

The S1 adapter implementation was deterministic-complete, but its payload,
throughput, quote-scale, ordering, and reconnect-gap probe cannot run honestly
outside Vietnamese market hours. The roadmap now records that gate as deferred
without treating it as permission to claim production readiness.

S2 added a dedicated normalized-event store, Redis hot projections, durable
checkpoints and spill recovery, deterministic replay, feed/data health, the
read-only health API, and opt-in DNSE runtime lifecycle wiring. Realtime data
never enters `provider_snapshots`, and book subscriptions remain disabled until
quote quantity scale is empirically proven.

## Verification

The S0-S2 suite passed 76 tests and the focused blast-radius suite passed 113.
The full backend run passed 2,661 tests; its 16 failures and 61 errors matched
pre-existing Upstash throttling, a missing topology document, and FiinQuant
environment expectations. Alembic upgrade/downgrade SQL, Compose validation,
compile, dependency, and whitespace checks passed.

## Decision

S2 is complete but disabled by default. Production activation and deployment
remain gated on the S1 open-market probe and discovery of the backend deployment
target.

## Next steps

Run the S1 probe during market hours, identify the backend service and deploy
command, apply the migration, deploy the backend, verify health, and only then
enable realtime ingestion.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
