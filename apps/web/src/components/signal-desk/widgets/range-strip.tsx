"use client"

/**
 * One price inside the range it has traded in, and where the closes cluster.
 *
 * Laid out by hand rather than by a charting library, for the reason the heatmap
 * is: what this draws is not a chart. It is a ruler with one mark on it, and
 * every library that could draw it would first turn the three numbers into a
 * series of one point and then argue about axes.
 *
 * **The marker is placed from the numbers, not from the percentile.** The server
 * sends both, and the position a reader sees has to be the arithmetic of low,
 * high and current — a marker drawn from a rounded percentage would sit beside
 * the number printed under it.
 *
 * **A band inside the band is optional and never invented.** When the frame
 * carries a sub-range — the sixty-session close cluster the condition review
 * measures — it is shaded inside the track. When it does not, nothing is shaded:
 * a shaded region with no numbers behind it is a claim about price structure
 * that nothing computed.
 *
 * **The picture is not the only way to read it.** The three prices and the
 * position are printed under the track, and the whole reading is the `img`
 * label, so a reader who cannot see the strip gets the same sentence rather than
 * "biểu đồ".
 *
 * **Positioned, not stretched.** This was one `viewBox` stretched to the panel's
 * width, which meant the rule that makes the position "readable to the pixel"
 * arrived six pixels wide on a wide panel and two on a narrow one — the mark
 * grew with the panel and the precision it claimed shrank. Position is a
 * percentage of the track and every thickness is a pixel, so the strip is the
 * same strip at any width.
 */

import type { Frame } from "@/lib/alpha-desk/types"

import {
  axisPresentation,
  columnIndex,
  formatPercentPoint,
  numberAt,
} from "../frame"
import type { WidgetProps } from "../widget-registry"
import { FOCUS, TRACK } from "./chart-theme"

/** The wedge above the mark, in the pixels it is actually drawn at. */
const WEDGE_WIDTH = 8
const WEDGE_HEIGHT = 6
const WEDGE = `0,0 ${WEDGE_WIDTH},0 ${WEDGE_WIDTH / 2},${WEDGE_HEIGHT}`

/** The cluster inside the range: the neutral series, thinned to sit under the
    mark rather than compete with it. */
const BAND = "hsl(var(--widget-series) / 0.35)"

export function RangeStripWidget({ frame, options }: WidgetProps) {
  const row = frame.rows[0]
  const low = read(frame, row, options.low, "low", 0)
  const high = read(frame, row, options.high, "high", 1)
  const current = read(frame, row, options.current, "current", 2)
  const percentile = read(frame, row, options.percentile, "percentile", 3)
  const bandLow = read(frame, row, options.bandLow, "zone_low")
  const bandHigh = read(frame, row, options.bandHigh, "zone_high")
  const bandLabel =
    typeof options.bandLabel === "string" ? options.bandLabel : "Vùng giá tập trung"

  if (low === null || high === null || current === null || high <= low) {
    return (
      <p className="text-meta text-muted-foreground">
        Chưa đủ số để vẽ dải giá.
      </p>
    )
  }

  const position = share(current, low, high)
  const band =
    bandLow !== null && bandHigh !== null && bandHigh > bandLow
      ? { from: share(bandLow, low, high), to: share(bandHigh, low, high) }
      : null
  const priceAxis = axisPresentation(
    [low, high, current, bandLow, bandHigh].filter(
      (value): value is number => value !== null,
    ),
    frame.unit,
  )

  // The sentence is written from fixed words rather than from the frame's own
  // labels: this is the reading a person who cannot see the strip is given, and
  // a column the server did not label would otherwise put a raw column name in
  // the middle of it.
  const reading =
    `Mức hiện tại ${priceAxis.measure(current)} trong dải ${priceAxis.format(low)}` +
    `–${priceAxis.format(high)}, ở ${formatPercentPoint(
      percentile ?? position * 100,
    )} của dải` +
    (band === null
      ? ""
      : `; ${bandLabel} ${priceAxis.format(bandLow as number)}–${priceAxis.format(
          bandHigh as number,
        )} ${priceAxis.unit}`)

  return (
    <figure className="m-0">
      <div className="mb-1 flex items-baseline justify-between gap-3 text-meta">
        <span className="font-medium text-ink-3">Dải giá 52 tuần</span>
        {priceAxis.unit !== "" && (
          <span className="whitespace-nowrap font-mono tabular-nums text-muted-foreground">
            {priceAxis.unit}
          </span>
        )}
      </div>
      <div className="relative h-6 overflow-hidden" role="img" aria-label={reading}>
        <div
          data-part="track"
          className="absolute inset-x-0 top-[7px] h-2.5 rounded-[3px]"
          style={{ background: TRACK }}
        />
        {band !== null && (
          <div
            data-part="band"
            className="absolute top-[7px] h-2.5 rounded-[3px]"
            style={{
              left: `${band.from * 100}%`,
              width: `${(band.to - band.from) * 100}%`,
              // Never nothing: a cluster narrower than a pixel is still a
              // cluster, and a zero-width shading would read as no cluster.
              minWidth: 2,
              background: BAND,
            }}
          />
        )}
        {/* The mark: a full-height rule so the position is readable to the
            pixel, and a wedge above it so it is findable at a glance. The
            wedge is SVG at a fixed size rather than a scaled shape, so it is
            the same triangle whatever the panel is doing. */}
        <div
          data-part="marker"
          className="absolute inset-y-0 w-0.5"
          style={{ left: `${position * 100}%`, marginLeft: -1, background: FOCUS }}
        />
        <svg
          aria-hidden
          width={WEDGE_WIDTH}
          height={WEDGE_HEIGHT}
          className="absolute top-0"
          style={{ left: `${position * 100}%`, marginLeft: -WEDGE_WIDTH / 2 }}
        >
          <polygon points={WEDGE} fill={FOCUS} />
        </svg>
      </div>

      <div className="mt-1 flex items-baseline justify-between gap-2 whitespace-nowrap font-mono text-meta tabular-nums">
        <span className="text-muted-foreground">{priceAxis.format(low)}</span>
        <span className="font-semibold text-ink-2">
          {priceAxis.format(current)}
          {percentile !== null && (
            <span className="ml-1 font-sans font-normal text-muted-foreground">
              ({formatPercentPoint(percentile)} dải)
            </span>
          )}
        </span>
        <span className="text-muted-foreground">{priceAxis.format(high)}</span>
      </div>

      {band !== null && (
        <figcaption className="mt-1 flex items-center gap-1.5 text-meta text-muted-foreground">
          <span
            aria-hidden
            className="inline-block h-2.5 w-4 rounded-[2px]"
            style={{ background: BAND }}
          />
          <span>
            {bandLabel}:{" "}
            <span className="whitespace-nowrap font-mono tabular-nums">
              {priceAxis.format(bandLow as number)}–
              {priceAxis.format(bandHigh as number)}
            </span>
          </span>
        </figcaption>
      )}
    </figure>
  )
}

/**
 * One cell of the frame's single row, by the name the server gave or by position.
 *
 * The positional fallback is for a frame this widget was pointed at without
 * options — `render_signal_desk` composes a desk view from frames a Study did not shape
 * for this widget, and "the first three columns are low, high and current" is
 * the only general rule there is. A column that is neither named nor at that
 * position answers null, and null is drawn as absent rather than as zero.
 */
function read(
  frame: Frame,
  row: unknown[] | undefined,
  option: unknown,
  name: string,
  position?: number,
): number | null {
  if (row === undefined) return null
  const named = columnIndex(frame, typeof option === "string" ? option : name)
  if (named >= 0) return numberAt(row, named)
  return position === undefined ? null : numberAt(row, position)
}

/** Where one value sits between the two ends, never outside them. */
function share(value: number, low: number, high: number): number {
  return Math.min(1, Math.max(0, (value - low) / (high - low)))
}
