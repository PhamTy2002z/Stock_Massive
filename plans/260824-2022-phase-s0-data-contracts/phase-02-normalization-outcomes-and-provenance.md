---
phase: 2
title: "Normalization, outcomes, and provenance"
status: pending
priority: P1
effort: "2h"
dependencies: [1]
---

# Phase 2: Normalization, outcomes, and provenance

## Overview

Encode the policy decisions that turn provider values into canonical evidence
without mixing source ownership.

## Requirements

- Functional: versioned normalization rules, typed outcomes, reconciliation
  records, provenance-preserving merge behavior, and retention classes.
- Non-functional: closed registries, deterministic output, and no adapter or
  storage dependency.

## Architecture

Normalization converts only through a versioned board/product rule. Outcomes
separate request errors, absence, quality degradation, duplicates, gaps, and
provider failures. Reconciliation compares evidence references without
selecting a hidden winner. Retention policy is a versioned registry.

## Related code files

- Create: `apps/api/src/stocks/realtime/normalization.py`
- Create: `apps/api/src/stocks/realtime/policy.py`
- Modify: `apps/api/src/stocks/realtime/__init__.py`

## Implementation steps

1. Encode audited DNSE price, quantity, and value conversions.
2. Refuse unknown rule versions and board/product combinations.
3. Define the nine explicit outcome kinds and retry semantics.
4. Define reconciliation and evidence merge contracts.
5. Define versioned retention classes and durations.

## Success criteria

- [x] No global multiplier exists across round-lot, odd-lot, and derivatives.
- [x] Cross-provider evidence remains separately addressable.
- [x] Every roadmap outcome and retention class has an executable declaration.

## Risk assessment

Unaudited quote quantity rules may be guessed. The registry refuses them until
a market-hours conformance result adds a new version.
