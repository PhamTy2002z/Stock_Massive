# Signal Desk workspace — implementation report

Date: 2026-08-28 · Branch: `feat/study-canvas-runtime` · Frontend only, no API change, no new dependency.

## Status of the gates

| Gate | Result |
|---|---|
| `pnpm type-check` | pass |
| `pnpm lint` | pass |
| `pnpm test` | **556 passed / 45 files** (baseline 455; +101, of which 33 are mine and the rest arrived with the parallel widgets task) |
| `pnpm build` | pass — compiled, typed and 9/9 static pages generated |

`pnpm build` at the default `distDir` fails on the standalone copy step because the user's own dev server owns `.next`. Verified with `E2E_NEXT_DIST_DIR=.next-verify pnpm build` (the escape hatch already in `next.config.js`), then removed the tree and restored `next-env.d.ts`, which that build rewrites.

## What was built

**1 · The pane inverted.** `inspectorWidth` is now "the room the chat column does not take": `viewport − sidebar − chatColumnWidth`. `chatColumnWidth` defaults to 420 and clamps to ≥380 with the canvas keeping ≥480 where the viewport allows. The drag handle resizes the *chat* column (`resize-chat`), `foldSidebarIfCramped` now folds when `viewport − 274 < 860`, and on a phone `inspectorWidth` returns 0 because the pane overlays rather than splits — which also fixes the composer, which had been positioned with `right: panelWidth` while `app-shell` zeroed the padding.

**2 · A tab per canvas.** `shell-state` holds `canvases: CanvasTab[]` plus the active id; `canvas-ready`, `open-canvas` and `canvas-title` all file into it. `Nguồn` is the last tab in the same strip with its own glyph and no close control. Canvas tabs close to their neighbour. A tab opened from a transcript card starts with a fallback name and learns its real one from the fetch the pane was doing anyway (`CanvasPanel onTitle` → `canvas-title`).

**3 · Build state, derived once.** `buildingLabel(live)` in `canvas-building.tsx` is the single derivation: a `run_study` / `get_series` / `render_canvas` call still `running` whose **round** has produced no canvas, and never on a settled Turn. Correlating by `round` is what makes it clear on `canvas.ready` without watching for the event, and the settled guard is what makes it clear on completed/failed/cancelled. `useDesk().building` feeds both the pane's skeleton and the composer pill — one fact, two readers.

**4 · Export is real.** `canvas-export.ts` writes the primary frame (first block's) as RFC 4180 CSV, headers through `labelOf`, cells raw so a spreadsheet can sort them, a UTF-8 BOM so Excel on Windows does not mangle the Vietnamese, filename from title + `as_of`. **"Lưu" is not rendered**; the reason is stated in `signal-desk-header.tsx` and in `copy.ts`.

**5 · Rename.** Every user-visible string moved (`SIGNAL_DESK_COPY` in `copy.ts`); "khối" → "mục"; the unreachable-artifact line became "Không mở được bảng này…". No wire name moved: `canvas.ready`, `CanvasPanel`, `canvasArtifactId`, `contracts/canvas-widget-catalog.json` are untouched. The dead "Nghiên cứu sâu" row is gone from `AttachMenu` (with the now-unused `Search` import).

**6 · Mobile.** `canvas-ready` never opens the pane below 768; nor does switching the mode on. Shrinking a window past the breakpoint closes a pane the *mode* opened but keeps one the reader opened deliberately. `close-inspector` now **sets** `inspectorPinned`, so a dismissal holds for the conversation.

## The coordinator's mid-task change — all seven points

- **Toggle** — `SignalDeskToggle` in `composer.tsx`, immediately right of `+`. `role="switch"`, `aria-checked`, focus ring, always-visible label (never collapsed to the glyph, or the switch loses its accessible name).
- **Immediate entry** — `{ type: "signal-desk", on }` opens/closes the pane in the same transition. `canvas.ready` now only appends-and-activates.
- **Chat unchanged** — nothing in submit/cancel/retry/scroll was touched.
- **Empty state** — `SIGNAL_DESK_COPY.empty`, one line, no illustration, no button.
- **Three states** — `off` / `on` (amber) / `running` (`aria-busy`, `animate-pulse motion-reduce:animate-none`). No locked state. **The symbol context chip gave up amber** → `border-border bg-surface-bubble text-ink-2`, ticker still mono. The on/off decision reads from `useDesk().signalDesk` and writes through `useDesk().setSignalDesk` — one edge for a future entitlement check.
- **Persistence** — `DeskSession.signalDeskThreads: string[]` (newest first, capped at 24, optional so an older stored record reads as "no desks"). `openThread` / `newThread` dispatch `{ type: "thread", signalDesk }` re-read for the arriving Thread; nothing carries forward.
- **Mobile** — as above.

`setSignalDesk` is the one function the flag passes through; pointing it at the request payload when the API carries a `mode` is a one-line change there.

## Files

Modified: `shell/{shell-state,desk-state,inspector,composer,shell.test}.tsx` · `canvas/{canvas-panel.tsx,canvas-panel.test.tsx}` · `alpha/message/canvas-card.tsx` · `lib/alpha-desk/{copy.ts,read-content.ts,desk-session.ts,desk-session.test.ts}`.
New: `canvas/{use-artifact.ts,canvas-export.ts,canvas-building.tsx,signal-desk-header.tsx}` + `canvas/{canvas-export,canvas-building,signal-desk-header}.test.*`.
Not touched: `canvas/widgets/**`, `canvas/frame.ts`, `canvas/canvas-block.tsx`, `canvas/chart-theme.ts`, anything under `apps/api/`.

## Deviations worth a reviewer's eye

1. **`globals.css` was not touched.** Every colour in the mock already had a token (`#1a1b1d`→`surface-raised`, `#8c8f93`→`ink-6`, the build dot's `#5fc9d6`→`floor`). The mock's `shimmer` keyframe is served by Tailwind's `animate-pulse` with an inline `animationDelay` for the stagger, which avoided adding a keyframe to a file whose brief said "tokens only".
2. **`desk-session.ts` was edited** though it was not in the ownership list — the coordinator's point 6 requires persisting through `writeDeskSession`. The new field is optional, so no existing caller changed.
3. **Internal layout identifiers were renamed** where their meaning genuinely inverted: `resize-inspector`→`resize-chat`, state `inspectorWidth`→`chatWidth`, `maxInspectorWidth`→`maxChatWidth`, `useInspectorDrag`→`useChatColumnDrag`. Dead `inspectorWide` / `toggle-inspector-wide` / `reset-inspector-width` were removed (no importers). None of these is a canvas wire name.
4. **One pane, one geometry.** Opening "Nguồn" from an answer now uses the same inverted layout (chat 420, sources wide) rather than the old 408px panel. That follows from Sources being a tab of this pane; if the client wants the citations column narrower, that is a content-column max-width in `inspector.tsx`, not a second geometry.
5. **The build skeleton outranks a finished canvas** in the content column, per the brief's wording and the mock. The earlier picture stays one tab click away, but it is briefly replaced while a new Study runs.
6. **`close-inspector` also switches the mode off.** A pill reading "on" over an ordinary chat layout would be a lie; the X is the way out of the workspace.

## Unresolved questions

- Reopening an old Thread rebuilds tabs only from what the reader clicks (stored messages are not walked for `canvases`). Should the strip repopulate from the transcript on thread open?
- Should `Nguồn` be selectable when no answer has been picked? It currently renders the existing "answer is no longer in this conversation" line.

Status: DONE
Summary: Signal Desk ships as a per-thread mode with an inverted 420px chat column, a tab strip over every canvas plus Nguồn, a single-source build state feeding both the pill and the skeleton, and a real client-side CSV export; web suite at **556 passing** with type-check, lint and build green.
Concerns/Blockers: `pnpm build` needs `E2E_NEXT_DIST_DIR` while the user's dev server holds `.next`; six deliberate deviations listed above, of which the "one pane, one geometry" effect on the Sources tab is the one most worth a client look.
