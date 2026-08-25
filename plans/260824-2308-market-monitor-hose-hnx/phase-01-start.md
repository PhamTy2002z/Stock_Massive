---
phase: 1
title: "Freeze monitor contracts and baseline"
status: completed
priority: P1
effort: "1d"
dependencies: []
---

# Phase 1: Freeze monitor contracts and baseline

## Overview

Turn the approved UX brief into executable response and metric contracts before
aggregation or rendering changes. Treat current dirty S3 work as baseline.

## Requirements

- Define five lens payloads, common metadata, filters, pagination, and detail.
- Lock complete, partial, stale, disconnected, unavailable, and recovered states.
- Require source, as-of, freshness, unit, method, issue, and coverage.
- Preserve stored-read-only and provider ownership boundaries.

## Architecture

Create one `stocks.monitor` boundary. Strict Pydantic schemas cannot represent
impossible coverage or a derived metric without its interpretation metadata.

## Related code files

- Create: `apps/api/src/stocks/monitor/__init__.py`
- Create: `apps/api/src/stocks/monitor/schemas.py`
- Create: `apps/api/tests/test_market_monitor_contracts.py`
- Read/protect: `apps/api/src/stocks/providers/contracts.py`
- Read/protect: `apps/api/src/stocks/realtime/contracts.py`

## Implementation steps

1. Capture overlapping dirty diffs; classify owned versus unrelated changes.
2. Write failing response/state/schema tests.
3. Define strict models, enums, horizons, filters, sort keys, and method versions.
4. Reject missing interpretation metadata and impossible coverage.
5. Run contract tests and the current S3 focused baseline.

## Success criteria

- [x] Public shapes and states are test-locked before service code.
- [x] Metrics cannot omit unit, as-of, coverage, or method.
- [x] Existing S3 focused baseline stays green.

## Risk assessment

Later public-shape churn would destabilize UI. Treat it as a phase-boundary
review, not incidental refactoring.
