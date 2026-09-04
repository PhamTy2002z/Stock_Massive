---
phase: 6
title: "Signal Desk Right Panel"
status: todo
priority: P1
effort: "20h"
dependencies: [5]
---

# Phase 6: Signal Desk Right Panel

## Context Links

- `apps/web/src/components/shell/inspector.tsx::Body`
- `apps/web/src/components/shell/desk-state.tsx::DeskProvider`
- `apps/web/src/components/signal-desk/signal-desk-empty.tsx`
- `apps/web/src/lib/alpha-desk/{api,types,read-content,live-turn,transcript}.ts`
- `apps/api/src/agent/schemas.py::CreateTurnRequest`
- Phase 5 `VisualPart` and Flint compile wrapper

## Overview

Wire the existing Signal Desk mode to the backend and replace only the existing
right-pane empty body with the latest visual for the active Signal Desk Turn.
The conversation column stays text-only. The chart is the primary pane content;
metadata and failures are compact, not a second explanatory answer.

## Requirements

- Functional: Turn creation sends strict `mode: chat | signal_desk` from the
  existing composer toggle; server default remains `chat` for older clients.
- Functional: Chat mode renders existing transcript exactly and never mounts
  Flint. Signal Desk mode shows running, ready, unavailable and error states in
  the pane right of the chat column.
- Functional: a new Signal Desk Turn clears the previous chart from “current”
  status and shows live progress; no stale chart is presented as its result.
- Functional: terminal/refetch and page refresh select the latest visual part
  belonging to the active Thread; switching Threads cannot leak another chart.
- Functional: sources remain reachable through the existing pane/header path;
  the chart itself does not duplicate long evidence prose.
- Visual integrity: use Phase 5 official Flint component/output unchanged; CSS
  controls only outer width, height, padding, loading/error framing.
- Accessibility: pane and figure have stable labels, loading/error announcements
  are readable, keyboard resize/close behavior stays intact, reduced motion is
  respected.
- Responsive: desktop uses right pane; compact viewport uses the existing
  full-width inspector behavior without a second layout implementation.

## UI State Table

| Turn state | Right pane | Chat column |
|---|---|---|
| No Signal Desk question yet | Existing `SignalDeskEmpty` | Existing transcript |
| Active Signal Desk Turn | Compact progress/loading state; no old chart as current | Normal text/thought/tool progress |
| Complete + ready visual | Flint chart, title/as-of/source count | Text answer only |
| Complete + insufficient evidence | Short unavailable state with stable reason | Text refusal/gaps |
| Compile/runtime error | Isolated chart error + retry render control | Text remains usable |
| Chat mode | Desk closed or no desk view | Existing behavior, no Flint mount |

## File Inventory

| Action | File | Purpose |
|---|---|---|
| Modify | `apps/web/src/lib/alpha-desk/api.ts` | Send mode on Turn creation. |
| Modify | `apps/web/src/components/shell/desk-state.tsx` | Bind current toggle to request and select active visual. |
| Modify | `apps/web/src/lib/alpha-desk/live-turn.ts` | Carry current visual/progress through terminal refetch without stale fallback. |
| Modify | `apps/web/src/lib/alpha-desk/read-content.ts` | Read persisted visual while preserving text parsing. |
| Modify | `apps/web/src/lib/alpha-desk/transcript.ts` | Explicitly exclude visual from chat entries. |
| Create | `apps/web/src/components/signal-desk/signal-desk-panel.tsx` | State switch and outer figure shell. |
| Create | `apps/web/src/components/signal-desk/flint-chart-view.tsx` | Client-only official compile/render boundary. |
| Modify | `apps/web/src/components/shell/inspector.tsx` | Attach panel at existing `Body` seam. |
| Modify | `apps/web/src/components/signal-desk/signal-desk-empty.tsx` | Only if copy must distinguish never-run from unavailable; no redesign. |
| Create | `apps/web/src/components/signal-desk/signal-desk-panel.test.tsx` | Mode/state/thread/replay/accessibility tests. |
| Modify | `apps/web/src/components/shell/shell.test.tsx` | Geometry, toggle, sources and compact behavior. |
| Modify | `apps/web/src/lib/alpha-desk/api.test.ts` | Request mode compatibility. |

## Function And Interface Checklist

- [ ] `createTurn(..., mode)` always sends one enum value; no UI-only truth is
      inferred on the server.
- [ ] `DeskProvider.submit` snapshots mode with the submitted question so a
      toggle changed during request cannot relabel the running Turn.
- [ ] `selectSignalDeskVisual(thread, liveTurn)` is pure, thread-scoped and
      prefers the active Turn state over prior completed artifacts.
- [ ] `SignalDeskPanel` owns only state selection; `FlintChartView` owns only
      official validate/compile/render.
- [ ] Flint/ECharts imports are client-only and lazy enough that Chat mode does
      not load or execute the chart runtime.
- [ ] Compilation error boundary cannot unmount Chat, inspector controls or
      source access.
- [ ] No component turns `visual` into markdown/text or inserts a chart card in
      transcript.
- [ ] Figure label uses host metadata; tool/provider raw strings are not used as
      HTML and no `dangerouslySetInnerHTML` is introduced.
- [ ] Existing keyboard separator semantics and responsive sizing remain.

## Implementation Steps

1. Add API client contract tests first: chat default/explicit mode, Signal Desk
   mode, invalid mode and retry preserving original mode.
2. Snapshot `signalDesk` at submit/queue/resend and carry it through all create
   paths; do not read the toggle later when the request finally dispatches.
3. Add a pure selector for active/live/persisted visual state and test Thread
   switching plus new-Turn stale clearing.
4. Build `FlintChartView` around Phase 5 wrapper with an isolated error boundary;
   apply no chart option/theme transformation.
5. Build the small panel state switch and attach it at `Inspector.Body`, keeping
   existing pane geometry and source toggle behavior.
6. Add compact/reduced-motion/keyboard/ARIA tests and a production build to
   catch browser-only ECharts import mistakes.
7. Run a real internal Signal Desk Turn, refresh mid-run and after completion,
   then switch Threads; record screenshots and result hashes in the phase report.

## Test Matrix

| Scenario | Expected |
|---|---|
| Toggle off + submit | `mode=chat`; no visual runtime/mount. |
| Toggle on + submit | `mode=signal_desk`; pane shows current progress. |
| Toggle changes while queued | Request uses submit-time snapshot. |
| New visual Turn after old chart | Old chart not labelled current; loading then new artifact. |
| Refresh during run | Reattaches to Turn/progress; no duplicate Turn/tool call. |
| Refresh after completion | Same visual hash compiles without backend work. |
| Switch Thread | Only selected Thread visual appears. |
| Invalid persisted visual | Pane error only; chat answer remains. |
| Flint compile throws | Error boundary remains inside pane. |
| Compact/keyboard/reduced motion | Existing inspector behavior and labels pass. |

## Verification Commands

```bash
pnpm --dir apps/web test -- src/lib/alpha-desk/api.test.ts src/lib/alpha-desk/live-turn.test.ts src/lib/alpha-desk/transcript.test.ts src/components/signal-desk/signal-desk-panel.test.tsx src/components/shell/shell.test.tsx
pnpm --dir apps/web lint
pnpm --dir apps/web type-check
pnpm --dir apps/web build
git diff --check
```

## Success Criteria

- [ ] A real Signal Desk prompt produces text in Chat and only the Flint visual
      in the right pane.
- [ ] Chat mode does not request, parse into transcript or mount a visual.
- [ ] Refresh/reconnect/Thread switching preserve ownership and deterministic
      visual selection without duplicate backend work.
- [ ] Flint output is unmodified and compile failures are isolated.
- [ ] Existing source drawer, pane resize, compact layout and accessibility tests
      remain green.

## Risks And Rollback

**Mode race:** queued send reads current toggle instead of submit-time value.
Prevent with immutable queued request object and regression test.

**Heavy chart bundle in Chat:** dynamic import is accidentally eager. Check build
chunks and a Chat-mode mount spy. Roll back `Body` to `SignalDeskEmpty` and stop
sending `signal_desk`; backend text/evidence path remains valid.
