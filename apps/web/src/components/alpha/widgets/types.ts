/**
 * The shapes a Widget renders, and the shape the backend persisted.
 *
 * Two families, and keeping them apart is the point. A `WidgetSpec` is what the
 * message stores — a fixed-date retrieval descriptor and nothing else. A
 * `WidgetData` is what resolving that descriptor produced. The component never
 * sees a descriptor and never fetches one: it takes data as props, so it cannot
 * re-query today's numbers inside a historical answer (ADR-0012).
 */

/** The registry names a persisted spec may carry. */
export const WIDGET_NAMES = [
  "metric_comparison",
  "ranked_symbols",
  "metric_trend",
  "relative_position",
] as const

export type WidgetName = (typeof WIDGET_NAMES)[number]

/** The validated spec, exactly as `apps/api` wrote it onto the message. */
export interface WidgetSpec {
  name: WidgetName
  version: number
  title: string
  fields: string[]
  unit: string | null
  as_of: string
  descriptor: Record<string, unknown>
  descriptor_id: string
  tool_call_ids: string[]
  /**
   * Whether the user asked for a picture, decided by the backend from the
   * user's own words. Failure is asymmetric on this bit (ADR-0012): a Widget
   * the agent offered disappears when it fails, and one the user asked for
   * leaves a short unavailable state with Retry.
   */
  requested: boolean
}

/** A selection the backend refused, where it had somewhere better to send us. */
export interface WidgetRefusal {
  code: string
  deep_link: string | null
}

interface ResolvedBase {
  as_of: string
  available: boolean
  unavailable_reason: string | null
}

export interface CrossSymbolPoint {
  symbol: string
  value: number | null
  details?: Record<string, unknown>
  refusal?: string | null
}

export interface CrossSymbolData extends ResolvedBase {
  kind: "cross_symbol" | "position"
  field: string
  unit: string
  interpretation?: string
  points: CrossSymbolPoint[]
}

export interface RankingRow {
  symbol: string
  [column: string]: unknown
}

export interface RankingData extends ResolvedBase {
  kind: "ranking"
  rows: RankingRow[]
  sort_by: string
  order: "asc" | "desc"
  matched_count?: number
}

export interface SeriesPoint {
  date: string
  value: number | null
}

export interface SeriesData extends ResolvedBase {
  kind: "series"
  field: string
  unit: string
  series: SeriesPoint[]
}

export type WidgetData = CrossSymbolData | RankingData | SeriesData

/** What every Widget component takes, and the only thing it takes. */
export interface WidgetProps<TData extends WidgetData> {
  spec: WidgetSpec
  data: TData
  /** Set inside the expanded view, which is the only place it is set. */
  expanded?: boolean
  /** Opens the expanded view. Absent inside it, so it cannot nest. */
  onExpand?: () => void
}
