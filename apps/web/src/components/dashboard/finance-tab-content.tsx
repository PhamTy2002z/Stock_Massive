"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"
import { useIncomeStatement } from "@/hooks/use-income-statement"
import { useBalanceSheet } from "@/hooks/use-balance-sheet"
import { useCashFlow } from "@/hooks/use-cash-flow"
import type { IncomeStatementRow, BalanceSheetRow, CashFlowRow } from "@/lib/api"

// Types for financial data
export type FinanceSubTab = "income" | "balance" | "cashflow"
export type PeriodType = "quarter" | "year"

interface FinanceTabContentProps {
  symbol: string
  className?: string
}

// Sub-tab configuration
const subTabs = [
  { value: "income" as const, label: "Kết quả kinh doanh" },
  { value: "balance" as const, label: "Cân đối kế toán" },
  { value: "cashflow" as const, label: "Lưu chuyển tiền tệ" },
]

type ApiRow = IncomeStatementRow | BalanceSheetRow | CashFlowRow

/**
 * Three distinct states, three distinct glyphs: `—` for "not published",
 * `0,0` for a real zero, and a leading minus for negatives. Accounting
 * parentheses read as a footnote to anyone outside finance, and they made a
 * loss indistinguishable from an annotation at a glance.
 */
function formatFinancialValue(value: number | null | undefined): {
  text: string
  tone: "empty" | "zero" | "negative" | "normal"
} {
  if (value === null || value === undefined) return { text: "—", tone: "empty" }
  if (value === 0) return { text: "0,0", tone: "zero" }

  const formatted = Math.abs(value).toLocaleString("vi-VN", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })

  return value < 0
    ? { text: `−${formatted}`, tone: "negative" }
    : { text: formatted, tone: "normal" }
}

/** A row nobody has published a single figure for. */
const isEmptyRow = (row: ApiRow, periods: string[]) =>
  periods.every((p) => row.values[p] === null || row.values[p] === undefined)

function Pill({
  label,
  isActive,
  onClick,
}: {
  label: string
  isActive: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={isActive}
      className={cn(
        "rounded-full text-[13px] leading-[1.29] tracking-[-0.208px]",
        "transition-transform duration-150 active:scale-95",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        isActive
          ? "border-2 border-interactive-strong px-[13px] py-1.5 font-semibold"
          : "border border-border px-3.5 py-[7px] text-muted-foreground hover:text-foreground"
      )}
    >
      {label}
    </button>
  )
}

function FinancialTable({ data, periods }: { data: ApiRow[]; periods: string[] }) {
  const columns = `minmax(240px,1.6fr) repeat(${periods.length},minmax(104px,1fr))`

  return (
    <div className="mt-1.5 overflow-x-auto">
      <div
        style={{ gridTemplateColumns: columns }}
        className="grid min-w-[680px] items-center gap-3.5 py-3 text-[13px] font-semibold leading-[1.29] tracking-[-0.208px] text-muted-foreground"
      >
        <span>Chỉ tiêu</span>
        {periods.map((period) => (
          <span key={period} className="text-right">
            {period}
          </span>
        ))}
      </div>

      {data.map((row, index) => {
        const rowAny = row as unknown as Record<string, unknown>
        const isStrong = Boolean(rowAny.is_header ?? rowAny.is_summary ?? false)

        return (
          <div
            key={row.id}
            style={{ gridTemplateColumns: columns }}
            className={cn(
              "grid min-w-[680px] items-center gap-3.5 border-t border-hairline py-[11px]",
              index % 2 === 1 && "bg-surface-sunken"
            )}
          >
            <span
              style={{ paddingLeft: row.level ? `${row.level * 16}px` : undefined }}
              className={cn(
                "text-[15px] leading-[1.47] tracking-[-0.374px]",
                isStrong && "font-semibold"
              )}
            >
              {row.label}
            </span>
            {periods.map((period) => {
              const { text, tone } = formatFinancialValue(row.values[period])
              return (
                <span
                  key={period}
                  className={cn(
                    "text-right text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums",
                    isStrong && "font-semibold",
                    tone === "negative" && "text-negative",
                    (tone === "empty" || tone === "zero") && "text-muted-foreground"
                  )}
                >
                  {text}
                </span>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}

export function FinanceTabContent({ symbol, className }: FinanceTabContentProps) {
  const [activeSubTab, setActiveSubTab] = useState<FinanceSubTab>("income")
  const [periodType, setPeriodType] = useState<PeriodType>("quarter")
  const [hideEmpty, setHideEmpty] = useState(true)

  const { data: incomeData, isFetching: incomeFetching } = useIncomeStatement(symbol, periodType, 4)
  const { data: balanceData, isFetching: balanceFetching } = useBalanceSheet(symbol, periodType, 4)
  const { data: cashFlowApiData, isFetching: cashFlowFetching } = useCashFlow(symbol, periodType, 4)

  // Whatever the API returned for the active sub-tab — no substitutes.
  // This used to fall back to hardcoded sample figures when the API came back
  // empty, which rendered invented numbers indistinguishable from real ones.
  const getTableData = () => {
    switch (activeSubTab) {
      case "balance":
        return { response: balanceData, isFetching: balanceFetching }
      case "cashflow":
        return { response: cashFlowApiData, isFetching: cashFlowFetching }
      case "income":
      default:
        return { response: incomeData, isFetching: incomeFetching }
    }
  }

  const { response, isFetching } = getTableData()
  const allRows: ApiRow[] = response?.rows ?? []
  const periods = response?.periods ?? []
  const rows = hideEmpty ? allRows.filter((row) => !isEmptyRow(row, periods)) : allRows
  const hiddenCount = allRows.length - rows.length
  const hasData = rows.length > 0 && periods.length > 0

  return (
    <div className={cn("min-w-0 rounded-card border border-border bg-card p-[14px]", className)}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap gap-2">
          {subTabs.map((tab) => (
            <Pill
              key={tab.value}
              label={tab.label}
              isActive={activeSubTab === tab.value}
              onClick={() => setActiveSubTab(tab.value)}
            />
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <span className="text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
            Đơn vị: {response?.unit ?? "—"}
          </span>
          <div className="flex gap-1.5">
            <Pill
              label="Quý"
              isActive={periodType === "quarter"}
              onClick={() => setPeriodType("quarter")}
            />
            <Pill
              label="Năm"
              isActive={periodType === "year"}
              onClick={() => setPeriodType("year")}
            />
          </div>
        </div>
      </div>

      <div className="mt-3.5 flex flex-wrap items-center justify-between gap-4 border-t border-hairline pt-3.5">
        <label className="flex cursor-pointer select-none items-center gap-2 text-[13px] leading-[1.43] tracking-[-0.208px]">
          <input
            type="checkbox"
            checked={hideEmpty}
            onChange={(event) => setHideEmpty(event.target.checked)}
            className="size-[15px] cursor-pointer accent-[hsl(var(--interactive))]"
          />
          Ẩn dòng chưa công bố
        </label>
        <span className="text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
          {hiddenCount > 0
            ? `${hiddenCount} dòng chưa công bố đang được ẩn`
            : `Hiển thị tất cả ${allRows.length} dòng`}
        </span>
      </div>

      {isFetching ? (
        <div className="mt-3 space-y-3">
          {[...Array(10)].map((_, i) => (
            <div key={i} className="h-4 animate-pulse rounded bg-muted" />
          ))}
        </div>
      ) : hasData ? (
        <>
          <FinancialTable data={rows} periods={periods} />
          <div className="mt-3.5 flex flex-wrap gap-4 border-t border-hairline pt-3.5 text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
            <span>— chưa công bố</span>
            <span>0,0 giá trị bằng không thực tế</span>
            <span>Số âm hiển thị dấu trừ thay vì ngoặc đơn</span>
          </div>
        </>
      ) : (
        <div className="py-8 text-center">
          <p className="text-[15px] leading-[1.47] tracking-[-0.374px]">
            Chưa có dữ liệu báo cáo tài chính cho {symbol}
          </p>
          <p className="mt-1 text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
            Nguồn dữ liệu không trả về kỳ báo cáo nào cho lựa chọn hiện tại.
          </p>
        </div>
      )}
    </div>
  )
}

// Skeleton for loading state
export function FinanceTabContentSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "h-[520px] min-w-0 animate-pulse rounded-card border border-border bg-card",
        className
      )}
    />
  )
}
