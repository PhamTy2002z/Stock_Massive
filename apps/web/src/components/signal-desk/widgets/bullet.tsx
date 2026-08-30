"use client"

/**
 * One value against one benchmark, per row, on a shared scale.
 *
 * The question this answers is "is this above or below where it should be", and
 * the reason it is not two bars is that a pair of bars asks the reader to
 * compare lengths where a mark on a track asks them to look at one place. The
 * benchmark is the quietest thing on the row for the same reason: it is the
 * reference, not the subject.
 *
 * No chart library. A track, a fill and a rule is layout, and pulling a runtime
 * in to place three boxes would cost the panel its first paint.
 */

import { columnIndex, formatMeasure, labelOf, numberAt, textAt } from "../frame"
import type { WidgetProps } from "../widget-registry"

export function BulletWidget({ frame, options }: WidgetProps) {
  const labelColumn =
    typeof options.label === "string" ? options.label : frame.columns[0]
  const valueColumn =
    typeof options.value === "string" ? options.value : frame.columns[1]
  const benchmarkColumn =
    typeof options.benchmark === "string" ? options.benchmark : frame.columns[2]

  const label = columnIndex(frame, labelColumn)
  const value = columnIndex(frame, valueColumn)
  const benchmark = columnIndex(frame, benchmarkColumn)

  const rows = frame.rows
    .map((row) => ({
      label: textAt(row, label),
      value: numberAt(row, value),
      benchmark: numberAt(row, benchmark),
    }))
    .filter((row): row is { label: string; value: number; benchmark: number | null } =>
      row.value !== null,
    )

  if (rows.length === 0) {
    return <p className="text-meta text-muted-foreground">Không có mức nào để so.</p>
  }

  // One scale across every row, so two rows of the same picture are comparable.
  // Negatives are not folded in: a track runs from zero, and a value below it is
  // clamped to nothing rather than drawn as a bar pointing the wrong way.
  const ceiling = Math.max(
    ...rows.flatMap((row) => [row.value, row.benchmark ?? 0].map(Math.abs)),
    1,
  )

  return (
    <ul className="m-0 list-none space-y-2 p-0">
      {rows.map((row, index) => (
        <li key={`${row.label}-${index}`} className="min-w-0">
          <div className="flex items-baseline justify-between gap-2">
            <span className="truncate text-meta text-muted-foreground">{row.label}</span>
            <span className="shrink-0 font-mono text-meta tabular-nums text-foreground">
              {formatMeasure(row.value, frame.unit)}
            </span>
          </div>
          <div className="relative mt-1 h-2 rounded-full bg-[hsl(var(--widget-track))]">
            <div
              className="absolute inset-y-0 left-0 rounded-full bg-[hsl(var(--widget-series))]"
              style={{ width: `${Math.min(100, Math.max(0, (row.value / ceiling) * 100))}%` }}
            />
            {row.benchmark !== null && (
              <span
                aria-hidden
                className="absolute inset-y-[-2px] w-[2px] rounded bg-[hsl(var(--widget-benchmark))]"
                style={{
                  left: `${Math.min(100, Math.max(0, (row.benchmark / ceiling) * 100))}%`,
                }}
                title={`Mốc ${formatMeasure(row.benchmark, frame.unit)}`}
              />
            )}
          </div>
        </li>
      ))}
      <li className="text-meta text-muted-foreground">
        Vạch dọc là {labelOf(frame, benchmarkColumn ?? "")}.
      </li>
    </ul>
  )
}
