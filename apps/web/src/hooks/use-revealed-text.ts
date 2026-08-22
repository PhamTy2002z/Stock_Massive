"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import { advanceCursor, revealedLength } from "@/lib/alpha-desk/reveal"

/**
 * An answer as far as it should be on screen, rather than as far as it arrived.
 *
 * The arithmetic is in `reveal.ts`; this is the clock that drives it. Four
 * things it does that arithmetic cannot:
 *
 * **It commits on a slower beat than it paces.** The cursor moves every frame
 * because a rate needs one, but the string handed to React changes at most
 * every `COMMIT_MS`. Each commit re-parses the Markdown revealed so far, and a
 * few words per commit is all the eye resolves anyway.
 *
 * **It refuses to catch up on a frame that was never drawn.** A backgrounded
 * tab hands back one enormous delta on its first frame, and a pacer that
 * honoured it would reveal the rest of the answer in one step. Capped, so a
 * reader who comes back sees it arriving rather than already arrived.
 *
 * **It starts over when the text is not the same text.** `key` is the Turn: a
 * new answer starts from nothing, and cannot inherit a cursor measured in
 * another one.
 *
 * **It stops entirely under `prefers-reduced-motion`, and when told to.** Text
 * appearing a word at a time is motion, and a reader who asked for none gets
 * the answer at once. `instant` is the same escape for prose that is being
 * redrawn rather than written.
 */

/** How often the revealed string is allowed to change. */
const COMMIT_MS = 55

/** The most one frame may be worth, however long the browser was away. */
const MAX_FRAME_MS = 100

export interface RevealedText {
  /** The prefix to render. Grows by whole words. */
  visible: string
  /** Whether every character received is on screen. */
  complete: boolean
}

export interface RevealOptions {
  /** What this text belongs to. A change starts the reveal over. */
  key?: string | null
  /**
   * Reveal nothing yet, and keep the pacer where it is.
   *
   * What the timeline's fold uses: the answer stays out of the layout until the
   * rows above it have finished collapsing, rather than racing them down the
   * page.
   */
  hold?: boolean
  /** Show everything, unpaced. For text being redrawn rather than written. */
  instant?: boolean
}

export function useRevealedText(text: string, options: RevealOptions = {}): RevealedText {
  const { key = null, hold = false, instant = false } = options

  // Read once, and no listener: a reader who changes the setting mid-answer is
  // not who this is for, and the subscription would outlive every draft.
  const still = useRef<boolean | null>(null)
  if (still.current === null) still.current = prefersReducedMotion()

  const [shown, setShown] = useState(0)
  const shownRef = useRef(0)
  const cursor = useRef(0)

  const commit = useCallback((length: number) => {
    if (length <= shownRef.current) return
    shownRef.current = length
    setShown(length)
  }, [])

  const reset = useCallback(() => {
    cursor.current = 0
    shownRef.current = 0
    setShown(0)
  }, [])

  // A different Turn, or a string that is not an extension of what was being
  // read out: either way the cursor means nothing in it.
  const seen = useRef(key)
  useEffect(() => {
    if (seen.current !== key) {
      seen.current = key
      reset()
      return
    }
    if (text.length < shownRef.current) reset()
  }, [key, text, reset])

  useEffect(() => {
    if (instant || still.current) {
      cursor.current = text.length
      commit(text.length)
      return
    }
    if (hold || shownRef.current >= text.length) return

    let frame = 0
    let last = performance.now()
    let since = 0

    const step = (now: number) => {
      const delta = Math.min(MAX_FRAME_MS, now - last)
      last = now
      since += delta
      cursor.current = advanceCursor(cursor.current, text.length, delta)
      if (since >= COMMIT_MS || cursor.current >= text.length) {
        since = 0
        commit(revealedLength(text, cursor.current))
      }
      if (shownRef.current < text.length) frame = requestAnimationFrame(step)
    }

    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [text, hold, instant, commit])

  return {
    visible: shown >= text.length ? text : text.slice(0, shown),
    complete: shown >= text.length,
  }
}

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false
}
