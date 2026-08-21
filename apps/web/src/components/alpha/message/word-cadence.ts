/**
 * How a block that just arrived reads itself out: a few words at a time.
 *
 * The backend still buffers provider deltas into **complete, Markdown-safe
 * units** (ADR-0013), and that stays the transport contract — nothing here asks
 * for smaller events, and no partial Markdown is ever parsed. What changes is
 * only presentation: the finished block is parsed whole, then its prose is
 * wrapped chunk by chunk so the text cascades in instead of appearing as one
 * slab. The DOM is complete the instant the block lands, so the layout never
 * reflows, assistive technology reads a finished paragraph, and a reader who
 * scrolls sees text that is already there.
 *
 * **A chunk is words, not characters.** Four whitespace-separated words —
 * roughly the three-to-five *chữ* a Vietnamese reader takes in at a glance —
 * because a per-character crawl is the illusion the buffered transport exists
 * to remove, and it makes a number unreadable while it is drawn.
 *
 * **Tables and code are never chunked.** A table that fills in cell by cell is
 * unreadable while it does it, and a fence is one artefact rather than prose.
 *
 * The cascade is capped in total (`CASCADE_CAP_MS`): a short block gets the full
 * per-chunk cadence, and a long one compresses its step so the answer is never
 * gated by its own animation.
 */

/** Rendered whole. Prose cadence inside these reads as damage, not as arrival. */
const OPAQUE_TAGS = new Set(["pre", "code", "table"])

/** Words per chunk. The middle of the three-to-five a glance takes in. */
export const WORDS_PER_CHUNK = 4

/** Delay between two chunks starting, before the cap applies. */
export const CHUNK_STEP_MS = 70

/** The longest a single block may take to finish cascading. */
export const CASCADE_CAP_MS = 1100

/** The class the stylesheet animates (`globals.css`). */
export const CHUNK_CLASS = "vg-chunk"

/**
 * The slice of a hast tree this walk touches.
 *
 * Declared locally because `@types/hast` is not a dependency of this app, and a
 * transitive type is not a contract. Only the four fields below are read or
 * written, so a looser tree than hast's is honest about what happens here.
 */
interface ProseNode {
  type: string
  tagName?: string
  value?: string
  properties?: Record<string, unknown>
  children?: ProseNode[]
}

/**
 * A rehype plugin: wrap every run of prose in a chunk span, in reading order.
 *
 * Delays are assigned in a second pass, because the step depends on how many
 * chunks the whole block turned out to have.
 */
export function chunkedProse() {
  return (tree: ProseNode): void => {
    const chunks: ProseNode[] = []
    wrapProse(tree, chunks)
    if (chunks.length === 0) return

    const step = Math.min(CHUNK_STEP_MS, CASCADE_CAP_MS / chunks.length)
    chunks.forEach((chunk, index) => {
      chunk.properties = {
        className: [CHUNK_CLASS],
        // The delay is written out rather than handed to CSS as an index: one
        // number in a style attribute needs no custom-property arithmetic, and
        // it is the same value a test can read back.
        style: `animation-delay:${Math.round(index * step)}ms`,
      }
    })
  }
}

/** Replace text children with chunk spans, depth first, skipping opaque subtrees. */
function wrapProse(node: ProseNode, chunks: ProseNode[]): void {
  const children = node.children
  if (!children) return

  const next: ProseNode[] = []
  for (const child of children) {
    if (child.type === "text" && typeof child.value === "string") {
      // Whitespace between two elements is not a chunk. Giving it one would
      // spend a step of the cadence on a gap nobody can see arrive.
      if (child.value.trim() === "") {
        next.push(child)
        continue
      }
      for (const text of chunkify(child.value)) {
        const span: ProseNode = {
          type: "element",
          tagName: "span",
          properties: {},
          children: [{ type: "text", value: text }],
        }
        chunks.push(span)
        next.push(span)
      }
      continue
    }

    if (child.type !== "element" || !OPAQUE_TAGS.has(child.tagName ?? "")) {
      wrapProse(child, chunks)
    }
    next.push(child)
  }

  node.children = next
}

/**
 * Split prose into chunks of at most `WORDS_PER_CHUNK` words.
 *
 * Whitespace runs are kept as their own tokens and carried into the chunk that
 * precedes them, so joining the result back gives the original string exactly —
 * a lost space is a word glued to the next one.
 */
function chunkify(value: string): string[] {
  const tokens = value.split(/(\s+)/).filter((token) => token !== "")
  const out: string[] = []
  let current = ""
  let words = 0

  for (const token of tokens) {
    current += token
    if (/^\s+$/.test(token)) continue
    words += 1
    if (words === WORDS_PER_CHUNK) {
      out.push(current)
      current = ""
      words = 0
    }
  }

  if (current !== "") out.push(current)
  return out
}
