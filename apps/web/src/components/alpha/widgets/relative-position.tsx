"use client"

import { RangeTrack } from "@/components/charts"
import { WIDGET_PALETTE } from "./palette"
import type { CrossSymbolData, WidgetProps } from "./types"
import { TooLittleData, WidgetFrame } from "./widget-frame"
import { WidgetTable } from "./widget-table"
import { formatFieldValue, unitLabel } from "./units"

export const RELATIVE_POSITION_VERSION = 1

/**
 * Where one value sits against the range or the sample it was ranked in.
 *
 * New, and informed by the range-card primitive on the stock overview — which
 * is where the "a position on a track beats a subtraction the reader has to do
 * in their head" reading came from. It reuses that extracted leaf with the
 * registry palette, and adds the two things a card on a fixed page never needed:
 * a stated date, and an honest answer when there is nothing to place the value
 * against.
 *
 * The position comes from the registered field's own details, never from
 * arithmetic here. A field that is already a percentile *is* its own position;
 * a field carrying `low` and `high` in its details is placed between them.
 * Anything else has no sanctioned position, so the value is stated as text
 * rather than invented as a mark on a track.
 */
export interface PositionReading {
  percent: number
  lowLabel: string
  highLabel: string
  basis: string
}

export function readPosition(data: CrossSymbolData): PositionReading | null {
  const point = data.points[0]
  if (!point || point.value === null) return null

  if (data.unit === "percentile") {
    return {
      percent: clamp(point.value),
      lowLabel: "phân vị 0",
      highLabel: "phân vị 100",
      basis: "so với các mã trong Universe",
    }
  }

  const low = numberOf(point.details?.low)
  const high = numberOf(point.details?.high)
  if (low !== null && high !== null && high > low) {
    return {
      percent: clamp(((point.value - low) / (high - low)) * 100),
      lowLabel: formatFieldValue(low, data.unit),
      highLabel: formatFieldValue(high, data.unit),
      basis: "so với biên độ của chính nó trong cửa sổ này",
    }
  }
  return null
}

function numberOf(value: unknown): number | null {
  return typeof value === "number" && !Number.isNaN(value) ? value : null
}

function clamp(value: number): number {
  return Math.min(100, Math.max(0, value))
}

export function RelativePosition({
  spec,
  data,
  expanded,
  onExpand,
}: WidgetProps<CrossSymbolData> & { onExpand?: () => void }) {
  const point = data.points[0]
  const reading = data.available ? readPosition(data) : null

  if (!reading || !point) {
    return (
      <TooLittleData
        title={spec.title}
        asOf={data.as_of}
        lines={
          point && point.value !== null
            ? [
                `${point.symbol}: ${formatFieldValue(point.value, data.unit)} (${unitLabel(data.unit)})`,
                "Chưa có biên độ tham chiếu để đặt giá trị này vào vị trí.",
              ]
            : ["Không dựng lại được giá trị cho ngày này."]
        }
      />
    )
  }

  const value = formatFieldValue(point.value, data.unit)

  return (
    <WidgetFrame
      title={spec.title}
      asOf={data.as_of}
      expanded={expanded}
      onExpand={onExpand}
      figureLabel={
        `Thanh vị trí: ${point.symbol} ở ${value}, tương đương ` +
        `${reading.percent.toFixed(0)}% khoảng từ ${reading.lowLabel} đến ` +
        `${reading.highLabel}, tại ngày ${data.as_of}`
      }
      summary={`${point.symbol} đang ở ${value} — ${reading.percent.toFixed(
        0
      )}% khoảng, ${reading.basis}.`}
      table={
        <WidgetTable
          caption={`${data.field} — dữ liệu ngày ${data.as_of}`}
          columns={["Chỉ tiêu", "Giá trị"]}
          rows={[
            ["Mã", point.symbol],
            [`Giá trị (${unitLabel(data.unit)})`, value],
            ["Cận dưới", reading.lowLabel],
            ["Cận trên", reading.highLabel],
            ["Vị trí trong khoảng", `${reading.percent.toFixed(0)}%`],
          ]}
        />
      }
    >
      <div className="flex items-baseline justify-between gap-3 text-[13px] tabular-nums">
        <span style={{ color: "hsl(var(--widget-ink-muted))" }}>
          {reading.lowLabel}
        </span>
        <span className="font-medium">{value}</span>
        <span style={{ color: "hsl(var(--widget-ink-muted))" }}>
          {reading.highLabel}
        </span>
      </div>
      <RangeTrack
        percent={reading.percent}
        className="mt-2.5"
        fillColor={WIDGET_PALETTE.seriesMuted}
        trackColor={WIDGET_PALETTE.track}
        markerColor={WIDGET_PALETTE.series}
        markerRingColor={WIDGET_PALETTE.surface}
      />
    </WidgetFrame>
  )
}
