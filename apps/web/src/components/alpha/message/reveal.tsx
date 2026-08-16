"use client"

import { useEffect, useState } from "react"

import { cn } from "@/lib/utils"

/**
 * How a block appears: all of it, once, with a light fade.
 *
 * **There is no typewriter effect** (`docs/specs/0002` §6). The backend already
 * buffers provider deltas into Markdown-safe units, so a block is complete when
 * it arrives; animating it character by character would be the client
 * re-introducing an illusion the transport deliberately removed, and it would
 * make a finished table unreadable while it drew itself.
 *
 * `animate` is false for everything that was already there — a reopened Thread,
 * the snapshot that answers a reconnect. Those render with no transition markup
 * at all rather than with a transition that happens to have finished, so "no
 * staged replay" is visible in the DOM rather than a matter of timing.
 */

// Inside the 150–200 ms the product spec fixes. Long enough to read as arrival,
// short enough that a fast Turn does not feel gated by its own animation.
export const REVEAL_MS = 180

export function Reveal({
  animate,
  className,
  children,
}: {
  animate: boolean
  className?: string
  children: React.ReactNode
}) {
  const [revealed, setRevealed] = useState(!animate)

  useEffect(() => {
    if (revealed) return
    // A frame later, so the browser has painted the transparent state and has
    // something to transition *from*. Setting both states in one commit would
    // render the end state directly and skip the fade.
    const frame = requestAnimationFrame(() => setRevealed(true))
    return () => cancelAnimationFrame(frame)
  }, [revealed])

  if (!animate) return <div className={className}>{children}</div>

  return (
    <div
      style={{ transitionDuration: `${REVEAL_MS}ms` }}
      className={cn(
        // `motion-reduce` removes the transition rather than shortening it: a
        // user who asked for no motion asked for none, and the content is
        // already complete either way.
        "transition-opacity ease-out motion-reduce:opacity-100 motion-reduce:transition-none",
        revealed ? "opacity-100" : "opacity-0",
        className,
      )}
    >
      {children}
    </div>
  )
}
