---
phase: 3
title: "Contract, mutation, and security tests"
status: pending
priority: P1
effort: "3h"
dependencies: [1, 2]
---

# Phase 3: Contract, mutation, and security tests

## Overview

Prove S0 fails closed before any persistence boundary exists.

## Requirements

- Functional: cover valid contracts, mutation matrix, normalization, outcomes,
  provenance, reconciliation, and retention.
- Non-functional: tests must exercise serialized models and unknown-field
  rejection, not only enum membership.

## Architecture

Focused test modules mirror the realtime package. A parameterized mutation
matrix changes one semantic dimension at a time and asserts validation fails
before a store is called.

## Related code files

- Create: `apps/api/tests/test_realtime_contracts.py`
- Create: `apps/api/tests/test_realtime_policy.py`

## Implementation steps

1. Build minimal valid fixtures for all eight events.
2. Mutate unit, board, timestamp, identity, basis, and duplicate fields.
3. Prove secret-like fields and raw payloads are rejected and never serialized.
4. Prove cross-source evidence cannot overwrite by logical observation key.

## Success criteria

- [x] Every S0 exit-gate failure dimension has a named executable test.
- [x] The focused realtime suite passes from the project virtual environment.

## Risk assessment

Tests that only assert implementation details can miss semantic regression.
Assert public serialized contract behavior and stable refusal categories.
