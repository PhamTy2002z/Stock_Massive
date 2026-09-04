"use client"

/**
 * Where one block's numbers came from, said only when it is not the usual place.
 *
 * Three words and no more, because the reader-facing consequence differs per
 * word. `store` is this deployment's own measurement and carries no badge at
 * all: a badge on every block is a badge nobody reads, and the provenance strip
 * above the board already says when and how healthy. `web` is a number read off
 * a page somebody else published, and that has to be visible beside the picture
 * rather than three clicks away. `derived` is arithmetic this Turn did on frames
 * it already had, which is neither of the first two and must not be able to pass
 * as the first.
 */

import { Globe, Sigma } from "lucide-react"

import type { VisualBlock } from "@/lib/alpha-desk/types"

export function SourceBadge({
  source,
  detail,
}: {
  source: VisualBlock["source"]
  /**
   * The domain a page came from, or how many frames a calculation read.
   *
   * Optional because the board does not always know: a frame's provenance holds
   * the query it was built from and the panel is handed the block, so the badge
   * says what it can and never invents the rest.
   */
  detail?: string
}) {
  if (source === "store") return null

  const isWeb = source === "web"
  const Icon = isWeb ? Globe : Sigma
  const label = isWeb ? "Nguồn web" : "Số tính ra"

  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border border-hairline bg-surface-sunken px-2 py-0.5 text-meta text-muted-foreground"
      title={detail}
    >
      <Icon aria-hidden className="h-3 w-3" />
      {label}
      {detail !== undefined && detail !== "" && (
        <span className="max-w-[10rem] truncate opacity-80">· {detail}</span>
      )}
    </span>
  )
}
