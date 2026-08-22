"use client"

import type { ComponentPropsWithoutRef, ReactNode } from "react"
import { createContext, memo, useContext, useMemo } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { cn } from "@/lib/utils"
import { chunkedProse } from "./word-cadence"

/**
 * The plugin list, built once per mode.
 *
 * A new array per render would make react-markdown reparse on every unrelated
 * render, and the plugin is stateless — it carries its own chunk list per call.
 *
 * The cast is the price of not depending on `@types/hast`: the walk declares the
 * handful of node fields it touches, which is narrower than a hast tree rather
 * than incompatible with one.
 */
type RehypePlugins = NonNullable<
  ComponentPropsWithoutRef<typeof ReactMarkdown>["rehypePlugins"]
>
const STAGGERED: RehypePlugins = [chunkedProse] as unknown as RehypePlugins
const PLAIN: RehypePlugins = []

/** The one field of a hast node this file reads: where the source unit ended. */
interface Positioned {
  position?: { end?: { offset?: number } }
}

/**
 * Where the trailing chip goes, passed by context rather than by closure.
 *
 * **This is what keeps the prose the same DOM across a re-render.** A renderer
 * declared inline is a new component type every time this file renders, and
 * React unmounts a subtree whose type changed: the paragraphs would be rebuilt
 * from scratch, which dropped the reader's text selection mid-drag and restarted
 * the `vg-chunk` cascade from its first word. The renderers below are therefore
 * module-level and constant, and the one thing they need per message — which
 * offset ends the answer, and what to hang there — reaches them through this
 * context instead.
 */
const TrailingSlot = createContext<{ node: ReactNode; end: number }>({
  node: undefined,
  end: Number.POSITIVE_INFINITY,
})

/** The trailing node for this element, or null where it does not belong here. */
function useTrailing(node: Positioned | undefined): ReactNode {
  const slot = useContext(TrailingSlot)
  if (slot.node === undefined) return null
  return (node?.position?.end?.offset ?? -1) >= slot.end ? slot.node : null
}

type WithNode<Tag extends keyof React.JSX.IntrinsicElements> =
  ComponentPropsWithoutRef<Tag> & { node?: Positioned }

/**
 * The paragraph that carries the chip is a `div`, not a `p`.
 *
 * The chip is a disclosure and its panel is a block element, which a `p` may not
 * contain: the browser closes the paragraph before the panel and hydration then
 * mismatches the server's markup. Only the tag name differs — nothing here
 * styles `p` specifically — and every other paragraph keeps its own tag.
 */
function Paragraph({ node, children, ...rest }: WithNode<"p">) {
  const trailing = useTrailing(node)
  if (trailing === null) return <p {...rest}>{children}</p>
  return (
    <div {...(rest as ComponentPropsWithoutRef<"div">)}>
      {children}
      {trailing}
    </div>
  )
}

function ListItem({ node, children, ...rest }: WithNode<"li">) {
  const trailing = useTrailing(node)
  return (
    <li {...rest}>
      {children}
      {trailing}
    </li>
  )
}

function HeaderCell(props: ComponentPropsWithoutRef<"th">) {
  return <th {...props} className="border border-border px-2.5 py-1.5 text-left font-semibold" />
}

function Cell(props: ComponentPropsWithoutRef<"td">) {
  return <td {...props} className="border border-border px-2.5 py-1.5 align-top" />
}

type MarkdownComponents = NonNullable<
  ComponentPropsWithoutRef<typeof ReactMarkdown>["components"]
>
const COMPONENTS: MarkdownComponents = {
  a: Anchor,
  table: Table,
  p: Paragraph,
  li: ListItem,
  th: HeaderCell,
  td: Cell,
}

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
 *
 * `stagger` adds one rehype pass that wraps the already-parsed prose in chunk
 * spans (`word-cadence`), for the one block a `content.block` event just
 * delivered. It runs after parsing, never instead of it: partial Markdown is
 * still never rendered.
 *
 * Memoised on its props, because a finished block is a finished block: the
 * transcript re-renders for every event of a live Turn, and reparsing text that
 * did not change costs a parse per event and — before the renderers above were
 * hoisted — cost the reader their selection as well.
 */
export const Markdown = memo(function Markdown({
  text,
  trailing,
  stagger = false,
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
  trailing?: ReactNode
  /** Cascade this block's prose in, a few words at a time. */
  stagger?: boolean
  className?: string
}) {
  const end = text.trimEnd().length
  const slot = useMemo(() => ({ node: trailing, end }), [trailing, end])

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
      <TrailingSlot.Provider value={slot}>
        <ReactMarkdown
          // GFM for the two things a Vietnamese equities answer actually uses:
          // tables of figures, and strikethrough on a superseded number.
          remarkPlugins={[remarkGfm]}
          rehypePlugins={stagger ? STAGGERED : PLAIN}
          components={COMPONENTS}
        >
          {text}
        </ReactMarkdown>
      </TrailingSlot.Provider>
    </div>
  )
})

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
