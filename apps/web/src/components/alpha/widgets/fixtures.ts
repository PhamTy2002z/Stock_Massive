/**
 * Fixtures for the Widget registry, shaped exactly as `apps/api` sends them.
 *
 * Every Widget test renders from one of these and touches no network, which is
 * the same property the components themselves have: they take data as props.
 * Keeping the fixtures beside the components rather than inside the test files
 * is deliberate — a shape that drifts from the API drifts in one place, and the
 * test that catches it is whichever one runs first.
 */

import type {
  CrossSymbolData,
  RankingData,
  SeriesData,
  WidgetSpec,
} from "./types"

export const AS_OF = "2026-08-14"

export function spec(overrides: Partial<WidgetSpec> = {}): WidgetSpec {
  return {
    name: "metric_comparison",
    version: 1,
    title: "So sánh động lượng",
    fields: ["momentum_rank.percentile_12_2"],
    unit: "percentile",
    as_of: AS_OF,
    descriptor: {
      kind: "cross_symbol",
      field: "momentum_rank.percentile_12_2",
      symbols: ["FPT", "VCB"],
      as_of: AS_OF,
    },
    descriptor_id: "d3adb33fd3adb33fd3adb33f",
    tool_call_ids: ["c1", "c2"],
    requested: false,
    ...overrides,
  }
}

export function crossSymbol(
  overrides: Partial<CrossSymbolData> = {}
): CrossSymbolData {
  return {
    kind: "cross_symbol",
    as_of: AS_OF,
    field: "momentum_rank.percentile_12_2",
    unit: "percentile",
    interpretation: "Xếp hạng động lượng 12-2 trong Universe.",
    points: [
      { symbol: "FPT", value: 82, details: {}, refusal: null },
      { symbol: "VCB", value: 41.5, details: {}, refusal: null },
      { symbol: "HPG", value: 12.3, details: {}, refusal: null },
    ],
    available: true,
    unavailable_reason: null,
    ...overrides,
  }
}

export function signedCrossSymbol(): CrossSymbolData {
  return crossSymbol({
    field: "drawdown_stats.current_drawdown_pct",
    unit: "percent",
    points: [
      { symbol: "FPT", value: 4.2, details: {}, refusal: null },
      { symbol: "VCB", value: -12.5, details: {}, refusal: null },
    ],
  })
}

export function ranking(overrides: Partial<RankingData> = {}): RankingData {
  return {
    kind: "ranking",
    as_of: AS_OF,
    sort_by: "adtv_vnd",
    order: "desc",
    matched_count: 30,
    rows: [
      { symbol: "FPT", adtv_vnd: 812_000_000_000 },
      { symbol: "VCB", adtv_vnd: 455_000_000_000 },
      { symbol: "HPG", adtv_vnd: 220_000_000_000 },
    ],
    available: true,
    unavailable_reason: null,
    ...overrides,
  }
}

export function series(overrides: Partial<SeriesData> = {}): SeriesData {
  return {
    kind: "series",
    as_of: AS_OF,
    field: "realized_volatility.yang_zhang_annualized_pct",
    unit: "percent_annualized",
    series: [
      { date: "2026-08-10", value: 28.4 },
      { date: "2026-08-11", value: 30.1 },
      { date: "2026-08-12", value: 27.9 },
      { date: "2026-08-13", value: 33.6 },
      { date: AS_OF, value: 35.2 },
    ],
    available: true,
    unavailable_reason: null,
    ...overrides,
  }
}

export function position(): CrossSymbolData {
  return crossSymbol({
    kind: "position",
    points: [{ symbol: "FPT", value: 82, details: {}, refusal: null }],
  })
}

export function unavailable(): CrossSymbolData {
  return crossSymbol({
    points: [
      { symbol: "FPT", value: null, details: {}, refusal: "window_too_short" },
      { symbol: "VCB", value: null, details: {}, refusal: "window_too_short" },
    ],
    available: false,
    unavailable_reason: "slice_unavailable",
  })
}
