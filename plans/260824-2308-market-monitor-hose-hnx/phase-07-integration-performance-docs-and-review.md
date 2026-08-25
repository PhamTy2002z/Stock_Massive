---
phase: 7
title: "Run integration, performance, docs, and review gates"
status: completed
priority: P1
effort: "0.5d"
dependencies: [4, 6]
---

# Phase 7: Run integration, performance, docs, and review gates

## Overview

Verify the complete vertical slice, update only durable owning docs, and review
the final diff against every accepted outcome.

## Requirements

- Cross-stack happy, partial, stale, disconnected, and recovered paths.
- URL, drill-down, inspector, responsive, and accessibility flows.
- Bounded query count, response size, and render behavior.
- No new secret, provider call, migration, or public-contract ambiguity.

## Related code files

- Modify if behavior changed: `docs/system-data-contracts.md`
- Modify if roadmap evidence changed: `docs/system-roadmap.md`
- Create/update: `apps/web/e2e/market-monitor.spec.ts`
- Review all paths from `git diff --name-only`

## Implementation steps

1. Run focused backend/frontend tests after integration.
2. Run full backend test/lint and web test/type/lint/build gates.
3. Run E2E for lenses, links, history, drill-down, inspector, mobile, and recovery.
4. Measure API query count/size and first-render behavior.
5. Update smallest owning docs from shipped source/tests.
6. Review correctness, semantics, security, a11y, performance, and contracts.
7. Fix in-scope findings in one batch and re-run affected gates.
8. Compare the result to every plan success criterion; stop on any miss.

## Success criteria

- [x] Final commands pass or only proven pre-existing failures remain.
- [x] No critical/high review finding remains.
- [x] Docs match code; roadmap moves only with executable evidence.
- [x] No background process started by this work remains.
- [x] Handoff names behavior, evidence, and external S1 limitation.

## Risk assessment

User verified S3 at 2,792 passed/1 skipped with one missing-doc baseline failure.
Reproduce that baseline when broad validation runs; never hide a new failure
under it.
