"use client"

/**
 * Inline notice for a sub-panel whose data could not be loaded.
 *
 * Prefers the API's own explanation — 501 replies say which capability the
 * provider lacks, 503 replies say what has not been computed yet. Those are far
 * more useful than "something went wrong", and fetchApi already surfaces them
 * as the error message.
 */
export function DataErrorNotice({ error }: { error: unknown }) {
  const detail = error instanceof Error ? error.message.trim() : ""

  return (
    <div className="p-4 rounded-lg bg-destructive/10 text-destructive text-sm">
      {detail || "Có lỗi khi tải dữ liệu. Vui lòng thử lại."}
    </div>
  )
}
