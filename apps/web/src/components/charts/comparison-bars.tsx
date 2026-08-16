"use client"

import { cn } from "@/lib/utils"

/**
 * One horizontal bar per row, on a track the rows share.
 *
 * Extracted from the valuation-versus-sector card, which is where the shape was
 * measured (ADR-0012). The split is the mechanical one every card in this
 * codebase needs: the card flattens a response into rows, and the leaf draws
 * rows. A widget built on the card instead would inherit its fetch, and a
 * widget that fetches re-queries today's numbers inside a historical answer.
 *
 * The leaf owns no colour. Both callers pass their own — the dashboard card
 * keeps the ink-on-hairline it has always drawn, and the Widget registry passes
 * its own palette — because a shared default is exactly how the two defects
 * ADR-0012 lists got into eight charts at once.
 */
export interface ComparisonRow {
  /** The row's own name, read out as the bar's label. */
  label: string
  /** Bar length as a share of the track, already clamped to 0–100. */
  percent: number
  /** The figure, formatted by the caller in the caller's locale. */
  display: string
  /** An optional reference tick, as a share of the track. */
  markerPercent?: number
  /** What the tick means, for its tooltip and its screen-reader text. */
  markerLabel?: string
  /** Secondary text at the end of the row. */
  trailing?: string
  /** Overrides the bar colour for this row alone — a signed field needs it. */
  color?: string
}

export interface ComparisonBarsProps {
  rows: ComparisonRow[]
  /** CSS colour for the bar. */
  barColor: string
  /** CSS colour for the track behind it. */
  trackColor: string
  /** CSS colour for the reference tick, when a row carries one. */
  markerColor?: string
  className?: string
  rowClassName?: string
  labelClassName?: string
  valueClassName?: string
  trailingClassName?: string
}

export function ComparisonBars({
  rows,
  barColor,
  trackColor,
  markerColor,
  className,
  rowClassName,
  labelClassName,
  valueClassName,
  trailingClassName,
}: ComparisonBarsProps) {
  return (
    <div className={className}>
      {rows.map((row) => (
        <div key={row.label} className={rowClassName}>
          <span className={labelClassName}>{row.label}</span>
          <div
            className="relative h-1.5 rounded-full"
            style={{ backgroundColor: trackColor }}
          >
            <span
              style={{
                width: `${row.percent}%`,
                backgroundColor: row.color ?? barColor,
              }}
              className="absolute inset-y-0 left-0 rounded-full"
            />
            {row.markerPercent !== undefined && (
              <span
                style={{ left: `${row.markerPercent}%`, backgroundColor: markerColor }}
                title={row.markerLabel}
                className="absolute -top-1 h-3.5 w-0.5"
              />
            )}
          </div>
          <span className={cn("tabular-nums", valueClassName)}>{row.display}</span>
          {row.trailing !== undefined && (
            <span className={cn("tabular-nums", trailingClassName)}>{row.trailing}</span>
          )}
        </div>
      ))}
    </div>
  )
}
