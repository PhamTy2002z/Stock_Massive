---
title: Phase 5 permission guardrails and web security
date: 2026-09-01
summary: "Closed the typed permission and web-security phase with adversarial, API, and web gates green."
---

# Phase 5 permission guardrails and web security

## What happened

Phase 5 started from `cae8732` on `feat/phase-05-permission-guardrails-web-security`. The capability registry gained ordered capability/resource rules, frozen schema validation, typed refusal outcomes, same-Turn untrusted-read taint, outbound credential blocking, recursive trace redaction, encoded-content scanning, and Redis per-domain fleet allowance.

Focused tests exposed two review regressions before closure: a final wildcard deny did not hide an earlier resource allow from schema projection, and an over-broad taint rule treated any untrusted result as an external read. Both were corrected and locked with tests.

## Decision

Keep the five-tool catalog and every shipped default permission unchanged. Permission, approval, deployment availability, tenant authorization, content escalation, and sandboxing stay separate mechanisms. The scanner remains advisory/fail-open; schema, authorization, secret egress, and side effects fail closed. Phase 10 remains the owner of full scale-out enforcement.

## Verification

The adversarial gate passed 25 tests with zero escalation, zero raw secret in trace, and zero benign blocks out of 20. The focused security suite passed 257 tests; the full API passed 1401 with 3 deselected. Web lint, type-check, 458 tests, and production build passed. Compileall and `git diff --check` were clean.

## Next steps

Phase 6 is the next sequential roadmap phase. Reuse the permission plane and do not reopen the retired local analysis, market-store, or multi-agent paths.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
