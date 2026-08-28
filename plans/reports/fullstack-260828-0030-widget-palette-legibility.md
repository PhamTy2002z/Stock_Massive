# Canvas widgets — colour system + legibility

## Executed scope
- Task: repoint the canvas palette off the brand/market ramp onto `--widget-*`; fix eight rendered legibility defects.
- Frontend only, `apps/web`. No API change, no dependency added, no commit.
- Branch `feat/study-canvas-runtime`. A parallel task owned `canvas-panel.tsx`, `provenance-strip.tsx`, `widget-registry.ts`, `components/shell/**`, `lib/alpha-desk/**` — untouched here.

## Files modified
| File | Δ |
|---|---|
| `widgets/chart-theme.ts` | +47/-12 — palette now lives here (`SERIES`, `SERIES_MUTED`, `FOCUS`, `TRACK`); grid/axis/tooltip repointed to `--widget-*` |
| `widgets/bar-series.tsx` | +147/-36 — `plotCeiling`, per-bar `Cell`, cap caption |
| `widgets/ranked-bars.tsx` | +111/-38 — value labels replace the bottom axis, focus leader, truncation note |
| `widgets/session-heatmap.tsx` | +54/-19 — series ramp, rotated per-column labels, right pad |
| `widgets/range-strip.tsx` (untracked) | SVG `viewBox` → laid-out HTML + fixed-size wedge |
| `widgets/stat-tiles.tsx` | +21/-7 — `auto-fit` grid, `formatQuantity`/`formatUnit` |
| `widgets/data-table.tsx` | +14/-3 — `w-max min-w-full`, focusable named scroll region |
| `widgets/line-series.tsx` | +10/-4 — series + muted dashed secondary |
| `widgets/scatter-quadrant.tsx` | +15/-4 — series fill, quieter dividers |
| `widgets/condition-checklist.tsx` (untracked) | routed through `formatMeasure` |
| `frame.ts` | +75/-9 — `magnitudeOf`, `formatQuantity`, `formatUnit`, `formatMeasure` |
| `canvas-block.tsx` | +44/-2 — "Xem dạng bảng" disclosure, lazily mounted |

`globals.css` **not** touched — every token needed (`--widget-series/-muted/-track/-grid/-axis/-focus/-neutral/-surface/-ink/-ink-muted`) already shipped for both themes.

New tests: `frame.test.ts` (12), `canvas-block.test.tsx` (5), `widgets/bar-series.test.tsx` (9), `widgets/stat-tiles.test.tsx` (6), `widgets/ranked-bars.test.tsx` (3) = **35 new**. Plus +3 heatmap, +2 range-strip assertions on existing files.

## Problem 1 — palette
`grep -rn "chart-1\|chart-3\|chart-5" apps/web/src/components/canvas/` → **empty**, including prose.

Amber (`--widget-focus`) now appears in exactly three places, each a single element:
- `bar-series` — the peak bucket, resolved by **index** (`values.indexOf(max)`) not by `>= max`, so an all-equal series paints zero amber bars rather than all of them; plus any bar the ceiling cut.
- `ranked-bars` — row 0 only, by the Study's own order (a tie at the top is still one leader).
- `range-strip` — the current-price rule and its wedge.

Market green/red were not introduced anywhere; `condition-checklist` keeps its existing `text-positive/negative/caution` status marks, which do carry direction.

## Problem 2 — the eight defects
1. **`bar_series` plot waste** — `plotCeiling(values)`: p90 × 1.15, `min`'d with the true max. The `min` is what makes a flat series untouched (its p90 *is* its max), so nothing is rescaled where nothing is hidden. Returns `null` for a series crossing zero (a cap would truncate one side of an across-axis comparison) and for an all-zero/empty series. Bars are clamped to the ceiling in JS rather than relying on recharts overflow. Caption states the ceiling and the count cut; the tooltip still reports the true value via the datum's `value` key.
2. **Heatmap labels** — every column labelled, rotated `-90` about its own cell centre (`HEADER` 16→36, `PAD_RIGHT` 6). No label runs past the drawing width.
3. **`ranked_bars`** — bottom value axis removed (`hide`), value printed at each bar's end via `LabelList` into a 56px right gutter, so there is now one convention on the panel instead of two. `MAX_ROWS` truncation says "Còn N mục ngoài top 8".
4. **`data_table`** — `w-max min-w-full` (columns size to content instead of being squeezed and clipped) inside a `role="region" tabIndex=0` named scroll box, so a keyboard can reach it.
5. **`stat_tiles`** — `grid-cols-[repeat(auto-fit,minmax(9rem,1fr))]`. Container-driven, which is correct here: the inspector is a draggable column, so viewport breakpoints measure the wrong box.
6. **Units** — magnitude is owned by the *value* layer. `formatNumber` (terse `ng`/`tr`/`tỷ`) still serves axis ticks; `formatQuantity` spells it (`nghìn`/`triệu`/`tỷ`) wherever a unit follows. `formatUnit` maps `shares`/`share` → `cp` and passes `%`, `VND`, `đ`, `mã`, `phiên` through. The fixture row now reads **"380,00 nghìn cp"**.
7. **`range_strip`** — `preserveAspectRatio="none"` gone with the whole `viewBox`. Track/band/marker are laid-out HTML at percentage positions; the 2px rule is `w-0.5` at every width; the wedge is a fixed 8×6 SVG. Token-only painting preserved (inline `background`/`fill`), so the existing both-themes test still bites.
8. **Reachable as data** — `canvas-block.tsx` renders a `<details>` "Xem dạng bảng" under every non-table block, mounting `DataTableWidget` on the same frame **only once opened** (a heatmap frame is ~540 cells; rendering that into a closed disclosure would land on the panel's first paint). Suppressed where the block already is the table or already degraded to one. The stale docblock claims in `session-heatmap` and `bar-series` were corrected to point at it.

`min_sample`-style null-vs-zero rules were left intact and are now asserted in `frame.test.ts` (`numberAt` → `null`, `textAt` → em dash, tiles/checklist em dash rather than `0`).

## Gates
| Gate | Result |
|---|---|
| `pnpm type-check` | pass |
| `pnpm lint` | pass |
| `pnpm test` | **551 passed / 45 files**, 0 failed (baseline 455) |
| `pnpm build` | pass |
| `widget-registry.test.ts` vs `contracts/canvas-widget-catalog.json` | pass, no regeneration |

Widget name/version contracts untouched; `widget-registry.ts` not edited.

Mid-run, 7 then 2 tests failed in `canvas-panel.test.tsx`, `desk-session.test.ts`, `canvas-building.test.tsx`, `canvas-export.test.ts` — all the parallel task's in-flight files (copy change "phân tích"→"bảng"; CSV newline escaping). They resolved on their side; final run is fully green. One `pnpm build` invocation printed "Build error occurred" after compiling successfully — the known `.next` race with the user's running dev server; two subsequent builds were clean.

## Concerns
- **The ceiling is a truncated axis, which is a real trade-off.** Chosen over a sqrt/log scale because a nonlinear scale silently misstates every bar's proportion with nothing on screen saying so, whereas a cap is visible: the cut bars are accented and the caption names the ceiling and the count. `plotCeiling` is pure and exported, so the rule is directly testable and easy to revisit. If you would rather never clip the peak, the change is one function.
- **Amber can reach 2–3 bars on a heavily multi-modal series** (peak + bars above the p90 ceiling). In the real fixture it is exactly 1. Marking a cut bar is a legibility necessity — an unmarked clipped bar is the chart lying — but it is not strictly "one element". Flag if you want cut bars drawn in the neutral series instead, with the caption carrying the whole signal.
- **Pre-existing `text-[9px]` in `session-heatmap`** (two SVG micro-labels) is off the DESIGN.md type ramp. Not introduced by me and not suppressed — changing the ramp or the heatmap's density was outside scope.
- `docs/` untouched: no user-facing workflow, command, contract or architecture changed — this is rendering behaviour inside an existing surface.

Status: DONE
Summary: Canvas widgets repointed off the brand/market ramp onto `--widget-*` with amber reserved for a single focus element, and all eight legibility defects fixed; `apps/web` finishes at **551 passing tests** (baseline 455) with type-check, lint and build green.
Concerns: The bar-series ceiling is a deliberately truncated axis (annotated, accented, pure-function `plotCeiling`) rather than a nonlinear scale — worth a second opinion if you would rather never clip the peak.
