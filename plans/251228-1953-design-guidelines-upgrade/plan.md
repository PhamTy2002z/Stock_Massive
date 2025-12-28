---
title: "Design Guidelines Upgrade - Modern SaaS Dashboard"
description: "Add 6 new sections: A11y, Data Density, Keyboard Shortcuts, Real-time Updates, Customization, Onboarding"
status: pending
priority: P1
effort: 16h
branch: main
tags: [frontend, ux, accessibility, design-system]
created: 2025-12-28
---

# Design Guidelines Upgrade - Modern SaaS Dashboard

## Overview

Upgrade `docs/design-guidelines.md` with 6 new sections to achieve modern SaaS dashboard standards for financial analysis. Focus: Pro-first with Retail mode option.

**Context:**
- Brainstorming report: `plans/reports/brainstorm-251228-1941-design-guidelines-upgrade.md`
- Current guidelines: `docs/design-guidelines.md` (792 lines)
- Target users: Both Pro traders (default) and Retail investors

## Phases

| # | Phase | Status | Effort | Link |
|---|-------|--------|--------|------|
| 1 | Accessibility Standards | Pending | 3h | [phase-01](./phase-01-accessibility-standards.md) |
| 2 | Data Density Modes | Pending | 3h | [phase-02](./phase-02-data-density-modes.md) |
| 3 | Keyboard Shortcuts | Pending | 2h | [phase-03](./phase-03-keyboard-shortcuts.md) |
| 4 | Real-time Updates | Pending | 3h | [phase-04](./phase-04-realtime-updates.md) |
| 5 | Dashboard Customization | Pending | 3h | [phase-05](./phase-05-dashboard-customization.md) |
| 6 | Onboarding & Help | Pending | 2h | [phase-06](./phase-06-onboarding-help.md) |

## Dependencies

- No backend changes required for Phases 1-3, 6
- Phase 4 (Real-time): May need backend WebSocket support (optional, polling fallback exists)
- Phase 5 (Customization): Needs `react-grid-layout` library

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Default density mode | `compact` | Pro-first approach |
| Command palette lib | `cmdk` | ShadCN compatible, lightweight |
| Grid layout lib | `react-grid-layout` | Mature, widely used |
| Onboarding lib | `driver.js` | Lightweight, no React dependency |
| Persistence | localStorage | Simple, no backend needed initially |

## Success Metrics

| Metric | Target |
|--------|--------|
| A11y Score (Lighthouse) | ≥ 95 |
| Keyboard-only navigation | 100% features |
| Time to first insight | < 3s |

## Unresolved Questions

1. ~~WebSocket backend: Build now or use polling fallback?~~ → **Resolved: Polling + Visual cues**
2. ~~Saved views sync: localStorage only or backend later?~~ → **Resolved: localStorage only**
3. A11y audit: External audit needed? (deferred)

---

## Validation Summary

**Validated:** 2025-12-28
**Questions asked:** 7

### Confirmed Decisions

| Decision | User Choice |
|----------|-------------|
| Scope | Docs only (16h) - no component implementation |
| Default density | Compact (Pro-first) |
| Persistence | localStorage only |
| Real-time approach | Polling + Visual cues (no WebSocket) |
| A11y refactor | Document only, no component refactor |
| Phase order | As planned (1→6) |
| Libraries | As planned (cmdk, driver.js, react-grid-layout) |

### Action Items
- [x] All decisions confirmed, no plan changes needed
- [ ] Proceed with Phase 1 implementation

### Recommendation
**✓ Ready to implement** - All key decisions validated, no blockers identified.
