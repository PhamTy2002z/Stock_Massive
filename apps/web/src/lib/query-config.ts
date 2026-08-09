/**
 * Shared TanStack Query timing presets (ms).
 *
 * Derived from the values already used across src/hooks/* — presets only
 * exist for durations that recur; one-off intervals stay inline in their hook.
 */

export const STALE_TIME = {
  /** 15s - realtime market data (indices, stock detail) */
  REALTIME: 15 * 1000,
  /** 30s - near-realtime data (VN30 overview) */
  FAST: 30 * 1000,
  /** 1 min - frequently updated data (sector performance, foreign flow, funds) */
  FREQUENT: 60 * 1000,
  /** 5 min - slow-changing data (financial statements, health score, trends) */
  STATIC: 5 * 60 * 1000,
} as const

export const REFETCH_INTERVAL = {
  /** 15s - realtime polling */
  REALTIME: 15 * 1000,
  /** 30s - near-realtime polling */
  FAST: 30 * 1000,
  /** 2 min - frequent polling */
  FREQUENT: 2 * 60 * 1000,
} as const
