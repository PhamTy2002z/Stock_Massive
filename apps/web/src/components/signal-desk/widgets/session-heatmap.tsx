"use client"

/**
 * Sessions down, buckets across, and how dark each cell is says how much traded.
 *
 * Hand-drawn SVG rather than a charting library, and the reason is the empty
 * cell. A matrix of thirty sessions by seventeen buckets is mostly *holes*: a
 * HOSE symbol has no 09:00 bucket at all, and a quiet quarter hour is simply
 * absent from the provider's answer. Every heatmap component worth using treats
 * a missing value as zero, and zero here is a different and false claim — that
 * the quarter hour existed and nobody traded in it. So the hole is drawn as a
 * hole, and that decision is the widget.
 *
 * **Four steps, not a gradient.** A continuous scale asks a reader to compare
 * two shades of the same colour across a panel's width, which nobody can do. A
 * banded scale asks them to compare *bands*, which is the question they have —
 * is this bucket in the busiest group or the quietest one. The bands are shares
 * of the session's own busiest bucket, so a quiet Tuesday and a frantic Friday
 * read alike.
 *
 * **Every column is labelled, and the label is not a hover.** Seventeen
 * four-character labels do not fit seventeen fourteen-pixel columns lying flat,
 * so they stand on end. Labelling every other one instead left the odd buckets
 * identifiable only by counting across, and a `<title>` does not answer that
 * either: there is no hover on a touch screen. The block's own "Xem dạng bảng"
 * disclosure is what carries the numbers as text.
 */

import { formatPercent, labelOf, numberAt } from "../frame"
import type { WidgetProps } from "../widget-registry"

/** The four bands, quietest first, as a share of the row's own busiest cell. */
const BANDS = [0.25, 0.5, 0.75, 1] as const

/**
 * What each band is painted with.
 *
 * One hue at four opacities rather than four hues: the quantity is ordered, and
 * four colours would invite a reader to look for four categories. The hue is
 * the shared neutral series token — the ladder used to climb through the brand
 * amber, which made a busy quarter hour look like a control — and it is defined
 * for both themes, so the ladder holds its contrast on either ground.
 */
const FILLS = [
  "hsl(var(--widget-series) / 0.22)",
  "hsl(var(--widget-series) / 0.48)",
  "hsl(var(--widget-series) / 0.72)",
  "hsl(var(--widget-series) / 0.95)",
] as const

const CELL = 14
const GAP = 2
const ROW_LABEL = 62
/** Tall enough for a five-character label standing on end, plus its gap. */
const HEADER = 36
/** So the last column's cell is not flush with the edge of the scroll box. */
const PAD_RIGHT = 6

export function SessionHeatmapWidget({ frame, options }: WidgetProps) {
  const rowKey = typeof options.rowKey === "string" ? options.rowKey : frame.columns[0]
  const keyIndex = frame.columns.indexOf(rowKey ?? "")
  // Every column except the one naming the row is a bucket.
  const buckets = frame.columns
    .map((column, index) => ({ column, index }))
    .filter((entry) => entry.index !== keyIndex)

  if (frame.rows.length === 0 || buckets.length === 0) {
    return <p className="text-meta text-muted-foreground">Chưa đủ phiên để vẽ.</p>
  }

  const width = ROW_LABEL + buckets.length * (CELL + GAP) + PAD_RIGHT
  const height = HEADER + frame.rows.length * (CELL + GAP)

  return (
    <figure className="m-0">
      <div className="overflow-x-auto scrollbar-thin">
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`Ma trận phiên theo khung giờ, ${frame.rows.length} phiên × ${buckets.length} khung giờ`}
        >
          {buckets.map((bucket, column) => {
            // Standing on end, reading upwards from its own cell. Rotating by
            // a quarter turn about the anchor turns the fourteen pixels a label
            // does not have across into the thirty it does have up, so every
            // column gets one instead of every other column.
            const centre = ROW_LABEL + column * (CELL + GAP) + CELL / 2
            const foot = HEADER - 4
            return (
              <text
                key={bucket.column}
                x={centre}
                y={foot}
                dominantBaseline="middle"
                transform={`rotate(-90 ${centre} ${foot})`}
                className="fill-ink-5 text-[9px] tabular-nums"
              >
                {bucket.column}
              </text>
            )
          })}

          {frame.rows.map((row, rowIndex) => {
            const values = buckets.map((bucket) => numberAt(row, bucket.index))
            const busiest = Math.max(
              ...values.filter((value): value is number => value !== null),
              0,
            )
            const y = HEADER + rowIndex * (CELL + GAP)
            return (
              <g key={rowIndex}>
                <text
                  x={0}
                  y={y + CELL - 3}
                  className="fill-ink-5 text-[9px] tabular-nums"
                >
                  {String(row[keyIndex] ?? "")}
                </text>
                {values.map((value, column) => (
                  <rect
                    key={buckets[column].column}
                    x={ROW_LABEL + column * (CELL + GAP)}
                    y={y}
                    width={CELL}
                    height={CELL}
                    rx={2}
                    fill={value === null ? "hsl(var(--surface-sunken))" : fillFor(value, busiest)}
                    stroke={value === null ? "hsl(var(--hairline))" : "none"}
                    strokeDasharray={value === null ? "1 1" : undefined}
                  >
                    <title>
                      {`${row[keyIndex] ?? ""} · ${buckets[column].column}: ` +
                        (value === null
                          ? "không có dữ liệu"
                          : formatPercent(busiest === 0 ? 0 : value / busiest))}
                    </title>
                  </rect>
                ))}
              </g>
            )
          })}
        </svg>
      </div>

      <figcaption className="mt-2 flex items-center gap-2 text-meta text-muted-foreground">
        <span>{labelOf(frame, rowKey ?? "")}</span>
        <span className="flex items-center gap-1">
          <span>thấp</span>
          {FILLS.map((fill) => (
            <span
              key={fill}
              aria-hidden
              className="inline-block size-2.5 rounded-[2px]"
              style={{ background: fill }}
            />
          ))}
          <span>cao</span>
        </span>
        <span className="flex items-center gap-1">
          <span
            aria-hidden
            className="inline-block size-2.5 rounded-[2px] border border-dashed border-hairline bg-surface-sunken"
          />
          <span>không có dữ liệu</span>
        </span>
      </figcaption>
    </figure>
  )
}

/** Which band one cell falls in, measured against its own row's busiest. */
function fillFor(value: number, busiest: number): string {
  if (busiest <= 0) return FILLS[0]
  const share = value / busiest
  const band = BANDS.findIndex((ceiling) => share <= ceiling)
  return FILLS[band === -1 ? FILLS.length - 1 : band]
}
