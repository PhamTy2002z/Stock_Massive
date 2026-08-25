---
title: Resolved capability contract phases 1 and 2
date: 2026-08-24
summary: Completed the immutable resolved tool surface and its contract baseline with review and offline verification.
---

# Resolved capability contract phases 1 and 2

Implemented and verified Phase 1 and Phase 2 of Resolved Capability Contract v1.

The registry now owns explicit conservative capability facts, while definitions resolves one immutable ordered surface with deterministic identity, typed sanitized availability, and synchronized bounded caching.

Key defects caught during review were nested schema mutability, catalogue mutation during availability probing, mutable-sequence descriptor bypass, and an unsynchronized LRU race. Each received a regression test and cause-aligned fix.

Verification completed with a 41-test final focused rerun, earlier 99/240/821 passing matrices, and 2786 default-offline passes with one pre-existing deleted-document topology failure. Static provider verification imported no provider package and made zero network calls.

Phase 1 and Phase 2 are marked completed. The parent plan remains in progress at Phase 3. Evergreen docs were not changed because public API, SSE, setup, database, and provider execution contracts are unchanged.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
