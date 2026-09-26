/**
 * The host's figure labels, drawn as what they are rather than as bracketed text.
 *
 * The API checks every figure in an answer against the Turn's own tool data and
 * writes the verdict beside it, in the text itself (`evidence/grounding.py` in
 * the API): `76.500 đồng [1 · phiên 25/09/2026]` for a figure with a dated
 * source, `[2 · 07/01/2026 · nguồn cũ]` for one resting on an old page, and
 * `[chưa kiểm chứng]` for one nothing backs. The text is the canonical record —
 * it is what a reopened Thread, a copy and the next Turn all read — so the
 * surface does not receive a second structure to keep in step with it. It reads
 * the labels back out of the prose.
 *
 * Why here and not in a component: react-markdown has no component for a text
 * node, and the labels sit inside paragraphs, list items, table cells and bold
 * runs alike. The tree is the one place all of them pass through
 * (`word-cadence.ts` is the same decision for the same reason).
 *
 * Nothing a label says is trusted as markup: the plugin builds the elements
 * itself, from the characters the pattern matched, and never parses them.
 */

/** A label the host writes: `[n · date…]` or `[chưa kiểm chứng]`. */
export const MARKER = /\[(?:(\d{1,3}) · ([^\]\n]{1,80})|(chưa kiểm chứng))\]/g

export const STALE_LABEL = "nguồn cũ"
export const UNVERIFIED_LABEL = "chưa kiểm chứng"

/** The heading the host writes above the dated source list. */
export const SOURCES_HEADING = "**Nguồn số liệu**"

export type FigureKind = "cited" | "stale" | "unverified"

export interface FigureMarker {
  kind: FigureKind
  /** The citation number, when the figure has a source. */
  source: number | null
  /** What the chip shows: the date and, for a stale source, that it is old. */
  label: string
}

/** One label as the chip it becomes; `null` for text that is not a label. */
export function readMarker(text: string): FigureMarker | null {
  const match = new RegExp(`^${MARKER.source}$`).exec(text)
  if (!match) return null
  if (match[3]) return { kind: "unverified", source: null, label: UNVERIFIED_LABEL }
  const detail = match[2].trim()
  return {
    kind: detail.endsWith(STALE_LABEL) ? "stale" : "cited",
    source: Number(match[1]),
    label: detail,
  }
}

/**
 * The dated source list the host appends, by citation number.
 *
 * Read from the text rather than sent alongside it, for the reason in the
 * module note. A line reads `- [1] Publisher — Title — đăng 20/08/2026 — <url>`.
 */
export function readSources(text: string): Map<number, string> {
  const sources = new Map<number, string>()
  const at = text.lastIndexOf(SOURCES_HEADING)
  if (at === -1) return sources
  for (const line of text.slice(at + SOURCES_HEADING.length).split("\n")) {
    const match = /^(?:- )?\[(\d{1,3})\] (.+)$/.exec(line.trim())
    if (match) sources.set(Number(match[1]), match[2].replace(/\s*—\s*<[^>]+>\s*$/, ""))
  }
  return sources
}

/** The classes the chips carry. Declared here so the renderer and tests agree. */
export const MARKER_CLASS: Record<FigureKind, string> = {
  cited: "vg-figure vg-figure-cited",
  stale: "vg-figure vg-figure-stale",
  unverified: "vg-figure vg-figure-unverified",
}

interface TextNode {
  type: "text"
  value: string
}

interface ElementNode {
  type: "element"
  tagName: string
  properties?: Record<string, unknown>
  children?: Node[]
}

interface OtherNode {
  type: string
  children?: Node[]
}

type Node = TextNode | ElementNode | OtherNode

/** Tags whose text is content rather than prose, and is left alone. */
const VERBATIM = new Set(["code", "pre"])

/**
 * A rehype plugin: every label in the prose becomes a titled `span`.
 *
 * `sources` is the list the answer ends with, so a chip can say which source it
 * cites without the reader scrolling to the bottom to find out.
 */
export function rehypeFigureMarkers(options: { sources?: Map<number, string> } = {}) {
  const sources = options.sources ?? new Map<number, string>()
  return (tree: Node): void => {
    walk(tree, sources)
  }
}

function walk(node: Node, sources: Map<number, string>): void {
  const children = (node as OtherNode).children
  if (!Array.isArray(children)) return
  const next: Node[] = []
  for (const child of children) {
    if (isText(child)) {
      next.push(...splitMarkers(child.value, sources))
      continue
    }
    if (!isElement(child) || !VERBATIM.has(child.tagName)) walk(child, sources)
    next.push(child)
  }
  ;(node as OtherNode).children = next
}

/**
 * One text node as prose and chips, in order, with every character kept.
 *
 * Exported for its own test: a dropped character here is invisible on screen.
 */
export function splitMarkers(value: string, sources: Map<number, string> = new Map()): Node[] {
  const nodes: Node[] = []
  let cursor = 0
  for (const match of value.matchAll(MARKER)) {
    const start = match.index ?? 0
    const marker = readMarker(match[0])
    if (!marker) continue
    if (start > cursor) nodes.push({ type: "text", value: value.slice(cursor, start) })
    nodes.push(chip(marker, sources))
    cursor = start + match[0].length
  }
  if (cursor < value.length) nodes.push({ type: "text", value: value.slice(cursor) })
  return nodes
}

function chip(marker: FigureMarker, sources: Map<number, string>): ElementNode {
  const source = marker.source === null ? undefined : sources.get(marker.source)
  const title =
    marker.kind === "unverified"
      ? "Số này không có trong dữ liệu công cụ của lượt này, hoặc không khớp mốc thời gian câu đó nói tới."
      : [source ? `[${marker.source}] ${source}` : `Nguồn [${marker.source}]`, marker.label]
          .filter(Boolean)
          .join(" · ")
  const text = marker.source === null ? marker.label : `${marker.source} · ${marker.label}`
  return {
    type: "element",
    tagName: "span",
    properties: {
      className: MARKER_CLASS[marker.kind].split(" "),
      title,
      "data-figure": marker.kind,
      ...(marker.source === null ? {} : { "data-source": String(marker.source) }),
    },
    children: [{ type: "text", value: text }],
  }
}

function isText(node: Node): node is TextNode {
  return node.type === "text" && typeof (node as TextNode).value === "string"
}

function isElement(node: Node): node is ElementNode {
  return node.type === "element" && typeof (node as ElementNode).tagName === "string"
}
