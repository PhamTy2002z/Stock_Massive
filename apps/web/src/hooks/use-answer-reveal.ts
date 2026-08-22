"use client"

import { useEffect, useMemo, useRef, useState } from "react"

import { isActive, type LiveTurn } from "@/lib/alpha-desk/live-turn"
import { TIMELINE_FOLD_MS } from "@/lib/alpha-desk/reveal"
import { CHUNK_FADE_MS } from "@/lib/alpha-desk/word-cadence"
import { useRevealedText } from "./use-revealed-text"

/**
 * What the surface is actually showing of the Turn in flight.
 *
 * Held above the view rather than inside the draft, for two reasons that are
 * really the same one. **Every step of the reveal has to be a commit of the
 * transcript**, because the pin and the spacer that keep a question still while
 * an answer arrives are built on exactly that (`view-chat`: "every way the
 * transcript can change height is a commit"). And **the reveal has to outlive
 * the view**, because the reader can switch to the board and back mid-answer,
 * and a pacer that lived in the component would start the answer over.
 *
 * Three things come out of it, and each answers a question the draft cannot:
 *
 * `text` — the answer as far as it should be on screen. Empty while the fold
 * above it is still moving.
 *
 * `working` — whether the timeline still reads as running. Not the same as the
 * Turn running: the work is over the moment there is a reply to read, and that
 * is the moment the reader is waiting for. It is read from the *received* text
 * rather than the shown text, which is why the draft cannot derive it.
 *
 * `handedOver` — whether the canonical message may replace the draft yet. The
 * Turn ends well before the last word is on screen, and swapping in a message
 * that draws the same text with no cadence would put every word still waiting on
 * screen at once.
 */
export interface DraftReveal {
  text: string
  working: boolean
  handedOver: boolean
}

export function useAnswerReveal(live: LiveTurn): DraftReveal {
  const inFlight = isActive(live) || live.phase === "cancelling"
  const working = inFlight && live.text === ""
  const traced = live.thoughts.length > 0 || live.toolCalls.length > 0

  // Prose that is already whole the first time it is seen was not written in
  // front of this reader: a Turn picked up after it ended, on a reload or in a
  // tab opened late. Pacing it would replay an answer as if it were arriving.
  const redrawn = useFirstSight(live.turnId, live.text !== "", () => !inFlight)

  const held = useFoldGate(working, traced)
  const { visible, complete } = useRevealedText(live.text, {
    key: live.turnId,
    hold: held,
    instant: redrawn,
  })

  const handedOver = useFadedIn(!inFlight && complete)

  // Memoised, because this is a dependency of the transcript projection and of
  // the effect that keeps a pinned question still. A new object on every render
  // of the desk would re-run both for reasons that have nothing to do with the
  // answer — including scrolling the transcript to the bottom.
  return useMemo(
    () => ({ text: visible, working, handedOver }),
    [visible, working, handedOver],
  )
}

/**
 * Whether the answer must still wait for the timeline to finish folding.
 *
 * Only ever released by the transition out of `working`, so a re-render for any
 * other reason cannot re-close a gate that has already opened. A Turn with
 * nothing in its timeline has nothing to fold and is never gated: there would
 * be no rows on screen to wait for.
 */
function useFoldGate(working: boolean, traced: boolean): boolean {
  const [folding, setFolding] = useState(false)
  const was = useRef(working)

  useEffect(() => {
    if (was.current === working) return
    const ended = was.current && !working
    was.current = working
    if (!ended || !traced) return
    setFolding(true)
    const timer = window.setTimeout(() => setFolding(false), TIMELINE_FOLD_MS)
    return () => window.clearTimeout(timer)
  }, [working, traced])

  return working || folding
}

/**
 * `done`, but not before the last word has finished fading in.
 *
 * The reveal is complete when the last word is in the DOM, and that word is
 * still a quarter of a second from being fully on screen. Handing over on the
 * earlier moment is visible: the canonical message draws it at full opacity
 * immediately.
 */
function useFadedIn(done: boolean): boolean {
  const [faded, setFaded] = useState(false)

  useEffect(() => {
    if (!done) {
      setFaded(false)
      return
    }
    const timer = window.setTimeout(() => setFaded(true), CHUNK_FADE_MS)
    return () => window.clearTimeout(timer)
  }, [done])

  return faded
}

/**
 * What was true the first time this key had something to say.
 *
 * Locked per key, so the answer to "was this prose already whole when we first
 * saw it" cannot change as the prose grows.
 */
function useFirstSight(
  key: string | null,
  ready: boolean,
  compute: () => boolean,
): boolean {
  const seen = useRef<{ key: string | null; value: boolean | null }>({
    key: null,
    value: null,
  })
  if (seen.current.key !== key) seen.current = { key, value: null }
  if (seen.current.value === null && ready) seen.current.value = compute()
  return seen.current.value ?? false
}
