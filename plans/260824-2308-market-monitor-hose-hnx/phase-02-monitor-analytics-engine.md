---
phase: 2
title: "Build monitor analytics engine"
status: completed
priority: P1
effort: "3d"
dependencies: [1]
---

# Phase 2: Build monitor analytics engine

## Overview

Build one bulk deterministic read model for pulse, breadth, trend, sector
rotation, stock screening, and valuation from stored evidence.

## Requirements

- HOSE/HNX scope and 1/5/20/252-session measures.
- Reuse canonical price, volume, trading-day, and corporate-action rules.
- Stable `as_of` results, ordering, coverage, and named refusals.
- Bounded bulk reads; no per-row provider or database fan-out.

## Architecture

Resolve the listed/tracked cohort once, bulk-load market, valuation, reference,
and index rows, then build immutable frames. Calculators consume frames rather
than ORM rows. Cache by scope, as-of, data generations, and method versions.

## Related code files

- Create: `apps/api/src/stocks/monitor/frames.py`
- Create: `apps/api/src/stocks/monitor/analytics.py`
- Create: `apps/api/src/stocks/monitor/service.py`
- Create: `apps/api/tests/test_market_monitor_analytics.py`
- Create: `apps/api/tests/test_market_monitor_queries.py`
- Modify only if required: `apps/api/src/stocks/signals/bars.py`
- Reuse: `listing_roster.py`, `trading_day.py`, provider snapshot store

## Implementation steps

1. Write fixtures for direction, limits, gaps, seams, actions, sectors, and valuation.
2. Implement bulk frame loading over canonical sessions/source ownership.
3. Compute breadth, MA breadth, highs/lows, liquidity, and volume breadth.
4. Compute index trend, sector returns, relative strength, participation, rotation.
5. Compute market/sector valuation medians and historical percentiles.
6. Implement shared stock filtering/sorting primitives.
7. Add generation cache and query-count/performance tests.

## Success criteria

- [x] Golden fixtures are exact across repeat runs.
- [x] Incomparable windows refuse/degrade instead of guessing.
- [x] Exchange/sector totals reconcile with coverage.
- [x] Query count remains bounded as cohort size grows.

## Risk assessment

If bulk optimization requires duplicating canonical adjustment logic, stop and
create a shared gateway instead; correctness outranks query reduction.
