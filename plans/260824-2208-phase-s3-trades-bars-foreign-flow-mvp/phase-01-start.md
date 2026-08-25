---
phase: 1
title: "Event-derived bars and query boundary"
status: completed
priority: P1
effort: "2d"
dependencies: []
---

# Event-derived bars and query boundary

## Overview

Build deterministic trade aggregation and bounded durable reads on top of the
existing normalized event store without introducing a second realtime path.

## Requirements

- Functional: admit G1 round-lot and G4 odd-lot trades with their existing
  normalization rules and keep board identity through every output.
- Functional: aggregate one-minute bars, then derive 3m, 5m, 15m, 30m, and 1h
  bars only from complete one-minute inputs within one trading session.
- Functional: retain input evidence IDs, method version, resolution, board
  policy, price basis, schema version, and collision-safe identity.
- Non-functional: late and duplicate events must recompute deterministically;
  no process-local state may be the only owner.

## Architecture

Add a pure aggregation module under `stocks/realtime` and call it from a
projection coordinator after the source event is durably appended. Derived bars
return through the same append/projection path with `stock_massive` provenance.
Extend `RealtimeEventStore` with bounded symbol/family/time reads and opaque
cursor ordering that matches durable replay.

## Related code files

- Create: `apps/api/src/stocks/realtime/aggregation.py`
- Create: `apps/api/src/stocks/realtime/bar_projection.py`
- Modify: `apps/api/src/stocks/realtime/contracts.py`
- Modify: `apps/api/src/stocks/realtime/storage.py`
- Modify: `apps/api/src/stocks/realtime/spine.py`
- Test: `apps/api/tests/test_realtime_aggregation.py`
- Test: `apps/api/tests/test_realtime_queries.py`

## Implementation steps

1. Write contract tests for board separation, session boundaries, gaps, late
   events, duplicates, provenance, and higher-resolution rollups.
2. Add backward-compatible derived-bar provenance fields and method versioning.
3. Implement pure trade-to-minute and minute-to-higher-resolution aggregation.
4. Add deterministic bounded event queries and cursor encoding/validation.
5. Wire derived processing after durable append without recursive inflation.

## Success criteria

- [x] G1 and G4 quantities remain canonical shares and separate board streams.
- [x] Aggregation is stable under reordered and duplicate input.
- [x] No bar crosses a break, auction, date, board, symbol, or product boundary.
- [x] Store queries are bounded and retain the replay order.

## Risk assessment

Late events can invalidate an already published bar. Recompute the affected
bucket from durable evidence and publish a superseding collision-safe identity;
never mutate prior evidence or silently patch totals.
