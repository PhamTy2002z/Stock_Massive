---
title: "Market Monitor HOSE HNX"
description: "Deliver an evidence-led five-lens market monitor over stored FiinQuant, Vnstock, and DNSE data without hiding partial coverage."
status: completed
priority: P1
effort: "12d"
branch: develop
tags: [feature, frontend, backend, api, market-data, critical]
blockedBy: []
blocks: []
created: 2026-08-24
---

# Market Monitor HOSE HNX

## Overview

Replace the single long VN30 board with a navigable Market Monitor for
Vietnamese investors and brokers with medium- and long-term horizons. Five
URL-addressable lenses answer, in sequence: what the market is doing, whether
the move is broad, where money is moving, which sectors lead, and which stocks
carry the evidence.

The serving path reads stored normalized evidence only. FiinQuant owns EOD
market and valuation history, Vnstock owns reference/fundamental facts, and
DNSE supplies the admitted realtime overlay. Missing or partial realtime
coverage degrades explicitly; it never triggers silent fallback or a zero.

## Scope

### In scope

- Tổng quan, Độ rộng, Dòng tiền, Ngành, and Cổ phiếu lenses.
- HOSE, HNX, and combined exchange filters over the tracked/listed cohort.
- Market pulse, breadth, trend regime, sector rotation, flow, and valuation.
- URL/deep-link state, browser history, filter/sort persistence, and inspector.
- Source, as-of, freshness, units, method version, quality, and coverage.
- Accessible responsive states, backend/API/frontend tests, build, and docs.

### Out of scope

- UPCOM, execution, alerts, Telegram/email, order-book/auction visuals.
- News sentiment, derivatives, proactive monitoring, and production deployment.
- Provider ownership changes or claims that S1 realtime has graduated.

## Architecture

```text
Listing roster + stored EOD snapshots + index series + realtime projections
                              |
                    deterministic monitor engine
                              |
       overview | breadth | flows | sectors | stocks | stock detail
                              |
        React Query hooks + URL state + five-lens Board workspace
                              |
                    existing symbol inspector
```

| Concern | Authority | Monitor use |
|---|---|---|
| EOD OHLCV, active flow, foreign value | FiinQuant | Historical baseline and cross-section |
| Valuation series | FiinQuant | P/E and P/B median/percentile |
| Exchange, industry, shares, foreign room | Vnstock reference | Classification and standing |
| Trades, bars, signed flow, intraday foreign flow | DNSE | Realtime overlay where covered |
| Index history | FiinQuant | VNINDEX/HNXINDEX trend and relative strength |

No request-time provider call. Responses always report eligible/evaluated
coverage and one of complete, partial, stale, disconnected, or unavailable.

## Metric definitions

- Breadth: advancing/declining/unchanged against prior comparable close.
- Trend breadth: share of evaluable symbols above MA20/50/200.
- High/low breadth: new 20-session and 252-session highs/lows.
- Liquidity: current traded value divided by trailing 20-session mean.
- Volume breadth: advancing volume / (advancing + declining volume).
- Sector performance: median constituent return for 1/5/20 sessions.
- Sector relative strength: sector median return minus owning index return.
- Flow intensity: foreign net value or signed flow divided by ADTV20.
- Valuation regime: median P/E/P/B and percentile against stored daily medians;
  exclude non-positive ratios and report sample coverage.

Every derived metric has one backend-owned method version and sample floor.

## Phases

| # | Phase | Status | Depends on |
|---|---|---|---|
| 1 | [Freeze monitor contracts and baseline](./phase-01-start.md) | Completed | S3 baseline |
| 2 | [Build monitor analytics engine](./phase-02-monitor-analytics-engine.md) | Completed | 1 |
| 3 | [Add realtime money-flow overlay and coverage](./phase-03-realtime-money-flow-and-coverage.md) | Completed | 1, 2 |
| 4 | [Expose bounded market-monitor APIs](./phase-04-market-monitor-api.md) | Completed | 2, 3 |
| 5 | [Add workspace navigation and URL state](./phase-05-workspace-navigation-and-client-state.md) | Completed | 1 |
| 6 | [Build five lenses and inspector integration](./phase-06-five-lens-ui-and-inspector.md) | Completed | 4, 5 |
| 7 | [Run integration, performance, docs, and review gates](./phase-07-integration-performance-docs-and-review.md) | Completed | 4, 6 |

## Contract traceability

| Phase | Contract items | Acceptance signals | Evidence / prerequisite |
|---|---|---|---|
| 1 | Provider, state, metric contracts | Contract tests reject semantic drift | S0-S3 contracts |
| 2 | Pulse, breadth, trend, sector, valuation | Deterministic fixture tests | Stored snapshots/index |
| 3 | Money flow, realtime, coverage | Replay/live-equivalent projections | Completed S3 local code |
| 4 | Complete API surface | Auth/bounds/schema/query tests | Phases 2-3 |
| 5 | Navigation and persistence | Deep-link/history/state tests | Existing shell |
| 6 | Responsive UI and inspector | Component/a11y/E2E tests | Stable API and URL state |
| 7 | Whole-product quality | Broad test/type/lint/build/E2E | All phases |

## Cross-plan relationships

- `260824-2208-phase-s3-trades-bars-foreign-flow-mvp` supplies the completed
  realtime store, projections, bounded reads, and quality semantics.
- `260824-s1-dnse-adapter-conformance` owns the market-hours probe and
  production graduation. This plan cannot claim complete-market realtime.
- This is a vertical System S4/S6 slice. Depth, auction, derivatives, and
  deployment remain out of scope.

## Validation

```bash
cd apps/api && .venv/bin/pytest -q tests/test_market_monitor_*.py tests/test_realtime_*.py tests/test_foreign_flow.py
cd apps/api && make test && make lint
cd apps/web && pnpm test && pnpm type-check && pnpm lint && pnpm build
cd apps/web && pnpm test:e2e -- --grep "market monitor"
```

Do not weaken, skip, narrow, or delete tests to pass. Attribute pre-existing
failures with a reproducible baseline; fix every new failure.

## Success criteria

- [x] Five lenses work end-to-end with real stored evidence and honest partial states.
- [x] HOSE/HNX, deep links, history, filters, sort, scroll, and inspector behave as specified.
- [x] APIs expose source, as-of, freshness, unit, method, issue, and coverage.
- [x] No request-time provider call, silent fallback, fabricated zero, or source overwrite.
- [x] Responsive loading, empty, stale, partial, disconnected, error, and recovery are tested.
- [x] Focused and broad gates pass; review leaves no unresolved critical issue.

## Risks and rollback

- Partial realtime stays EOD-first with explicit evaluated/eligible coverage.
- Cross-sectional reads use bounded bulk queries and generation-keyed caches.
- Current dirty S3 files are baseline evidence; never revert unrelated edits.
- Reuse canonical bar rules for corporate actions and price-basis seams.
- Rollback monitor-only modules and restore BoardView; leave S0-S3 storage intact.

## Open questions

None. Production DNSE graduation remains an external S1 prerequisite.

<!-- slug: market-monitor-hose-hnx -->
