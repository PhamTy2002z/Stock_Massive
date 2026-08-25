---
phase: 3
title: "Source-neutral projections and signal bridge"
status: completed
priority: P1
effort: "1d"
dependencies: [1, 2]
---

# Source-neutral projections and signal bridge

## Overview

Publish deterministic trade and foreign-flow metrics, reconstruct the UPCOM
anchor input, and supply foreign share flow to the existing signal contract.

## Requirements

- Functional: derive session VWAP, signed flow, trade intensity, volume
  acceleration, and foreign buy/sell/net volume and value with evidence IDs.
- Functional: reconstruct prior-day UPCOM round-lot continuous VWAP while
  excluding G4 odd-lot, negotiated, auction, and ineligible sessions.
- Functional: serve foreign net share volume beside ADTV shares through
  `foreign_flow_pressure.net_volume_over_adtv`.
- Non-functional: projections are source-neutral, rebuildable, versioned, and
  refuse incomplete evidence rather than mixing units or sources.

## Architecture

Add strict projection models and a deterministic engine fed by durable events.
Store current projections in Redis through the existing hot-store boundary and
rebuild them from PostgreSQL replay. Extend the signal window with an explicit
foreign-share series rather than writing DNSE realtime data into historical EOD
snapshots.

## Related code files

- Create: `apps/api/src/stocks/realtime/metrics.py`
- Modify: `apps/api/src/stocks/realtime/projections.py`
- Modify: `apps/api/src/stocks/signals/bars.py`
- Modify: `apps/api/src/stocks/signals/fields.py`
- Modify: `apps/api/src/stocks/signals/foreign_flow.py`
- Modify: `apps/api/src/stocks/signals/registry.py`
- Test: `apps/api/tests/test_realtime_metrics.py`
- Test: `apps/api/tests/test_foreign_flow.py`
- Test: `apps/api/tests/test_market_behavior.py`

## Implementation steps

1. Add strict projection and foreign-share window contracts.
2. Implement trade, foreign-flow, and UPCOM methods with explicit versions.
3. Persist rebuildable hot projections with evidence and quality metadata.
4. Replace the registered share-pressure refusal only when the complete DNSE
   session window exists; retain exact refusal semantics otherwise.
5. Prove replay rebuilds identical projections.

## Success criteria

- [x] Every metric has units, as-of time, method version, quality, and evidence.
- [x] UPCOM anchor excludes all ineligible activity by construction.
- [x] Share-pressure reads real stored shares and never substitutes money flow.
- [x] Missing sessions, foreign flow, or ADTV shares still refuse explicitly.

## Risk assessment

Changing the signal from always-refused to conditionally served is a public
behavior change. Preserve its field name, unit, claim, interpretation boundary,
and refusal codes, and cover both old refusal and new success paths.
