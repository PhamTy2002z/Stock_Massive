"use client"

import { useState } from "react"
import type { PeerMetrics } from "@/lib/api"
import { PremiumBadge } from "./premium-badge"
import { cn } from "@/lib/utils"
import { ArrowUpDown, ArrowUp, ArrowDown, Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useRouter } from "next/navigation"

interface PeerComparisonTableProps {
  peers: PeerMetrics[]
  targetSymbol: string
}

type SortKey = "symbol" | "pe" | "pb" | "roe" | "roa" | "market_cap"
type SortDir = "asc" | "desc"

export function PeerComparisonTable({
  peers,
  targetSymbol,
}: PeerComparisonTableProps) {
  const router = useRouter()
  const [sortKey, setSortKey] = useState<SortKey>("market_cap")
  const [sortDir, setSortDir] = useState<SortDir>("desc")

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc")
    } else {
      setSortKey(key)
      setSortDir("desc")
    }
  }

  const sortedPeers = [...peers].sort((a, b) => {
    if (sortKey === "symbol") {
      return sortDir === "asc"
        ? a.symbol.localeCompare(b.symbol)
        : b.symbol.localeCompare(a.symbol)
    }
    const aVal = a[sortKey] ?? 0
    const bVal = b[sortKey] ?? 0
    return sortDir === "asc" ? aVal - bVal : bVal - aVal
  })

  // Export to CSV per design-guidelines.md
  const handleExport = () => {
    const headers = ["Mã CP", "Tên công ty", "P/E", "P/B", "ROE (%)", "ROA (%)", "vs Sector (%)"]
    const rows = sortedPeers.map((p) => [
      p.symbol,
      p.company_name ?? "",
      p.pe?.toFixed(2) ?? "",
      p.pb?.toFixed(2) ?? "",
      p.roe?.toFixed(2) ?? "",
      p.roa?.toFixed(2) ?? "",
      p.premium_pe?.toFixed(1) ?? "",
    ])
    const csv = [headers, ...rows].map((r) => r.join(",")).join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `sector-peers-${targetSymbol}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const SortIcon = ({ column }: { column: SortKey }) => {
    if (sortKey !== column) return <ArrowUpDown className="h-3 w-3 opacity-50" />
    return sortDir === "asc" ? (
      <ArrowUp className="h-3 w-3" />
    ) : (
      <ArrowDown className="h-3 w-3" />
    )
  }

  const SortableHeader = ({
    column,
    children,
    align = "right",
  }: {
    column: SortKey
    children: React.ReactNode
    align?: "left" | "right"
  }) => (
    <th
      className={cn(
        "px-3 py-2 font-medium cursor-pointer hover:bg-muted/80 transition-colors",
        align === "right" ? "text-right" : "text-left"
      )}
      onClick={() => handleSort(column)}
    >
      <span className={cn(
        "flex items-center gap-1",
        align === "right" && "justify-end"
      )}>
        {children}
        <SortIcon column={column} />
      </span>
    </th>
  )

  const handleRowClick = (symbol: string) => {
    router.push(`/stocks/${symbol}`)
  }

  return (
    <div className="space-y-2">
      {/* Export button */}
      <div className="flex justify-end">
        <Button
          variant="outline"
          size="sm"
          onClick={handleExport}
          className="h-8 gap-1.5"
        >
          <Download className="h-3.5 w-3.5" />
          <span className="text-xs">Xuất CSV</span>
        </Button>
      </div>

      {/* Table with horizontal scroll for mobile */}
      <div className="overflow-x-auto rounded-lg border border-border/50">
        <table className="w-full text-sm">
          {/* Sticky header */}
          <thead className="bg-muted/50 sticky top-0">
            <tr>
              {/* Frozen first column */}
              <th className="sticky left-0 z-10 bg-muted/50 px-3 py-2 text-left font-medium min-w-[140px]">
                Mã CP
              </th>
              <SortableHeader column="pe">P/E</SortableHeader>
              <SortableHeader column="pb">P/B</SortableHeader>
              <SortableHeader column="roe">ROE</SortableHeader>
              <SortableHeader column="roa">ROA</SortableHeader>
              <th className="px-3 py-2 text-right font-medium">vs Sector</th>
            </tr>
          </thead>
          <tbody>
            {sortedPeers.map((peer) => (
              <tr
                key={peer.symbol}
                className={cn(
                  "border-t border-border/30 hover:bg-muted/30 transition-colors cursor-pointer",
                  peer.symbol === targetSymbol && "bg-primary/5 font-semibold"
                )}
                onClick={() => handleRowClick(peer.symbol)}
              >
                {/* Frozen first column with sticky positioning */}
                <td className={cn(
                  "sticky left-0 z-10 px-3 py-2 min-w-[140px]",
                  peer.symbol === targetSymbol ? "bg-primary/5" : "bg-background"
                )}>
                  <div>
                    <span className={cn(
                      "font-medium",
                      peer.symbol === targetSymbol && "text-primary"
                    )}>
                      {peer.symbol}
                    </span>
                    {peer.company_name && (
                      <p className="text-xs text-muted-foreground truncate max-w-[120px]">
                        {peer.company_name}
                      </p>
                    )}
                  </div>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {peer.pe?.toFixed(2) ?? "-"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {peer.pb?.toFixed(2) ?? "-"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {peer.roe?.toFixed(2) ?? "-"}%
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {peer.roa?.toFixed(2) ?? "-"}%
                </td>
                <td className="px-3 py-2 text-right">
                  <PremiumBadge value={peer.premium_pe} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
