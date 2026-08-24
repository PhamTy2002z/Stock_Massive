# Realtime ingestion spine progress

S2 implementation is complete and disabled by default until its production
dependencies pass. The deferred S1 market-hours probe remains an explicit
activation gate rather than a blocker for outside-hours development.

## Delivered

- Added dedicated realtime event, checkpoint, spill, and health storage with a
  reversible Alembic migration.
- Added monotonic Redis projections, bounded ingestion, deterministic replay,
  REST/WebSocket reconciliation, and opt-in application lifecycle ownership.
- Added `GET /api/v1/realtime/health`, environment contracts, Compose wiring,
  architecture docs, and controlled resource tests.

## Verification

- S0-S2 regression: 76 passed.
- Owner and blast-radius regression: 113 passed.
- Full backend baseline: 2,661 passed, 1 skipped, 16 failed, and 61 errors. The
  failures match the pre-existing Upstash, missing topology document, and
  FiinQuant environment groups; no realtime test failed.
- Alembic head, isolated upgrade/downgrade SQL, dependency integrity, Compose
  configuration, compile, and whitespace checks passed.
- The local Docker Compose API was rebuilt and migrated to `c8f2a6d31e04` on
  August 24, 2026. `/health` returned `200`, all four realtime tables existed,
  and the deployed runtime reported realtime ingestion disabled.
- A verified 7.2 MB pre-migration PostgreSQL backup and its SHA-256 digest are
  recorded in [the deployment runbook](../../docs/deployment.md).

## Remaining gates

- Run the S1 controlled probe during an open-market window.
- Configure DNSE credentials, validate live-market semantics and capacity, and
  then explicitly enable realtime ingestion.
- Define a remote production platform and public URL if this service must move
  beyond the current local Docker Compose deployment.
