---
phase: 1
title: "Event contract foundation"
status: in-progress
priority: P1
effort: "3h"
dependencies: []
---

# Phase 1: Event contract foundation

## Overview

Create the source-neutral realtime package and the eight strict event models
owned by S0.

## Requirements

- Functional: define `TradeTick`, `BookSnapshot`, `ForeignFlowSnapshot`,
  `AuctionSnapshot`, `SessionState`, `IndexTick`, `SecurityDefinition`, and
  `ClosedBar`.
- Non-functional: immutable models, forbidden unknown fields, aware timestamps,
  exact decimals, and collision-safe identity.

## Architecture

The package lives at `src/stocks/realtime`. A shared `EventMetadata` value
contains all roadmap-required identity, timing, unit, schema, hash, and quality
fields. Each event binds metadata to its own event family and unit invariants.

## Related code files

- Create: `apps/api/src/stocks/realtime/contracts.py`
- Create: `apps/api/src/stocks/realtime/__init__.py`
- Read: `apps/api/src/stocks/providers/contracts.py`

## Implementation steps

1. Define closed enums and strict shared value objects.
2. Define metadata and deterministic evidence identity.
3. Define eight event contracts and cross-field invariants.
4. Export only stable contract symbols from the package boundary.

## Success criteria

- [x] All eight models construct from valid canonical values.
- [x] Wrong family, unit, board, time, hash, identity, and price basis refuse at
  model construction.

## Risk assessment

Over-generalized inheritance can hide event-specific rules. Keep a small shared
base and put semantic checks on each concrete event.
