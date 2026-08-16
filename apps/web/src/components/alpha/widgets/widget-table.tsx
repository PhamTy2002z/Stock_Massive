"use client"

/**
 * The data-table equivalent every Widget carries.
 *
 * One table rather than four, because the accessibility requirement is the same
 * requirement in all four cases and four copies is how one of them ends up
 * without a caption. The caption is not decoration: it is what a screen reader
 * announces before the rows, and it is where the data date goes.
 */
export interface WidgetTableProps {
  caption: string
  columns: string[]
  rows: (string | number)[][]
}

export function WidgetTable({ caption, columns, rows }: WidgetTableProps) {
  return (
    <table className="w-full border-collapse text-[13px] leading-[1.43]">
      <caption className="pb-2 text-left" style={{ color: "hsl(var(--widget-ink-muted))" }}>
        {caption}
      </caption>
      <thead>
        <tr>
          {columns.map((column, index) => (
            <th
              key={column}
              scope="col"
              className={
                index === 0
                  ? "border-b border-[hsl(var(--widget-grid))] py-1.5 text-left font-medium"
                  : "border-b border-[hsl(var(--widget-grid))] py-1.5 text-right font-medium"
              }
            >
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={String(row[0])}>
            {row.map((cell, index) => (
              <td
                key={columns[index] ?? index}
                className={
                  index === 0
                    ? "border-b border-[hsl(var(--widget-grid))] py-1.5 text-left"
                    : "border-b border-[hsl(var(--widget-grid))] py-1.5 text-right tabular-nums"
                }
              >
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
