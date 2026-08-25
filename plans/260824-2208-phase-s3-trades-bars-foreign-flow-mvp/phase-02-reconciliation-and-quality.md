---
phase: 2
title: "Reconciliation and quality"
status: completed
priority: P1
effort: "1d"
dependencies: [1]
---

# Reconciliation and quality

## Overview

Compare trade, bar, DNSE daily, and FiinQuant evidence without changing any
source value, and turn incomplete or mismatched sessions into explicit quality.

## Requirements

- Functional: reconcile G1 trade totals to one-minute bars and minute bars to
  DNSE daily OHLCV/value.
- Functional: compare DNSE daily evidence with FiinQuant under the existing
  cross-provider provenance contract.
- Functional: preserve mismatch, incomplete, and not-comparable outcomes.
- Non-functional: tolerances are versioned policy owned by the product owner,
  not implicit floating-point defaults.

## Architecture

Implement a pure reconciliation service that produces
`ReconciliationResult` plus a session quality projection. The service consumes
evidence references and explicit metric tolerances. It never writes adjusted
market data.

## Related code files

- Create: `apps/api/src/stocks/realtime/reconciliation.py`
- Modify: `apps/api/src/stocks/realtime/policy.py`
- Modify: `apps/api/src/stocks/realtime/health.py`
- Test: `apps/api/tests/test_realtime_session_reconciliation.py`

## Implementation steps

1. Freeze the owner-approved tolerance profile and method version in tests.
2. Add deterministic trade-to-bar, bar-to-DNSE, and cross-provider comparisons.
3. Map incomplete and mismatched results to data quality without altering
   stored measurements.
4. Cover missing boards, partial sessions, late events, and unit mismatches.

## Success criteria

- [x] Exact fixtures reconcile and deliberate drift produces a mismatch.
- [x] Cross-provider comparison retains both evidence identities and sources.
- [x] Every completed comparison records the applied tolerance profile in an
  append-only shadow audit.
- [x] No reconciliation code overwrites normalized or EOD evidence.

## Risk assessment

A tolerance selected from one observed session can hide data corruption. The
owner approved immutable exact-zero v1 in shadow mode on August 24, 2026. Keep
v1 unchanged; propose v2 only after 10–20 live sessions demonstrate a
legitimate repeatable difference. Production activation remains blocked by the
separate S1 market-hours probe.
