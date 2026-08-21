/**
 * The Alpha Desk Widget registry.
 *
 * The transcript needs exactly one of these — `MessageWidgets` — and everything
 * else is exported for the tests and for the registry's own internals. A
 * component reached directly rather than through the registry would be a
 * component reached without its `(name, version)` check, which is the whole
 * mechanism ADR-0012 is built on.
 */

export { MessageWidgets } from "./message-widgets"
export type { MessageWidgetsProps } from "./message-widgets"
export { WidgetSlot, PLACEHOLDER_CLASS } from "./widget-slot"
export type { WidgetSlotProps, SlotState } from "./widget-slot"
export { WidgetExpand } from "./widget-expand"
export { lookupWidget, supportedWidgets } from "./registry"
export { parseWidgetSpec, parseWidgetSpecs, parseWidgetRefusals } from "./spec"
export { widgetResolverFor, WidgetDataUnavailable } from "./resolve"
export { WIDGET_PALETTE } from "./palette"
export { MetricComparison } from "./metric-comparison"
export { RankedSymbols } from "./ranked-symbols"
export { MetricTrend } from "./metric-trend"
export { RelativePosition } from "./relative-position"
export { QuarterlyFinancials } from "./quarterly-financials"
export { WIDGET_NAMES } from "./types"
export type {
  CrossSymbolData,
  PeriodFigures,
  PeriodsData,
  RankingData,
  SeriesData,
  WidgetData,
  WidgetName,
  WidgetRefusal,
  WidgetSpec,
} from "./types"
