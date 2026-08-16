"use client"

import { ComparisonBars, type ComparisonRow } from "@/components/charts"
import {
  WIDGET_PALETTE,
  directionColor,
  directionLabel,
  directionOf,
  directionSign,
} from "./palette"
import type { CrossSymbolData, WidgetProps } from "./types"
import { TooLittleData, WidgetFrame } from "./widget-frame"
import { WidgetTable } from "./widget-table"
import { formatFieldValue, unitLabel } from "./units"

export const METRIC_COMPARISON_VERSION = 1

/**
 * One registered field across symbols, as bars on a shared track.
 *
 * Built on the comparison leaf extracted from the valuation-versus-sector card
 * and drawn with the registry palette (ADR-0012). It takes its points as props
 * and fetches nothing, which is what lets it appear inside an answer dated to
 * last March without quietly redrawing itself with today's figures.
 *
 * A signed field is coloured by direction *and* labelled with an arrow and a
 * Vietnamese word, because colour alone would leave the sign unreadable to a
 * reader who cannot separate the two hues.
 */
export function MetricComparison({
  spec,
  data,
  expanded,
  onExpand,
}: WidgetProps<CrossSymbolData> & { onExpand?: () => void }) {
  const present = data.points.filter((point) => point.value !== null)

  // One bar is not a comparison, and an empty axis is not an answer.
  if (!data.available || present.length < 2) {
    return (
      <TooLittleData
        title={spec.title}
        asOf={data.as_of}
        lines={unavailableLines(data)}
      />
    )
  }

  // A field can be negative, so the track is scaled by the widest magnitude
  // rather than by the maximum: scaling by the maximum would draw every bar of
  // a wholly negative field at full length.
  const widest = Math.max(...present.map((point) => Math.abs(point.value as number)))
  const scale = widest === 0 ? 1 : widest

  // A field that never crosses zero carries no direction, so it is drawn in the
  // one neutral series colour. Colouring an all-positive percentile green would
  // be the widget inventing a reading the registry did not sanction.
  const signed = present.some((point) => (point.value as number) < 0)

  const rows: ComparisonRow[] = present.map((point) => {
    const value = point.value as number
    const direction = directionOf(value)
    return {
      label: point.symbol,
      percent: (Math.abs(value) / scale) * 100,
      display: signed
        ? `${directionSign(direction)} ${formatFieldValue(value, data.unit)}`
        : formatFieldValue(value, data.unit),
      color: signed ? directionColor(direction) : WIDGET_PALETTE.series,
    }
  })

  const ranked = [...present].sort(
    (a, b) => (b.value as number) - (a.value as number)
  )
  const leader = ranked[0]
  const laggard = ranked[ranked.length - 1]

  return (
    <WidgetFrame
      title={spec.title}
      asOf={data.as_of}
      expanded={expanded}
      onExpand={onExpand}
      figureLabel={`Biểu đồ cột so sánh ${data.field} giữa ${present
        .map((point) => point.symbol)
        .join(", ")} tại ngày ${data.as_of}`}
      summary={
        `${leader.symbol} cao nhất ở ${formatFieldValue(leader.value, data.unit)}, ` +
        `${laggard.symbol} thấp nhất ở ${formatFieldValue(laggard.value, data.unit)}` +
        ` (${unitLabel(data.unit)}).`
      }
      table={
        <WidgetTable
          caption={`${data.field} — dữ liệu ngày ${data.as_of}`}
          columns={["Mã", `Giá trị (${unitLabel(data.unit)})`, "Chiều"]}
          rows={data.points.map((point) => [
            point.symbol,
            formatFieldValue(point.value, data.unit),
            directionLabel(directionOf(point.value)),
          ])}
        />
      }
    >
      {/* Narrow screens keep the same rows; the label column shrinks and the
          bar takes what is left, so nothing scrolls sideways. */}
      <ComparisonBars
        rows={rows}
        barColor={WIDGET_PALETTE.series}
        trackColor={WIDGET_PALETTE.track}
        emphasisColor={WIDGET_PALETTE.focus}
        rowClassName="grid grid-cols-[minmax(44px,64px)_minmax(0,1fr)_minmax(72px,auto)] items-center gap-2 py-1.5"
        labelClassName="truncate text-[13px] font-medium"
        valueClassName="text-right text-[13px]"
      />
      <ul className="sr-only">
        {present.map((point) => (
          <li key={point.symbol}>
            {point.symbol}: {formatFieldValue(point.value, data.unit)},{" "}
            {directionLabel(directionOf(point.value))}
          </li>
        ))}
      </ul>
      {signed && (
        // The direction key, in words rather than in swatches.
        <p className="sr-only">
          {directionSign("up")} {directionLabel("up")}, {directionSign("down")}{" "}
          {directionLabel("down")}
        </p>
      )}
    </WidgetFrame>
  )
}

export function unavailableLines(data: CrossSymbolData): string[] {
  const lines = data.points.map((point) =>
    point.value === null
      ? `${point.symbol}: chưa đủ dữ liệu${point.refusal ? ` (${point.refusal})` : ""}`
      : `${point.symbol}: ${formatFieldValue(point.value, data.unit)}`
  )
  return lines.length > 0
    ? lines
    : ["Không dựng lại được lát dữ liệu cho ngày này."]
}
