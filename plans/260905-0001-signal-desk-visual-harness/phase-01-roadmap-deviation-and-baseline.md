---
phase: 1
title: "Roadmap Deviation And Baseline"
status: todo
priority: P1
effort: "6h"
dependencies: []
---

# Phase 1: Roadmap Deviation And Baseline

## Context Links

- `CLAUDE.md` — current capability and retired-path boundary
- `docs/roadmap.md` §2, §4, §6, §9, Phase 6, Phase 12
- `plans/reports/research-260904-2254-vnstock-personal-to-saas-production.md`
- [Flint](https://github.com/microsoft/flint-chart)
- [Vnstock](https://github.com/thinh-vu/vnstock)

## Overview

Roadmap hiện cấm market-data SDK, chart runtime, MCP và mọi output Signal Desk.
Không implementation nào được bắt đầu khi mâu thuẫn này còn tồn tại. Phase này
biến chỉ đạo mới thành một deviation có phạm vi hẹp, được product owner chấp
nhận, rồi đóng baseline code/test để các phase sau không vô tình khôi phục
Study/Board/widget/local-store cũ.

## Requirements

- Functional: deviation ghi rõ quyết định cũ, evidence mới, trade-off, option
  chọn và rollback; không sửa authority trước khi owner chấp nhận.
- Functional: roadmap mở đúng ba capability: request mode `signal_desk`, một
  `get_market_data` read capability, và official Flint visual renderer.
- Functional: Phase 6 evidence engine vẫn là nền; paid quality gate còn lại
  được chuyển vào Phase 7 của plan này, không chạy hai corpus cạnh tranh.
- Functional: các plan Signal Desk/phase cũ đã bị xoá khỏi `plans/`; không
  reuse code path, schema hay terminology của chúng.
- Non-functional: Chat text-only; no-advice; personal internal Vnstock only;
  production disabled pending written rights.
- Non-functional: giữ nguyên truth contract, one-call-one-result, typed Turn
  settlement, permission/budget plane và sequential roadmap order.

## Decision Surface

| Existing decision | New evidence/direction | Narrow amendment |
|---|---|---|
| Signal Desk output retired | UI mode/pane đã được owner restore; Flint có typed assembly/compiler boundary. | Mở visual part ở pane phải, không mở Board/Study/widget. |
| Market SDK prohibited | Live Vnstock probe chứng minh bounded OHLCV/quote/trades dùng được cho internal research. | Mở một provider-neutral read tool, internal profile only. |
| MCP waits for Phase 12 | Official Flint MCP cho phép validate demo mà không build compiler riêng. | Cho phép local spike Phase 2; product không có generic MCP gateway. |
| Phase 6 web-only evidence | Structured market values cần unit/time/provenance mà web search không bảo đảm. | Thêm `STORE_FIGURE` evidence, giữ web làm narrative/primary source. |

## File Inventory

| Action | File | Purpose |
|---|---|---|
| Create | `plans/reports/deviation-260905-signal-desk-flint-vnstock.md` | Durable owner decision and evidence. |
| Modify after approval | `CLAUDE.md` | Replace only the conflicting capability/retired-path statements. |
| Modify after approval | `docs/roadmap.md` | Insert new sequential track and runnable gates. |
| Verify | `apps/api/src/agent/{loop,lanes,guardrails,registry,toolsets,executor}.py` | Freeze baseline owners. |
| Verify | `apps/web/src/components/shell/{inspector,desk-state}.tsx` | Confirm existing mode/pane seam. |

## Interface Checklist

- [ ] `CreateTurnRequest` remains unchanged in this phase.
- [ ] Runtime tool catalog remains unchanged in this phase.
- [ ] No package or migration is added in this phase.
- [ ] New roadmap text names exact future owner files and runnable gates.
- [ ] Roadmap explicitly says `mode=chat` is backward-compatible default.
- [ ] Roadmap explicitly keeps Study DSL, Board DSL, widgets, stock store,
      scheduler, watchlist, broker/order and generic MCP out of scope.

## Implementation Steps

1. Record current branch SHA, dirty files and focused baseline command results;
   do not alter user-owned `AGENTS.md` or the existing Vnstock research report.
2. Write deviation report from the locked decision table above, including why
   Flint wins over lieflat for core and why a second agent loop is rejected.
3. Stop at the owner decision gate. If rejected, close this plan without code.
4. After acceptance, amend `CLAUDE.md` and `docs/roadmap.md` together so their
   capability catalogs and phase order agree.
5. Mark old Signal Desk compiler plan `superseded` (retain history), and link
   this plan plus Phase 6 evidence plan from the roadmap.
6. Run baseline focused tests and retired-path scans; record results in the
   deviation report so later failures have a fixed comparison point.

## Test Matrix

| Scenario | Check | Expected |
|---|---|---|
| Authority before approval | Git diff | Only deviation/plan records change. |
| Authority after approval | Cross-file search | `CLAUDE.md` and roadmap describe the same three openings. |
| Existing UI seam | Web shell tests | Signal Desk toggle and empty right pane remain green. |
| Existing loop | API guardrail/lane/loop tests | Current bounded behavior green before extension. |
| Retired paths | `rg` allowlist scan | No runtime Study/Board/widget/store/watchlist path is reopened. |

## Verification Commands

```bash
git status --short --branch
cd apps/api && pytest -q tests/test_agent_guardrails.py tests/test_agent_lanes.py tests/test_agent_loop.py
pnpm --dir apps/web test -- src/components/shell/shell.test.tsx
rg -n 'Study|Board DSL|widget|stock store|watchlist|generic MCP' CLAUDE.md docs/roadmap.md
git diff --check
```

## Success Criteria

- [ ] Product owner acceptance is stored in the deviation report.
- [ ] Authority files agree on scope, order, stop conditions and rollback.
- [ ] All later phases are blocked until this phase is complete.
- [ ] Baseline commands are reproducible and green, or existing failures are
      named with evidence rather than silently accepted.
- [ ] No production code, dependency, schema or API contract changed.

## Risks And Rollback

**Scope creep:** wording accidentally reopens the old analysis system. Signal is
any capability beyond the three-row amendment. Response: remove it before
approval. Rollback is documentation-only: revert the accepted amendment and
leave Signal Desk as the existing empty client pane.

**Conflicting authority:** one file amended without the other. Response: phase
cannot complete until a cross-file search proves agreement.
