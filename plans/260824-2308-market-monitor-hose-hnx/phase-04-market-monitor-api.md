---
phase: 4
title: "Expose bounded market-monitor APIs"
status: completed
priority: P1
effort: "1.5d"
dependencies: [2, 3]
---

# Phase 4: Expose bounded market-monitor APIs

## Overview

Publish cohesive authenticated endpoints for every lens and symbol detail,
backed only by the monitor service.

## Requirements

- Overview, breadth, flows, sectors, stocks, and stock-detail reads.
- HOSE/HNX, date, horizon, filter, sort, and pagination inputs.
- Strict validation, bounded payloads/windows, rate limits, and cache correctness.
- No provider instantiation on request.

## Architecture

Mount `/api/v1/stocks/market-monitor`. Routers only validate/translate.
Successful empty or partial findings remain HTTP 200 with coverage/issues.

## Related code files

- Create: `apps/api/src/stocks/monitor/router.py`
- Create: `apps/api/tests/test_market_monitor_api.py`
- Modify: `apps/api/src/stocks/router.py`
- Reuse: core rate-limit and cache utilities

## Implementation steps

1. Write route tests for auth, validation, bounds, partial data, and cache invalidation.
2. Add routes without exposing ORM/provider payloads.
3. Add stable cursor/page behavior and whitelisted filters/sorts.
4. Assert reads never construct provider clients.
5. Lock OpenAPI/public schemas.
6. Run monitor, realtime, snapshot, signal, auth, and rate-limit tests.

## Success criteria

- [x] Each lens loads independently without frontend request fan-out.
- [x] Invalid exchange/horizon/date/sort/filter/cursor inputs fail clearly.
- [x] Empty/partial findings carry reasons.
- [x] Response size and query count stay bounded.

## Risk assessment

Keep summaries compact and stock results paginated. Test serialized size at the
maximum supported limit.
