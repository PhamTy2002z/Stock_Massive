"use client"

import type { ComponentPropsWithoutRef } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { cn } from "@/lib/utils"

/**
 * One block's prose, rendered as the Markdown it already is.
 *
 * The backend buffers provider deltas into complete, **Markdown-safe** units and
 * emits one event per unit (ADR-0013) — a closed paragraph, a whole bullet
 * group, a complete table, a closed fence. So a block is not text that happens
 * to contain asterisks; it is Markdown, and showing it verbatim put `**` on
 * screen in front of readers.
 *
 * Two rules make this safe to do at all:
 *
 * **No raw HTML.** `rehype-raw` is deliberately absent, so the plugin chain has
 * no path from model output to markup. An `<img onerror>` in an answer renders
 * as the text it is. This is why no sanitiser is needed rather than why one was
 * skipped: nothing here can produce an element the code below did not name.
 *
 * **No autolinked bare URLs into a live anchor without a rel.** Every link goes
 * through the component below, which opens in a new tab and sends no referrer —
 * the prose is derived from untrusted external claims, and a link in it is not a
 * link this product is vouching for.
 */
export function Markdown({
  text,
  trailing,
  className,
}: {
  text: string
  /**
   * Rendered inside the last paragraph or list item, on the same line.
   *
   * The citation chip belongs at the end of the sentence it supports, and a
   * sibling after the renderer would sit on a line of its own — a chip on its
   * own line reads as a caption for the whole answer rather than as a mark on
   * the claim. Placed by source offset rather than by index, because the last
   * *element* is not the last *block* once a list is involved.
   */
  trailing?: React.ReactNode
  className?: string
}) {
  const end = text.trimEnd().length
  const isLast = (node: { position?: { end?: { offset?: number } } } | undefined) =>
    trailing !== undefined && (node?.position?.end?.offset ?? -1) >= end

  return (
    <div
      className={cn(
        "text-[0.95rem] leading-[1.62] [&>*+*]:mt-3",
        // Headings inside an answer are section labels, not page titles: one
        // step of weight and none of size, so a bolded line cannot start
        // competing with the question above it.
        "[&_h1]:text-[1.05rem] [&_h1]:font-semibold [&_h2]:text-[1rem] [&_h2]:font-semibold",
        "[&_h3]:text-[0.95rem] [&_h3]:font-semibold [&_h4]:text-[0.95rem] [&_h4]:font-semibold",
        "[&_strong]:font-semibold [&_strong]:text-ink-display",
        "[&_em]:italic",
        "[&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5",
        "[&_li]:mt-1 [&_li>ul]:mt-1 [&_li>ol]:mt-1",
        "[&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_blockquote]:text-ink-3",
        "[&_code]:rounded [&_code]:bg-surface-raised [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-micro",
        "[&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-surface-raised [&_pre]:p-3",
        "[&_pre_code]:bg-transparent [&_pre_code]:p-0",
        "[&_hr]:border-border",
        className,
      )}
    >
      <ReactMarkdown
        // GFM for the two things a Vietnamese equities answer actually uses:
        // tables of figures, and strikethrough on a superseded number.
        remarkPlugins={[remarkGfm]}
        components={{
          a: Anchor,
          table: Table,
          p: ({ node, children, ...rest }) => (
            <p {...rest}>
              {children}
              {isLast(node) && trailing}
            </p>
          ),
          li: ({ node, children, ...rest }) => (
            <li {...rest}>
              {children}
              {isLast(node) && trailing}
            </li>
          ),
          th: (props) => (
            <th
              {...props}
              className="border border-border px-2.5 py-1.5 text-left font-semibold"
            />
          ),
          td: (props) => (
            <td {...props} className="border border-border px-2.5 py-1.5 align-top" />
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}

/**
 * A table wide enough to need scrolling, scrolling inside its own box.
 *
 * The transcript column is fixed and the inspector can take half of it; a table
 * that pushed the column wider would move the composer and the question above
 * it, so the overflow is the table's own problem to hold.
 */
function Table(props: ComponentPropsWithoutRef<"table">) {
  return (
    <div className="overflow-x-auto">
      <table {...props} className="w-full border-collapse text-meta" />
    </div>
  )
}

function Anchor({ href, children, ...rest }: ComponentPropsWithoutRef<"a">) {
  return (
    <a
      {...rest}
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary underline decoration-primary/40 underline-offset-2 hover:decoration-primary"
    >
      {children}
    </a>
  )
}
