"use client"

import type { PeriodFigures, PeriodsData, WidgetProps } from "./types"
import { TooLittleData, WidgetFrame, formatDataDate } from "./widget-frame"
import { WidgetTable } from "./widget-table"
import { formatFieldValue, unitLabel } from "./units"

export const QUARTERLY_FINANCIALS_VERSION = 1

/**
 * A statement read across quarters, as the table it already is.
 *
 * The four Widgets before this one draw a picture and keep a table behind a
 * disclosure. This one inverts that, and the inversion is the whole design:
 * *what changed between Q2 and Q1* is a comparison of eight numbers against
 * eight other numbers, and there is no chart of a mixed income statement that
 * answers it better than the rows do. Drawing one — eight quarters of revenue as
 * a line, with profit and margin left out because they share no axis — would
 * spend the reader's attention on a shape and then send them to the disclosure
 * for the answer. So there is no picture, and therefore no `table` prop: the
 * rows are the figure, in the accessibility tree from the first render.
 *
 * **Column names are the server's, unprettified.** A label dictionary here would
 * be a second vocabulary for the statement lines, and the failure mode of a
 * dictionary that has drifted is a blank column header over real numbers —
 * strictly worse than `revenue_vnd`, which at least names the thing. The unit is
 * stated once, in the caption, because it is one unit for the whole table
 * (`units.ts` never converts; ADR-0012 keeps scaling on the server).
 *
 * **Period order is the server's too.** `periods` arrives newest first and is
 * rendered in that order rather than re-sorted, because sorting would mean this
 * component deciding what "recent" means for a `period_end` it cannot parse.
 *
 * At 360px a statement table is wider than the column, and the overflow is the
 * table's own to hold — the same rule the prose renderer's tables follow, since
 * a table that widened the transcript would move the composer and the question
 * above it.
 */
export function QuarterlyFinancials({
  spec,
  data,
  expanded,
  onExpand,
}: WidgetProps<PeriodsData>) {
  // No columns is as empty as no rows: a period list with nothing measured
  // against it is a table of dates, which reads as data and is not.
  if (!data.available || data.periods.length === 0 || data.figures.length === 0) {
    return (
      <TooLittleData
        title={spec.title}
        asOf={data.as_of}
        lines={[
          `Chưa có số liệu theo kỳ của ${data.symbol} để dựng lại bảng cho ngày này.`,
        ]}
      />
    )
  }

  const newest = data.periods[0]
  const staleCount = data.periods.filter((period) => period.stale).length
  const unit = unitLabel(data.unit)

  return (
    <WidgetFrame
      title={spec.title}
      asOf={data.as_of}
      expanded={expanded}
      onExpand={onExpand}
      figureLabel={
        `Bảng ${data.periods.length} kỳ báo cáo của ${data.symbol}, ` +
        `${data.figures.length} chỉ tiêu, đơn vị ${unit}, tại ngày ${data.as_of}`
      }
      summary={
        `${data.symbol}: ${data.periods.length} kỳ báo cáo, mới nhất là kỳ ` +
        `${formatDataDate(newest.period_end)}` +
        (staleCount > 0
          ? `; ${staleCount} kỳ đã cũ so với ngày dữ liệu.`
          : ".")
      }
    >
      <div className="overflow-x-auto">
        <WidgetTable
          caption={`Kết quả theo kỳ của ${data.symbol} — đơn vị ${unit} — dữ liệu ngày ${formatDataDate(data.as_of)}`}
          columns={["Kỳ", ...data.figures]}
          rows={data.periods.map((period) => [
            periodLabel(period),
            ...data.figures.map((figure) =>
              formatFieldValue(figureValue(period, figure), data.unit)
            ),
          ])}
        />
      </div>
    </WidgetFrame>
  )
}

/**
 * One period's row header, carrying its staleness in words.
 *
 * Stated in the label rather than tinted or badged, for the reason the
 * comparison Widget states its direction in text: a cell whose only mark is a
 * colour is unmarked to a reader who cannot see it, and this label is also what
 * a screen reader announces as the row's header.
 */
function periodLabel(period: PeriodFigures): string {
  return period.stale
    ? `${formatDataDate(period.period_end)} · số liệu cũ`
    : formatDataDate(period.period_end)
}

/**
 * One figure of one period, or nothing.
 *
 * Checked with `typeof` rather than read straight off the map: a quarter whose
 * statement had no such line carries no key at all, and the index signature
 * hands back the declared type either way. Without this, an absent line reaches
 * the formatter as `undefined` and throws inside the transcript — which costs
 * the reader the text answer, not just the cell.
 */
function figureValue(period: PeriodFigures, figure: string): number | null {
  const raw = period.figures[figure]
  return typeof raw === "number" ? raw : null
}
