"use client"

import { WIDGET_PALETTE, directionLabel, directionOf } from "./palette"
import type { SeriesData, WidgetProps } from "./types"
import { TooLittleData, WidgetFrame } from "./widget-frame"
import { WidgetTable } from "./widget-table"
import { formatFieldValue, unitLabel } from "./units"

export const METRIC_TREND_VERSION = 1

/** Below this a line is two dots and a guess, and the bullets say more. */
const MIN_POINTS = 3

/**
 * One registered field over the fixed historical window the descriptor names.
 *
 * The trend leaf ADR-0012 asks for, generalised out of the Recharts patterns on
 * the dashboard but drawn as plain inline SVG here, for three reasons that all
 * come from the same decision list. A Widget has to be keyboard operable and
 * screen-reader labelled, and a charting library's DOM is neither by default.
 * It has to fit a 360px column without a horizontal scroller, which a
 * `ResponsiveContainer` measured at zero width does not. And it has to render
 * from a fixture in a test with no network and no layout engine, which is
 * exactly the case a container measuring its own parent cannot serve.
 *
 * The path is drawn in a 0–100 viewBox and stretched, so the component has no
 * opinion about its own width and the caller sizes it with CSS.
 */
export function MetricTrend({
  spec,
  data,
  expanded,
  onExpand,
}: WidgetProps<SeriesData>) {
  const present = data.series.filter(
    (point): point is { date: string; value: number } => point.value !== null
  )

  if (!data.available || present.length < MIN_POINTS) {
    return (
      <TooLittleData
        title={spec.title}
        asOf={data.as_of}
        lines={
          present.length === 0
            ? ["Không dựng lại được chuỗi dữ liệu cho khoảng thời gian này."]
            : present.map(
                (point) => `${point.date}: ${formatFieldValue(point.value, data.unit)}`
              )
        }
      />
    )
  }

  const values = present.map((point) => point.value)
  const low = Math.min(...values)
  const high = Math.max(...values)
  const span = high - low || 1
  const first = values[0]
  const last = values[values.length - 1]

  const path = present
    .map((point, index) => {
      const x = (index / (present.length - 1)) * 100
      const y = 100 - ((point.value - low) / span) * 100
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`
    })
    .join(" ")

  // The same reading of a sign the rest of the registry uses, rather than a
  // third wording of it three files apart.
  const direction = directionLabel(directionOf(last - first))

  return (
    <WidgetFrame
      title={spec.title}
      asOf={data.as_of}
      expanded={expanded}
      onExpand={onExpand}
      figureLabel={
        `Đường xu hướng ${data.field} qua ${present.length} phiên, ` +
        `từ ${present[0].date} đến ${present[present.length - 1].date}`
      }
      summary={
        `${data.field} ${direction} từ ${formatFieldValue(first, data.unit)} ` +
        `đến ${formatFieldValue(last, data.unit)} qua ${present.length} phiên; ` +
        `thấp nhất ${formatFieldValue(low, data.unit)}, ` +
        `cao nhất ${formatFieldValue(high, data.unit)}.`
      }
      table={
        <WidgetTable
          caption={`${data.field} theo phiên — đến ngày ${data.as_of}`}
          columns={["Phiên", `Giá trị (${unitLabel(data.unit)})`]}
          rows={data.series.map((point) => [
            point.date,
            formatFieldValue(point.value, data.unit),
          ])}
        />
      }
    >
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
        className="h-24 w-full sm:h-32"
      >
        <line
          x1="0"
          y1="100"
          x2="100"
          y2="100"
          stroke={WIDGET_PALETTE.grid}
          strokeWidth="1"
          vectorEffect="non-scaling-stroke"
        />
        <path
          d={path}
          fill="none"
          stroke={WIDGET_PALETTE.series}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          // Without this the non-uniform stretch smears the line weight.
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div
        className="mt-1 flex justify-between text-[11px] tabular-nums"
        style={{ color: WIDGET_PALETTE.inkMuted }}
      >
        <span>{present[0].date}</span>
        <span>{present[present.length - 1].date}</span>
      </div>
    </WidgetFrame>
  )
}
