"use client"

/**
 * The route's own failure, which until now fell through to Next's default page.
 *
 * Without this file an exception thrown while rendering the workspace — a 500
 * from a server component, a bug in the shell — reached the reader as Next's
 * unstyled "Application error: a client-side exception has occurred". That page
 * is not in any language this product speaks, offers nothing to press, and
 * looks like the site is gone rather than like one request went wrong.
 *
 * `reset()` re-renders the segment, which is the right first move: most of what
 * lands here is a transient read that will succeed on a second attempt, and it
 * costs the reader nothing to find out.
 */

import { useEffect } from "react"

import { FailureState } from "@/components/ui/failure-state"
import { describeFailure } from "@/lib/failure"

export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // The digest is the only thread between what the reader saw and the server
    // log that recorded it; a boundary that swallows it leaves the report
    // unanswerable.
    console.error("route error", error.digest ?? "(no digest)", error)
  }, [error])

  return <FailureState failure={describeFailure(error)} density="page" onRetry={reset} />
}
