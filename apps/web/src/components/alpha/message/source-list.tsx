"use client"

import type { ToolResult } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"
import { SourceIcon } from "./source-icon"

/**
 * The result card behind a tool call — the thing "8 nguồn" or a single search
 * row expands into.
 *
 * **Every string a `ToolResult` carries was written by a page a search engine
 * chose, not by this product or its model.** That is why every field here is
 * printed as plain text: no `Markdown` component, no `dangerouslySetInnerHTML`,
 * nothing that would let a page's own title or snippet supply markup or a
 * script this surface would then run on the reader's behalf. `href` gets the
 * same suspicion — only `http:`/`https:` becomes a clickable link, so a result
 * whose URL carries another scheme (`javascript:`, `data:`, …) still shows its
 * title and snippet, just with nothing to click.
 */
export function SourceList({
  results,
  className,
}: {
  results: ToolResult[]
  className?: string
}) {
  if (results.length === 0) return null

  return (
    <div
      className={cn(
        "grid gap-[17px] overflow-y-auto rounded-card border border-border bg-surface-panel p-4",
        className,
      )}
    >
      {results.map((result, index) => (
        <SourceRow key={`${result.url}-${index}`} result={result} />
      ))}
    </div>
  )
}

function SourceRow({ result }: { result: ToolResult }) {
  const href = safeHref(result.url)

  const body = (
    <div className="grid gap-[0.28rem]">
      <div className="text-meta font-medium leading-[1.4] text-ink-2">{result.title}</div>
      <div className="truncate text-micro leading-[1.45] text-muted-foreground">
        {result.snippet}
      </div>
      <div className="mt-[0.1rem] flex items-center gap-[0.45rem]">
        {/* One mark, not a stack: the domain is spelled out beside it, so
            the chip stack's overlap and ring would be decoration on a row that
            is already saying the thing plainly. */}
        <SourceIcon source={result.source} size={18} />
        <span className="text-micro text-muted-foreground">{result.source}</span>
      </div>
    </div>
  )

  if (!href) return body

  return (
    <a href={href} target="_blank" rel="noopener noreferrer nofollow" className="block">
      {body}
    </a>
  )
}

/** `null` for anything that is not `http:`/`https:`, including a malformed URL. */
function safeHref(url: string): string | null {
  try {
    const parsed = new URL(url)
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? url : null
  } catch {
    return null
  }
}
