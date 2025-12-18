"use client"

import { useState, useMemo } from "react"
import { cn } from "@/lib/utils"
import { ChevronLeft, ChevronRight } from "lucide-react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

// Shareholder data type
interface Shareholder {
  id: string
  name: string
  shares: number // In millions
  ownershipPct: number
  updateDate: string // YYYY-MM-DD
}

interface ShareholdersTabContentProps {
  symbol?: string
  className?: string
}

// Mock shareholders data
const mockShareholders: Shareholder[] = [
  { id: "1", name: "Đoàn Nguyên Đức", shares: 304.95, ownershipPct: 28.84, updateDate: "2025-10-05" },
  { id: "2", name: "Đoàn Hoàng Nam", shares: 52.00, ownershipPct: 4.92, updateDate: "2025-10-05" },
  { id: "3", name: "Công ty Cổ phần Tư vấn Đầu tư Hướng Việt", shares: 60.06, ownershipPct: 4.74, updateDate: "2025-10-05" },
  { id: "4", name: "Công ty Cổ phần Chứng khoán LPBank", shares: 50.00, ownershipPct: 4.73, updateDate: "2025-10-05" },
  { id: "5", name: "Ngân hàng Deutsche Aktiengesellschaft", shares: 27.53, ownershipPct: 3.49, updateDate: "2015-06-15" },
  { id: "6", name: "Lê Minh Tâm", shares: 28.00, ownershipPct: 2.65, updateDate: "2025-10-05" },
  { id: "7", name: "Vietnam Century Fund", shares: 15.56, ownershipPct: 1.97, updateDate: "2015-06-15" },
  { id: "8", name: "Đoàn Hoàng Anh", shares: 13.00, ownershipPct: 1.23, updateDate: "2025-10-05" },
  { id: "9", name: "Công ty Cổ phần Chứng khoán OCBS", shares: 15.40, ownershipPct: 1.22, updateDate: "2025-10-05" },
  { id: "10", name: "Jaccar Capital Fund", shares: 8.69, ownershipPct: 1.10, updateDate: "2025-03-10" },
  { id: "11", name: "Nguyen Van A", shares: 7.50, ownershipPct: 0.95, updateDate: "2025-10-05" },
  { id: "12", name: "Tran Thi B", shares: 6.80, ownershipPct: 0.86, updateDate: "2025-10-05" },
  { id: "13", name: "Dragon Capital", shares: 6.20, ownershipPct: 0.78, updateDate: "2025-09-20" },
  { id: "14", name: "Pyn Elite Fund", shares: 5.90, ownershipPct: 0.74, updateDate: "2025-08-15" },
  { id: "15", name: "Vietnam Holding Ltd", shares: 5.50, ownershipPct: 0.69, updateDate: "2025-07-10" },
  { id: "16", name: "Mekong Enterprise Fund", shares: 5.20, ownershipPct: 0.66, updateDate: "2025-06-25" },
  { id: "17", name: "VinaCapital Vietnam Opportunity Fund", shares: 4.80, ownershipPct: 0.61, updateDate: "2025-05-18" },
  { id: "18", name: "Templeton Frontier Markets Fund", shares: 4.50, ownershipPct: 0.57, updateDate: "2025-04-22" },
  { id: "19", name: "KITMC Việt Nam Growth Fund", shares: 4.20, ownershipPct: 0.53, updateDate: "2025-03-30" },
  { id: "20", name: "Indochina Capital Vietnam Holdings", shares: 3.90, ownershipPct: 0.49, updateDate: "2025-02-14" },
  { id: "21", name: "Amundi Funds Asia Equity", shares: 3.60, ownershipPct: 0.45, updateDate: "2025-01-28" },
  { id: "22", name: "SSI Securities Corporation", shares: 3.30, ownershipPct: 0.42, updateDate: "2024-12-15" },
  { id: "23", name: "VNDirect Securities", shares: 3.10, ownershipPct: 0.39, updateDate: "2024-11-20" },
  { id: "24", name: "Ho Chi Minh City Securities", shares: 2.90, ownershipPct: 0.37, updateDate: "2024-10-25" },
  { id: "25", name: "Bao Viet Securities", shares: 2.70, ownershipPct: 0.34, updateDate: "2024-09-18" },
  { id: "26", name: "MB Securities", shares: 2.50, ownershipPct: 0.32, updateDate: "2024-08-22" },
  { id: "27", name: "Vietcombank Securities", shares: 2.30, ownershipPct: 0.29, updateDate: "2024-07-15" },
  { id: "28", name: "Techcombank Securities", shares: 2.10, ownershipPct: 0.27, updateDate: "2024-06-10" },
  { id: "29", name: "BIDV Securities", shares: 1.90, ownershipPct: 0.24, updateDate: "2024-05-05" },
  { id: "30", name: "Agribank Securities", shares: 1.70, ownershipPct: 0.21, updateDate: "2024-04-18" },
  { id: "31", name: "Sacombank Securities", shares: 1.50, ownershipPct: 0.19, updateDate: "2024-03-22" },
  { id: "32", name: "VPBank Securities", shares: 1.30, ownershipPct: 0.16, updateDate: "2024-02-28" },
  { id: "33", name: "ACB Securities", shares: 1.20, ownershipPct: 0.15, updateDate: "2024-01-15" },
  { id: "34", name: "Eximbank Securities", shares: 1.10, ownershipPct: 0.14, updateDate: "2023-12-20" },
  { id: "35", name: "HDBank Securities", shares: 1.00, ownershipPct: 0.13, updateDate: "2023-11-25" },
  { id: "36", name: "OCB Securities", shares: 0.95, ownershipPct: 0.12, updateDate: "2023-10-18" },
  { id: "37", name: "TPBank Securities", shares: 0.90, ownershipPct: 0.11, updateDate: "2023-09-22" },
  { id: "38", name: "LienVietPostBank Securities", shares: 0.85, ownershipPct: 0.11, updateDate: "2023-08-15" },
  { id: "39", name: "SeABank Securities", shares: 0.80, ownershipPct: 0.10, updateDate: "2023-07-10" },
  { id: "40", name: "NCB Securities", shares: 0.75, ownershipPct: 0.09, updateDate: "2023-06-05" },
  { id: "41", name: "VietABank Securities", shares: 0.70, ownershipPct: 0.09, updateDate: "2023-05-18" },
  { id: "42", name: "BacABank Securities", shares: 0.65, ownershipPct: 0.08, updateDate: "2023-04-22" },
  { id: "43", name: "VietCapitalBank Securities", shares: 0.60, ownershipPct: 0.08, updateDate: "2023-03-15" },
  { id: "44", name: "Kienlongbank Securities", shares: 0.55, ownershipPct: 0.07, updateDate: "2023-02-28" },
  { id: "45", name: "PGBank Securities", shares: 0.50, ownershipPct: 0.06, updateDate: "2023-01-20" },
]

// Format shares with "triệu" unit
function formatShares(value: number): string {
  return `${value.toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} triệu`
}

// Format percentage
function formatPercent(value: number): string {
  return `${value.toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`
}

export function ShareholdersTabContent({
  symbol = "HAG",
  className,
}: ShareholdersTabContentProps) {
  const [currentPage, setCurrentPage] = useState(1)
  const [rowsPerPage, setRowsPerPage] = useState(10)

  // Calculate pagination
  const totalItems = mockShareholders.length
  const totalPages = Math.ceil(totalItems / rowsPerPage)
  const startIndex = (currentPage - 1) * rowsPerPage
  const endIndex = Math.min(startIndex + rowsPerPage, totalItems)

  // Get current page data
  const currentData = useMemo(() => {
    return mockShareholders.slice(startIndex, endIndex)
  }, [startIndex, endIndex])

  // Handle page change
  const goToPage = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page)
    }
  }

  // Handle rows per page change
  const handleRowsPerPageChange = (value: string) => {
    setRowsPerPage(Number(value))
    setCurrentPage(1) // Reset to first page
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Title */}
      <h3 className="text-sm text-muted-foreground">
        Danh sách cổ đông lớn của {symbol}
      </h3>

      {/* Table */}
      <div className="rounded-lg border border-border/50 bg-card/50 overflow-hidden">
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full min-w-[600px] border-collapse">
            <thead>
              <tr className="border-b border-border/50 bg-muted/30">
                <th className="py-3 px-4 text-left text-sm font-medium text-muted-foreground">
                  Cổ đông
                </th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">
                  Số lượng
                </th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">
                  Tỷ lệ sở hữu
                </th>
                <th className="py-3 px-4 text-right text-sm font-medium text-muted-foreground whitespace-nowrap">
                  Ngày cập nhật
                </th>
              </tr>
            </thead>
            <tbody>
              {currentData.map((shareholder) => (
                <tr
                  key={shareholder.id}
                  className="border-b border-border/30 transition-colors hover:bg-muted/20"
                >
                  <td className="py-3 px-4 text-sm font-medium text-foreground">
                    {shareholder.name}
                  </td>
                  <td className="py-3 px-4 text-sm text-right tabular-nums text-foreground/90">
                    {formatShares(shareholder.shares)}
                  </td>
                  <td className="py-3 px-4 text-sm text-right tabular-nums text-foreground/90">
                    {formatPercent(shareholder.ownershipPct)}
                  </td>
                  <td className="py-3 px-4 text-sm text-right tabular-nums text-muted-foreground">
                    {shareholder.updateDate}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-border/50 bg-muted/20">
          {/* Items info */}
          <span className="text-sm text-muted-foreground">
            {startIndex + 1}-{endIndex} trên {totalItems} cổ đông
          </span>

          {/* Right side controls */}
          <div className="flex items-center gap-4">
            {/* Rows per page */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground whitespace-nowrap">
                Hàng mỗi trang
              </span>
              <Select
                value={String(rowsPerPage)}
                onValueChange={handleRowsPerPageChange}
              >
                <SelectTrigger className="w-[70px] h-8 text-sm bg-background border-border/50">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10</SelectItem>
                  <SelectItem value="20">20</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Page navigation */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => goToPage(currentPage - 1)}
                disabled={currentPage === 1}
                className={cn(
                  "p-1.5 rounded-md transition-colors",
                  "hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                )}
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>

              <span className="text-sm text-muted-foreground whitespace-nowrap min-w-[80px] text-center">
                Trang {currentPage}/{totalPages}
              </span>

              <button
                onClick={() => goToPage(currentPage + 1)}
                disabled={currentPage === totalPages}
                className={cn(
                  "p-1.5 rounded-md transition-colors",
                  "hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
                )}
                aria-label="Next page"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Skeleton for loading state
export function ShareholdersTabContentSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-4", className)}>
      {/* Title skeleton */}
      <div className="h-5 w-64 rounded bg-muted animate-pulse" />

      {/* Table skeleton */}
      <div className="rounded-lg border border-border/50 bg-card/50 p-4 space-y-3">
        {/* Header */}
        <div className="flex gap-4 pb-2 border-b border-border/30">
          <div className="h-4 w-32 rounded bg-muted animate-pulse" />
          <div className="h-4 w-20 rounded bg-muted animate-pulse ml-auto" />
          <div className="h-4 w-24 rounded bg-muted animate-pulse" />
          <div className="h-4 w-24 rounded bg-muted animate-pulse" />
        </div>
        {/* Rows */}
        {[...Array(10)].map((_, i) => (
          <div key={i} className="flex gap-4">
            <div className="h-4 w-48 rounded bg-muted animate-pulse" />
            <div className="h-4 w-20 rounded bg-muted animate-pulse ml-auto" />
            <div className="h-4 w-16 rounded bg-muted animate-pulse" />
            <div className="h-4 w-24 rounded bg-muted animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  )
}
