"use client"

import { WIDGET_PALETTE } from "./palette"
import type { RankingData, WidgetProps } from "./types"
import { TooLittleData, WidgetFrame } from "./widget-frame"
import { WidgetTable } from "./widget-table"
import { formatFieldValue, unitLabel } from "./units"

export const RANKED_SYMBOLS_VERSION = 1

/**
 * The ordered result of a Universe screen, mobile-first.
 *
 * New rather than extracted, because nothing on this surface ranked symbols
 * without also fetching them. The list is the primary form and the bar is an
 * ornament on it — **bars only where their length carries meaning**
 * (ADR-0012): a screen sorted by a figure with no zero to measure from gets
 * rank numbers and no bars at all, since a bar drawn from an arbitrary origin
 * invites a comparison the data does not support.
 *
 * A list is also what makes this readable at 360px without a horizontal
 * scroller: rows stack, and the row is already the layout.
 */

/** Sort keys whose zero is real, so a bar length means something. */
const MEASURABLE_FROM_ZERO = new Set([
  "market_cap_vnd",
  "adtv_vnd",
  "ttm_net_income_vnd",
])

/** How each screen column is written, since a screen is not a Signal Field. */
const COLUMN_UNITS: Record<string, string> = {
  market_cap_vnd: "vnd",
  adtv_vnd: "vnd",
  ttm_net_income_vnd: "vnd",
  provider_pe: "ratio",
  provider_pb: "ratio",
}

export function RankedSymbols({
  spec,
  data,
  expanded,
  onExpand,
}: WidgetProps<RankingData>) {
  const unit = COLUMN_UNITS[data.sort_by] ?? null
  const values = data.rows.map((row) => {
    const raw = row[data.sort_by]
    return typeof raw === "number" ? raw : null
  })
  const present = values.filter((value): value is number => value !== null)

  if (!data.available || data.rows.length === 0) {
    return (
      <TooLittleData
        title={spec.title}
        asOf={data.as_of}
        lines={["Không dựng lại được kết quả lọc cho ngày này."]}
      />
    )
  }

  const bars = MEASURABLE_FROM_ZERO.has(data.sort_by) && present.length > 0
  const widest = bars ? Math.max(...present.map(Math.abs)) || 1 : 1

  return (
    <WidgetFrame
      title={spec.title}
      asOf={data.as_of}
      expanded={expanded}
      onExpand={onExpand}
      figureLabel={
        `Danh sách ${data.rows.length} mã xếp theo ${data.sort_by}, ` +
        `${data.order === "desc" ? "giảm dần" : "tăng dần"}, tại ngày ${data.as_of}`
      }
      summary={
        `${data.rows[0]?.symbol} dẫn đầu theo ${data.sort_by}` +
        (data.matched_count !== undefined
          ? `; ${data.rows.length}/${data.matched_count} mã đạt điều kiện được hiển thị.`
          : ".")
      }
      table={
        <WidgetTable
          caption={`Kết quả lọc theo ${data.sort_by} — dữ liệu ngày ${data.as_of}`}
          columns={["Hạng", "Mã", `${data.sort_by} (${unitLabel(unit)})`]}
          rows={data.rows.map((row, index) => [
            index + 1,
            row.symbol,
            formatFieldValue(values[index], unit),
          ])}
        />
      }
    >
      <ol className="m-0 list-none p-0">
        {data.rows.map((row, index) => (
          <li
            key={row.symbol}
            className="grid grid-cols-[28px_minmax(44px,auto)_minmax(0,1fr)] items-center gap-2 py-1.5"
          >
            <span
              className="text-meta tabular-nums"
              style={{ color: WIDGET_PALETTE.inkMuted }}
            >
              {index + 1}
            </span>
            <span className="truncate text-meta font-medium">{row.symbol}</span>
            <span className="flex min-w-0 items-center justify-end gap-2">
              {bars && values[index] !== null && (
                <span
                  aria-hidden="true"
                  className="hidden h-1.5 min-w-0 flex-1 rounded-full sm:block"
                  style={{ backgroundColor: WIDGET_PALETTE.track }}
                >
                  <span
                    className="block h-full rounded-full"
                    style={{
                      width: `${(Math.abs(values[index] as number) / widest) * 100}%`,
                      backgroundColor: WIDGET_PALETTE.series,
                    }}
                  />
                </span>
              )}
              <span className="shrink-0 text-meta tabular-nums">
                {formatFieldValue(values[index], unit)}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </WidgetFrame>
  )
}
