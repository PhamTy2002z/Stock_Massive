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

// Mock data for quarters - will be replaced by backend
const mockQuarters = ["Q3/2025", "Q2/2025", "Q1/2025", "Q4/2024"]

// Income Statement data structure
interface FinancialRow {
  id: string
  label: string
  values: Record<string, number | null>
  level?: number // Indentation level (0 = root, 1 = child, etc.)
  isHeader?: boolean // Bold section headers
  isSummary?: boolean // Bold summary rows
}

// Mock Income Statement Data
const incomeStatementData: FinancialRow[] = [
  { id: "revenue", label: "Doanh thu bán hàng và cung cấp dịch vụ", values: { "Q3/2025": 1905644.2, "Q2/2025": 2332804.4, "Q1/2025": 1390061.9, "Q4/2024": 1634682.0 }, isSummary: true },
  { id: "deductions", label: "Các khoản giảm trừ doanh thu", values: { "Q3/2025": -10239.7, "Q2/2025": -5384, "Q1/2025": -10305.8, "Q4/2024": -45354 }, level: 1 },
  { id: "net_revenue", label: "Doanh thu thuần", values: { "Q3/2025": 1895404.6, "Q2/2025": 2327420.4, "Q1/2025": 1379756.1, "Q4/2024": 1589328.0 }, isSummary: true },
  { id: "cogs", label: "Giá vốn hàng bán", values: { "Q3/2025": -1133050.8, "Q2/2025": -1440618.8, "Q1/2025": -815296.8, "Q4/2024": -1007423.4 }, level: 1 },
  { id: "gross_profit", label: "Lãi gộp", values: { "Q3/2025": 762353.8, "Q2/2025": 886801.6, "Q1/2025": 564459.3, "Q4/2024": 581904.0 }, isSummary: true },
  { id: "selling_exp", label: "Chi phí bán hàng", values: { "Q3/2025": -107687.9, "Q2/2025": -107938.7, "Q1/2025": -110050.1, "Q4/2024": -124742 }, level: 1 },
  { id: "admin_exp", label: "Chi phí quản lý doanh nghiệp", values: { "Q3/2025": -35818, "Q2/2025": -42909.6, "Q1/2025": -36486.6, "Q4/2024": -44460.7 }, level: 1 },
  { id: "finance_income", label: "Thu nhập tài chính", values: { "Q3/2025": 78926.6, "Q2/2025": 77591, "Q1/2025": 58093.4, "Q4/2024": 67106.0 }, level: 1 },
  { id: "finance_exp", label: "Chi phí tài chính", values: { "Q3/2025": -198536.7, "Q2/2025": -286378.8, "Q1/2025": -108753.7, "Q4/2024": -182663.8 }, level: 1 },
  { id: "interest_exp", label: "Chi phí tiền lãi vay", values: { "Q3/2025": -203624.7, "Q2/2025": -217296.1, "Q1/2025": -142662.4, "Q4/2024": -244734.7 }, level: 2 },
  { id: "operating_profit", label: "Lãi/Lỗ từ hoạt động kinh doanh", values: { "Q3/2025": 499237.7, "Q2/2025": 527165.5, "Q1/2025": 367262.4, "Q4/2024": 297144.0 }, isSummary: true },
  { id: "other_income", label: "Thu nhập khác", values: { "Q3/2025": 124.9, "Q2/2025": 11810.2, "Q1/2025": 5903.6, "Q4/2024": 6553.0 }, level: 1 },
  { id: "other_exp", label: "Thu nhập/Chi phí khác", values: { "Q3/2025": -67285.2, "Q2/2025": -38521.2, "Q1/2025": -14660.9, "Q4/2024": -117471.2 }, level: 1 },
  { id: "other_profit", label: "Lợi nhuận khác", values: { "Q3/2025": -67160.3, "Q2/2025": -26711, "Q1/2025": -8757.3, "Q4/2024": -110918 }, level: 1 },
  { id: "ebt", label: "Lợi nhuận trước thuế", values: { "Q3/2025": 432077.4, "Q2/2025": 500454.5, "Q1/2025": 358505.1, "Q4/2024": 186226.0 }, isSummary: true },
  { id: "tax", label: "Chi phí thuế TNDN", values: { "Q3/2025": 0, "Q2/2025": 18848.6, "Q1/2025": 1907, "Q4/2024": 22793.0 }, level: 1 },
  { id: "net_profit", label: "Lợi nhuận thuần", values: { "Q3/2025": 432077.4, "Q2/2025": 519303.1, "Q1/2025": 360412.1, "Q4/2024": 209020 }, isSummary: true },
  { id: "parent_profit", label: "Cổ đông của Công ty mẹ", values: { "Q3/2025": 415963.6, "Q2/2025": 492902.8, "Q1/2025": 340703.7, "Q4/2024": 204285.0 }, level: 1 },
  { id: "minority_profit", label: "Cổ đông thiểu số", values: { "Q3/2025": 16113.9, "Q2/2025": 26400.3, "Q1/2025": 19708.4, "Q4/2024": 4734.0 }, level: 1 },
]

// Mock Balance Sheet Data
const balanceSheetData: FinancialRow[] = [
  { id: "current_assets", label: "TÀI SẢN NGẮN HẠN", values: { "Q3/2025": 8867543.9, "Q2/2025": 8707882.4, "Q1/2025": 8530647.8, "Q4/2024": 8435357.7 }, isHeader: true, isSummary: true },
  { id: "cash", label: "Tiền và tương đương tiền", values: { "Q3/2025": 113974.5, "Q2/2025": 136029.1, "Q1/2025": 39930.3, "Q4/2024": 149708.8 }, level: 1 },
  { id: "short_invest", label: "Giá trị thuần đầu tư ngắn hạn", values: { "Q3/2025": 0, "Q2/2025": 0, "Q1/2025": 0, "Q4/2024": 0 }, level: 1 },
  { id: "receivables", label: "Các khoản phải thu ngắn hạn", values: { "Q3/2025": 7813719.6, "Q2/2025": 7771905.9, "Q1/2025": 7657080.9, "Q4/2024": 7536948.4 }, level: 1 },
  { id: "inventory", label: "Hàng tồn kho ròng", values: { "Q3/2025": 892004, "Q2/2025": 767521.2, "Q1/2025": 803936.8, "Q4/2024": 694457.7 }, level: 1 },
  { id: "other_current", label: "Tài sản lưu động khác", values: { "Q3/2025": 47845.9, "Q2/2025": 32426.2, "Q1/2025": 29699.7, "Q4/2024": 54242.7 }, level: 1 },
  { id: "long_assets", label: "TÀI SẢN DÀI HẠN", values: { "Q3/2025": 13624560.4, "Q2/2025": 12462570.6, "Q1/2025": 12639145.9, "Q4/2024": 13845458.2 }, isHeader: true, isSummary: true },
  { id: "long_receivables", label: "Phải thu về cho vay dài hạn", values: { "Q3/2025": 697004, "Q2/2025": 274178.9, "Q1/2025": 606032.2, "Q4/2024": 46813.2 }, level: 1 },
  { id: "fixed_assets", label: "Tài sản cố định", values: { "Q3/2025": 6030316.5, "Q2/2025": 5602001.9, "Q1/2025": 5903291.2, "Q4/2024": 6567006.9 }, level: 1 },
  { id: "invest_assets", label: "Giá trị ròng tài sản đầu tư", values: { "Q3/2025": 34769.1, "Q2/2025": 35242, "Q1/2025": 35714.9, "Q4/2024": 34296.3 }, level: 1 },
  { id: "long_invest", label: "Đầu tư dài hạn", values: { "Q3/2025": 443168.3, "Q2/2025": 443168.3, "Q1/2025": 429462.5, "Q4/2024": 557387 }, level: 1 },
  { id: "goodwill", label: "Lợi thế thương mại", values: { "Q3/2025": 0, "Q2/2025": 0, "Q1/2025": 0, "Q4/2024": 0 }, level: 1 },
  { id: "other_long", label: "Tài sản dài hạn khác", values: { "Q3/2025": 360834.7, "Q2/2025": 230373.6, "Q1/2025": 265564.5, "Q4/2024": 370977.6 }, level: 1 },
  { id: "total_assets", label: "TỔNG CỘNG TÀI SẢN", values: { "Q3/2025": 22492104.3, "Q2/2025": 21170453, "Q1/2025": 21169793.7, "Q4/2024": 22280815.8 }, isHeader: true, isSummary: true },
  { id: "liabilities", label: "NỢ PHẢI TRẢ", values: { "Q3/2025": 13532271.1, "Q2/2025": 12750086.3, "Q1/2025": 14137319.6, "Q4/2024": 12955187.7 }, isHeader: true, isSummary: true },
  { id: "short_debt", label: "Nợ ngắn hạn", values: { "Q3/2025": 9530292.8, "Q2/2025": 9058255.5, "Q1/2025": 9656045.6, "Q4/2024": 11122837.7 }, level: 1 },
  { id: "long_debt", label: "Nợ dài hạn", values: { "Q3/2025": 4001978.3, "Q2/2025": 3691830.8, "Q1/2025": 4481274, "Q4/2024": 1832350.1 }, level: 1 },
  { id: "equity", label: "VỐN CHỦ SỞ HỮU", values: { "Q3/2025": 8959833.1, "Q2/2025": 8420366.7, "Q1/2025": 7032474.1, "Q4/2024": 9325628.1 }, isHeader: true, isSummary: true },
  { id: "capital_fund", label: "Vốn và các quỹ", values: { "Q3/2025": 8959833.1, "Q2/2025": 8420366.7, "Q1/2025": 7032474.1, "Q4/2024": 9325628.1 }, level: 1 },
  { id: "other_fund", label: "Các quỹ khác", values: { "Q3/2025": 0, "Q2/2025": 0, "Q1/2025": 0, "Q4/2024": 0 }, level: 1 },
  { id: "retained", label: "Lãi chưa phân phối", values: { "Q3/2025": -626177.6, "Q2/2025": -957008, "Q1/2025": -1452426.2, "Q4/2024": -422660.1 }, level: 1 },
  { id: "state_fund", label: "Vốn Ngân sách nhà nước và quỹ khác", values: { "Q3/2025": 0, "Q2/2025": 0, "Q1/2025": 0, "Q4/2024": 0 }, level: 1 },
  { id: "minority", label: "LỢI ÍCH CỦA CỔ ĐÔNG THIỂU SỐ", values: { "Q3/2025": 576647.4, "Q2/2025": 557338, "Q1/2025": 501041.1, "Q4/2024": 581381.9 }, isHeader: true, isSummary: true },
  { id: "total_capital", label: "TỔNG CỘNG NGUỒN VỐN", values: { "Q3/2025": 22492104.3, "Q2/2025": 21170453, "Q1/2025": 21169793.7, "Q4/2024": 22280815.8 }, isHeader: true, isSummary: true },
]

// Mock Cash Flow Data
const cashFlowData: FinancialRow[] = [
  { id: "ebt_cf", label: "Lãi/Lỗ ròng trước thuế", values: { "Q3/2025": 432077.4, "Q2/2025": 500454.5, "Q1/2025": 358505.0, "Q4/2024": null }, isSummary: true },
  { id: "depreciation", label: "Khấu hao TSCĐ", values: { "Q3/2025": 81801.9, "Q2/2025": 224282.8, "Q1/2025": 77088.7, "Q4/2024": null }, level: 1 },
  { id: "provision", label: "Dự phòng RR tín dụng", values: { "Q3/2025": -11585.5, "Q2/2025": 65469.2, "Q1/2025": -45685.5, "Q4/2024": null }, level: 1 },
  { id: "fx_diff", label: "Lãi/Lỗ chênh lệch tỷ giá chưa thực hiện", values: { "Q3/2025": -3355.4, "Q2/2025": -5392.7, "Q1/2025": -5923.8, "Q4/2024": null }, level: 1 },
  { id: "invest_loss", label: "Lãi/Lỗ từ hoạt động đầu tư", values: { "Q3/2025": 16236.6, "Q2/2025": -56883.1, "Q1/2025": -34554.1, "Q4/2024": null }, level: 1 },
  { id: "interest_income", label: "Thu nhập lãi", values: { "Q3/2025": 203624.7, "Q2/2025": 217296.1, "Q1/2025": 142662.4, "Q4/2024": null }, level: 1 },
  { id: "cfo_before_wc", label: "Lưu chuyển tiền thuần từ HĐKD trước thay đổi VLĐ", values: { "Q3/2025": 718799.8, "Q2/2025": 945226.8, "Q1/2025": 492092.8, "Q4/2024": null }, isSummary: true },
  { id: "receivables_change", label: "Tăng/Giảm các khoản phải thu", values: { "Q3/2025": -197586.1, "Q2/2025": -303940.2, "Q1/2025": -532710.1, "Q4/2024": null }, level: 1 },
  { id: "inventory_change", label: "Tăng/Giảm hàng tồn kho", values: { "Q3/2025": -503010.8, "Q2/2025": -135150.2, "Q1/2025": -209961.2, "Q4/2024": null }, level: 1 },
  { id: "payables_change", label: "Tăng/Giảm các khoản phải trả", values: { "Q3/2025": 39146.9, "Q2/2025": -1381111.2, "Q1/2025": 207908.3, "Q4/2024": null }, level: 1 },
  { id: "prepaid_change", label: "Tăng/Giảm chi phí trả trước", values: { "Q3/2025": -6073.5, "Q2/2025": -117530.8, "Q1/2025": -42507.1, "Q4/2024": null }, level: 1 },
  { id: "interest_paid", label: "Chi phí lãi vay đã trả", values: { "Q3/2025": -102807.7, "Q2/2025": -98708.6, "Q1/2025": -101136.6, "Q4/2024": null }, level: 1 },
  { id: "tax_paid", label: "Tiền thu nhập doanh nghiệp đã trả", values: { "Q3/2025": 0, "Q2/2025": 0, "Q1/2025": -37.7, "Q4/2024": null }, level: 1 },
  { id: "other_cfo", label: "Tiền chi khác từ các hoạt động kinh doanh", values: { "Q3/2025": -768, "Q2/2025": -768, "Q1/2025": -768, "Q4/2024": null }, level: 1 },
  { id: "net_cfo", label: "Lưu chuyển tiền tệ ròng từ các hoạt động SXKD", values: { "Q3/2025": -52299.4, "Q2/2025": -1091982.2, "Q1/2025": -187119.5, "Q4/2024": null }, isSummary: true },
  { id: "capex", label: "Mua sắm TSCĐ", values: { "Q3/2025": -491768.7, "Q2/2025": -501385, "Q1/2025": -175290.2, "Q4/2024": null }, level: 1 },
  { id: "asset_sale", label: "Tiền thu được từ thanh lý tài sản cố định", values: { "Q3/2025": -17925.7, "Q2/2025": 33447, "Q1/2025": 3953, "Q4/2024": null }, level: 1 },
  { id: "loan_invest", label: "Tiền chi cho vay, mua công cụ nợ của đơn vị khác", values: { "Q3/2025": -54485.2, "Q2/2025": -469331.9, "Q1/2025": -18529.3, "Q4/2024": null }, level: 1 },
  { id: "loan_collect", label: "Tiền thu hồi cho vay, bán lại các công cụ nợ của đơn vị khác", values: { "Q3/2025": 140893.4, "Q2/2025": 284737.2, "Q1/2025": 2100, "Q4/2024": null }, level: 1 },
  { id: "invest_other", label: "Đầu tư vào các doanh nghiệp khác", values: { "Q3/2025": 0, "Q2/2025": -202500, "Q1/2025": -5000, "Q4/2024": null }, level: 1 },
  { id: "invest_sale", label: "Tiền thu từ việc bán các khoản đầu tư vào doanh nghiệp khác", values: { "Q3/2025": 0, "Q2/2025": 7500, "Q1/2025": 0, "Q4/2024": null }, level: 1 },
  { id: "dividend_received", label: "Tiền thu cổ tức và lợi nhuận được chia", values: { "Q3/2025": 17700.4, "Q2/2025": 13894.7, "Q1/2025": 20038.7, "Q4/2024": null }, level: 1 },
  { id: "net_cfi", label: "Lưu chuyển từ hoạt động đầu tư", values: { "Q3/2025": -405585.8, "Q2/2025": -833638, "Q1/2025": -172727.8, "Q4/2024": null }, isSummary: true },
  { id: "equity_issue", label: "Tăng vốn cổ phần từ góp vốn và/hoặc phát hành cổ phiếu", values: { "Q3/2025": 0, "Q2/2025": 0, "Q1/2025": 0, "Q4/2024": null }, level: 1 },
  { id: "equity_buyback", label: "Chi trả cho việc mua lại, trả cổ phiếu", values: { "Q3/2025": 0, "Q2/2025": 0, "Q1/2025": 0, "Q4/2024": null }, level: 1 },
  { id: "borrow_receive", label: "Tiền thu được các khoản đi vay", values: { "Q3/2025": 3477138, "Q2/2025": 4432509.2, "Q1/2025": 1979025.2, "Q4/2024": null }, level: 1 },
  { id: "borrow_repay", label: "Tiền trả các khoản đi vay", values: { "Q3/2025": -2367142, "Q2/2025": -2628818, "Q1/2025": -1453296.9, "Q4/2024": null }, level: 1 },
  { id: "dividend_paid", label: "Cổ tức đã trả", values: { "Q3/2025": 0, "Q2/2025": 0, "Q1/2025": 0, "Q4/2024": null }, level: 1 },
  { id: "net_cff", label: "Lưu chuyển tiền từ hoạt động tài chính", values: { "Q3/2025": 1109996.1, "Q2/2025": 1803691.2, "Q1/2025": 525728.3, "Q4/2024": null }, isSummary: true },
  { id: "net_change", label: "Lưu chuyển tiền thuần trong kỳ", values: { "Q3/2025": 652110.8, "Q2/2025": -121929.1, "Q1/2025": 165881.0, "Q4/2024": null }, isSummary: true },
  { id: "cash_begin", label: "Tiền và tương đương tiền", values: { "Q3/2025": 193660.8, "Q2/2025": 315589.9, "Q1/2025": 149708.8, "Q4/2024": null }, level: 1 },
  { id: "fx_effect", label: "Ảnh hưởng của chênh lệch tỷ giá", values: { "Q3/2025": 0, "Q2/2025": 0, "Q1/2025": 0, "Q4/2024": null }, level: 1 },
  { id: "cash_end", label: "Tiền và tương đương tiền cuối kỳ", values: { "Q3/2025": 845771.6, "Q2/2025": 193660.8, "Q1/2025": 315589.9, "Q4/2024": null }, isSummary: true },
]

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
  const {
    data: incomeData,
    isLoading: incomeLoading,
  } = useIncomeStatement(symbol, periodType, 4)

  // Fetch balance sheet data from API
  const {
    data: balanceData,
    isLoading: balanceLoading,
  } = useBalanceSheet(symbol, periodType, 4)

  // Fetch cash flow data from API
  const {
    data: cashFlowApiData,
    isLoading: cashFlowLoading,
  } = useCashFlow(symbol, periodType, 4)

  // Get the appropriate data and periods based on active sub-tab
  const getTableData = () => {
    switch (activeSubTab) {
      case "income":
        // Use API data if available, otherwise fall back to mock
        if (incomeData && incomeData.rows.length > 0) {
          return { data: incomeData.rows, periods: incomeData.periods, isLoading: incomeLoading }
        }
        return { data: incomeStatementData, periods: mockQuarters, isLoading: incomeLoading }
      case "balance":
        // Use API data if available, otherwise fall back to mock
        if (balanceData && balanceData.rows.length > 0) {
          return { data: balanceData.rows, periods: balanceData.periods, isLoading: balanceLoading }
        }
        return { data: balanceSheetData, periods: ["Q3/2025", "Q2/2025", "Q1/2025", "Q4/2024"], isLoading: balanceLoading }
      case "cashflow":
        // Use API data if available, otherwise fall back to mock
        if (cashFlowApiData && cashFlowApiData.rows.length > 0) {
          return { data: cashFlowApiData.rows, periods: cashFlowApiData.periods, isLoading: cashFlowLoading }
        }
        return { data: cashFlowData, periods: mockQuarters, isLoading: cashFlowLoading }
      default:
        return { data: incomeStatementData, periods: mockQuarters, isLoading: false }
    }
  }

  const { data, periods, isLoading } = getTableData()

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
        {isLoading ? (
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
        ) : (
          <FinancialTable data={data} periods={periods} />
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
