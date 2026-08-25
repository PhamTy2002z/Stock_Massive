---
phase: 4
title: "Bounded APIs, replay, and graduation"
status: completed
priority: P1
effort: "1d"
dependencies: [1, 2, 3]
---

# Bounded APIs, replay, and graduation

## Overview

Expose S3 evidence through thin read-only endpoints, prove Universe separation
and replay parity, then reconcile the roadmap only from executable evidence.

## Requirements

- Functional: add bars, trades, foreign-flow, and projection/health endpoints
  with bounded windows and stable cursor pagination.
- Functional: enforce current Universe membership on serving and subscription;
  keep full-market security-definition refresh independent.
- Functional: expose source, board, units, as-of time, freshness, quality, and
  evidence IDs without raw DNSE payloads.
- Non-functional: endpoint reads never contact providers and replay produces the
  same bars and projections as live-path processing.

## Architecture

Keep `router.py` thin and place query, Universe, cursor, freshness, and response
assembly in `service.py`. Reuse durable events and projection contracts. Update
roadmap/docs only after focused and broad gates prove each checkbox.

## Related code files

- Modify: `apps/api/src/stocks/realtime/router.py`
- Modify: `apps/api/src/stocks/realtime/service.py`
- Modify: `apps/api/src/stocks/realtime/runtime.py`
- Modify: `apps/api/tests/test_realtime_router.py`
- Create: `apps/api/tests/test_realtime_mvp.py`
- Modify: `docs/system-roadmap.md`
- Modify: `docs/system-data-contracts.md`

## Implementation steps

1. Define strict response and cursor contracts, then add thin endpoints.
2. Prove invalid symbols, non-Universe symbols, oversized windows, bad cursors,
   empty data, stale data, partial sessions, and provider isolation.
3. Run live-path and replay-path parity over identical normalized fixtures.
4. Run focused tests, realtime regressions, affected signal tests, backend
   compile/full suite, and pending-diff review.
5. Update only roadmap items and durable architecture rationale supported by
   source, tests, or accepted live evidence.

## Success criteria

- [x] Public reads are bounded, paginated, source-neutral, and provider-free.
- [x] Universe filtering and full-market instrument refresh cannot drift into
  one concern.
- [x] Replay equality covers bars, projections, evidence IDs, and quality.
- [x] No new backend test, compile, security, or contract regression remains.

The final backend run passed 2,792 tests with one skip and 56 deselections. Its
only failure is the pre-existing deployment-topology assertion for
`docs/streaming-topology.md`, which is absent from `HEAD` and outside S3. The
focused affected suite passed 169 tests, and backend compile plus diff checks
passed.

## Risk assessment

Roadmap completion can outrun live evidence. Leave the S1 probe and any
unapproved S3 tolerance gate unchecked even when deterministic implementation
is complete; never describe outside-hours fixtures as production proof.
