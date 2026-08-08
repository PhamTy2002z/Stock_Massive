"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
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

// Income Statement data structure
interface FinancialRow {
  id: string
  label: string
  values: Record<string, number | null>
  level?: number // Indentation level (0 = root, 1 = child, etc.)
  isHeader?: boolean // Bold section headers
  isSummary?: boolean // Bold summary rows
}


// Format number with Vietnamese locale
function formatFinancialValue(value: number | null): string {
  if (value === null || value === undefined) return "-"

  // Handle negative numbers with parentheses
  const isNegative = value < 0
  const absValue = Math.abs(value)

  // Format with dots as thousand separators and comma for decimal
  const formatted = absValue.toLocaleString("de-DE", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })

  return isNegative ? `(${formatted})` : formatted
}

// Financial Data Table Component - supports legacy FinancialRow and API response rows
function FinancialTable({
  data,
  periods,
}: {
  data: (FinancialRow | IncomeStatementRow | BalanceSheetRow | CashFlowRow)[]
  periods: string[]
}) {
  return (
    <div className="w-full overflow-x-auto scrollbar-thin">
      <table className="w-full min-w-[600px] border-collapse">
        <thead>
          <tr className="border-b border-border/50">
            <th className="sticky left-0 z-10 bg-background py-3 px-4 text-left text-sm font-medium text-muted-foreground min-w-[280px]">
              Chỉ tiêu
            </th>
            {periods.map((period) => (
              <th
                key={period}
                className="py-3 px-3 text-right text-sm font-medium text-muted-foreground whitespace-nowrap min-w-[110px]"
              >
                {period}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => {
            // Handle both legacy format (isHeader/isSummary) and API format (is_header/is_summary)
            const rowAny = row as unknown as Record<string, unknown>
            const isHeader = rowAny.isHeader ?? rowAny.is_header ?? false
            const isSummary = rowAny.isSummary ?? rowAny.is_summary ?? false
            const level = (row.level as number) || 0

            return (
              <tr
                key={row.id}
                className={cn(
                  "border-b border-border/30 transition-colors hover:bg-muted/30",
                  isHeader && "bg-muted/20"
                )}
              >
                <td
                  className={cn(
                    "sticky left-0 z-10 bg-background py-2.5 px-4 text-sm",
                    isSummary || isHeader
                      ? "font-semibold text-foreground"
                      : "text-foreground/90",
                    isHeader && "bg-muted/20 uppercase text-xs tracking-wide"
                  )}
                  style={{
                    paddingLeft: level ? `${16 + level * 16}px` : "16px",
                  }}
                >
                  {row.label}
                </td>
                {periods.map((period) => (
                  <td
                    key={period}
                    className={cn(
                      "py-2.5 px-3 text-right text-sm tabular-nums whitespace-nowrap",
                      isSummary || isHeader
                        ? "font-semibold text-foreground"
                        : "text-foreground/90"
                    )}
                  >
                    {formatFinancialValue(row.values[period])}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function FinanceTabContent({ symbol, className }: FinanceTabContentProps) {
  const [activeSubTab, setActiveSubTab] = useState<FinanceSubTab>("income")
  const [periodType, setPeriodType] = useState<PeriodType>("quarter")

  // Fetch income statement data from API
  const { data: incomeData, isFetching: incomeFetching } = useIncomeStatement(symbol, periodType, 4)

  // Fetch balance sheet data from API
  const { data: balanceData, isFetching: balanceFetching } = useBalanceSheet(symbol, periodType, 4)

  // Fetch cash flow data from API
  const { data: cashFlowApiData, isFetching: cashFlowFetching } = useCashFlow(symbol, periodType, 4)

  // Whatever the API returned for the active sub-tab — no substitutes.
  // This used to fall back to hardcoded sample figures when the API came back
  // empty, which rendered invented numbers indistinguishable from real ones.
  const getTableData = () => {
    switch (activeSubTab) {
      case "balance":
        return { data: balanceData?.rows ?? [], periods: balanceData?.periods ?? [], isFetching: balanceFetching }
      case "cashflow":
        return { data: cashFlowApiData?.rows ?? [], periods: cashFlowApiData?.periods ?? [], isFetching: cashFlowFetching }
      case "income":
      default:
        return { data: incomeData?.rows ?? [], periods: incomeData?.periods ?? [], isFetching: incomeFetching }
    }
  }

  const { data, periods, isFetching } = getTableData()
  const hasData = data.length > 0 && periods.length > 0

  return (
    <div className={cn("space-y-4", className)}>
      {/* Sub-tabs and Controls Row */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        {/* Sub-tabs */}
        <div className="flex items-center gap-1 p-1 rounded-lg bg-muted/50 border border-border/50">
          {subTabs.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setActiveSubTab(tab.value)}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded-md transition-all duration-200",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                activeSubTab === tab.value
                  ? "bg-background text-foreground shadow-sm border border-border/80"
                  : "text-muted-foreground hover:text-foreground hover:bg-background/50"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Right side controls */}
        <div className="flex items-center gap-3">
          {/* Unit indicator */}
          <span className="text-xs text-muted-foreground">
            ĐVT: Triệu đồng
          </span>

          {/* Period selector */}
          <Select
            value={periodType}
            onValueChange={(value: PeriodType) => setPeriodType(value)}
          >
            <SelectTrigger className="w-[100px] h-8 text-sm bg-muted/50 border-border/50">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="quarter">Quý</SelectItem>
              <SelectItem value="year">Năm</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Financial Table */}
      <div className="rounded-lg border border-border/50 bg-card/50 overflow-hidden">
        {isFetching ? (
          <div className="p-4 space-y-3">
            {[...Array(10)].map((_, i) => (
              <div key={i} className="flex gap-4">
                <div className="h-4 w-48 rounded bg-muted animate-pulse" />
                <div className="h-4 w-20 rounded bg-muted animate-pulse ml-auto" />
                <div className="h-4 w-20 rounded bg-muted animate-pulse" />
                <div className="h-4 w-20 rounded bg-muted animate-pulse" />
                <div className="h-4 w-20 rounded bg-muted animate-pulse" />
              </div>
            ))}
          </div>
        ) : hasData ? (
          <FinancialTable data={data} periods={periods} />
        ) : (
          <div className="p-8 text-center">
            <p className="text-sm font-medium text-foreground">
              Chưa có dữ liệu báo cáo tài chính cho {symbol}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Nguồn dữ liệu không trả về kỳ báo cáo nào cho lựa chọn hiện tại.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

// Skeleton for loading state
export function FinanceTabContentSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-4", className)}>
      {/* Sub-tabs skeleton */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-1 p-1 rounded-lg bg-muted/50 border border-border/50">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-8 w-28 rounded-md bg-muted animate-pulse" />
          ))}
        </div>
        <div className="flex items-center gap-3">
          <div className="h-4 w-24 rounded bg-muted animate-pulse" />
          <div className="h-8 w-[100px] rounded bg-muted animate-pulse" />
        </div>
      </div>

      {/* Table skeleton */}
      <div className="rounded-lg border border-border/50 bg-card/50 p-4 space-y-3">
        {[...Array(10)].map((_, i) => (
          <div key={i} className="flex gap-4">
            <div className="h-4 w-48 rounded bg-muted animate-pulse" />
            <div className="h-4 w-20 rounded bg-muted animate-pulse ml-auto" />
            <div className="h-4 w-20 rounded bg-muted animate-pulse" />
            <div className="h-4 w-20 rounded bg-muted animate-pulse" />
            <div className="h-4 w-20 rounded bg-muted animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  )
}
