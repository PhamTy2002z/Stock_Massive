/**
 * How a span the server assigned survives a panel narrower than a page.
 *
 * The grid is the server's: it decided that these two charts are a pair and
 * that the comparison under them takes the width, and that arrangement is a
 * claim about the analysis rather than about the screen. Exactly one thing is
 * left to this end — a viewport too narrow for thirds — because it is the one
 * fact the server cannot see.
 *
 * The rules mirror `studies/layout.py`, and `layout.test.ts` holds the table
 * equal to it. A collapse invented here that the server did not anticipate would
 * be the browser re-laying out a board and calling it a breakpoint.
 */

/** The grid, the same twelve the server packed into. */
export const COLUMNS = 12

/**
 * Below this the panel cannot hold three charts side by side.
 *
 * Measured against the *panel*, not the viewport: the inspector is a column the
 * reader drags, so a media query would ask the wrong question — at 420 pixels of
 * panel on a wide screen every breakpoint says "wide". The caller measures its
 * own box and passes the width in.
 */
export const NARROW = 900

/**
 * What one block is worth at a given panel width.
 *
 * A third becomes a half and a half becomes the width; anything already full
 * stays full. Two steps rather than one because a third collapsing straight to
 * twelve turns a row of three charts into three screens of scrolling, where a
 * pair reads.
 */
export function spanAt(span: number, width: number): number {
  const clamped = Math.max(1, Math.min(COLUMNS, Math.round(span)))
  if (width >= NARROW) return clamped
  if (clamped <= 4) return 6
  if (clamped <= 6) return COLUMNS
  return clamped
}

/** The CSS the block carries. One declaration, so nothing here does maths twice. */
export function gridColumn(span: number, width: number): string {
  return `span ${spanAt(span, width)} / span ${spanAt(span, width)}`
}
