/**
 * Every word of an answer in its own element, so every word can arrive.
 *
 * The fade belongs to the word, which means the word has to be something CSS can
 * address — and prose parsed out of Markdown is text nodes, which CSS cannot. So
 * this splits them: each run of non-whitespace becomes a `span` carrying
 * `vg-chunk`, and the whitespace between them stays exactly the text it was,
 * because that is what decides where a line wraps.
 *
 * **Nothing here decides when a word appears.** A word fades in when it is
 * mounted, and what mounts it is the pacer growing the revealed text one commit
 * at a time (`reveal.ts`). That is the whole cadence: a commit's worth of words
 * arrives together as a cluster, the next one a beat later. Staggering them here
 * as well — an `animation-delay` per word — would mean text that is laid out
 * before it is visible, and the transcript's pin cannot absorb height that
 * appeared without a commit.
 *
 * **Words, not groups of words.** The pacer hands over whole words, so a span is
 * never re-written once it is mounted. A group whose text grew after it faded in
 * would show its last word without the fade.
 *
 * **Nothing inside `code` or `pre` is touched.** Their whitespace is content, and
 * a span per word inside a code block is a span per word the reader would have
 * to select around.
 *
 * A rehype plugin rather than a `components` override because react-markdown has
 * no component for a text node: the only place to get between the parse and the
 * elements is the tree itself.
 */

/** The class the stylesheet animates. Declared in `globals.css`. */
export const CHUNK_CLASS = "vg-chunk"

/** How long one word takes to fade in. Must match `vg-chunk-in` in `globals.css`. */
export const CHUNK_FADE_MS = 260

/** Tags whose text is content rather than prose, and is left alone. */
const VERBATIM = new Set(["code", "pre"])

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

export function rehypeWordCadence() {
  return (tree: Node): void => {
    split(tree)
  }
}

function split(node: Node): void {
  const children = (node as OtherNode).children
  if (!Array.isArray(children)) return

  const next: Node[] = []
  for (const child of children) {
    if (isText(child)) {
      next.push(...wrapWords(child.value))
      continue
    }
    if (!isElement(child) || !VERBATIM.has(child.tagName)) split(child)
    next.push(child)
  }
  ;(node as OtherNode).children = next
}

/**
 * One text node as alternating words and whitespace.
 *
 * Exported for its own test: this is the only place in the path where a
 * character can be dropped, and a dropped character is invisible in a
 * screenshot.
 */
export function wrapWords(value: string): Node[] {
  if (value === "") return []
  const nodes: Node[] = []
  for (const piece of value.split(/(\s+)/)) {
    if (piece === "") continue
    if (/^\s+$/.test(piece)) {
      nodes.push({ type: "text", value: piece })
      continue
    }
    nodes.push({
      type: "element",
      tagName: "span",
      properties: { className: [CHUNK_CLASS] },
      children: [{ type: "text", value: piece }],
    })
  }
  return nodes
}

function isText(node: Node): node is TextNode {
  return node.type === "text" && typeof (node as TextNode).value === "string"
}

function isElement(node: Node): node is ElementNode {
  return node.type === "element" && typeof (node as ElementNode).tagName === "string"
}
