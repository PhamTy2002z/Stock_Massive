/**
 * `(name, version)` to component, and nothing else.
 *
 * Keyed on the pair rather than on the name, because ADR-0012 pins the version
 * server-side precisely so that an old message keeps rendering the way it was
 * written. Version 2 of `metric_comparison` will be a second entry here, not an
 * edit to the first — a message from March is a historical record, and silently
 * redrawing it under a newer component is the same class of mistake as silently
 * re-resolving its data to today.
 *
 * A miss returns `undefined`, and the slot degrades on it. There is no fallback
 * component: guessing at what an unknown Widget meant is exactly the failure a
 * named registry exists to avoid.
 */

import type { ComponentType } from "react"
import { MetricComparison, METRIC_COMPARISON_VERSION } from "./metric-comparison"
import { MetricTrend, METRIC_TREND_VERSION } from "./metric-trend"
import { RankedSymbols, RANKED_SYMBOLS_VERSION } from "./ranked-symbols"
import { RelativePosition, RELATIVE_POSITION_VERSION } from "./relative-position"
import type { WidgetData, WidgetSpec } from "./types"

/**
 * The one signature the registry can be looked up through.
 *
 * `data` is the union because the lookup key is a string and TypeScript cannot
 * follow a runtime name to a data shape. What makes the pairing safe is the
 * `kind` recorded beside each entry: the slot refuses to render a component
 * whose entry does not match the resolved data's kind, so the widening below is
 * checked at the one place it is narrowed again.
 */
export type RegisteredWidget = ComponentType<{
  spec: WidgetSpec
  data: WidgetData
  expanded?: boolean
  onExpand?: () => void
}>

export interface WidgetEntry {
  component: RegisteredWidget
  /** The descriptor kind this component can actually draw. */
  kind: WidgetData["kind"]
}

function key(name: string, version: number): string {
  return `${name}@${version}`
}

/** Widen one concrete component to the registry's signature. See above. */
function entry(
  component: unknown,
  kind: WidgetData["kind"]
): WidgetEntry {
  return { component: component as RegisteredWidget, kind }
}

const REGISTRY: Record<string, WidgetEntry> = {
  [key("metric_comparison", METRIC_COMPARISON_VERSION)]: entry(
    MetricComparison,
    "cross_symbol"
  ),
  [key("ranked_symbols", RANKED_SYMBOLS_VERSION)]: entry(RankedSymbols, "ranking"),
  [key("metric_trend", METRIC_TREND_VERSION)]: entry(MetricTrend, "series"),
  [key("relative_position", RELATIVE_POSITION_VERSION)]: entry(
    RelativePosition,
    "position"
  ),
}

export function lookupWidget(spec: WidgetSpec): WidgetEntry | undefined {
  return REGISTRY[key(spec.name, spec.version)]
}

/** Every pair this build ships, for the tests that assert the registry's shape. */
export function supportedWidgets(): string[] {
  return Object.keys(REGISTRY).sort()
}
