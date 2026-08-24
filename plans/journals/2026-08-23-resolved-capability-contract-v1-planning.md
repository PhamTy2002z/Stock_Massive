---
title: Resolved Capability Contract v1 planning
date: 2026-08-23
summary: Architecture and provider-data decisions for the post-eval harness capability contract.
---

# Resolved Capability Contract v1 planning

## Outcome

Created and validated the Stage 1 Resolved Capability Contract v1 plan after the Stage 0 eval/replay harness.

## Decisions

- Keep ToolEntry as static declaration and make definitions.py own an immutable per-lane resolved surface.
- Preserve separate Conversation and Analysis orchestrators while closing dispatch of lane-unselected globally registered tools.
- Keep provider Capability contracts separate from agent capability metadata.
- Treat Main/Cover as coverage only, never automatic fallback.
- Preserve executable data truth: FiinQuant market/valuation ownership; VNStock reference/fundamentals; three VNStock calls per fundamental symbol; no inferred valuation adapter, index fallback, outstanding shares, basis, or publication time.

## Verification

- AgentKit structural validation passed.
- Four phases and 83 checklist items parsed.
- Internal links, dependency declarations, placeholders, and diff whitespace checks passed.
- Implementation remains blocked on Stage 0 graduation and approved baseline.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
