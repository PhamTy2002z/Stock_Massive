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

/** The note the host appends to explain the unverified label, which is no longer drawn. */
const UNVERIFIED_NOTE = /\n*Số có nhãn \[chưa kiểm chứng\][^\n]*/g

/** The answer as the surface draws it: without the note about a label it does not show. */
export function withoutUnverifiedNote(text: string): string {
  return text.replace(UNVERIFIED_NOTE, "")
}

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

/** One source an answer lists at its end, as the sources pill shows it. */
export interface CitedSource {
  label: string
  /** The page, when the line carried one. */
  url: string | null
}

/** A heading above a source list: the host's `**Nguồn số liệu**` or the model's own `Nguồn:`. */
const SOURCES_LINE = /^(?:#{1,4} *)?(?:\*\*)?Nguồn(?: số liệu| tham khảo)?:?(?:\*\*)?:? *$/i
const SOURCE_ENTRY = /^(?:[-*] )?\[(\d{1,3})\] (.+)$/
/** The host's notes about its labels, which sit among the closing lists. */
const LABEL_NOTE = /^Số có nhãn /

/**
 * The answer without the source lists it ends with, and those lists' lines.
 *
 * Every source belongs in the sources pill beside the answer, not in a numbered
 * list under it (owner decision, 2026-09-27). Only a tail that is nothing but
 * headings, `[n]` lines, rules and the host's label notes is cut, so a `Nguồn:`
 * that starts a paragraph of prose stays prose. The host's list and one the
 * model wrote itself say the same sources twice, so the host's wins.
 */
export function splitSources(text: string): { body: string; sources: CitedSource[] } {
  const lines = text.split("\n")
  let cut = lines.length
  for (let index = lines.length - 1; index >= 0; index--) {
    const line = lines[index].trim()
    if (SOURCES_LINE.test(line)) cut = index
    else if (line !== "" && line !== "---" && !SOURCE_ENTRY.test(line) && !LABEL_NOTE.test(line)) break
  }
  if (cut === lines.length) return { body: text, sources: [] }

  // The host's list is built from the evidence itself; one the model wrote says
  // the same sources in other words, so it is read only when the host wrote none.
  let tail = lines.slice(cut)
  const host = tail.findIndex((line) => line.trim() === SOURCES_HEADING)
  if (host !== -1) tail = tail.slice(host)

  const seen = new Set<string>()
  const sources: CitedSource[] = []
  for (const line of tail) {
    const match = SOURCE_ENTRY.exec(line.trim())
    if (!match) continue
    const link = /\s*—\s*<([^>]+)>\s*$/.exec(match[2])
    const label = (link ? match[2].slice(0, link.index) : match[2]).trim()
    if (seen.has(label)) continue
    seen.add(label)
    sources.push({ label, url: link ? link[1] : null })
  }
  const body = lines.slice(0, cut).join("\n").replace(/(?:\s*\n---)?\s*$/, "")
  return { body, sources }
}

/**
 * A bare citation the model wrote itself: `[1]`, `[2, 3]`, `[1–4]`.
 *
 * Its list is in the sources pill, so the number points at nothing on screen.
 * Not a link (`[1](…)` is an anchor by the time the tree is walked).
 */
const BARE_CITATION = / ?\[\d{1,3}(?: *[,;–-] *\d{1,3})*\]/g

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
      next.push(...splitMarkers(child.value.replace(BARE_CITATION, ""), sources))
      continue
    }
    if (!isElement(child) || !VERBATIM.has(child.tagName)) walk(child, sources)
    next.push(child)
  }
  ;(node as OtherNode).children = next
}

/**
 * One text node as prose and chips, in order, with every prose character kept.
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
    // A cited figure is the normal case and draws nothing, not even the space the
    // host wrote before its label: its source and date are in the closing list.
    // An unverified one draws nothing either (owner decision, 2026-09-27: the
    // words cost the reader more than they told). The label stays in the text and
    // in the claim ledger; a figure with no source is simply absent from the list.
    const silent = marker.kind !== "stale"
    const before = value.slice(cursor, start)
    const prose = silent ? before.replace(/ $/, "") : before
    if (prose) nodes.push({ type: "text", value: prose })
    if (!silent) nodes.push(chip(marker, sources))
    cursor = start + match[0].length
  }
  if (cursor < value.length) nodes.push({ type: "text", value: value.slice(cursor) })
  return nodes
}

function chip(marker: FigureMarker, sources: Map<number, string>): ElementNode {
  const source = marker.source === null ? undefined : sources.get(marker.source)
  const title = [source ? `[${marker.source}] ${source}` : `Nguồn [${marker.source}]`, marker.label]
    .filter(Boolean)
    .join(" · ")
  const text = STALE_LABEL
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
