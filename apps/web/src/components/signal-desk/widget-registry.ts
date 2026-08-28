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
import { ConditionChecklistWidget } from "./widgets/condition-checklist"
import { DataTableWidget } from "./widgets/data-table"
import { LineSeriesWidget } from "./widgets/line-series"
import { RangeStripWidget } from "./widgets/range-strip"
import { RankedBarsWidget } from "./widgets/ranked-bars"
import { ScatterQuadrantWidget } from "./widgets/scatter-quadrant"
import { SessionHeatmapWidget } from "./widgets/session-heatmap"
import { StatTilesWidget } from "./widgets/stat-tiles"

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
  "bar_series@1": ["series"],
  "session_heatmap@1": ["matrix"],
  "ranked_bars@1": ["table"],
  "line_series@1": ["series"],
  "range_strip@1": ["table"],
  "condition_checklist@1": ["table"],
  "scatter_quadrant@1": ["table"],
  "data_table@1": ["series", "matrix", "table"],
}

const REGISTRY: Record<string, Widget> = {
  "stat_tiles@1": StatTilesWidget,
  "bar_series@1": BarSeriesWidget,
  "session_heatmap@1": SessionHeatmapWidget,
  "ranked_bars@1": RankedBarsWidget,
  "line_series@1": LineSeriesWidget,
  "range_strip@1": RangeStripWidget,
  "condition_checklist@1": ConditionChecklistWidget,
  "scatter_quadrant@1": ScatterQuadrantWidget,
  "data_table@1": DataTableWidget,
}

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
