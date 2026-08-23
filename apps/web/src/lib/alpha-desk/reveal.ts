/**
 * How fast an answer appears once it has arrived, and where it may stop.
 *
 * The transport does not pace anything. A Turn's prose is published as whole
 * pieces — one `content.delta` carrying the model's entire reply is the normal
 * case, not the exception — so an answer that is simply rendered as it lands
 * appears all at once, in a single frame, after a wait. Nothing about that is
 * wrong, and nothing about it reads as an answer being written either.
 *
 * So the cadence is made here, and it is made by **growing the text**, one
 * commit at a time, rather than by revealing text that is already laid out. That
 * is not a detail: the transcript's pin and its spacer are built on the rule
 * that every way the transcript can change height is a commit (`view-chat`).
 * Text that occupied its final height while invisible broke that rule twice
 * over — the spacer gave back the whole answer in one step, and the browser then
 * changed the height again, as words faded and the timeline folded, with no
 * commit for anything to absorb.
 *
 * Two rules, and they are the whole of the arithmetic:
 *
 * **The rate follows the backlog.** A pacer with one fixed speed is either too
 * slow for a long answer or too fast for a short one, so the speed is whatever
 * clears what is waiting in `REVEAL_DRAIN_MS` — bounded at both ends, because a
 * sentence still has to be readable on the way past and a page of prose still
 * has to be finished before the reader has moved on.
 *
 * **A word is never shown in halves.** The cursor advances in characters
 * because that is what a rate is measured in, and what is put on screen is
 * rounded back to the last completed word. A word is one animated element, and
 * one element cannot fade in twice.
 *
 * A table is the exception to the second rule, and `tableBoundary` says why: a
 * grid re-measures every column when any cell grows, so it is paced by the row
 * rather than by the word.
 */

/** How long the pacer aims to take over whatever is waiting to be shown. */
export const REVEAL_DRAIN_MS = 1500

/** Slowest it will go, in characters a second. Below this a short answer crawls. */
export const REVEAL_MIN_CPS = 90

/** Fastest it will go. Above this the words stop reading as words arriving. */
export const REVEAL_MAX_CPS = 1200

/**
 * The longest run of non-whitespace shown a character at a time.
 *
 * Rounding back to the last completed word stalls on text that has no words in
 * it — a URL, a base64 blob. Past this length the run is revealed as it comes
 * rather than held back for a boundary that may be hundreds of characters away.
 */
export const REVEAL_PARTIAL_MAX = 24

/**
 * How long the reasoning timeline takes to fold, both ways.
 *
 * Written in `reasoning-timeline` as `duration-300` and as the `visibility`
 * transition that waits for it, and read by the reveal, because the answer must
 * not start growing until the rows above it have finished getting out of the
 * way. Two motions over the same pixels read as a stutter, and a fold competing
 * with text that is pushing it down the page reads as a jump.
 */
export const TIMELINE_FOLD_MS = 300

/** Characters a second, for a backlog of this many characters. */
export function revealRate(backlog: number): number {
  if (backlog <= 0) return 0
  const rate = (backlog * 1000) / REVEAL_DRAIN_MS
  return Math.min(REVEAL_MAX_CPS, Math.max(REVEAL_MIN_CPS, rate))
}

/**
 * Where the cursor is after `deltaMs` more of pacing.
 *
 * Fractional, and deliberately so: at these rates a frame is worth a few
 * characters, and rounding every frame down would lose most of them.
 */
export function advanceCursor(cursor: number, length: number, deltaMs: number): number {
  if (cursor >= length) return length
  const moved = cursor + (revealRate(length - cursor) * Math.max(0, deltaMs)) / 1000
  return Math.min(length, moved)
}

/** How much of `text` may be on screen with the cursor here. */
export function revealedLength(text: string, cursor: number): number {
  const end = Math.min(Math.max(0, Math.floor(cursor)), text.length)
  // Everything that exists is everything there is to wait for: the last word of
  // a finished answer has no trailing space to announce it.
  if (end >= text.length) return text.length

  const row = tableBoundary(text, end)
  if (row !== null) return row

  let start = end
  while (start > 0 && !isSpace(text.charAt(start - 1))) start -= 1
  return end - start > REVEAL_PARTIAL_MAX ? end : start
}

/**
 * Where a boundary inside a table may fall, or `null` outside one.
 *
 * A table is the one construct here whose layout is not incremental. Its column
 * widths are measured from every cell it holds, so a word landing in one cell
 * re-measures the whole grid: every column moves sideways, the widest header
 * re-wraps, and the table changes height without a row having been added. Paced
 * a word at a time that is a re-measure per commit — the flicker a growing
 * table shows, and height the transcript's spacer was never handed.
 *
 * So a table grows by **whole lines**, and only once it is a table. Two
 * complete lines is the threshold because that is GFM's: a header row alone is
 * a paragraph of pipe characters, and letting it through would put the source
 * on screen and then re-mount every word of it as cells a commit later.
 */
function tableBoundary(text: string, end: number): number | null {
  const lineStart = text.lastIndexOf("\n", end - 1) + 1
  let blockStart = lineStart
  while (blockStart > 0) {
    const previousStart = text.lastIndexOf("\n", blockStart - 2) + 1
    if (!isTableLine(text.slice(previousStart, blockStart - 1))) break
    blockStart = previousStart
  }

  const partial = text.slice(lineStart, end)
  // An empty partial line with table lines above it is the start of the next
  // row, which is as much inside the table as the middle of a row is.
  const inside = isTableLine(partial) || (partial === "" && blockStart < lineStart)
  if (!inside) return null

  const complete = countLines(text.slice(blockStart, lineStart))
  return complete >= 2 ? lineStart : blockStart
}

/** Whether this line is a row of a table: GFM allows it three spaces of indent. */
function isTableLine(line: string): boolean {
  const indent = line.length - line.trimStart().length
  return indent <= 3 && line.trimStart().startsWith("|")
}

function countLines(text: string): number {
  let lines = 0
  for (const character of text) if (character === "\n") lines += 1
  return lines
}

function isSpace(character: string): boolean {
  return character === " " || character === "\n" || character === "\t" || character === "\r"
}
