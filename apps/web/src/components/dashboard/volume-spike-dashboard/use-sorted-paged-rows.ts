"use client"

import { useMemo, useState } from "react"

export type SpikeSortField = "spike_ratio" | "current_volume" | "price_change_pct"

const PAGE_SIZE = 10

/**
 * Shared sort + paginate state for spike stock tables.
 * Defaults: sort by spike_ratio desc, page 1, page size 10.
 */
export function useSortedPagedRows<
  Row extends { [K in SpikeSortField]?: number | null },
>(rows: Row[]) {
  const [sortField, setSortField] = useState<SpikeSortField>("spike_ratio")
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc")
  const [page, setPage] = useState(1)

  const sortedRows = useMemo(() => {
    return [...rows].sort((a, b) => {
      const aVal = a[sortField] ?? -Infinity
      const bVal = b[sortField] ?? -Infinity
      return sortDir === "desc" ? (bVal > aVal ? 1 : -1) : (aVal > bVal ? 1 : -1)
    })
  }, [rows, sortField, sortDir])

  const pagedRows = sortedRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const totalPages = Math.ceil(sortedRows.length / PAGE_SIZE)

  const toggleSort = (field: SpikeSortField) => {
    if (sortField === field) {
      setSortDir(sortDir === "desc" ? "asc" : "desc")
    } else {
      setSortField(field)
      setSortDir("desc")
    }
    setPage(1)
  }

  return {
    sortField,
    sortDir,
    page,
    setPage,
    pageSize: PAGE_SIZE,
    sortedRows,
    pagedRows,
    totalPages,
    toggleSort,
  }
}
