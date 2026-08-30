/**
 * Which component draws which widget, and what happens when none does.
 *
 * A desk view is persisted with the widget *name and version* it was drawn with,
 * so an artifact written last month keeps asking for the version it was written
 * against. That is the whole reason versions are on the wire, and it only works
 * if a viewer meeting a version it does not know degrades rather than breaks:
 * `data_table` renders the numbers without the picture, which a reader can see
 * through, where a blank panel or a thrown error is a conversation that stops.
 *
 * The same fallback catches a frame whose *kind* the widget cannot draw — a
 * heatmap asked to render a series. The server checks that on every run
 * (`studies/runner.py`), so reaching it here means the two builds disagree, and
 * a table is the honest thing to show while they do.
 *
 * The catalog is generated from the server's own widget module
 * (`contracts/signal-desk-widget-catalog.json`) and `widget-registry.test.ts` holds
 * this map equal to it, so a name that exists on one side and not the other is
 * a red test rather than a blank block in front of a reader.
 */

import type { ComponentType } from "react"

import type { Frame, Provenance } from "@/lib/alpha-desk/types"

import { BarSeriesWidget } from "./widgets/bar-series"
import { BulletWidget } from "./widgets/bullet"
import { ComparisonTableWidget } from "./widgets/comparison-table"
import { ConditionChecklistWidget } from "./widgets/condition-checklist"
import { DataTableWidget } from "./widgets/data-table"
import { DonutWidget } from "./widgets/donut"
import { GroupedBarWidget } from "./widgets/grouped-bar"
import { LineSeriesWidget } from "./widgets/line-series"
import { RangeStripWidget } from "./widgets/range-strip"
import { RankedBarsWidget } from "./widgets/ranked-bars"
import { ScatterQuadrantWidget } from "./widgets/scatter-quadrant"
import { SessionHeatmapWidget } from "./widgets/session-heatmap"
import { StatTilesWidget } from "./widgets/stat-tiles"
import { TextCardWidget } from "./widgets/text-card"
import { WaterfallWidget } from "./widgets/waterfall"

/** What every widget is handed, and the whole of it. */
export interface WidgetProps {
  frame: Frame
  /**
   * Which column means what, decided by the server.
   *
   * The choices that change what a chart *claims* — which column is the bar,
   * whether a scale starts at zero — belong with the layer that knows what the
   * numbers mean, so they arrive rather than being guessed here.
   */
  options: Record<string, unknown>
  /** Where the numbers came from and when they were frozen. */
  provenance: Provenance
}

export type Widget = ComponentType<WidgetProps>

/** The widget every viewer implements, and the one it falls back to. */
export const FALLBACK: { widget: string; version: number } = {
  widget: "data_table",
  version: 1,
}

/** Which frame kinds each widget can draw, mirroring the server's catalog. */
const ACCEPTS: Record<string, Frame["kind"][]> = {
  "stat_tiles@1": ["table"],
  "stat_tiles@2": ["table"],
  "bar_series@1": ["series"],
  "bar_series@2": ["series"],
  "session_heatmap@1": ["matrix"],
  "ranked_bars@1": ["table"],
  "ranked_bars@2": ["table"],
  "line_series@1": ["series"],
  "line_series@2": ["series"],
  "range_strip@1": ["table"],
  "condition_checklist@1": ["table"],
  "scatter_quadrant@1": ["table"],
  "scatter_quadrant@2": ["table"],
  "grouped_bar@1": ["series", "table"],
  "comparison_table@1": ["table"],
  "donut@1": ["table"],
  "waterfall@1": ["table", "series"],
  "bullet@1": ["table"],
  "text_card@1": ["table"],
  "data_table@1": ["series", "matrix", "table"],
}

/**
 * Five widgets appear twice, and both entries are the same component.
 *
 * Version 2 of each reads what a frame declares about its own series and points;
 * version 1 is kept because artifacts written before that exist and have to keep
 * rendering, and dropping the entry would send every one of them to the table.
 * One component serves both honestly: an older frame declares nothing, and a
 * component handed nothing draws exactly what it drew before.
 */
const REGISTRY: Record<string, Widget> = {
  "stat_tiles@1": StatTilesWidget,
  "stat_tiles@2": StatTilesWidget,
  "bar_series@1": BarSeriesWidget,
  "bar_series@2": BarSeriesWidget,
  "session_heatmap@1": SessionHeatmapWidget,
  "ranked_bars@1": RankedBarsWidget,
  "ranked_bars@2": RankedBarsWidget,
  "line_series@1": LineSeriesWidget,
  "line_series@2": LineSeriesWidget,
  "range_strip@1": RangeStripWidget,
  "condition_checklist@1": ConditionChecklistWidget,
  "scatter_quadrant@1": ScatterQuadrantWidget,
  "scatter_quadrant@2": ScatterQuadrantWidget,
  "grouped_bar@1": GroupedBarWidget,
  "comparison_table@1": ComparisonTableWidget,
  "donut@1": DonutWidget,
  "waterfall@1": WaterfallWidget,
  "bullet@1": BulletWidget,
  "text_card@1": TextCardWidget,
  "data_table@1": DataTableWidget,
}

/**
 * Widgets the catalog lists that no component here draws, and why not.
 *
 * `kpi_strip` and `caption` are *block kinds of a board*, not drawings of a
 * frame: the strip is laid out by `kpi-strip.tsx` from figures the server
 * already resolved, and a caption is a sentence assembled from cells of several
 * frames. Neither takes a `frame` and neither could satisfy `WidgetProps`.
 *
 * They are in the server's catalog because the catalog is what a board's blocks
 * are checked against, and the contract test reads this list rather than
 * failing: a name missing from the registry by accident is still a red test.
 */
export const NOT_FRAME_WIDGETS: string[] = ["caption@1", "kpi_strip@1"]

export function widgetKey(name: string, version: number): string {
  return `${name}@${version}`
}

/** Every `name@version` this build can draw. What the contract test compares. */
export function knownWidgets(): string[] {
  return Object.keys(REGISTRY).sort()
}

/** Which frame kinds one widget accepts, or none when it is not known here. */
export function acceptedKinds(name: string, version: number): Frame["kind"][] {
  return ACCEPTS[widgetKey(name, version)] ?? []
}

export interface Resolved {
  component: Widget
  /** True when the component drawing this block is not the one it asked for. */
  degraded: boolean
}

/**
 * The component to draw one block with, and whether it is the one asked for.
 *
 * Never null. A caller has a block to render whatever arrived, and the one
 * thing it must never do is render nothing without saying so — which is why
 * `degraded` comes back beside the component rather than being inferred by
 * comparing names at the call site.
 */
export function resolveWidget(
  name: string,
  version: number,
  kind: Frame["kind"] | undefined,
): Resolved {
  const component = REGISTRY[widgetKey(name, version)]
  const draws = kind !== undefined && acceptedKinds(name, version).includes(kind)
  if (component !== undefined && draws) return { component, degraded: false }
  return { component: DataTableWidget, degraded: true }
}
