"use client"

import type { ComponentPropsWithoutRef } from "react"
import ReactMarkdown, { type Options } from "react-markdown"
import remarkGfm from "remark-gfm"

import { rehypeWordCadence } from "@/lib/alpha-desk/word-cadence"
import { cn } from "@/lib/utils"

/**
 * An answer's prose, rendered as the Markdown it is.
 *
 * The model writes Markdown, so showing the text verbatim put `**` on screen in
 * front of readers. Two rules make rendering it safe to do at all:
 *
 * **No raw HTML.** `rehype-raw` is deliberately absent, so the plugin chain has
 * no path from model output to markup. An `<img onerror>` in an answer renders
 * as the text it is. This is why no sanitiser is needed rather than why one was
 * skipped: nothing here can produce an element the code below did not name, and
 * the one plugin that adds elements adds `span`s it writes itself around text it
 * never reads as markup.
 *
 * **No autolinked bare URL becomes a live anchor without a rel.** Every link
 * goes through the component below, which opens in a new tab and sends no
 * referrer — the prose can be written out of untrusted external pages, and a
 * link in it is not a link this product is vouching for.
 *
 * The text grows by deltas while a Turn runs, so this is re-parsed as it
 * arrives and will sometimes parse a half-written construct. That is the
 * accepted cost of prose that appears as it is written; the alternative is
 * holding each sentence back until it closes, which is the buffering the
 * streaming path exists to avoid.
 *
 * **`animate` splits the prose into one element per word** (`word-cadence`), so
 * each word fades in as the pacer reveals it. Only an answer being written asks
 * for it: the same message rendered from history is text that was always there,
 * and a fade on a re-render would animate a paragraph the reader is part-way
 * through.
 */
export function Markdown({
  text,
  animate = false,
  className,
}: {
  text: string
  /** Whether this prose is arriving, and its words should fade in as it does. */
  animate?: boolean
  className?: string
}) {
  const rehypePlugins: Options["rehypePlugins"] = animate ? [rehypeWordCadence] : undefined
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
        // GFM for the two things an answer actually uses beyond plain prose:
        // tables, and strikethrough on a superseded line.
        remarkPlugins={[remarkGfm]}
        rehypePlugins={rehypePlugins}
        components={{
          a: Anchor,
          table: Table,
          th: ({ node: _node, ...props }) => (
            <th
              {...props}
              className="border border-border px-2.5 py-1.5 text-left font-semibold"
            />
          ),
          td: ({ node: _node, ...props }) => (
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
 * The hast node react-markdown hands a component alongside the element's own
 * props. Every component here drops it: spread into the element it becomes a
 * `node="[object Object]"` attribute on every cell of every table.
 */
type WithNode<T> = T & { node?: unknown }
type TableProps = WithNode<ComponentPropsWithoutRef<"table">>
type AnchorProps = WithNode<ComponentPropsWithoutRef<"a">>

/**
 * A table wide enough to need scrolling, scrolling inside its own box.
 *
 * The transcript column is fixed and the inspector can take half of it; a table
 * that pushed the column wider would move the composer and the question above
 * it, so the overflow is the table's own problem to hold.
 */
function Table({ node: _node, ...props }: TableProps) {
  return (
    <div className="overflow-x-auto">
      <table {...props} className="w-full border-collapse text-meta" />
    </div>
  )
}

function Anchor({ href, children, node: _node, ...rest }: AnchorProps) {
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
