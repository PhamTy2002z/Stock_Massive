/**
 * One step of putting a new question at the top of the transcript.
 *
 * A question can only be scrolled to the top if the top is a scroll position
 * the transcript *has* — and right after a question is asked it usually is not:
 * the answer has not arrived, so there is nothing below to scroll past. The
 * transcript therefore ends in a spacer sized to exactly the shortfall, and the
 * pin takes two steps: make the room, then move.
 *
 * Both steps are decided here rather than in the view, because the arithmetic is
 * where this went wrong twice. Once by racing a single animation frame against
 * React's commit — the frame scrolled against the transcript's old height and
 * the question stopped halfway up, with the previous answer still under it. And
 * once by reading this number as "how much room is still missing" and waiting
 * for it to reach zero, which for a short answer is a moment that never comes,
 * so the question never moved at all.
 *
 * The number is neither of those. It is **the whole spacer the layout needs**,
 * measured against a `scrollHeight` that already includes whatever spacer is
 * there — which is what makes it land on the same value once the DOM really
 * carries it. That equality is the readiness signal, and it is the only correct
 * one: `tail` from the layout matching `tail` from the arithmetic means the room
 * exists, so the scroll can be asked for.
 */

export interface PinLayout {
  /** Where the question would sit, as an offset into the transcript. */
  target: number
  /** The transcript's full height, spacer included. */
  scrollHeight: number
  /** The height of the window onto it. */
  clientHeight: number
  /** The spacer the transcript carries right now. */
  tail: number
}

export interface PinStep {
  /** The spacer the layout needs. */
  tail: number
  /** Where to scroll, or null when this step only makes room. */
  scroll: number | null
}

export function pinStep({ target, scrollHeight, clientHeight, tail }: PinLayout): PinStep {
  const reachable = scrollHeight - clientHeight
  const needed = Math.max(0, Math.round(tail + target - reachable))
  // Equal means the spacer in the arithmetic is the spacer in the DOM, so the
  // position asked for is a position that exists.
  return needed === tail ? { tail, scroll: target } : { tail: needed, scroll: null }
}
