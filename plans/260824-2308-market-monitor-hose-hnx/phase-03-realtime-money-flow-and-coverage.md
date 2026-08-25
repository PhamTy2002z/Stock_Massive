---
phase: 3
title: "Add realtime money-flow overlay and coverage"
status: completed
priority: P1
effort: "2d"
dependencies: [1, 2]
---

# Phase 3: Add realtime money-flow overlay and coverage

## Overview

Overlay admitted DNSE projections on the EOD monitor while preserving source,
session, board, unit, and completeness boundaries.

## Requirements

- Signed active flow, foreign flow, VWAP, acceleration, and flow/ADTV.
- Historical foreign net for 1/5/20 sessions and ranked inflow/outflow.
- Typed no-feed, partial, stale, disconnected, and recovered states.
- Realtime never overwrites EOD evidence or silently merges G1/G4.

## Architecture

Add a bounded bulk read to the hot projection boundary. Merge results into a
separate realtime overlay. Expose EOD and realtime clocks independently.

## Related code files

- Create: `apps/api/src/stocks/monitor/realtime.py`
- Create: `apps/api/tests/test_market_monitor_flow.py`
- Modify carefully: `apps/api/src/stocks/realtime/projections.py`
- Modify carefully: `apps/api/src/stocks/realtime/service.py`
- Reuse: realtime metrics and foreign-flow signal modules

## Implementation steps

1. Write fixture tests for all feed/coverage/board/recovery states.
2. Add one bounded bulk projection read with stable symbol ordering.
3. Compute flow ranks and price/flow quadrants only for comparable evidence.
4. Merge EOD and realtime without mutating either.
5. Propagate health and per-metric eligible/evaluated coverage.
6. Run S3, foreign-flow, and monitor-flow regressions.

## Success criteria

- [x] Partial DNSE coverage is never labeled full-market realtime.
- [x] Realtime loss leaves EOD readable with an explicit state.
- [x] G1/G4 and share/value units are never silently combined.
- [x] Existing S3 replay/projection contracts stay green.

## Risk assessment

S1 lacks market-hours graduation and DNSE credentials are absent in this shell.
Use deterministic fixtures; do not fabricate the external live gate.
